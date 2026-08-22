# Deep Inspection Audit: `modules/vision`

> **Audit Frameworks**: Ponytail (Over-Engineering & Dead Code) + Systematic Debugging (Root Cause & Failure Modes) + Paranoid-Minimalist  
> **Target Subsystem**: [`sentinelshield/modules/vision/`](file:///D:/Projects/SentinelShield/sentinelshield/modules/vision/)

---

## 1. Ponytail Over-Engineering & Simplification Analysis
- **`<delete>`**: Avoided loading monolithic multi-gigabyte models when standard morphological operations and regex extraction provide instant results.
- **`<stdlib>`**: `re`, `threading`.
- **`<yagni>`**: Deblurring pipeline uses fixed 2-pass CLAHE/Laplacian filters rather than complex GAN/diffusion restoration models that would exhaust 6GB VRAM.
- **`<shrink>`**: `normalize_plate` is a single regex substitution line: `re.sub(r"[^A-Z0-9]", "", (p or "").upper())`.
- **Net Verdict**: Lean, practical computer vision pipeline.

---

## 2. Systematic Debugging & Failure Mode Analysis

| Component | Potential Root Cause / Failure Mode | Evidence & Trace | Paranoid Defensive Guard |
| :--- | :--- | :--- | :--- |
| `blur_box` / `enhance_blurry_crop` | Out-of-bounds bounding box coordinates | `x < 0` or `x + w > frame_width` | Coordinates are clamped to image boundaries before array slicing: `max(0, x)`, `min(w, img.shape[1])`. |
| `read_plate_text` | OCR text contains weird punctuation or unicode | Malformed chars cause regex failure | `extract_plates_from_text` tests multiple regex variations with uppercase normalization. |
| `detect_fast_alpr` | CUDA out of memory / missing weights | Deep learning inference raises exception | Circuit breaker disables backend (`_fast_alpr_unavailable = True`) and falls back to morphological OCR. |

---

## 3. Polish & Upgrade Recommendations
1. **Confidence Thresholding Calibration**: Expose OCR confidence score filtering in `settings.py` so operators can tune strictness.
2. **State Code Whitelist**: Add validation table for all 36 Indian State & Union Territory codes (`GJ`, `MH`, `DL`, etc.).
