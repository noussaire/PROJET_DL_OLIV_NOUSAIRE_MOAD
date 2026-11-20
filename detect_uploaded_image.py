"""Independent, in-memory YOLO image analysis. No Esri/OpenCV recovery or GPS."""
import base64
import binascii
import io
import math
import time
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from model_config import CONFIG

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_BODY_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 12_000_000
BUDGET_SECONDS = 45


class ImageAnalysisError(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def validate_roi(roi, width, height):
    if roi is None:
        return None
    if not isinstance(roi, list) or not 3 <= len(roi) <= 64:
        raise ImageAnalysisError('ROI : fournir de 3 a 64 sommets, ou null pour toute l\'image.')
    points = []
    for point in roi:
        if not isinstance(point, dict):
            raise ImageAnalysisError('Sommet ROI invalide.')
        x, y = point.get('x'), point.get('y')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y)):
            raise ImageAnalysisError('Coordonnees ROI non numeriques ou non finies.')
        if not (0 <= x <= width and 0 <= y <= height):
            raise ImageAnalysisError('ROI hors des dimensions de l\'image orientee.')
        points.append((float(x), float(y)))
    if points[0] == points[-1]:
        points.pop()
    if len(points) < 3 or len(set(points)) != len(points):
        raise ImageAnalysisError('ROI : sommets repetes ou insuffisants.')
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points, points[1:]+points[:1]))
    if abs(area) < 1e-6:
        raise ImageAnalysisError('ROI de surface nulle.')
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on_segment(a, b, p):
        return abs(cross(a,b,p)) < 1e-8 and min(a[0],b[0]) <= p[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= p[1] <= max(a[1],b[1])
    n = len(points)
    for i in range(n):
        a,b = points[i],points[(i+1)%n]
        for j in range(i+1,n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            c,d = points[j],points[(j+1)%n]
            if (cross(a,b,c)*cross(a,b,d) < 0 and cross(c,d,a)*cross(c,d,b) < 0) or any((
                on_segment(a,b,c),on_segment(a,b,d),on_segment(c,d,a),on_segment(c,d,b))):
                raise ImageAnalysisError('ROI auto-intersectee.')
    return np.array(points, dtype=np.float32)


def decode_image(encoded):
    if not isinstance(encoded, str) or not encoded:
        raise ImageAnalysisError('Image base64 absente.', 400)
    if len(encoded) > 4 * ((MAX_FILE_BYTES + 2) // 3):
        raise ImageAnalysisError('Image compressee superieure a 8 MiB.', 413)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ImageAnalysisError('Encodage base64 invalide.', 400)
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise ImageAnalysisError('Image vide ou superieure a 8 MiB.', 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as header:
                fmt = header.format
                if fmt not in ('JPEG', 'PNG', 'WEBP'):
                    raise ImageAnalysisError('Formats autorises : JPG, PNG et WebP uniquement.', 415)
                source_width, source_height = header.size
                if source_width <= 0 or source_height <= 0 or source_width * source_height > MAX_PIXELS:
                    raise ImageAnalysisError('Limite : 12 millions de pixels decodes.', 413)
                if getattr(header, 'n_frames', 1) != 1:
                    raise ImageAnalysisError('Les images animees ou multitrames sont refusees.', 415)
            # Metadata access may consume a PNG stream; verify on a fresh in-memory reader.
            with Image.open(io.BytesIO(raw)) as checked:
                checked.verify()
            with Image.open(io.BytesIO(raw)) as original:
                orientation = original.getexif().get(274, 1)
                if orientation not in range(1, 9):
                    raise ImageAnalysisError('Orientation EXIF invalide.')
                original.load()  # Strict Pillow decoding: truncated files must not reach YOLO.
                oriented = ImageOps.exif_transpose(original)
                transparent = 'A' in oriented.getbands() or 'transparency' in oriented.info
                if transparent:
                    rgba = oriented.convert('RGBA')
                    background = Image.new('RGBA', rgba.size, (255,255,255,255))
                    rgb = Image.alpha_composite(background, rgba).convert('RGB')
                else:
                    rgb = oriented.convert('RGB')
                bgr = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
        return bgr, dict(format=fmt, sourceWidth=source_width, sourceHeight=source_height,
                        orientationApplied=orientation != 1, transparencyOnWhite=transparent)
    except ImageAnalysisError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageAnalysisError('Image trop grande pour un decodage sur.', 413)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageAnalysisError('Image invalide, tronquee ou format non pris en charge.', 415)


def analyze_uploaded_image(data, model_provider=None, status_provider=None, clock=time.monotonic):
    started = clock()
    if not isinstance(data, dict) or data.get('mode', 'LIVE') != 'LIVE':
        raise ImageAnalysisError('Cette route accepte uniquement le mode LIVE.', 400)
    image_id = data.get('imageId')
    if not isinstance(image_id, str) or not 1 <= len(image_id) <= 64:
        raise ImageAnalysisError('Identifiant image absent ou invalide.', 400)
    image, image_info = decode_image(data.get('imageBase64'))
    height, width = image.shape[:2]
    for key, actual in (('imageWidth', width), ('imageHeight', height)):
        if key in data and (type(data[key]) is not int or data[key] != actual):
            raise ImageAnalysisError('Dimensions de l\'apercu incompatibles avec l\'orientation EXIF decodee.')
    roi = validate_roi(data.get('roiPx'), width, height)
    if model_provider is None or status_provider is None:
        from detect_any_polygon import get_yolo_model, get_model_status
        model_provider = model_provider or get_yolo_model
        status_provider = status_provider or get_model_status
    status = status_provider()
    if not status.get('modelLoaded') or status.get('profile') != 'yolo11m_v1':
        raise ImageAnalysisError('YOLO11m V1 non charge ; aucun autre modele ni simulation utilise.', 503)
    parameters = CONFIG['inferenceParameters'].copy()
    required = dict(imgsz=1280, conf=0.20, iou=0.50, max_det=1000, device='cpu')
    if parameters != required:
        raise ImageAnalysisError('Configuration YOLO11m incompatible avec le parcours image LIVE.', 503)
    def check_time():
        if clock() - started > BUDGET_SECONDS:
            raise ImageAnalysisError('Delai CPU depasse. Utiliser une image plus petite.', 504)
    check_time()
    inference_started = clock()
    model = model_provider()
    if model is None:
        raise ImageAnalysisError('Modele indisponible ; aucune simulation utilisee.', 503)
    try:
        result = model.predict(image, **parameters, verbose=False, save=False)[0]
    except Exception as error:
        raise ImageAnalysisError('Echec de l\'inference YOLO. Aucune detection simulee.', 500) from error
    inference_ms = round((clock() - inference_started) * 1000, 1)
    check_time()
    detections = []
    raw_count = len(result.boxes)
    for box in result.boxes:
        coords = [float(v) for v in box.xyxy[0].tolist()]
        score = float(box.conf[0])
        class_id = int(box.cls[0])
        if len(coords) != 4 or not all(math.isfinite(v) for v in coords) or not math.isfinite(score):
            raise ImageAnalysisError('Coordonnees ou score YOLO invalides.', 500)
        x1,y1,x2,y2 = coords
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height and 0 <= score <= 1):
            raise ImageAnalysisError('Detection YOLO hors du referentiel image.', 500)
        center = [(x1+x2)/2, (y1+y2)/2]
        if roi is not None and cv2.pointPolygonTest(roi, tuple(center), False) < 0:
            continue
        detections.append(dict(id=len(detections)+1, bboxPx=coords, centerPx=center,
                               confidence=score, classId=class_id,
                               className=str(result.names[class_id]), source='YOLO'))
    warnings_list = [
        'Classe trees : reconnaissance exclusive des oliviers non garantie.',
        'Les performances du dataset ne valident pas ces nouvelles images drone.',
        'Analyse globale a 1280 pixels : de petits arbres peuvent etre perdus ; aucun tuilage en V1.',
        'Aucun GPS, diametre en metres, age ou diagnostic sanitaire calcule.',
    ]
    if raw_count >= parameters['max_det']:
        warnings_list.append('Plafond max_det=1000 potentiellement atteint sur l\'image entiere.')
    if image_info['transparencyOnWhite']:
        warnings_list.append('Transparence composee sur fond blanc avant inference.')
    return dict(success=True, mode='LIVE', engine='YOLO', imageId=image_id,
                coordinateSystem='IMAGE_PIXELS', imageWidth=width, imageHeight=height,
                **image_info, totalDetections=len(detections), rawDetectionCount=raw_count,
                roiApplied=roi is not None, detections=detections, model=CONFIG['model'],
                modelPath=CONFIG['modelPath'], inferenceParameters=parameters,
                inferenceTimeMs=inference_ms, totalTimeMs=round((clock()-started)*1000, 1),
                warnings=warnings_list, error=None)
