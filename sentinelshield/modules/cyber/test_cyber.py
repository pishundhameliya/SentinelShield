"""Unit and integration tests for Cyber & Decoy Trap module."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from sentinelshield.core.database import db_manager
from sentinelshield.modules.cyber.honeypot import CyberHoneypotService, EVENT_POINTS
from sentinelshield.modules.alerts.service import AlertService


class MockRequestClient:
    def __init__(self, host: str):
        self.host = host


class MockRequestUrl:
    def __init__(self, path: str):
        self.path = path


class MockRequest:
    def __init__(self, host: str, method: str, path: str, headers: dict[str, str] | None = None):
        self.client = MockRequestClient(host)
        self.method = method
        self.url = MockRequestUrl(path)
        self.headers = headers or {}


class TestCyberSubsystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Backup original DB path and set up a clean isolated DB for testing
        cls.orig_db_path = db_manager.db_path
        cls.test_db_path = "test_cyber_isolated.db"
        db_manager.db_path = cls.test_db_path
        
        # Clean up any leftover database files
        for f in (cls.test_db_path, cls.test_db_path + "-wal", cls.test_db_path + "-shm"):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        # Initialize tables
        db_manager.init_schema()
        cls.cyber = CyberHoneypotService()

    @classmethod
    def tearDownClass(cls):
        # Restore original DB path
        db_manager.db_path = cls.orig_db_path
        
        # Clean up database files
        for f in (cls.test_db_path, cls.test_db_path + "-wal", cls.test_db_path + "-shm", cls.test_db_path + "-journal"):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def setUp(self):
        # Clear database records before each test
        db_manager.execute("DELETE FROM cyber_events")
        db_manager.execute("DELETE FROM cyber")
        db_manager.execute("DELETE FROM cyber_activity")
        db_manager.execute("DELETE FROM cyber_camera_health")
        
        # Reset memory tracking states
        with self.cyber._lock:
            self.cyber._failed_logins.clear()
            self.cyber._requests.clear()
            self.cyber._scans.clear()

    def test_failed_login_threshold(self):
        source_ip = "192.168.1.100"
        camera_id = "test-cam-1"
        
        # Attempt 4 failed logins
        for i in range(4):
            res = self.cyber.track_auth_attempt(source_ip, camera_id, False, username="attacker")
            self.assertEqual(res["status"], "failed")
            self.assertEqual(res["consecutive_failures"], i + 1)
            self.assertFalse(res["threshold_breached"])
            self.assertIsNone(res["event"])
            
        # 5th failed login triggers threshold
        res = self.cyber.track_auth_attempt(source_ip, camera_id, False, username="attacker")
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["consecutive_failures"], 5)
        self.assertTrue(res["threshold_breached"])
        self.assertIsNotNone(res["event"])
        self.assertEqual(res["event"]["event_type"], "failed_login")
        self.assertIn("attacker", res["event"]["description"])
        
        # Count should be reset, next failed login is failure 1
        res = self.cyber.track_auth_attempt(source_ip, camera_id, False, username="attacker")
        self.assertEqual(res["consecutive_failures"], 1)
        self.assertFalse(res["threshold_breached"])
        
        # Successful login resets the counter
        self.cyber.track_auth_attempt(source_ip, camera_id, False, username="attacker")
        res = self.cyber.track_auth_attempt(source_ip, camera_id, True)
        self.assertEqual(res["status"], "success")
        
        # Next failed login starts at 1
        res = self.cyber.track_auth_attempt(source_ip, camera_id, False, username="attacker")
        self.assertEqual(res["consecutive_failures"], 1)

    def test_repeated_connection_detection(self):
        source_ip = "192.168.1.101"
        camera_id = "test-cam-2"
        
        # Send 19 safe requests
        for i in range(19):
            res = self.cyber.track_request(source_ip, camera_id, "/live/stream.mjpg")
            self.assertEqual(res["request_count"], i + 1)
            self.assertFalse(res["unauthorized_access"])
            self.assertIsNone(res["repeated_event"])
            
        # 20th request triggers rate-limit breach
        res = self.cyber.track_request(source_ip, camera_id, "/live/stream.mjpg")
        self.assertEqual(res["request_count"], 20)
        self.assertIsNotNone(res["repeated_event"])
        self.assertEqual(res["repeated_event"]["event_type"], "repeated_requests")

    def test_unauthorized_endpoint_detection(self):
        source_ip = "192.168.1.102"
        camera_id = "test-cam-3"
        
        # Accessing an unauthorized endpoint should immediately trigger event
        res = self.cyber.track_request(source_ip, camera_id, "/admin/config.php")
        self.assertTrue(res["unauthorized_access"])
        self.assertIsNotNone(res["unauthorized_event"])
        self.assertEqual(res["unauthorized_event"]["event_type"], "unauthorized_endpoint")
        self.assertIn("/admin/config.php", res["unauthorized_event"]["description"])

    def test_port_scan_detection(self):
        source_ip = "192.168.1.103"
        
        # Access camera 1 and camera 2 on ports
        res1 = self.cyber.track_connection(source_ip, "cam-1", 80)
        self.assertFalse(res1["port_scan_detected"])
        self.assertEqual(res1["unique_targets"], 1)
        
        res2 = self.cyber.track_connection(source_ip, "cam-2", 8080)
        self.assertFalse(res2["port_scan_detected"])
        self.assertEqual(res2["unique_targets"], 2)
        
        # 3rd unique camera/port target triggers port scan
        res3 = self.cyber.track_connection(source_ip, "cam-3", 554)
        self.assertTrue(res3["port_scan_detected"])
        self.assertEqual(res3["unique_targets"], 3)
        self.assertEqual(res3["event"]["event_type"], "port_scan")
        self.assertIn("cam-3:554", res3["event"]["description"])

    def test_threat_score_and_severity_classification(self):
        source_ip = "192.168.1.104"
        camera_id = "test-cam-4"
        
        # Verify score progression and severity levels:
        # LOW (<15), MEDIUM (15-29), HIGH (30-59), CRITICAL (>=60)
        
        # Event 1: failed login (points = 10, total = 10) -> LOW
        ev1 = self.cyber.record_event("failed_login", "Failed login", camera_id, source_ip)
        self.assertEqual(ev1["score"], 10)
        self.assertEqual(ev1["severity"], "LOW")
        
        # Event 2: repeated connection (points = 12, total = 10 + 12 = 22) -> MEDIUM
        ev2 = self.cyber.record_event("repeated_connection", "Repeated connection", camera_id, source_ip)
        self.assertEqual(ev2["score"], 22)
        self.assertEqual(ev2["severity"], "MEDIUM")
        
        # Event 3: unauthorized endpoint (points = 15, total = 22 + 15 = 37) -> HIGH
        ev3 = self.cyber.record_event("unauthorized_endpoint", "Access admin", camera_id, source_ip)
        self.assertEqual(ev3["score"], 37)
        self.assertEqual(ev3["severity"], "HIGH")
        
        # Event 4: port scan (points = 25, total = 37 + 25 = 62) -> CRITICAL
        ev4 = self.cyber.record_event("port_scan", "Port scan", camera_id, source_ip, score=25)
        self.assertEqual(ev4["score"], 62)
        self.assertEqual(ev4["severity"], "CRITICAL")

    def test_decoy_request_logging_and_auth_headers(self):
        # 1. Normal Request (no auth)
        req = MockRequest("10.0.0.1", "GET", "/onvif/device_service")
        res = self.cyber.trigger_honeypot_incident("10.0.0.1", "GET /onvif/device_service", request=req)
        
        self.assertFalse(res["ok"])
        self.assertEqual(res["camera"], "CAM-HONEYPOT-01")
        self.assertEqual(res["event"]["event_type"], "unauthorized_endpoint")
        self.assertIn("GET /onvif/device_service", res["event"]["description"])
        
        # Check logged activity in database
        activity = self.cyber.get_honeypot_hits()
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0]["source_ip"], "10.0.0.1")
        self.assertEqual(activity[0]["action"], "GET /onvif/device_service")
        
        # 2. Authentication Request (with Basic auth)
        # admin:supersecret -> Basic YWRtaW46c3VwZXJzZWNyZXQ=
        auth_headers = {"authorization": "Basic YWRtaW46c3VwZXJzZWNyZXQ="}
        req_auth = MockRequest("10.0.0.2", "POST", "/onvif/device_service", headers=auth_headers)
        res_auth = self.cyber.trigger_honeypot_incident("10.0.0.2", "POST /onvif/device_service", request=req_auth)
        
        self.assertEqual(res_auth["event"]["event_type"], "failed_login")
        self.assertIn("admin", res_auth["event"]["description"])
        
        # Check logged activity in database includes user detail
        activity = self.cyber.get_honeypot_hits()
        self.assertEqual(len(activity), 2)
        actions = [a["action"] for a in activity]
        self.assertTrue(any("[Auth: admin]" in act for act in actions))

    def test_camera_disconnect_reconnect_health(self):
        camera_id = "cam-health-test"
        
        # 1. Initial State
        res = self.cyber.update_camera_health(camera_id, "connected", "192.168.1.50")
        self.assertEqual(res["camera_id"], camera_id)
        self.assertEqual(res["state"], "connected")
        self.assertFalse(res["suspicious"])
        self.assertIsNone(res["event"])
        
        # 2. Unexpected Disconnect
        res = self.cyber.update_camera_health(camera_id, "disconnected", "192.168.1.50")
        self.assertEqual(res["state"], "disconnected")
        self.assertIsNotNone(res["event"])
        self.assertEqual(res["event"]["event_type"], "repeated_connection")
        self.assertIn("Unexpected camera disconnect", res["event"]["description"])
        
        # 3. Reconnect
        res = self.cyber.update_camera_health(camera_id, "reconnected", "192.168.1.50")
        self.assertEqual(res["state"], "reconnected")
        self.assertIsNotNone(res["event"])
        self.assertEqual(res["event"]["event_type"], "repeated_connection")
        self.assertIn("Camera reconnected", res["event"]["description"])
        
        # 4. Suspect state change (IP spoof / change)
        res = self.cyber.update_camera_health(camera_id, "disconnected", "192.168.1.99")
        self.assertTrue(res["suspicious"])
        self.assertEqual(res["event"]["event_type"], "connection_anomaly")

    def test_simulation_mode(self):
        res = self.cyber.simulate("failed_login", "192.168.10.10", "cam-test-sim")
        self.assertTrue(res["simulated"])
        self.assertTrue(res["description"].startswith("SIMULATION: "))

    @patch.object(AlertService, 'create_alert_with_cooldown')
    def test_alert_generation(self, mock_create_alert):
        source_ip = "192.168.1.200"
        camera_id = "alert-camera"
        
        # Record small event - score = 10 (LOW), should not trigger alert
        self.cyber.record_event("failed_login", "Failed login", camera_id, source_ip)
        mock_create_alert.assert_not_called()
        
        # Record critical event - score = 65 (CRITICAL), should trigger alert
        self.cyber.record_event("port_scan", "Aggressive scan", camera_id, source_ip, score=65)
        mock_create_alert.assert_called_once()
        args, kwargs = mock_create_alert.call_args
        self.assertEqual(args[0], camera_id)
        self.assertEqual(args[1], "cyber")
        self.assertEqual(args[2], "Cybersecurity critical event")
        self.assertEqual(kwargs["severity"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()
