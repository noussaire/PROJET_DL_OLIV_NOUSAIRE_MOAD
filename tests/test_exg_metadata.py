"""ExG reporting regressions on controlled RGB images, without weights or network."""
import json
import ast
import math
import types
import unittest
import cv2
import numpy as np
import test_traceability as legacy


class ExgMetadataTests(unittest.TestCase):
    def test_detection_module_diff_is_strictly_additive_metadata(self):
        backup = sorted((legacy.ROOT / 'backups').glob('exg-transparency-*/detect_any_polygon.py'))[-1]
        before = ast.parse(backup.read_text(encoding='utf-8-sig'))
        current = ast.parse((legacy.ROOT / 'detect_any_polygon.py').read_text(encoding='utf-8-sig'))
        current.body = [n for n in current.body if not isinstance(n, ast.FunctionDef) or n.name != 'describe_exg']
        for node in ast.walk(current):
            if isinstance(node, ast.Dict):
                pairs = [(k,v) for k,v in zip(node.keys,node.values)
                         if not isinstance(k, ast.Constant) or k.value != 'exgMetadata']
                node.keys, node.values = [p[0] for p in pairs], [p[1] for p in pairs]
        self.assertEqual(ast.dump(before), ast.dump(current))

    def fixture(self, values):
        fixture = legacy.DetectorTests()
        fixture.setUp()
        image = np.full((256, 256, 3), (130, 150, 180), dtype=np.uint8)
        boxes = []
        for i, value in enumerate(values):
            x, y = 35 + (i % 4) * 60, 35 + (i // 4) * 65
            cv2.circle(image, (x, y), 9, (40, 40 + value // 2, 40), -1)
            boxes.append(types.SimpleNamespace(xyxy=np.array([[x-11, y-11, x+11, y+11]]), conf=np.array([0.91])))
        model = types.SimpleNamespace(predict=lambda *a, **k: [types.SimpleNamespace(boxes=boxes)])
        fixture.ns['get_yolo_model'] = lambda: model
        fixture.ns['fetch_tile'] = lambda *a: image.copy()
        return fixture

    def test_fixed_thresholds_and_strict_equalities_are_unchanged(self):
        for values in ([-2, 0, 10], [-2, 0, 10, 20, 30]):
            fixture = self.fixture(values)
            trees = fixture.ns['detect_trees_in_polygon'](fixture.vertices)
            self.assertEqual(len(trees), len(values))
            for tree, value in zip(trees, values):
                metadata = tree['exgMetadata']
                self.assertEqual(metadata['value'], value)
                self.assertEqual(metadata['classificationMethod'], 'FIXED_SMALL_SAMPLE')
                self.assertEqual((metadata['lowerThreshold'], metadata['upperThreshold']), (0, 10))
                expected = 'SUSPECT' if value < 0 else 'STRESS' if value < 10 else 'SAIN'
                self.assertEqual(tree['health'], expected)
                self.assertEqual(metadata['samplePixelCount'], 49)

    def test_relative_percentiles_describe_the_final_hybrid_population(self):
        values = list(range(0, 64, 8))
        fixture = self.fixture(values)
        trees = fixture.ns['detect_trees_in_polygon'](fixture.vertices)
        self.assertEqual(len(trees), 8)
        lower, upper = np.percentile(values, [15, 30])
        for tree, value in zip(trees, values):
            metadata = tree['exgMetadata']
            self.assertEqual(metadata['value'], value)
            self.assertEqual(metadata['populationSize'], 8)
            self.assertEqual(metadata['classificationMethod'], 'PERCENTILES_15_30')
            self.assertEqual(metadata['lowerThreshold'], lower)
            self.assertEqual(metadata['upperThreshold'], upper)
            expected = 'SUSPECT' if value < lower else 'STRESS' if value < upper else 'SAIN'
            self.assertEqual(tree['health'], expected)
            self.assertEqual(metadata['category'], {'SUSPECT':'LOW','STRESS':'INTERMEDIATE','SAIN':'HIGH'}[expected])

    def test_all_previous_fields_and_geometry_remain_identical(self):
        fixture = self.fixture(list(range(0, 64, 8)))
        current = fixture.ns['detect_trees_in_polygon'](fixture.vertices)
        backup = sorted((legacy.ROOT / 'backups').glob('exg-transparency-*/detect_any_polygon.py'))[-1]
        before = dict(fixture.ns)
        exec(legacy.functions_only(backup), before)
        before['get_yolo_model'] = fixture.ns['get_yolo_model']
        before['fetch_tile'] = fixture.ns['fetch_tile']
        original = before['detect_trees_in_polygon'](fixture.vertices)
        self.assertEqual([{k:v for k,v in t.items() if k != 'exgMetadata'} for t in current], original)

    def test_edge_window_and_nonfinite_reporting_do_not_invent_values(self):
        fixture = self.fixture([0])
        describe = fixture.ns['describe_exg']
        metadata = describe(0, 'STRESS', 0, 10, 1, 0, 0, 256, 256)
        self.assertEqual((metadata['sampleWidth'], metadata['sampleHeight'], metadata['samplePixelCount']), (4,4,16))
        self.assertEqual(metadata['value'], 0)
        invalid = describe(math.nan, 'SAIN', math.inf, 10, 1, 0, 0, 256, 256)
        self.assertIsNone(invalid['value'])
        self.assertIsNone(invalid['lowerThreshold'])
        json.dumps(invalid, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
