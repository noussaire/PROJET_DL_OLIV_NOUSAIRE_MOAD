"""Integration contracts without loading weights or accessing the network."""
import os
import time
import types
import unittest
import cv2  # Load native modules before legacy handler fixtures temporarily patch sys.modules.
import numpy
from unittest.mock import patch
from unittest.mock import Mock
import test_traceability as legacy
from model_config import get_config


class ModelIntegrationTests(unittest.TestCase):
    def test_missing_selected_checkpoint_never_loads_another_model(self):
        factory = Mock(side_effect=AssertionError('No checkpoint may be loaded'))
        ns = dict(os=os, time=time, MODEL_NAME='YOLO11m V1',
                  CONFIG={'modelPath': str(legacy.ROOT / '__missing_selected_checkpoint__.pt')},
                  _MODEL_ATTEMPTED=False, _YOLO_MODEL=None, _MODEL_READY=False,
                  _MODEL_ERROR=None, _MODEL_LOAD_MS=None)
        exec(legacy.functions_only(legacy.ROOT / 'detect_any_polygon.py'), ns)
        with patch.dict(legacy.sys.modules, {'ultralytics': types.SimpleNamespace(YOLO=factory)}):
            self.assertIsNone(ns['get_yolo_model']())
            self.assertIsNone(ns['get_yolo_model']())
        factory.assert_not_called()
        self.assertFalse(ns['_MODEL_READY'])
        self.assertIn('Selected checkpoint missing', ns['_MODEL_ERROR'])

    def test_profiles_are_reversible_and_unknown_profile_is_rejected(self):
        with patch.dict(os.environ, {'OLIVESMART_MODEL': 'yolo11m_v1'}):
            current = get_config()
            self.assertEqual(current['inferenceParameters'], dict(
                imgsz=1280, conf=0.20, iou=0.50, max_det=1000, device='cpu'))
            self.assertTrue(current['modelPath'].endswith('models' + os.sep + 'yolo11m_olivesmart_v1.pt'))
        with patch.dict(os.environ, {'OLIVESMART_MODEL': 'yolov8n'}):
            historical = get_config()
            self.assertTrue(historical['modelPath'].endswith(os.sep + 'best.pt'))
            self.assertEqual(historical['inferenceParameters']['imgsz'], 640)
        with patch.dict(os.environ, {'OLIVESMART_MODEL': 'typo'}):
            with self.assertRaisesRegex(ValueError, 'no fallback'):
                get_config()

    def test_raw_yolo_is_preserved_before_hybrid_and_parameters_reach_predict(self):
        fixture = legacy.DetectorTests()
        fixture.setUp()
        model = fixture.ns['get_yolo_model']()
        original_predict = model.predict
        calls = []
        def predict(*args, **kwargs):
            calls.append(kwargs)
            return original_predict(*args, **kwargs)
        model.predict = predict
        context = {}
        result = fixture.ns['detect_trees_in_polygon'](fixture.vertices, analysis_context=context)
        metadata = context['analysisMetadata']
        self.assertEqual(metadata['yoloRawCount'], 1)
        self.assertEqual(metadata['yoloInPolygonCount'], 1)
        self.assertEqual(metadata['hybridCount'], len(result))
        self.assertEqual(len(result), 2)
        self.assertEqual(metadata['yoloRawTrees'][0]['bboxMosaicPx'], [49, 49, 71, 71])
        self.assertNotIn('health', metadata['yoloRawTrees'][0])
        for key, value in get_config()['inferenceParameters'].items():
            self.assertEqual(calls[0][key], value)

    def test_oversized_parcel_is_rejected_before_fetching(self):
        fixture = legacy.DetectorTests()
        fixture.setUp()
        with self.assertRaisesRegex(ValueError, '7 x 7'):
            fixture.ns['detect_trees_in_polygon']([
                {'lat': 31.6, 'lng': -8.0}, {'lat': 31.6, 'lng': -7.9},
                {'lat': 31.7, 'lng': -7.9}])

    def test_busy_server_returns_explicit_failure(self):
        fixture = legacy.HandlerTests()
        fixture.setUp()
        lock = fixture.server._ANALYSIS_LOCK
        lock.acquire()
        try:
            handler = fixture.handler('/api/v1/analyze-parcel', {'vertices': []})
            handler.do_POST()
            self.assertEqual(handler.status, 503)
            payload = legacy.json.loads(handler.wfile.getvalue())
            self.assertFalse(payload['success'])
            self.assertEqual(payload['trees'], [])
        finally:
            lock.release()


if __name__ == '__main__':
    unittest.main()
