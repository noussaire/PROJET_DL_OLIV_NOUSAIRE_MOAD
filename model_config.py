"""Reversible satellite model selection. Read once when the process starts."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILES = {
    'yolo11m_v1': {
        'name': 'YOLO11m V1',
        'path': ROOT / 'models' / 'yolo11m_olivesmart_v1.pt',
        'parameters': dict(imgsz=1280, conf=0.20, iou=0.50, max_det=1000, device='cpu'),
    },
    'yolov8n': {
        'name': 'best.pt (YOLOv8n)',
        'path': ROOT / 'best.pt',
        'parameters': dict(imgsz=640, conf=0.10, iou=0.35, max_det=300, device='cpu'),
    },
}


def get_config():
    profile = os.environ.get('OLIVESMART_MODEL', 'yolo11m_v1').lower()
    if profile not in PROFILES:
        raise ValueError('OLIVESMART_MODEL must be yolo11m_v1 or yolov8n; no fallback allowed')
    selected = PROFILES[profile]
    return dict(profile=profile, model=selected['name'], modelPath=str(selected['path']),
                inferenceParameters=selected['parameters'].copy())


CONFIG = get_config()
