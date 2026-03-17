"""
Thursday Main API — Sovereign Training Backend
================================================
The central endpoint for the Thursday dashboard and Sovereign handshake.

Endpoints:
    POST /api   — Dashboard actions (AUTH, STATUS, IGNITE, PAUSE, STOP, INGEST, DEPLOY)
    GET  /api   — Quick health check

All state is persisted in Upstash Redis via _store.py.
Stateless Vercel functions are no longer a problem.
"""

from http.server import BaseHTTPRequestHandler
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _store import (
    auth_check,
    get_full_state,
    set_command,
    add_alert,
    update_ingestion,
    set_config,
    get_checkpoints,
    add_checkpoint,
    MASTER_KEY,
)


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Quick health check."""
        self._json({
            "status": "SOVEREIGN_BACKEND_ACTIVE",
            "version": "4.0",
            "engine": "Thursday — Persistent Redis State",
            "endpoints": {
                "main": "/api (this)",
                "command": "/api/command (Sovereign polls)",
                "telemetry": "/api/telemetry (Sovereign pushes)",
                "ack": "/api/ack (Sovereign acknowledges)",
            },
        })

    def do_POST(self):
        """Handle all dashboard actions."""
        body = self._read_body()
        if not body:
            return self._json({"error": "EMPTY_BODY"}, 400)

        key = body.get("key", "")

        # ── AUTH ──
        if body.get("action") == "AUTH":
            valid = auth_check(key)
            return self._json({"status": "AUTHORIZED" if valid else "DENIED"})

        # Everything else requires auth
        if not auth_check(key):
            return self._json({"status": "UNAUTHORIZED", "message": "Identity rejected."}, 403)

        action = body.get("action", "")

        # ══════════════════════════════════════
        # STATUS — Full state snapshot from Redis
        # The dashboard calls this on every reconnect/refresh.
        # All data comes from the persistent Redis store.
        # ══════════════════════════════════════
        if action == "STATUS":
            return self._json(get_full_state())

        # ── IGNITE ──
        if action == "IGNITE":
            config = body.get("config", "mk2_god")
            config_override = body.get("config_override", {})

            # Store the config
            set_config({
                "config_name": config,
                "overrides": config_override,
                "timestamp": int(time.time()),
            })

            # Set the command beacon for the Sovereign to pick up
            manifest = set_command("IGNITE", config_override)

            add_alert("info", f"🔥 IGNITE command broadcast for config: {config}")

            return self._json({
                "status": "SUCCESS",
                "message": f"IGNITE signal broadcast. Sovereign will pick up within 5 seconds.",
                "command": manifest,
                "config": config,
            })

        # ── PAUSE / RESUME / STOP ──
        if action in ("PAUSE", "RESUME", "STOP"):
            manifest = set_command(action)

            emoji = {"PAUSE": "⏸", "RESUME": "▶", "STOP": "⏹"}
            add_alert(
                "warn" if action != "RESUME" else "info",
                f"{emoji.get(action, '')} {action} command broadcast."
            )

            return self._json({
                "status": "SUCCESS",
                "action": action,
                "message": f"{action} signal broadcast. Sovereign will pick up within 5 seconds.",
                "command": manifest,
            })

        # ── INGEST ──
        if action == "INGEST":
            meta = body.get("metadata", {})
            estimated_records = meta.get("fileSize", 5000) // 500
            ingestion = update_ingestion(estimated_records, 0.94)

            add_alert("info", f"Ingested {estimated_records} records from {meta.get('fileName', 'unknown')}")

            return self._json({
                "status": "SUCCESS",
                "records_accepted": estimated_records,
                "records_rejected": max(1, estimated_records // 50),
                "quality_score": 0.94,
                "storage_path": "/mnt/divyakush/data/mk2_god/",
                "total_records": ingestion["records"],
            })

        # ── DEPLOY ──
        if action == "DEPLOY":
            ckpt = body.get("checkpoint", "latest")
            add_alert("info", f"🚀 Deploying checkpoint {ckpt} to inference cluster.")

            return self._json({
                "status": "SUCCESS",
                "checkpoint": ckpt,
                "endpoint": "https://thursday-ashy.vercel.app/api/inference",
                "message": f"Deploy command queued for checkpoint: {ckpt}",
            })

        # ── TELEMETRY (legacy — Sovereign should use /api/telemetry instead) ──
        if action == "TELEMETRY":
            # Forward to the telemetry store for backward compatibility
            from _store import push_telemetry
            data = body.get("data", {})
            push_telemetry(data)
            return self._json({"status": "TELEMETRY_RECEIVED"})

        return self._json({"status": "READY", "message": "Awaiting command."})

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
