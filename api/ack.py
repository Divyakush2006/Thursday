"""
Thursday Acknowledgment Endpoint
=================================
POST /api/ack  — Sovereign confirms it received and executed a command.
                 This clears the command to IDLE so it doesn't re-execute.
"""

from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _store import auth_check, clear_command, add_alert


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        """
        Sovereign calls this after picking up and executing a command.

        Expected payload:
        {
            "key": "PROJECT_DIVYAKUSH_OMEGA_99",
            "status": "RECEIVED",
            "command": "IGNITE",
            "job_id": "MK2-GOD-001",
            "gpus_allocated": 120
        }
        """
        body = self._read_body()
        if not body:
            return self._json({"error": "EMPTY_BODY"}, 400)

        if not auth_check(body.get("key", "")):
            return self._json({"error": "UNAUTHORIZED"}, 403)

        acked_command = body.get("command", "UNKNOWN")
        job_id = body.get("job_id", "")
        gpus = body.get("gpus_allocated", 0)

        # Clear the command so it won't be re-read
        clear_command()

        # Log the acknowledgment
        msg = f"Sovereign acknowledged: {acked_command}"
        if job_id:
            msg += f" (Job: {job_id}, {gpus} GPUs)"
        add_alert("info", msg)

        self._json({
            "status": "ACKNOWLEDGED",
            "command_cleared": True,
            "message": f"Command '{acked_command}' cleared from beacon.",
        })

    def do_OPTIONS(self):
        self._cors_preflight()

    # ── Helpers ──

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
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Key")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors_preflight(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Key")
        self.end_headers()
