"""Centroid multi-frame vehicle tracker with distance association."""
from __future__ import annotations

import time
from typing import Any


class CentroidVehicleTracker:
    """Tracks vehicle bounding boxes and centroids across consecutive frames."""

    @staticmethod
    def associate_tracks(
        camera_id: str,
        vehicles: list[dict[str, Any]],
        state: dict[str, Any],
        distance_threshold: float = 100.0,
    ) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any], bool]]]:
        """Associate detected vehicle bounding boxes with active tracks.
        
        Returns:
            updated_current_tracks: dict of currently active tracks
            track_results: list of tuples (track_id, vehicle_box, is_new)
        """
        current: dict[str, Any] = {}
        used: set[str] = set()
        track_results: list[tuple[str, dict[str, Any], bool]] = []

        existing_tracks = state.get("tracks", {})
        next_id = state.get("next_id", 1)
        count = state.get("count", 0)

        for vehicle in vehicles:
            center = (vehicle["x"] + vehicle["w"] // 2, vehicle["y"] + vehicle["h"] // 2)
            selected = None
            selected_distance = 10**9

            for track_id, track in existing_tracks.items():
                if track_id in used:
                    continue
                old = track.get("center", (0, 0))
                distance = ((center[0] - old[0]) ** 2 + (center[1] - old[1]) ** 2) ** 0.5
                if distance < distance_threshold and distance < selected_distance:
                    selected, selected_distance = track_id, distance

            is_new = selected is None
            track_id = selected or f"{camera_id}-v{next_id}"
            if is_new:
                next_id += 1
                count += 1

            track = existing_tracks.get(track_id, {"plate": None, "saved": False})
            track["center"] = center
            track["box"] = vehicle
            track["last_seen"] = time.time()
            current[track_id] = track
            used.add(track_id)

            track_results.append((track_id, vehicle, is_new))

        # Filter out tracks not seen for >2.5s, merging recently seen active tracks
        now = time.time()
        merged_tracks = dict(existing_tracks)
        merged_tracks.update(current)
        active_tracks = {k: v for k, v in merged_tracks.items() if now - v.get("last_seen", 0) < 2.5}

        state["tracks"] = active_tracks
        state["next_id"] = next_id
        state["count"] = count

        return active_tracks, track_results
