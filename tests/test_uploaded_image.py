import base64
import io
import json
import types
import unittest
from unittest.mock import Mock, patch
import numpy as np
from PIL import Image
import detect_uploaded_image as upload
import test_traceability as legacy


def image_data(fmt='PNG', size=(120,80), orientation=None):
    image=Image.new('RGB', size, (40,110,50))
    buffer=io.BytesIO()
    kwargs={}
    if orientation is not None:
        exif=Image.Exif();exif[274]=orientation;kwargs['exif']=exif
    image.save(buffer,format=fmt,**kwargs)
    return buffer.getvalue()


class UploadedImageTests(unittest.TestCase):
    def request(self, raw=None, **kwargs):
        return dict(imageBase64=base64.b64encode(raw or image_data()).decode(),imageId='test-image',mode='LIVE',**kwargs)
    def analyze(self, request, boxes=None, clock=None):
        if boxes is None: boxes=[[10,10,30,30],[70,40,100,70]]
        records=[types.SimpleNamespace(xyxy=np.array([b]),conf=np.array([0.8]),cls=np.array([0])) for b in boxes]
        model=types.SimpleNamespace(predict=Mock(return_value=[types.SimpleNamespace(boxes=records,names={0:'trees'})]))
        result=upload.analyze_uploaded_image(request,lambda:model,lambda:dict(modelLoaded=True,profile='yolo11m_v1'),**({'clock':clock} if clock else {}))
        return result,model
    def test_jpg_png_webp_decoded_pixels_and_parameters(self):
        for fmt in ['JPEG','PNG','WEBP']:
            result,model=self.analyze(self.request(image_data(fmt)))
            self.assertEqual(result['totalDetections'],2)
            self.assertEqual((result['imageWidth'],result['imageHeight']),(120,80))
            self.assertEqual(model.predict.call_count,1)
            self.assertEqual(model.predict.call_args.args[0].shape,(80,120,3))
            for key,value in dict(imgsz=1280,conf=.2,iou=.5,max_det=1000,device='cpu').items():
                self.assertEqual(model.predict.call_args.kwargs[key],value)
            self.assertEqual(result['detections'][0]['bboxPx'],[10,10,30,30])
            self.assertEqual(result['detections'][0]['centerPx'],[20,20])
            self.assertFalse(any(k in result['detections'][0] for k in ['lat','lng','age','health','diam']))
    def test_roi_filters_centers_without_rewriting_coordinates(self):
        result,_=self.analyze(self.request(roiPx=[dict(x=0,y=0),dict(x=50,y=0),dict(x=50,y=80),dict(x=0,y=80)]))
        self.assertEqual(result['rawDetectionCount'],2);self.assertEqual(result['totalDetections'],1)
        self.assertEqual(result['detections'][0]['bboxPx'],[10,10,30,30])
    def test_zero_detections_is_success(self):
        result,_=self.analyze(self.request(),boxes=[])
        self.assertTrue(result['success']);self.assertEqual(result['detections'],[])
    def test_exif_orientation_is_applied_and_preview_mismatch_is_rejected(self):
        result,_=self.analyze(self.request(image_data('JPEG',orientation=6)),boxes=[])
        self.assertTrue(result['orientationApplied'])
        self.assertEqual((result['sourceWidth'],result['sourceHeight']),(120,80))
        self.assertEqual((result['imageWidth'],result['imageHeight']),(80,120))
        with self.assertRaisesRegex(upload.ImageAnalysisError,'apercu'):
            self.analyze(self.request(image_data('JPEG',orientation=6),imageWidth=120,imageHeight=80))
        for orientation in range(1,9):
            result,_=self.analyze(self.request(image_data('JPEG',orientation=orientation)),boxes=[])
            self.assertEqual((result['imageWidth'],result['imageHeight']), (80,120) if orientation>=5 else (120,80))
    def test_invalid_roi(self):
        for roi in [[],[dict(x=1,y=1)], [dict(x=-1,y=0),dict(x=30,y=0),dict(x=0,y=30)],
            [dict(x=0,y=0),dict(x=121,y=0),dict(x=0,y=30)],
            [dict(x=0,y=0),dict(x=1,y=1),dict(x=2,y=2)],
            [dict(x=0,y=0),dict(x=80,y=60),dict(x=0,y=60),dict(x=80,y=0)],
            [dict(x=False,y=0),dict(x=30,y=0),dict(x=0,y=30)],
            [dict(x=float('nan'),y=0),dict(x=30,y=0),dict(x=0,y=30)]]:
            with self.assertRaises(upload.ImageAnalysisError):self.analyze(self.request(roiPx=roi))
    def test_corrupt_truncated_and_wrong_formats(self):
        for raw in [b'<svg/>',b'not an image',image_data('JPEG')[:-80],image_data('PNG')[:35],image_data('GIF')]:
            with self.assertRaises(upload.ImageAnalysisError):upload.decode_image(base64.b64encode(raw).decode())
        with self.assertRaises(upload.ImageAnalysisError):upload.decode_image('/local/path.jpg')
        with self.assertRaises(upload.ImageAnalysisError):upload.decode_image('https://example.invalid/image.png')
    def test_animated_webp_is_rejected(self):
        buffer=io.BytesIO();Image.new('RGB',(20,20),'red').save(buffer,format='WEBP',save_all=True,
            append_images=[Image.new('RGB',(20,20),'blue')],duration=100,loop=0)
        with self.assertRaisesRegex(upload.ImageAnalysisError,'animees'):
            upload.decode_image(base64.b64encode(buffer.getvalue()).decode())
        buffer=io.BytesIO();Image.new('RGB',(20,20),'red').save(buffer,format='PNG',save_all=True,
            append_images=[Image.new('RGB',(20,20),'blue')],duration=100,loop=0)
        with self.assertRaisesRegex(upload.ImageAnalysisError,'animees'):
            upload.decode_image(base64.b64encode(buffer.getvalue()).decode())
    def test_size_limits_before_decode_or_pixel_allocation(self):
        with patch.object(upload.base64,'b64decode',side_effect=AssertionError('must reject first')):
            with self.assertRaises(upload.ImageAnalysisError):upload.decode_image('A'*(4*((upload.MAX_FILE_BYTES+2)//3)+1))
        header=Mock();header.__enter__=Mock(return_value=header);header.__exit__=Mock(return_value=False)
        header.format='PNG';header.n_frames=1;header.size=(4000,4000)
        with patch.object(upload.Image,'open',return_value=header):
            with self.assertRaisesRegex(upload.ImageAnalysisError,'12 millions'):
                upload.decode_image('YWJj')
        header.load.assert_not_called();header.verify.assert_not_called()
    def test_model_error_no_demo_and_budget(self):
        with self.assertRaisesRegex(upload.ImageAnalysisError,'non charge'):
            upload.analyze_uploaded_image(self.request(),lambda:None,lambda:dict(modelLoaded=False))
        with self.assertRaisesRegex(upload.ImageAnalysisError,'mode LIVE'):
            upload.analyze_uploaded_image(dict(self.request(),mode='DEMO'))
        ticks=iter([0,46])
        with self.assertRaisesRegex(upload.ImageAnalysisError,'Delai CPU'):
            self.analyze(self.request(),clock=lambda:next(ticks))
    def test_http_rejects_large_body_before_read(self):
        fixture=legacy.HandlerTests();fixture.setUp()
        handler=fixture.handler('/api/v1/analyze-image')
        handler.headers={'Content-Length':str(upload.MAX_BODY_BYTES+1),'Content-Type':'application/json'}
        handler.rfile=Mock();handler.rfile.read.side_effect=AssertionError('body must not be read')
        handler.do_POST();self.assertEqual(handler.status,413)
        handler.rfile.read.assert_not_called()
        self.assertFalse(json.loads(handler.wfile.getvalue())['success'])
    def test_image_route_uses_the_same_busy_lock(self):
        fixture=legacy.HandlerTests();fixture.setUp()
        fixture.server._ANALYSIS_LOCK.acquire()
        try:
            handler=fixture.handler('/api/v1/analyze-image')
            handler.do_POST()
            self.assertEqual(handler.status,503)
            self.assertFalse(json.loads(handler.wfile.getvalue())['success'])
        finally:fixture.server._ANALYSIS_LOCK.release()


if __name__=='__main__':unittest.main()
