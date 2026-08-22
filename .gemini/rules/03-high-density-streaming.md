# Antigravity Rule: High-Density Real-Time Streaming (200+ Feeds)

## Performance Envelope
- Target: 200 concurrent live CCTV streams on single workstation (24GB RAM, RTX 4050 6GB VRAM).
- Aggregate throughput: $>25,000\text{ FPS}$, per-frame latency $<0.05\text{ ms}$.

## Streaming Invariants
1. **Zero Dynamic Allocation**: Ingestion loops must never allocate new numpy arrays. Use pre-allocated `(90, 160, 3)` numpy ring buffers in `MultiCameraTamperPool`.
2. **Multiprocessing Core Partitioning**: Parallel stream decodes are partitioned across dedicated worker processes in `StreamWorkerPool` to bypass the Python GIL.
3. **Adaptive Client Backpressure**: Drop intermediate frames dynamically if client network queue lags (`mjpeg_frame_generator`).
4. **Exponential Backoff Reconnect**: Failed video/RTSP streams reconnect using $1\text{s} \rightarrow 2\text{s} \rightarrow 4\text{s} \rightarrow 8\text{s} \rightarrow 16\text{s}$ backoff.
