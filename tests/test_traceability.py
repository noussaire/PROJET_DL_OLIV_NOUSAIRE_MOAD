"""Lightweight tests: synthetic 256px images, fake YOLO, no model/network/server."""
import ast
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def functions_only(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    return compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), str(path), 'exec')


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.detector = types.ModuleType('detect_any_polygon')
        self.detector.MODEL_NAME = 'best.pt (YOLOv8n)'
        self.detector.get_model_status = lambda: {'status': 'DOWN', 'modelLoaded': False}
        self.detector.detect_trees_in_polygon = lambda vertices, analysis_context: []
        spec = importlib.util.spec_from_file_location('tested_ai_server', ROOT / 'ai_engine_server.py')
        self.server = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'detect_any_polygon': self.detector}):
            spec.loader.exec_module(self.server)

    def handler(self, path, data=None):
        h = self.server.OliveDetectionHandler.__new__(self.server.OliveDetectionHandler)
        h.path = path
        raw = json.dumps(data or {}).encode()
        h.headers = {'Content-Length': str(len(raw))}
        h.rfile, h.wfile = io.BytesIO(raw), io.BytesIO()
        h.send_response = lambda status: setattr(h, 'status', status)
        h.send_header = lambda *args: None
        h.end_headers = lambda: None
        return h

    def test_python_error_is_failure_without_trees(self):
        def fail(*args, **kwargs):
            raise RuntimeError('private internal detail')
        self.server.detect_trees_in_polygon = fail
        h = self.handler('/api/v1/analyze-parcel', {'vertices': []})
        h.do_POST()
        result = json.loads(h.wfile.getvalue())
        self.assertEqual(h.status, 500)
        self.assertFalse(result['success'])
        self.assertEqual(result['trees'], [])
        self.assertNotIn('private internal detail', result['error'])

    def test_empty_analysis_is_success(self):
        h = self.handler('/api/v1/analyze-parcel', {'vertices': []})
        h.do_POST()
        result = json.loads(h.wfile.getvalue())
        self.assertTrue(result['success'])
        self.assertEqual(result['engine'], 'NONE')
        self.assertEqual(result['totalTrees'], 0)

    def test_health_reports_unavailable_model(self):
        h = self.handler('/health')
        h.do_GET()
        self.assertEqual(h.status, 503)
        self.assertFalse(json.loads(h.wfile.getvalue())['modelLoaded'])

    def test_health_reports_loaded_model_without_inference(self):
        self.server.get_model_status = lambda: {'status': 'UP', 'modelLoaded': True,
                'model': 'best.pt (YOLOv8n)', 'classes': {0: 'Olive_Tree'}}
        h = self.handler('/health')
        h.do_GET()
        result = json.loads(h.wfile.getvalue())
        self.assertEqual(h.status, 200)
        self.assertEqual(result['classes'], {'0': 'Olive_Tree'})


class DetectorTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np
        self.cv2, self.np = cv2, np
        self.ns = dict(math=math, cv2=cv2, np=np, MODEL_NAME='best.pt (YOLOv8n)',
                       _MODEL_READY=True)
        exec(functions_only(ROOT / 'detect_any_polygon.py'), self.ns)
        img = np.full((256, 256, 3), (130, 150, 180), dtype=np.uint8)
        for xy in [(60, 60), (160, 160)]:
            cv2.circle(img, xy, 9, (40, 65, 40), -1)
        box = types.SimpleNamespace(xyxy=np.array([[49, 49, 71, 71]]), conf=np.array([0.91]))
        model = types.SimpleNamespace(names={0: 'Olive_Tree'}, predict=lambda *a, **k: [types.SimpleNamespace(boxes=[box])])
        self.ns['get_yolo_model'] = lambda: model
        self.ns['fetch_tile'] = lambda *a: img.copy()
        x, y, z = 250000, 210000, 19
        def gps(px, py):
            return {'lng': ((x + px/256) / 2**z) * 360 - 180,
                    'lat': math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py/256) / 2**z))))}
        self.vertices = [gps(5, 5), gps(250, 5), gps(250, 250), gps(5, 250)]

    def test_yolo_and_opencv_provenance_and_original_geometry(self):
        context = {}
        result = self.ns['detect_trees_in_polygon'](self.vertices, analysis_context=context)
        self.assertEqual({t['source'] for t in result}, {'YOLO', 'OPENCV'})
        self.assertEqual(context['engine'], 'YOLO+OPENCV')
        for t in result:
            self.assertIn(t['source'], t['sources'])
        # Compare against the protected original on exactly the same synthetic image.
        backups = sorted((ROOT / 'backups').glob('traceability-*/detect_any_polygon.py'))
        self.assertTrue(backups)
        original = dict(self.ns)
        exec(functions_only(backups[0]), original)
        original['get_yolo_model'] = self.ns['get_yolo_model']
        original['fetch_tile'] = self.ns['fetch_tile']
        before = original['detect_trees_in_polygon'](self.vertices)
        fields = ('lat', 'lng', 'box', 'diam', 'conf', 'health', 'ageCategory')
        self.assertEqual([{k: t[k] for k in fields} for t in before],
                         [{k: t[k] for k in fields} for t in result])

    def test_yolo_failure_does_not_silently_switch_engine(self):
        def fail(*a, **k):
            raise RuntimeError('fake prediction failure')
        self.ns['get_yolo_model'] = lambda: types.SimpleNamespace(predict=fail)
        with self.assertRaisesRegex(RuntimeError, 'YOLO inference failed'):
            self.ns['detect_trees_in_polygon'](self.vertices)

    def test_missing_model_is_error(self):
        self.ns['get_yolo_model'] = lambda: None
        with self.assertRaisesRegex(RuntimeError, 'best.pt unavailable'):
            self.ns['detect_trees_in_polygon'](self.vertices)

    def test_tile_failure_is_not_a_successful_empty_analysis(self):
        def fail(*args):
            raise RuntimeError('Satellite tile unavailable')
        self.ns['fetch_tile'] = fail
        with self.assertRaisesRegex(RuntimeError, 'Satellite tile unavailable'):
            self.ns['detect_trees_in_polygon'](self.vertices)


if __name__ == '__main__':
    unittest.main()
