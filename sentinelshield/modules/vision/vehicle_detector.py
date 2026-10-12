"""Vehicle detector: YOLOv8 (if ultralytics/torch are installed) or RF-DETR COCO via ONNX Runtime.

The RF-DETR model ships with open-image-models (already a fast-alpr dependency) and
runs on CPU without torch. Only real COCO vehicle classes are reported. If no neural
detector can be loaded, no vehicles are returned — the old edge/contour heuristic
labelled shop signs, lights and road texture as cars, so it was removed.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

from sentinelshield.config import settings

logger = logging.getLogger(__name__)

# COCO label -> label used across SentinelShield (UI, tracker, DB)
VEHICLE_LABELS = {
    "car": "car",
    "motorcycle": "bike/activa",
    "bicycle": "bike/activa",  # the model often calls ridden scooters/motorbikes "bicycle"
    "bus": "bus/truck",
    "truck": "bus/truck",
}

_yolo_detector = None
_yolo_initialized = False

_rfdetr = None
_rfdetr_tried = False
_rfdetr_error: str | None = None
_rfdetr_load_ms: float | None = None
_model_lock = threading.Lock()
_infer_lock = threading.Lock()  # one inference at a time: avoids oversubscribing the CPU

# Single background worker for live streams (see detect_vehicles_nonblocking)
_live_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vehicle-detect")


def _init_yolo():
    global _yolo_detector, _yolo_initialized
    if _yolo_initialized:
        return _yolo_detector

    _yolo_initialized = True
    try:
        from ultralytics import YOLO
        import torch
        model_path = os.path.join(os.path.dirname(__file__), "models", "yolov8s.pt")
        if not os.path.exists(model_path):
            logger.warning("YOLOv8 model not found at %s.", model_path)
            return None

        logger.info("Loading YOLOv8 model from %s", model_path)
        _yolo_detector = YOLO(model_path)

        if torch.cuda.is_available():
            _yolo_detector.model.half()
            logger.info("YOLOv8 FP16 mode enabled")

    except ImportError:
        logger.info("Ultralytics/Torch not installed; using RF-DETR ONNX vehicle detector.")
    except Exception as e:
        logger.error("Failed to load YOLOv8: %s", e)

    return _yolo_detector


def _init_rfdetr():
    global _rfdetr, _rfdetr_tried, _rfdetr_error, _rfdetr_load_ms
    if _rfdetr_tried:
        return _rfdetr
    with _model_lock:
        if _rfdetr_tried:
            return _rfdetr
        _rfdetr_tried = True
        started = time.time()
        try:
            from open_image_models import create_detector
            _rfdetr = create_detector(settings.vehicle_model, conf_thresh=settings.vehicle_min_conf)
            _rfdetr_load_ms = round((time.time() - started) * 1000)
            logger.info("Vehicle detector %s ready in %s ms", settings.vehicle_model, _rfdetr_load_ms)
        except Exception as exc:  # missing package / offline model download
            _rfdetr_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Vehicle detector unavailable: %s", _rfdetr_error)
    return _rfdetr


def warm_up() -> None:
    """Load the vehicle model in the background so the first scan is not delayed."""
    threading.Thread(target=lambda: _init_yolo() or _init_rfdetr(), name="vehicle-warmup", daemon=True).start()


def detector_status() -> dict[str, Any]:
    if _yolo_detector is not None:
        return {"engine": "YOLOv8 (ultralytics)", "available": True, "state": "ready", "error": None}
    loaded = _rfdetr_tried and _rfdetr is not None
    return {
        "engine": f"RF-DETR COCO (ONNX) — {settings.vehicle_model}",
        "available": loaded,
        "state": "ready" if loaded else ("error" if _rfdetr_error else "loading"),
        "error": _rfdetr_error,
        "load_ms": _rfdetr_load_ms,
        "min_confidence": settings.vehicle_min_conf,
    }


def _detect_yolo(detector, frame) -> list[dict[str, Any]]:
    # 2, 3, 5, 7 are COCO classes for car, motorcycle, bus, truck
    results = detector.track(source=frame, persist=True, conf=0.35, iou=0.45, verbose=False, classes=[2, 3, 5, 7])
    boxes_out = []
    if results and len(results) > 0 and results[0].boxes is not None:
        boxes = results[0].boxes
        if boxes.id is not None:
            coco_names = {2: "car", 3: "bike/activa", 5: "bus/truck", 7: "bus/truck"}
            for tid, cf, cls_id, (x1, y1, x2, y2) in zip(
                boxes.id.int().tolist(), boxes.conf.tolist(), boxes.cls.int().tolist(), boxes.xyxy.tolist()
            ):
                boxes_out.append({
                    "x": int(x1), "y": int(y1), "w": int(x2 - x1), "h": int(y2 - y1),
                    "cls": coco_names.get(cls_id, "vehicle"),
                    "confidence": round(cf, 2),
                    "track_id": tid,
                })
    return boxes_out


def _detect_rfdetr(detector, frame) -> list[dict[str, Any]]:
    h, w = frame.shape[:2]
    with _infer_lock:
        results = detector.predict(frame)
    boxes_out = []
    for r in results:
        cls_name = VEHICLE_LABELS.get(r.label)
        if cls_name is None or r.confidence < settings.vehicle_min_conf:
            continue
        b = r.bounding_box
        x1, y1 = max(int(b.x1), 0), max(int(b.y1), 0)
        x2, y2 = min(int(b.x2), w), min(int(b.y2), h)
        if x2 - x1 < 12 or y2 - y1 < 12:  # too small to be useful (or noise)
            continue
        boxes_out.append({
            "x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1,
            "cls": cls_name,
            "confidence": round(float(r.confidence), 2),
        })
    boxes_out.sort(key=lambda b: -b["confidence"])
    return boxes_out


def detect_vehicles(frame: np.ndarray, prev_gray: np.ndarray | None = None) -> list[dict[str, Any]]:
    """Detect real vehicles in a BGR frame. `prev_gray` is accepted for backward compatibility."""
    if frame is None or getattr(frame, "size", 0) == 0:
        return []

    detector = _init_yolo()
    if detector is not None:
        try:
            return _detect_yolo(detector, frame)
        except Exception as e:
            logger.error("YOLO tracking failed: %s", e)

    detector = _init_rfdetr()
    if detector is not None:
        try:
            return _detect_rfdetr(detector, frame)
        except Exception as e:
            logger.error("RF-DETR vehicle detection failed: %s", e)
    return []


def detect_vehicles_nonblocking(frame: np.ndarray, camera_state: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Live-stream variant: never blocks the video loop.

    Submits the frame to a background worker when it is idle and returns the most
    recent finished result for this camera as (vehicles, fresh). `camera_state` is the
    per-camera dict from `core.state.tracking_state`, which holds the pending job.
    """
    fresh = False
    pending = camera_state.get("vehicle_job")
    if pending is not None and pending.done():
        try:
            camera_state["vehicles_latest"] = pending.result()
        except Exception:
            camera_state["vehicles_latest"] = []
        camera_state["vehicle_job"] = None
        fresh = True
    if camera_state.get("vehicle_job") is None and frame is not None:
        camera_state["vehicle_job"] = _live_executor.submit(detect_vehicles, frame.copy())
    return camera_state.get("vehicles_latest", []), fresh
