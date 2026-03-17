"""
Thursday Telemetry Endpoint
===========================
POST /api/telemetry  — Sovereign pushes training metrics every 30s
GET  /api/telemetry  — Dashboard fetches latest telemetry + history
"""

from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _store import (
    auth_check, push_telemetry, get_latest_telemetry,
    get_telemetry_history, add_alert,
)


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        """
        Sovereign pushes telemetry here every 30 seconds during training.

        Expected payload:
        {
            "key": "PROJECT_DIVYAKUSH_OMEGA_99",
            "action": "TELEMETRY_PUSH",
            "data": {
                "step": 1500,
                "total_steps": 2500000,
                "loss": 2.3418,
                "lr": 0.00015,
                "gnorm": 0.72,
                "tflops": 842.5,
                "tok_per_sec": 1420000,
                "gpu_util": 91.4,
                "gpu_temp": 68.2,
                "vram_gb": 10240,
                "ib_gbps": 312.8,
                "eta_h": 528.0,
                "status": "TRAINING_ACTIVE",
                "active_nodes": 15,
                "active_gpus": 120,
                "alerts": []
            }
        }
        """
        body = self._read_body()
        if not body:
            return self._json({"error": "EMPTY_BODY"}, 400)

        if not auth_check(body.get("key", "")):
            return self._json({"error": "UNAUTHORIZED"}, 403)

        data = body.get("data", {})
        if not data:
            return self._json({"error": "NO_DATA"}, 400)

        # Store telemetry
        push_telemetry(data)

        self._json({
            "status": "TELEMETRY_RECEIVED",
            "step": data.get("step", 0),
            "message": "Metrics persisted to sovereign state store.",
        })

    def do_GET(self):
        """
        Dashboard polls this for the latest telemetry and chart history.
        Requires OMEGA_99 key in X-Auth-Key header or ?key= query param.
        """
        key = self._get_auth_key()
        if not auth_check(key):
            return self._json({"error": "UNAUTHORIZED"}, 403)

        latest = get_latest_telemetry() or {}
        history = get_telemetry_history()

        self._json({
            "status": "OK",
            "latest": latest,
            "history": history[-200:],  # Last 200 data points for charts
            "total_records": len(history),
        })

    def do_OPTIONS(self):
        self._cors_preflight()

    # ── Helpers ──

    def _get_auth_key(self):
        key = self.headers.get("X-Auth-Key", "")
        if key:
            return key
        if "?" in self.path:
            params = dict(
                p.split("=", 1) for p in self.path.split("?", 1)[1].split("&")
                if "=" in p
            )
            return params.get("key", "")
        return ""

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return None
            return json.loads(self.rfile.read(length))
        except Exception:
            return None

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Key")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors_preflight(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Key")
        self.end_headers()
