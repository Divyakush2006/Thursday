"""
Local dev server for Thursday dashboard.
Serves index.html + handles /api POST endpoint.
Usage: python dev_server.py
"""
import http.server
import json
import hashlib
import time
import os

PORT = 3000
MASTER_KEY = os.environ.get("OMEGA_99", "PROJECT_DIVYAKUSH_OMEGA_99")

_state = {
    "training_state": "idle",
    "job_id": None, "config": None, "start_time": None,
    "current_step": 0, "total_steps": 0,
    "latest_loss": None, "latest_lr": None, "latest_grad_norm": None,
    "gpus_allocated": 0,
    "loss_history": [], "checkpoints": [], "alerts": [],
    "ingested_records": 0, "ingested_quality": 0,
}

def _add_alert(sev, msg):
    _state["alerts"].append({"severity": sev, "message": msg, "timestamp": time.time()})
    if len(_state["alerts"]) > 100: _state["alerts"] = _state["alerts"][-100:]

class Handler(http.server.SimpleHTTPRequestHandler):

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        key = body.get("key", "")

        if body.get("action") == "AUTH":
            valid = hashlib.sha256(key.encode()).hexdigest() == hashlib.sha256(MASTER_KEY.encode()).hexdigest()
            return self._json({"status": "AUTHORIZED" if valid else "DENIED"})

        if key != MASTER_KEY:
            return self._json({"status": "UNAUTHORIZED"}, 403)

        action = body.get("action", "")

        if action == "STATUS":
            return self._json({
                "status": "SUCCESS", "online": True,
                "total_gpus": 128, "training_gpus": 120, "orchestrator_gpus": 8, "hot_spare_gpus": 16,
                "avg_gpu_utilization": 12.4, "avg_gpu_temperature": 42, "avg_gpu_memory_pct": 8.2,
                "ib_throughput_gbps": 0, "node_count": 15,
                "storage_used_tb": 12.4, "storage_total_tb": 100,
                "training_state": _state["training_state"],
                "job_id": _state["job_id"], "config": _state["config"],
                "start_time": _state["start_time"],
                "current_step": _state["current_step"], "total_steps": _state["total_steps"],
                "latest_loss": _state["latest_loss"], "latest_lr": _state["latest_lr"],
                "latest_grad_norm": _state["latest_grad_norm"],
                "gpus_allocated": _state["gpus_allocated"],
                "loss_history": _state["loss_history"][-200:],
                "checkpoints": _state["checkpoints"],
                "alerts": _state["alerts"][-50:],
                "ingested_records": _state["ingested_records"],
                "ingested_quality": _state["ingested_quality"],
            })

        if action == "INGEST":
            meta = body.get("metadata", {})
            recs = meta.get("fileSize", 5000) // 500
            _state["ingested_records"] += recs
            _state["ingested_quality"] = 0.94
            _add_alert("info", f"Ingested {recs} records")
            return self._json({"status": "SUCCESS", "records_accepted": recs, "total_records": _state["ingested_records"]})

        if action == "IGNITE":
            cfg = body.get("config", "mk2_god")
            jid = f"MK2-GOD-{cfg.upper()}-{int(time.time()) % 10000:04d}"
            _state.update({
                "training_state": "training", "job_id": jid, "config": cfg,
                "start_time": time.time(), "current_step": 0,
                "total_steps": 50000 if cfg == "mk2_god" else 5000,
                "gpus_allocated": 120 if cfg == "mk2_god" else 8,
                "loss_history": [], "checkpoints": [],
            })
            _add_alert("info", f"Training ignited: {cfg} on {_state['gpus_allocated']} GPUs (job: {jid})")
            return self._json({"status": "SUCCESS", "job_id": jid, "gpus_allocated": _state["gpus_allocated"]})

        if action in ("PAUSE", "RESUME", "STOP"):
            _state["training_state"] = {"PAUSE": "paused", "RESUME": "training", "STOP": "idle"}[action]
            _add_alert("warn", f"Training {action.lower()}d.")
            return self._json({"status": "SUCCESS", "training_state": _state["training_state"]})

        if action == "DEPLOY":
            return self._json({"status": "SUCCESS", "checkpoint": body.get("checkpoint", "latest")})

        return self._json({"status": "READY"})

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"\n  🚀 Thursday Dashboard running at http://localhost:{PORT}\n")
    print(f"  Password: {MASTER_KEY}\n")
    http.server.HTTPServer(("", PORT), Handler).serve_forever()
