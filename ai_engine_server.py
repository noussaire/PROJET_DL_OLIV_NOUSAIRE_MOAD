import json
import math
import time
import os
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import cv2
import numpy as np

# Reuse detection logic
from detect_any_polygon import detect_trees_in_polygon, get_model_status, MODEL_NAME

PORT = 8000
_ANALYSIS_LOCK = threading.Lock()

class OliveDetectionHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            status = get_model_status()
            self.send_response(200 if status['modelLoaded'] else 503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        # Bound CPU/memory use and protect the shared Ultralytics predictor.
        if not _ANALYSIS_LOCK.acquire(blocking=False):
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'engine': 'NONE',
                'model': MODEL_NAME, 'mode': 'LIVE', 'totalTrees': 0, 'trees': [],
                'error': 'Une analyse CPU est deja en cours. Reessayer apres sa fin.'}).encode('utf-8'))
            return
        try:
            self._analyze_post()
        finally:
            _ANALYSIS_LOCK.release()

    def _analyze_post(self):
        if self.path == '/api/v1/analyze-image':
            self._analyze_image()
            return
        if self.path in ['/api/v1/analyze-parcel', '/api/detect-polygon']:
            content_length = int(self.headers.get('content-length', self.headers.get('Content-Length', 0)))
            body = self.rfile.read(content_length)
            start_time = time.time()
            try:
                data = json.loads(body.decode('utf-8'))
                vertices = data.get('vertices', [])
                print(f"[AI Service] Processing polygon with {len(vertices)} vertices")
                
                # Run computer vision detection on satellite tiles
                context = {'engine': 'NONE', 'model': MODEL_NAME}
                trees = detect_trees_in_polygon(vertices, analysis_context=context)
                elapsed_ms = int((time.time() - start_time) * 1000)

                total = len(trees)
                sains = sum(1 for t in trees if t['health'] == 'SAIN')
                stress = sum(1 for t in trees if t['health'] == 'STRESS')
                suspects = sum(1 for t in trees if t['health'] == 'SUSPECT')

                young = sum(1 for t in trees if t.get('ageCategory') == 'JEUNE')
                adult = sum(1 for t in trees if t.get('ageCategory') == 'ADULTE')
                centenary = sum(1 for t in trees if t.get('ageCategory') == 'CENTENAIRE')

                total_area = round(sum(t.get('crownAreaM2', 0) for t in trees), 1)
                mean_diam = round(sum(t.get('diam', 4.0) for t in trees) / max(1, total), 1)
                mean_conf = round(sum(t.get('conf', 0.9) for t in trees) / max(1, total), 3)

                response_payload = {
                    "totalTrees": total,
                    "healthyCount": sains,
                    "stressCount": stress,
                    "suspectCount": suspects,
                    "meanConfidence": mean_conf,
                    "inferenceTimeMs": elapsed_ms,
                    "meanCrownDiameterMeters": mean_diam,
                    "trees": trees,
                    "youngCount": young,
                    "adultCount": adult,
                    "centenaryCount": centenary,
                    "totalCanopyAreaM2": total_area,
                    "droneVideoStatus": "NON_TRAITE",
                    "success": True,
                    "engine": context['engine'],
                    "model": context['model'],
                    "mode": "LIVE",
                    "error": None
                }
                if 'analysisMetadata' in context:
                    metadata = context['analysisMetadata']
                    metadata['totalAnalysisMs'] = elapsed_ms
                    metadata['modelLoadMs'] = get_model_status().get('modelLoadMs')
                    response_payload['analysisMetadata'] = metadata

                print(f"[AI Service] Successfully detected {total} olive trees (Sains: {sains}, Stress: {stress}, Suspects: {suspects}) in {elapsed_ms}ms")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode('utf-8'))

            except Exception as e:
                print(f"[AI Service ERROR] {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                message = ('Analyse trop longue sur CPU. Reduire la parcelle.' if isinstance(e, TimeoutError)
                    else str(e) if isinstance(e, ValueError)
                    else 'Analyse Python impossible. Verifier le checkpoint selectionne et le journal du service; aucun autre modele utilise.')
                self.wfile.write(json.dumps({'success': False, 'engine': 'NONE',
                    'model': MODEL_NAME, 'mode': 'LIVE', 'totalTrees': 0, 'trees': [],
                    'error': message}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def _analyze_image(self):
        from detect_uploaded_image import analyze_uploaded_image, ImageAnalysisError, MAX_BODY_BYTES
        status = 200
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ImageAnalysisError('Content-Length requis ; transfert chunked non accepte.', 411)
            length_header = self.headers.get('Content-Length')
            if length_header is None:
                raise ImageAnalysisError('Content-Length requis.', 411)
            try:
                length = int(length_header)
            except ValueError:
                raise ImageAnalysisError('Content-Length invalide.', 400)
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ImageAnalysisError('Corps JSON vide ou superieur a 12 MiB.', 413)
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise ImageAnalysisError('Content-Type application/json requis.', 415)
            connection = getattr(self, 'connection', None)
            if connection is not None:
                connection.settimeout(15)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ImageAnalysisError('Requete tronquee.', 400)
            try:
                data = json.loads(raw.decode('utf-8'), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            except (ValueError, UnicodeDecodeError):
                raise ImageAnalysisError('JSON invalide.', 400)
            payload = analyze_uploaded_image(data)
        except ImageAnalysisError as error:
            status = error.status
            payload = dict(success=False, mode='LIVE', engine='NONE', coordinateSystem='IMAGE_PIXELS',
                           detections=[], totalDetections=0, error=str(error))
        except TimeoutError:
            status = 408
            payload = dict(success=False, mode='LIVE', engine='NONE', detections=[], totalDetections=0,
                           error='Delai de reception de l\'image depasse.')
        except Exception as error:
            print(f'[Image LIVE ERROR] {type(error).__name__}: {error}')
            status = 500
            payload = dict(success=False, mode='LIVE', engine='NONE', detections=[], totalDetections=0,
                           error='Analyse image impossible ; aucune simulation utilisee.')
        self.close_connection = True
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')
        self.end_headers()
        try:
            self.wfile.write(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError):
            pass  # Caller cancellation never starts another inference or a fallback.

def run_server():
    server_address = ('0.0.0.0', PORT)
    httpd = ThreadingHTTPServer(server_address, OliveDetectionHandler)
    print(f"==================================================================")
    print(f"[AI Service] Threading Python AI Server live on http://0.0.0.0:{PORT}")
    print(f"==================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    run_server()
