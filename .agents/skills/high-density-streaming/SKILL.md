---
name: high-density-streaming
description: Protocols and performance invariants for scaling real-time video streaming to 200+ concurrent cameras on limited hardware
---

# High-Density Real-Time Video Streaming (200+ Feeds)

## Core Hardware Envelope
- Target platform: Standard workstation / laptop (24 GB RAM, NVIDIA RTX 4050 6GB VRAM, 8–16 CPU cores).
- Aggregate throughput target: $>25,000\text{ FPS}$, latency $<0.05\text{ ms}$ per frame.

## The 5 Invariants of High-Density Streaming
1. **Zero Dynamic Memory Allocation**:
   - Never instantiate new numpy arrays or frame buffers inside per-frame loops.
   - Use pre-allocated `(90, 160, 3)` ring buffers (`MultiCameraTamperPool`) with fixed capacity and $O(1)$ LRU eviction.
2. **Multiprocessing Partitioning (GIL Bypass)**:
   - Never run 50+ camera decodes in a single Python process threadpool.
   - Partition camera feeds across dedicated worker processes matching CPU core topology (`StreamWorkerPool`).
3. **Adaptive Client Backpressure**:
   - Never let a slow browser or mobile viewer slow down the ingestion worker.
   - Drop intermediate frames if client transport queue backs up (`mjpeg_frame_generator`).
4. **Exponential Backoff Reconnect**:
   - When remote RTSP or HTTP video links fail, use exponential backoff (`1s -> 2s -> 4s -> 8s -> 16s`) to prevent socket thread thrashing.
5. **Hardware Decode Probing**:
   - Probe CUDA/NVDEC/MSMF/D3D11 hardware backends before falling back to CPU decoding.
