from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import os
import json
import hmac
from datetime import datetime, timezone

app = FastAPI(title="Sandbox Skill Runner")

RUNNER_NAME = os.getenv("RUNNER_NAME", "runner")
API_TOKEN = os.getenv("RUNNER_API_TOKEN", "")
POLICY_PATH = os.getenv("RUNNER_POLICY", "/app/policy.json")
MAX_BODY_BYTES = int(os.getenv("RUNNER_MAX_BODY_BYTES", "65536"))  # 64KB


class RunRequest(BaseModel):
    skill: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=120)
    payload: Dict[str, Any] = Field(default_factory=dict)


@app.middleware("http")
async def size_guard(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
        return JSONResponse({"ok": False, "error": "payload_too_large"}, status_code=413)
    return await call_next(request)


def _safe_token_match(given: Optional[str]) -> bool:
    if not API_TOKEN:
        return False
    if given is None:
        return False
    return hmac.compare_digest(given, API_TOKEN)


def read_policy() -> Dict[str, Any]:
    try:
        with open(POLICY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"allowedSkills": [], "actions": {}}


def audit(event: Dict[str, Any]) -> None:
    # stdout only; container logs are the audit trail
    print(json.dumps(event, ensure_ascii=False), flush=True)


@app.get("/health")
def health():
    return {
        "ok": True,
        "runner": RUNNER_NAME,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/run")
def run(req: RunRequest, x_runner_token: Optional[str] = Header(default=None)):
    now = datetime.now(timezone.utc).isoformat()

    if not _safe_token_match(x_runner_token):
        audit({"ts": now, "runner": RUNNER_NAME, "event": "deny", "reason": "unauthorized"})
        return {"ok": False, "error": "unauthorized"}

    policy = read_policy()
    allowed = set(policy.get("allowedSkills", []))
    actions = policy.get("actions", {})

    if req.skill not in allowed:
        audit({"ts": now, "runner": RUNNER_NAME, "event": "deny", "reason": "skill_not_allowed", "skill": req.skill})
        return {"ok": False, "error": "skill_not_allowed", "skill": req.skill}

    skill_actions = actions.get(req.skill, {})
    action_cfg = skill_actions.get(req.action)
    if not action_cfg:
        audit({"ts": now, "runner": RUNNER_NAME, "event": "deny", "reason": "action_not_allowed", "skill": req.skill, "action": req.action})
        return {"ok": False, "error": "action_not_allowed", "skill": req.skill, "action": req.action}

    # Secure default: explicit allowlist only, no shell execution fallback.
    # You can add concrete safe handlers here later.
    audit({
        "ts": now,
        "runner": RUNNER_NAME,
        "event": "allowed_stub",
        "skill": req.skill,
        "action": req.action,
        "payload_keys": sorted(list(req.payload.keys())),
    })

    return {
        "ok": True,
        "runner": RUNNER_NAME,
        "skill": req.skill,
        "action": req.action,
        "mode": "secure-stub",
        "note": "Action is allowlisted and authenticated. Concrete handler not wired yet.",
    }
