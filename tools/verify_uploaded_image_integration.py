"""Real local image through isolated Python + Java + browser. No uploaded image is saved."""
import json
import base64
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import detect_uploaded_image as upload
    from ai_engine_server import OliveDetectionHandler
    from http.server import ThreadingHTTPServer
    original=upload.analyze_uploaded_image
    python_results={}
    def record(data):
        response=original(data)
        python_results[response['imageId'] + ':' + str(response['roiApplied'])]=response
        return response
    upload.analyze_uploaded_image=record
    report=ROOT/'springboot-microservice-olive/target/surefire-reports/TEST-com.olivesmart.detection.service.ModelMetadataTest.xml'
    props={p.attrib['name']:p.attrib['value'] for p in ET.parse(report).findall('./properties/property')}
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));java_port=reservation.getsockname()[1]
    server=ThreadingHTTPServer(('127.0.0.1',0),OliveDetectionHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    out=ROOT/'resultats_tests/image-live';out.mkdir(parents=True,exist_ok=True)
    log=open(out/'java.log','w',encoding='utf-8');process=None
    try:
        process=subprocess.Popen([str(Path(props['java.home'])/'bin/java.exe'),'-cp',props['java.class.path'],
            'com.olivesmart.detection.OliveSmartApplication','--server.address=127.0.0.1',f'--server.port={java_port}',
            f'--olivesmart.ai.service-url=http://127.0.0.1:{server.server_port}'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        base=f'http://127.0.0.1:{java_port}'
        ready=False
        for _ in range(90):
            if process.poll() is not None:raise RuntimeError('Java stopped; inspect image-live/java.log')
            try:
                with urllib.request.urlopen(base+'/api/v1/parcelles/metriques-modele',timeout=2) as response:
                    ready=json.load(response).get('modelLoaded',False)
                if ready:break
            except OSError:pass
            time.sleep(.5)
        assert ready,'Isolated services not ready'
        from PIL import Image
        exif=Image.Exif();exif[274]=6
        buffer=io.BytesIO();Image.new('RGB',(120,80),'green').save(buffer,format='JPEG',exif=exif)
        env=dict(os.environ,OLIVESMART_IMAGE_TEST_JAVA=base+'/api/v1/images/analyser',
                 OLIVESMART_IMAGE_TEST_EXIF=base64.b64encode(buffer.getvalue()).decode())
        browser=subprocess.run(['node',str(ROOT/'tools/verify_upload_browser.cjs')],cwd=ROOT,env=env,timeout=160,check=False)
        checks=json.loads((out/'browser-checks.json').read_text(encoding='utf-8'))
        assert browser.returncode==0,checks
        compared=[]
        for check in checks:
            assert check['ok'],check
            for java in check['javaResults']:
                python=python_results[java['imageId'] + ':' + str(java['roiApplied'])]
                assert java['detections']==python['detections']
                assert java['totalDetections']==python['totalDetections']
                compared.append(dict(width=check['width'],imageId=java['imageId'],pythonCount=python['totalDetections'],javaCount=java['totalDetections']))
            assert check['frontendCount']==check['javaResults'][0]['totalDetections']
        (out/'python-responses.json').write_text(json.dumps(python_results,indent=2),encoding='utf-8')
        (out/'pipeline-checks.json').write_text(json.dumps(dict(ok=True,comparisons=compared),indent=2),encoding='utf-8')
        print('PYTHON = JAVA = FRONTEND',json.dumps(compared))
    finally:
        upload.analyze_uploaded_image=original
        if process is not None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close();server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
