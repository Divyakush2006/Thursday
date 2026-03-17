"""
Thursday Command Endpoint
=========================
GET  /api/command  — Sovereign polls this every 5s for pending commands
POST /api/command  — Dashboard writes commands (IGNITE, PAUSE, STOP)
"""

from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _store import auth_check, get_command, set_command, add_alert, MASTER_KEY


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        """
        Sovereign polls this every 5 seconds.
        Returns the current command manifest.
        Requires OMEGA_99 key in X-Auth-Key header or ?key= query param.
        """
        key = self._get_auth_key()
        if not auth_check(key):
            return self._json({"error": "UNAUTHORIZED"}, 403)

        command = get_command()
        self._json({
            "status": "OK",
            "key": MASTER_KEY,
            **command,
        })

    def do_POST(self):
        """
        Dashboard sends commands here.
        Body: { "key": "...", "command": "IGNITE", "config_override": {} }
        """
        body = self._read_body()
        if not body:
            return self._json({"error": "EMPTY_BODY"}, 400)

        if not auth_check(body.get("key", "")):
            return self._json({"error": "UNAUTHORIZED"}, 403)

        command = body.get("command", "").upper()
        valid_commands = {"IGNITE", "PAUSE", "RESUME", "STOP", "IDLE"}

        if command not in valid_commands:
            return self._json({
                "error": "INVALID_COMMAND",
                "valid": list(valid_commands),
            }, 400)

        config_override = body.get("config_override", {})
        manifest = set_command(command, config_override)

        # Log the command as an alert
        if command != "IDLE":
            add_alert("info", f"Command issued: {command}")

        self._json({
            "status": "SIGNAL_BROADCASTED",
            "command": command,
            "timestamp": manifest["timestamp"],
            "message": f"Command '{command}' stored. Sovereign will pick up within 5 seconds.",
        })

    def do_OPTIONS(self):
        self._cors_preflight()

    # ── Helpers ──

    def _get_auth_key(self):
        """Extract auth key from header or query param."""
        # Check header first
        key = self.headers.get("X-Auth-Key", "")
        if key:
            return key
        # Check query param
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
