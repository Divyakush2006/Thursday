"""
Thursday Sovereign State Store — Upstash Redis REST Client
==========================================================
Zero-dependency persistent state using Upstash Redis REST API.
Every key survives cold starts, page refreshes, and session resets.

Redis Keys:
    thursday:command           — Current command for Sovereign to poll
    thursday:cluster:status    — Cluster state string
    thursday:telemetry:latest  — Latest telemetry snapshot (JSON)
    thursday:telemetry:history — Array of historical telemetry (capped at 500)
    thursday:checkpoints       — Array of checkpoint records
    thursday:alerts            — Array of alert records (capped at 100)
    thursday:config            — Active training config (JSON)
    thursday:ingestion         — Data ingestion stats (JSON)
    thursday:heartbeat         — Last Sovereign heartbeat timestamp
"""

import json
import os
import time
import urllib.request
import urllib.error

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
MASTER_KEY = os.environ.get("OMEGA_99", "PROJECT_DIVYAKUSH_OMEGA_99")

# Max entries for capped collections
MAX_TELEMETRY_HISTORY = 500
MAX_ALERTS = 100
MAX_CHECKPOINTS = 50


# ═══════════════════════════════════════
# REDIS REST CLIENT (zero dependencies)
# ═══════════════════════════════════════

def _redis_cmd(*args):
    """Execute a Redis command via Upstash REST API."""
    if not REDIS_URL or not REDIS_TOKEN:
        return None

    url = REDIS_URL
    # Build the REST path: /command/arg1/arg2/...
    # But for complex values, use POST with body
    payload = json.dumps(list(args)).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {REDIS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result")
    except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
        print(f"[STORE] Redis error: {e}")
        return None


# ═══════════════════════════════════════
# KEY OPERATIONS
# ═══════════════════════════════════════

def get_raw(key):
    """Get a raw string value."""
    return _redis_cmd("GET", key)


def set_raw(key, value, ttl=None):
    """Set a raw string value, optionally with TTL in seconds."""
    if ttl:
        return _redis_cmd("SET", key, value, "EX", str(ttl))
    return _redis_cmd("SET", key, value)


def get_json(key):
    """Get and parse a JSON value."""
    raw = get_raw(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def set_json(key, obj, ttl=None):
    """Serialize an object to JSON and store it."""
    return set_raw(key, json.dumps(obj), ttl)


# ═══════════════════════════════════════
# DOMAIN OPERATIONS
# ═══════════════════════════════════════

def auth_check(key):
    """Validate the master key."""
    return key == MASTER_KEY


# ── COMMANDS ──

def get_command():
    """Get the current command manifest for the Sovereign."""
    data = get_json("thursday:command")
    if not data:
        return {
            "command": "IDLE",
            "timestamp": 0,
            "config_override": {},
        }
    return data


def set_command(command, config_override=None):
    """Set a command for the Sovereign to pick up."""
    manifest = {
        "command": command.upper(),
        "timestamp": int(time.time()),
        "config_override": config_override or {},
    }
    set_json("thursday:command", manifest)
    # Also update cluster status
    status_map = {
        "IGNITE": "PROVISIONING",
        "PAUSE": "PAUSED",
        "RESUME": "TRAINING",
        "STOP": "IDLE",
    }
    if command.upper() in status_map:
        set_raw("thursday:cluster:status", status_map[command.upper()])
    return manifest


def clear_command():
    """Reset command to IDLE after Sovereign acknowledges."""
    return set_command("IDLE")


# ── TELEMETRY ──

def push_telemetry(data):
    """Store incoming telemetry from the Sovereign."""
    # Store latest snapshot
    set_json("thursday:telemetry:latest", data)

    # Append to history (capped)
    history = get_json("thursday:telemetry:history") or []
    history.append({
        "step": data.get("step", 0),
        "loss": data.get("loss", 0),
        "lr": data.get("lr", 0),
        "gnorm": data.get("gnorm", 0),
        "tflops": data.get("tflops", 0),
        "gpu_util": data.get("gpu_util", 0),
        "tok_per_sec": data.get("tok_per_sec", 0),
        "ts": int(time.time()),
    })
    # Cap at MAX entries
    if len(history) > MAX_TELEMETRY_HISTORY:
        history = history[-MAX_TELEMETRY_HISTORY:]
    set_json("thursday:telemetry:history", history)

    # Update cluster status
    status = data.get("status", "TRAINING_ACTIVE")
    set_raw("thursday:cluster:status", status)

    # Record heartbeat
    set_raw("thursday:heartbeat", str(int(time.time())))

    # Auto-checkpoint every 500 steps
    step = data.get("step", 0)
    if step > 0 and step % 500 == 0:
        add_checkpoint(step, data.get("loss", 0))

    # Forward any alerts
    alerts = data.get("alerts", [])
    for alert_msg in alerts:
        add_alert("warn", alert_msg)


def get_latest_telemetry():
    """Get the most recent telemetry snapshot."""
    return get_json("thursday:telemetry:latest")


def get_telemetry_history():
    """Get telemetry history for charting."""
    return get_json("thursday:telemetry:history") or []


# ── CHECKPOINTS ──

def add_checkpoint(step, loss, path=None):
    """Record a checkpoint."""
    checkpoints = get_json("thursday:checkpoints") or []
    ckpt = {
        "step": step,
        "loss": round(loss, 4) if isinstance(loss, float) else loss,
        "timestamp": int(time.time()),
        "path": path or f"/mnt/divyakush/checkpoints/MK2-God/step-{step}/",
    }
    checkpoints.append(ckpt)
    if len(checkpoints) > MAX_CHECKPOINTS:
        checkpoints = checkpoints[-MAX_CHECKPOINTS:]
    set_json("thursday:checkpoints", checkpoints)
    set_raw("thursday:checkpoint:latest", ckpt["path"])
    return ckpt


def get_checkpoints():
    """Get all recorded checkpoints."""
    return get_json("thursday:checkpoints") or []


# ── ALERTS ──

def add_alert(severity, message):
    """Add an alert to the persistent store."""
    alerts = get_json("thursday:alerts") or []
    alerts.append({
        "severity": severity,
        "message": message,
        "timestamp": int(time.time()),
    })
    if len(alerts) > MAX_ALERTS:
        alerts = alerts[-MAX_ALERTS:]
    set_json("thursday:alerts", alerts)


def get_alerts():
    """Get all alerts."""
    return get_json("thursday:alerts") or []


# ── CONFIG ──

def set_config(config):
    """Store the active training config."""
    set_json("thursday:config", config)


def get_config():
    """Get the active training config."""
    return get_json("thursday:config")


# ── INGESTION ──

def update_ingestion(records, quality):
    """Update data ingestion stats."""
    current = get_json("thursday:ingestion") or {"records": 0, "quality": 0}
    current["records"] = current.get("records", 0) + records
    current["quality"] = quality
    set_json("thursday:ingestion", current)
    return current


def get_ingestion():
    """Get data ingestion stats."""
    return get_json("thursday:ingestion") or {"records": 0, "quality": 0}


# ── HEARTBEAT ──

def get_heartbeat():
    """Get the last Sovereign heartbeat timestamp."""
    raw = get_raw("thursday:heartbeat")
    return int(raw) if raw else 0


# ═══════════════════════════════════════
# FULL STATE SNAPSHOT (for dashboard reconnection)
# ═══════════════════════════════════════

def get_full_state():
    """
    Build the complete state snapshot for dashboard restoration.
    Called when the dashboard reconnects after a refresh or re-login.
    """
    telemetry = get_latest_telemetry() or {}
    command = get_command()
    cluster_status = get_raw("thursday:cluster:status") or "IDLE"
    ingestion = get_ingestion()
    heartbeat = get_heartbeat()

    # Determine if Sovereign is reachable (heartbeat within last 60s)
    sovereign_alive = (int(time.time()) - heartbeat) < 60 if heartbeat else False

    return {
        "status": "SUCCESS",
        "online": sovereign_alive or cluster_status != "IDLE",
        # Cluster hardware
        "total_gpus": 128,
        "training_gpus": telemetry.get("active_gpus", 120),
        "orchestrator_gpus": 8,
        "hot_spare_gpus": 16,
        "avg_gpu_utilization": telemetry.get("gpu_util", 0),
        "avg_gpu_temperature": telemetry.get("gpu_temp", 0),
        "avg_gpu_memory_pct": (telemetry.get("vram_gb", 0) / 9600 * 100)
            if telemetry.get("vram_gb") else 0,
        "ib_throughput_gbps": telemetry.get("ib_gbps", 0),
        "node_count": telemetry.get("active_nodes", 15),
        "storage_used_tb": 12.4,
        "storage_total_tb": 100,
        # Training state
        "training_state": _map_cluster_to_training_state(cluster_status),
        "job_id": telemetry.get("job_id"),
        "config": (get_config() or {}).get("config_name"),
        "current_step": telemetry.get("step", 0),
        "total_steps": telemetry.get("total_steps", 0),
        "latest_loss": telemetry.get("loss"),
        "latest_lr": telemetry.get("lr"),
        "latest_grad_norm": telemetry.get("gnorm"),
        "gpus_allocated": telemetry.get("active_gpus", 0),
        # History for charts
        "loss_history": get_telemetry_history()[-200:],
        "checkpoints": get_checkpoints(),
        "alerts": get_alerts()[-50:],
        # Ingestion
        "ingested_records": ingestion.get("records", 0),
        "ingested_quality": ingestion.get("quality", 0),
        # Sovereign health
        "sovereign_heartbeat": heartbeat,
        "sovereign_alive": sovereign_alive,
        # Current command
        "pending_command": command.get("command", "IDLE"),
    }


def _map_cluster_to_training_state(status):
    """Map cluster status strings to dashboard training states."""
    mapping = {
        "IDLE": "idle",
        "PROVISIONING": "preparing",
        "TRAINING_ACTIVE": "training",
        "TRAINING": "training",
        "PAUSED": "paused",
        "CRASH_PAUSED": "failed",
        "COMPLETED": "completed",
    }
    return mapping.get(status, "idle")
