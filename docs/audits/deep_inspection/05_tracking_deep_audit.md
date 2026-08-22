# Deep Inspection Audit: `modules/tracking`

> **Audit Frameworks**: Ponytail (Over-Engineering & Dead Code) + Systematic Debugging (Root Cause & Failure Modes) + Paranoid-Minimalist  
> **Target Subsystem**: [`sentinelshield/modules/tracking/`](file:///D:/Projects/SentinelShield/sentinelshield/modules/tracking/)

---

## 1. Ponytail Over-Engineering & Simplification Analysis
- **`<delete>`**: None.
- **`<stdlib>`**: Pure Python math and `time`. Zero heavy external matrix or Kalman filtering dependencies.
- **`<yagni>`**: Avoided multi-camera 3D camera calibration matrices; multi-hop trajectory is reconstructed via timestamped camera GIS node sightings.
- **`<shrink>`**: `associate_tracks` fits in under 50 lines.
- **Net Verdict**: Highly efficient $O(N)$ track association.

---

## 2. Systematic Debugging & Failure Mode Analysis

| Component | Potential Root Cause / Failure Mode | Evidence & Trace | Paranoid Defensive Guard |
| :--- | :--- | :--- | :--- |
| `CentroidVehicleTracker.associate_tracks` | Vehicle jumps across camera frame | Track ID reassigned | Distance threshold (100px) creates new track ID if distance exceeds threshold, preventing false continuous trajectories. |
| `TrackingService.find_vehicle` | SQL injection in license plate query | Attacker passes `' OR '1'='1` | SQL query strictly uses parameterized placeholders: `SELECT * FROM sightings WHERE plate=?`. |
| `TrackingService.calculate_route` | Vehicle seen only once | Insufficient nodes to draw polyline | Returns single-point route manifest without crashing UI map renderer. |

---

## 3. Polish & Upgrade Recommendations
1. **Speed Vector Estimation**: Calculate average inter-camera velocity ($\text{km/h}$) based on timestamps and GIS distance between cameras to flag speeding anomalies.
2. **Predictive Next-Camera Route Node**: Project the most likely next intersection camera based on heading vector.
