r"""One real Esri parcel through isolated loopback Python + Java, then stop both.

Uses the already built Java test classpath; never installs or downloads dependencies.
Esri imagery may populate the application's normal tile cache.
Run from the project root: .venv\Scripts\python.exe -B tools\verify_satellite_integration.py
"""
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    started = time.perf_counter()
    import detect_any_polygon as detector
    from ai_engine_server import OliveDetectionHandler
    from http.server import ThreadingHTTPServer
    status = detector.get_model_status()
    assert status['modelLoaded'], status
    assert status['profile'] == 'yolo11m_v1', status
    assert status['classes'] == {0: 'trees'}, status
    parameters = dict(imgsz=1280, conf=0.20, iou=0.50, max_det=1000, device='cpu')
    assert status['inferenceParameters'] == parameters

    # Preserve the previous /metriques-modele shape in addition to additive fields.
    report_path = ROOT / 'springboot-microservice-olive/target/surefire-reports/TEST-com.olivesmart.detection.service.ModelMetadataTest.xml'
    props = {p.attrib['name']: p.attrib['value'] for p in ET.parse(report_path).findall('./properties/property')}
    classpath = props['java.class.path']
    java = str(Path(props['java.home']) / 'bin/java.exe')
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        java_port = reservation.getsockname()[1]
    server = ThreadingHTTPServer(('127.0.0.1', 0), OliveDetectionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = ROOT / 'resultats_tests'
    output.mkdir(exist_ok=True)
    java_log = open(output / 'yolo11m_integration_java.log', 'w', encoding='utf-8')
    process = None
    try:
        process = subprocess.Popen([java, '-cp', classpath,
            'com.olivesmart.detection.OliveSmartApplication',
            '--server.address=127.0.0.1', f'--server.port={java_port}',
            f'--olivesmart.ai.service-url=http://127.0.0.1:{server.server_port}'],
            cwd=ROOT, stdout=java_log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        base = f'http://127.0.0.1:{java_port}'
        ready = None
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError('Isolated Java process stopped; inspect yolo11m_integration_java.log')
            try:
                with urllib.request.urlopen(base + '/api/v1/parcelles/metriques-modele', timeout=2) as response:
                    ready = json.load(response)
                if ready.get('modelLoaded'):
                    break
            except OSError:
                pass
            time.sleep(0.5)
        assert ready and ready['modelLoaded'], ready
        assert ready['model'] == 'YOLO11m V1', ready
        assert ready['classes'] == ['trees'], ready

        # A single Esri Z19 tile around the existing Haouz demonstration parcel.
        x, y = detector.lat_lng_to_tile(31.6338, -7.9653, 19)
        def point(dx, dy):
            return dict(lng=(x + dx) / 2**19 * 360 - 180,
                        lat=math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + dy) / 2**19)))))
        vertices = [point(.15, .15), point(.85, .15), point(.85, .85), point(.15, .85)]
        request = urllib.request.Request(base + '/api/v1/parcelles/analyser',
            data=json.dumps(dict(mode='LIVE', vertices=vertices)).encode(),
            headers={'Content-Type': 'application/json'})
        analysis_started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=65) as response:
            payload = json.load(response)
        elapsed_ms = round((time.perf_counter() - analysis_started) * 1000, 1)
        assert payload['success'] and payload['model'] == 'YOLO11m V1', payload
        metadata = payload['analysisMetadata']
        assert payload['totalTrees'] == len(payload['trees']) == metadata['hybridCount']
        assert metadata['yoloRawCount'] == len(metadata['yoloRawTrees'])
        assert metadata['yoloInPolygonCount'] == sum(t['insideParcel'] for t in metadata['yoloRawTrees'])
        for key, value in parameters.items():
            assert metadata['inferenceParameters'][key] == value
            assert getattr(detector.get_yolo_model().predictor.args, key) == value
        assert all(t['source'] in ('YOLO', 'OPENCV') for t in payload['trees'])
        report = dict(status=status, parametersObserved=parameters, vertices=vertices,
                      javaPythonHttpRoundTripMs=elapsed_ms,
                      totalVerificationMs=round((time.perf_counter() - started) * 1000, 1),
                      response=payload)
        (output / 'yolo11m_satellite_integration.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(model=status['model'], modelPath=status['modelPath'],
            classes=status['classes'], parameters=parameters,
            parameterCount=sum(p.numel() for p in detector.get_yolo_model().model.parameters()),
            modelLoadMs=status['modelLoadMs'], roundTripMs=elapsed_ms,
            yoloRawCount=metadata['yoloRawCount'], yoloInPolygonCount=metadata['yoloInPolygonCount'],
            hybridCount=payload['totalTrees'], yoloInferenceMs=metadata['yoloInferenceMs'],
            totalAnalysisMs=metadata['totalAnalysisMs']), ensure_ascii=False))
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        java_log.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()
