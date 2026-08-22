"""CCTV Deblurring and Super-Resolution Image Enhancement Pipeline."""
from __future__ import annotations

import base64
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


def enhance_blurry_crop(crop: np.ndarray) -> dict[str, Any]:
    """CCTV Deblurring & Contrast Enhancement Pipeline.
    
    Applies bicubic upscaling, CLAHE contrast boost in LAB space,
    unsharp mask deblurring, adaptive thresholding, and Laplacian variance scoring.
    """
    if crop is None or crop.size == 0:
        return {"enhanced_bgr": crop, "b64": "", "laplacian_score": 0.0, "scale_applied": 1.0}

    h, w = crop.shape[:2]

    # 1. Bicubic Rescaling / Upscaling if low resolution
    scale = 1.0
    if h < 90 or w < 220:
        scale = max(2.5, 240.0 / max(h, 1))
        new_w, new_h = int(w * scale), int(h * scale)
        crop_upscaled = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    else:
        crop_upscaled = crop.copy()

    # 2. CLAHE (Contrast Limited Adaptive Histogram Equalization) in LAB space
    lab = cv2.cvtColor(crop_upscaled, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    enhanced_lab = cv2.merge((cl, a, b))
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # 3. Unsharp Masking & Sharpening Filter (Deblurring)
    blur = cv2.GaussianBlur(enhanced_bgr, (0, 0), sigmaX=3.0)
    sharpened_bgr = cv2.addWeighted(enhanced_bgr, 1.8, blur, -0.8, 0)

    # 4. Grayscale & Adaptive Thresholding
    gray = cv2.cvtColor(sharpened_bgr, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # 5. Measure Sharpness / Laplacian Variance Score
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Encode enhanced crop to JPEG Base64 for web rendering
    ok, buf = cv2.imencode(".jpg", sharpened_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    b64_str = base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    return {
        "enhanced_bgr": sharpened_bgr,
        "thresh_gray": thresh,
        "b64": f"data:image/jpeg;base64,{b64_str}",
        "laplacian_score": round(laplacian_var, 2),
        "scale_applied": round(scale, 2),
    }


def blur_box(frame: np.ndarray, box: dict[str, int]) -> None:
    """Blur a bounding box region in-place for privacy filtering."""
    if frame is None or frame.size == 0 or not box:
        return
    height, width = frame.shape[:2]
    x = max(0, min(width, int(box.get("x", 0))))
    y = max(0, min(height, int(box.get("y", 0))))
    right = max(x, min(width, x + int(box.get("w", 0))))
    bottom = max(y, min(height, y + int(box.get("h", 0))))
    crop = frame[y:bottom, x:right]
    if crop.size:
        frame[y:bottom, x:right] = cv2.GaussianBlur(crop, (0, 0), 12)
