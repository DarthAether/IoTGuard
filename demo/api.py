"""
IoTGuard - Demo API
Lightweight demo version that runs without Gemini API or MQTT dependencies.
Command risk analysis uses deterministic rule-based logic instead of LLM inference.
"""

import base64
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Path, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="IoTGuard - Demo",
    description="AI-powered IoT command safety system (demo mode — rule-based analysis)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

START_TIME = time.time()


@app.middleware("http")
async def add_demo_header(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Demo-Mode"] = "true"
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    command: str = Field(..., description="Natural-language IoT command to analyze")
    device_id: str = Field(..., description="Target device identifier")
    user_role: str = Field("user", description="Role of the requesting user")


class CommandRequest(BaseModel):
    command: str = Field(..., description="Command to execute on device")


class AuthRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEVICES = {
    "door_lock_1": {
        "device_id": "door_lock_1",
        "name": "Front Door Lock",
        "type": "smart_lock",
        "location": "Main Entrance",
        "manufacturer": "August",
        "firmware": "3.2.1",
        "state": {"locked": True, "battery_pct": 84},
        "online": True,
    },
    "camera_1": {
        "device_id": "camera_1",
        "name": "Living Room Camera",
        "type": "security_camera",
        "location": "Living Room",
        "manufacturer": "Ring",
        "firmware": "5.1.0",
        "state": {"recording": True, "night_vision": True, "motion_detection": True},
        "online": True,
    },
    "speaker_1": {
        "device_id": "speaker_1",
        "name": "Kitchen Speaker",
        "type": "smart_speaker",
        "location": "Kitchen",
        "manufacturer": "Amazon Echo",
        "firmware": "7.4.2",
        "state": {"volume": 40, "playing": False, "do_not_disturb": False},
        "online": True,
    },
    "thermostat_1": {
        "device_id": "thermostat_1",
        "name": "HVAC Thermostat",
        "type": "thermostat",
        "location": "Hallway",
        "manufacturer": "Nest",
        "firmware": "6.0.3",
        "state": {"temperature_set": 72, "current_temp": 71, "mode": "auto", "fan": "auto"},
        "online": True,
    },
    "light_1": {
        "device_id": "light_1",
        "name": "Bedroom Lights",
        "type": "smart_light",
        "location": "Master Bedroom",
        "manufacturer": "Philips Hue",
        "firmware": "1.88.1",
        "state": {"on": False, "brightness": 80, "color_temp": 3500},
        "online": True,
    },
}

SECURITY_RULES = [
    {
        "rule_id": "R001",
        "name": "Block remote unlock without MFA",
        "description": "Prevent door/lock unlock commands unless multi-factor authentication is verified",
        "severity": "CRITICAL",
        "enabled": True,
    },
    {
        "rule_id": "R002",
        "name": "Prevent camera disable",
        "description": "Block commands that disable security cameras during non-maintenance windows",
        "severity": "HIGH",
        "enabled": True,
    },
    {
        "rule_id": "R003",
        "name": "Factory reset protection",
        "description": "Require admin approval for factory reset or firmware rollback commands",
        "severity": "CRITICAL",
        "enabled": True,
    },
    {
        "rule_id": "R004",
        "name": "Temperature range guard",
        "description": "Reject thermostat settings outside the 55-85 F safe range",
        "severity": "MEDIUM",
        "enabled": True,
    },
    {
        "rule_id": "R005",
        "name": "Night-mode light policy",
        "description": "Limit light brightness to 30 % between 11 PM and 6 AM",
        "severity": "LOW",
        "enabled": True,
    },
    {
        "rule_id": "R006",
        "name": "Bulk command rate limit",
        "description": "Rate-limit batch commands to prevent denial-of-service on the IoT mesh",
        "severity": "MEDIUM",
        "enabled": True,
    },
]


# ---------------------------------------------------------------------------
# Rule-based risk analysis
# ---------------------------------------------------------------------------

RISK_RULES: list[tuple[re.Pattern, str, str, list[str]]] = [
    # (pattern, risk_level, explanation, safe_alternatives)
    (
        re.compile(r"\b(factory\s*reset|hard\s*reset|wipe|erase\s*all|format)\b", re.I),
        "CRITICAL",
        "This command would perform an irreversible factory reset, erasing all device configuration and user data.",
        ["Back up device settings first", "Schedule reset during maintenance window with admin approval"],
    ),
    (
        re.compile(r"\b(disable|deactivate|turn\s*off)\b.*\b(camera|alarm|security|sensor|motion\s*detect)", re.I),
        "CRITICAL",
        "Disabling a security device removes a layer of physical protection and may violate safety policies.",
        ["Temporarily pause notifications instead", "Set a maintenance window with auto-reenable"],
    ),
    (
        re.compile(r"\b(delete|remove|drop|purge)\b", re.I),
        "CRITICAL",
        "Deletion commands can permanently remove device data, recordings, or configuration profiles.",
        ["Archive data before deletion", "Use soft-delete if available"],
    ),
    (
        re.compile(r"\b(unlock|open)\b", re.I),
        "HIGH",
        "Unlocking or opening an entry point remotely carries physical security risk if the requester's identity is not fully verified.",
        ["Require multi-factor authentication before unlock", "Use a time-limited unlock with auto-relock"],
    ),
    (
        re.compile(r"\b(disable|deactivate|turn\s*off)\b", re.I),
        "HIGH",
        "Disabling a device may leave gaps in automation or security monitoring.",
        ["Use a scheduled downtime instead", "Confirm with household members before disabling"],
    ),
    (
        re.compile(r"\b(lock|close|arm|engage)\b", re.I),
        "NONE",
        "Locking and arming commands improve physical security and are considered safe.",
        [],
    ),
    (
        re.compile(r"\b(turn\s*on|switch\s*on|enable|activate)\b", re.I),
        "LOW",
        "Turning on a device is generally safe, but may increase energy usage or trigger connected automations.",
        [],
    ),
    (
        re.compile(r"\b(turn\s*off|switch\s*off)\b.*\b(light|lamp|bulb)\b", re.I),
        "NONE",
        "Turning off lights is a routine, safe operation.",
        [],
    ),
    (
        re.compile(r"\b(set|change|adjust|update)\b.*\b(temperature|thermostat|temp)\b", re.I),
        "LOW",
        "Adjusting temperature is generally safe within normal ranges. Extreme values may cause discomfort or HVAC strain.",
        ["Keep settings within the 55-85 F recommended range"],
    ),
    (
        re.compile(r"\b(turn\s*off|switch\s*off)\b", re.I),
        "LOW",
        "Turning off a non-security device is generally low risk.",
        [],
    ),
]

DEFAULT_ANALYSIS = (
    "MEDIUM",
    "This command could not be fully classified by the rule engine. Manual review is recommended.",
    ["Review device documentation", "Test in a safe environment first"],
)


def _analyze_command(command: str, device_id: str) -> dict:
    cmd_lower = command.lower().strip()

    risk_level, explanation, alternatives = DEFAULT_ANALYSIS
    matched_rules: list[str] = []

    for pattern, level, expl, alts in RISK_RULES:
        if pattern.search(cmd_lower):
            risk_level = level
            explanation = expl
            alternatives = alts
            break

    # Check which security rules would fire
    for rule in SECURITY_RULES:
        if risk_level in ("CRITICAL", "HIGH") and rule["severity"] in ("CRITICAL", "HIGH") and rule["enabled"]:
            matched_rules.append(rule["rule_id"])

    blocked = risk_level in ("CRITICAL", "HIGH")

    return {
        "analysis_id": str(uuid.uuid4()),
        "command": command,
        "device_id": device_id,
        "risk_level": risk_level,
        "risk_score": {"NONE": 0.0, "LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.8, "CRITICAL": 1.0}[risk_level],
        "explanation": explanation,
        "safe_alternatives": alternatives,
        "triggered_rules": matched_rules,
        "blocked": blocked,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine": "rule-based-v1 (demo)",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(username: str) -> str:
    payload = f'{{"sub":"{username}","mode":"demo","iat":{int(time.time())}}}'
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "IoTGuard",
        "version": "1.0.0",
        "status": "running",
        "mode": "demo",
        "docs_url": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "mode": "demo",
    }


@app.post("/api/v1/analyze")
async def analyze(req: AnalyzeRequest):
    if req.device_id not in DEVICES:
        raise HTTPException(status_code=404, detail=f"Device '{req.device_id}' not found. Available: {list(DEVICES.keys())}")
    return _analyze_command(req.command, req.device_id)


@app.post("/api/v1/analyze-and-execute")
async def analyze_and_execute(req: AnalyzeRequest):
    if req.device_id not in DEVICES:
        raise HTTPException(status_code=404, detail=f"Device '{req.device_id}' not found. Available: {list(DEVICES.keys())}")

    analysis = _analyze_command(req.command, req.device_id)

    if analysis["blocked"]:
        execution = {
            "executed": False,
            "reason": f"Command blocked — risk level {analysis['risk_level']}",
            "device_state": DEVICES[req.device_id]["state"],
        }
    else:
        execution = {
            "executed": True,
            "reason": "Command passed safety checks",
            "device_state": DEVICES[req.device_id]["state"],
            "execution_ms": round(random.uniform(50, 200), 1),
        }

    return {**analysis, "execution": execution}


@app.get("/api/v1/devices")
async def list_devices():
    return {"devices": list(DEVICES.values()), "total": len(DEVICES)}


@app.post("/api/v1/devices/{device_id}/command")
async def execute_command(device_id: str = Path(...), body: CommandRequest = ...):
    if device_id not in DEVICES:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    device = DEVICES[device_id]
    # Simulate state change
    new_state = dict(device["state"])
    cmd = body.command.lower()
    if "lock" in cmd and "unlock" not in cmd:
        new_state["locked"] = True
    elif "unlock" in cmd or "open" in cmd:
        new_state["locked"] = False
    elif "turn on" in cmd or "switch on" in cmd:
        if "on" in new_state:
            new_state["on"] = True
    elif "turn off" in cmd or "switch off" in cmd:
        if "on" in new_state:
            new_state["on"] = False

    return {
        "device_id": device_id,
        "command": body.command,
        "previous_state": device["state"],
        "new_state": new_state,
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/rules")
async def list_rules():
    return {"rules": SECURITY_RULES, "total": len(SECURITY_RULES)}


@app.get("/api/v1/analytics/dashboard")
async def dashboard():
    total = random.randint(500, 2000)
    blocked = random.randint(20, 80)
    return {
        "period": "last_24h",
        "commands_analyzed": total,
        "commands_blocked": blocked,
        "block_rate_pct": round(blocked / total * 100, 1),
        "risk_distribution": {
            "NONE": random.randint(150, 400),
            "LOW": random.randint(200, 600),
            "MEDIUM": random.randint(80, 250),
            "HIGH": random.randint(30, 90),
            "CRITICAL": random.randint(5, 25),
        },
        "top_blocked_devices": [
            {"device_id": "door_lock_1", "blocked_count": random.randint(8, 30)},
            {"device_id": "camera_1", "blocked_count": random.randint(5, 15)},
        ],
        "active_rules": sum(1 for r in SECURITY_RULES if r["enabled"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/auth/token")
async def auth_token(req: AuthRequest):
    return {
        "access_token": _make_token(req.username),
        "token_type": "bearer",
        "expires_in": 3600,
        "mode": "demo",
        "note": "Demo mode — any credentials are accepted",
    }
