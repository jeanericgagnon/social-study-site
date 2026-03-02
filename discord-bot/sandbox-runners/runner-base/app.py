from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import os
import json
import hmac
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import re

app = FastAPI(title="Sandbox Skill Runner")

RUNNER_NAME = os.getenv("RUNNER_NAME", "runner")
API_TOKEN = os.getenv("RUNNER_API_TOKEN", "")
POLICY_PATH = os.getenv("RUNNER_POLICY", "/app/policy.json")
MAX_BODY_BYTES = int(os.getenv("RUNNER_MAX_BODY_BYTES", "65536"))  # 64KB
RATE_LIMIT_PER_MIN = int(os.getenv("RUNNER_RATE_LIMIT_PER_MIN", "120"))

# very small local-only rate limiter
_RATE = {"window": int(time.time() // 60), "count": 0}


class RunRequest(BaseModel):
    skill: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=120)
    payload: Dict[str, Any] = Field(default_factory=dict)


@app.middleware("http")
async def guards(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
        return JSONResponse({"ok": False, "error": "payload_too_large"}, status_code=413)

    if request.method == "POST" and request.url.path == "/run":
        ctype = request.headers.get("content-type", "")
        if "application/json" not in ctype:
            return JSONResponse({"ok": False, "error": "invalid_content_type"}, status_code=415)

        minute = int(time.time() // 60)
        if _RATE["window"] != minute:
            _RATE["window"] = minute
            _RATE["count"] = 0
        _RATE["count"] += 1
        if _RATE["count"] > RATE_LIMIT_PER_MIN:
            return JSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)

    return await call_next(request)


def _safe_token_match(given: Optional[str]) -> bool:
    if not API_TOKEN or given is None:
        return False
    return hmac.compare_digest(given, API_TOKEN)


def read_policy() -> Dict[str, Any]:
    try:
        with open(POLICY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"allowedSkills": [], "actions": {}}


def audit(event: Dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _domain_ok(url: str, allowed_domains: list[str]) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return any(host == d or host.endswith(f".{d}") for d in allowed_domains)
    except Exception:
        return False


def _payload_policy_ok(req: RunRequest, action_cfg: Dict[str, Any]) -> tuple[bool, str]:
    payload = req.payload or {}

    if action_cfg.get("requireUrl"):
        url = payload.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return False, "invalid_url"
        allowed_domains = action_cfg.get("allowedDomains", [])
        if allowed_domains and not _domain_ok(url, allowed_domains):
            return False, "domain_not_allowed"

    if action_cfg.get("requireTo"):
        to = payload.get("to")
        if not isinstance(to, str) or "@" not in to:
            return False, "invalid_recipient"
        allowed_domains = action_cfg.get("allowedRecipientDomains", [])
        if allowed_domains:
            domain = to.split("@")[-1].lower()
            if domain not in [d.lower() for d in allowed_domains]:
                return False, "recipient_domain_not_allowed"

    required_fields = action_cfg.get("requiredFields", [])
    for f in required_fields:
        if f not in payload:
            return False, f"missing_field:{f}"

    max_payload_keys = int(action_cfg.get("maxPayloadKeys", 20))
    if len(payload.keys()) > max_payload_keys:
        return False, "too_many_payload_keys"

    return True, "ok"


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()[:200]


def _handle_playwright_smoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = payload.get("url", "")
    timeout_s = int(payload.get("timeoutSec", 10))
    timeout_s = max(2, min(timeout_s, 20))

    req = Request(
        url,
        headers={
            "User-Agent": "SandboxRunner/1.0 (+playwright-mcp-smoke)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urlopen(req, timeout=timeout_s) as resp:
            body_bytes = resp.read(16384)
            content_type = resp.headers.get("Content-Type", "")
            status = getattr(resp, "status", 200)
            final_url = resp.geturl()
            html = body_bytes.decode("utf-8", errors="ignore")
            title = _extract_title(html)
            return {
                "ok": True,
                "mode": "real-handler",
                "status": int(status),
                "finalUrl": final_url,
                "contentType": content_type,
                "title": title,
                "bytesRead": len(body_bytes),
            }
    except HTTPError as e:
        return {"ok": False, "mode": "real-handler", "error": "http_error", "status": int(e.code)}
    except URLError as e:
        return {"ok": False, "mode": "real-handler", "error": "network_error", "detail": str(e.reason)}
    except Exception:
        return {"ok": False, "mode": "real-handler", "error": "smoke_failed"}


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
    if not action_cfg or not action_cfg.get("enabled", False):
        audit({"ts": now, "runner": RUNNER_NAME, "event": "deny", "reason": "action_not_allowed", "skill": req.skill, "action": req.action})
        return {"ok": False, "error": "action_not_allowed", "skill": req.skill, "action": req.action}

    ok, reason = _payload_policy_ok(req, action_cfg)
    if not ok:
        audit({"ts": now, "runner": RUNNER_NAME, "event": "deny", "reason": reason, "skill": req.skill, "action": req.action})
        return {"ok": False, "error": reason, "skill": req.skill, "action": req.action}

    if req.skill == "playwright-mcp" and req.action == "smoke":
        result = _handle_playwright_smoke(req.payload or {})
        audit({
            "ts": now,
            "runner": RUNNER_NAME,
            "event": "executed",
            "skill": req.skill,
            "action": req.action,
            "result_ok": bool(result.get("ok")),
        })
        return {
            "runner": RUNNER_NAME,
            "skill": req.skill,
            "action": req.action,
            **result,
        }

    audit({
        "ts": now,
        "runner": RUNNER_NAME,
        "event": "allowed_stub",
        "skill": req.skill,
        "action": req.action,
        "payload_keys": sorted(list((req.payload or {}).keys())),
    })

    return {
        "ok": True,
        "runner": RUNNER_NAME,
        "skill": req.skill,
        "action": req.action,
        "mode": "secure-stub",
        "note": "Action is allowlisted/authenticated and passed payload policy checks.",
    }
