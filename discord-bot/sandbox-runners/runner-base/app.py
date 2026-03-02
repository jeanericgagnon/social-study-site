from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urljoin
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


def _extract_links(base_url: str, html: str) -> list[str]:
    links = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        href = (m.group(1) or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_url = urljoin(base_url, href)
        if abs_url.startswith(("http://", "https://")):
            links.append(abs_url)
    # stable unique order
    out = []
    seen = set()
    for u in links:
        key = u.split("#", 1)[0]
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _classify_url(url: str) -> str:
    p = (urlparse(url).path or "").lower()
    if any(k in p for k in ["registry", "gift-registry", "wedding-registry"]):
        return "registry"
    if any(k in p for k in ["template", "design", "themes", "gallery", "examples", "showcase"]):
        return "templates"
    if any(k in p for k in ["website-builder", "build", "website", "create", "maker", "features"]):
        return "builder"
    return "other"


def _same_domain(a: str, b: str) -> bool:
    try:
        ha = (urlparse(a).hostname or "").lower()
        hb = (urlparse(b).hostname or "").lower()
        return ha == hb
    except Exception:
        return False


def _fetch_page(url: str, timeout_s: int) -> Dict[str, Any]:
    req = Request(
        url,
        headers={
            "User-Agent": "SandboxRunner/1.0 (+playwright-scraper)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_s) as resp:
        body_bytes = resp.read(32768)
        content_type = resp.headers.get("Content-Type", "")
        status = int(getattr(resp, "status", 200))
        final_url = resp.geturl()
        html = body_bytes.decode("utf-8", errors="ignore")
        return {
            "status": status,
            "finalUrl": final_url,
            "contentType": content_type,
            "title": _extract_title(html),
            "bytesRead": len(body_bytes),
            "links": _extract_links(final_url, html),
        }


def _handle_playwright_smoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = payload.get("url", "")
    timeout_s = int(payload.get("timeoutSec", 10))
    timeout_s = max(2, min(timeout_s, 20))

    try:
        page = _fetch_page(url, timeout_s)
        return {
            "ok": True,
            "mode": "real-handler",
            "status": int(page["status"]),
            "finalUrl": page["finalUrl"],
            "contentType": page["contentType"],
            "title": page["title"],
            "bytesRead": page["bytesRead"],
        }
    except HTTPError as e:
        return {"ok": False, "mode": "real-handler", "error": "http_error", "status": int(e.code)}
    except URLError as e:
        return {"ok": False, "mode": "real-handler", "error": "network_error", "detail": str(e.reason)}
    except Exception:
        return {"ok": False, "mode": "real-handler", "error": "smoke_failed"}


def _handle_playwright_scrape(payload: Dict[str, Any], action_cfg: Dict[str, Any]) -> Dict[str, Any]:
    start_url = str(payload.get("url", "")).strip()
    if not start_url:
        return {"ok": False, "mode": "real-handler", "error": "invalid_url"}

    timeout_s = int(payload.get("timeoutSec", 10))
    timeout_s = max(2, min(timeout_s, 20))

    policy_max_pages = int(action_cfg.get("maxPages", 20))
    req_max_pages = int(payload.get("maxPages", min(10, policy_max_pages)))
    max_pages = max(1, min(req_max_pages, policy_max_pages))

    queue = [start_url]
    visited = set()
    pages = []
    discovered = {"builder": [], "registry": [], "templates": []}

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            page = _fetch_page(url, timeout_s)
            final_url = page["finalUrl"]
            pages.append({
                "url": final_url,
                "status": page["status"],
                "title": page["title"],
                "contentType": page["contentType"],
            })

            cls = _classify_url(final_url)
            if cls in discovered and final_url not in discovered[cls]:
                discovered[cls].append(final_url)

            for link in page["links"]:
                if _same_domain(start_url, link) and link not in visited and link not in queue:
                    queue.append(link)
                    lcls = _classify_url(link)
                    if lcls in discovered and link not in discovered[lcls]:
                        discovered[lcls].append(link)
        except HTTPError as e:
            pages.append({"url": url, "status": int(e.code), "error": "http_error"})
        except Exception:
            pages.append({"url": url, "error": "fetch_failed"})

    return {
        "ok": True,
        "mode": "real-handler",
        "startUrl": start_url,
        "pagesCrawled": len(pages),
        "maxPages": max_pages,
        "pages": pages,
        "builderPages": discovered["builder"],
        "registryPages": discovered["registry"],
        "templatePages": discovered["templates"],
    }


def _handle_automation_run(payload: Dict[str, Any], action_cfg: Dict[str, Any]) -> Dict[str, Any]:
    workflow_id = str(payload.get("workflowId", "")).strip()
    if not workflow_id:
        return {"ok": False, "mode": "real-handler", "error": "invalid_workflow_id"}

    allowed_ids = [str(x) for x in action_cfg.get("allowedWorkflowIds", [])]
    if allowed_ids and workflow_id not in allowed_ids:
        return {"ok": False, "mode": "real-handler", "error": "workflow_not_allowed", "workflowId": workflow_id}

    # secure no-op execution record (real handler with strict allowlist gate)
    return {
        "ok": True,
        "mode": "real-handler",
        "result": "queued",
        "workflowId": workflow_id,
        "note": "Workflow accepted by allowlist. Executor hook not yet attached.",
    }


def _handle_agentmail_send(payload: Dict[str, Any], action_cfg: Dict[str, Any]) -> Dict[str, Any]:
    to = str(payload.get("to", "")).strip().lower()
    subject = str(payload.get("subject", "")).strip()
    body = str(payload.get("body", "")).strip()
    template_id = str(payload.get("templateId", "")).strip()

    if not to or "@" not in to:
        return {"ok": False, "mode": "real-handler", "error": "invalid_recipient"}
    if not subject:
        return {"ok": False, "mode": "real-handler", "error": "missing_subject"}

    max_subject_len = int(action_cfg.get("maxSubjectLength", 120))
    if len(subject) > max_subject_len:
        return {"ok": False, "mode": "real-handler", "error": "subject_too_long"}

    allowed_templates = [str(x) for x in action_cfg.get("allowedTemplateIds", [])]
    if allowed_templates:
        if not template_id:
            return {"ok": False, "mode": "real-handler", "error": "missing_template_id"}
        if template_id not in allowed_templates:
            return {"ok": False, "mode": "real-handler", "error": "template_not_allowed", "templateId": template_id}

    max_body_len = int(action_cfg.get("maxBodyLength", 4000))
    if body and len(body) > max_body_len:
        return {"ok": False, "mode": "real-handler", "error": "body_too_long"}

    return {
        "ok": True,
        "mode": "real-handler",
        "result": "queued",
        "to": to,
        "subject": subject,
        "templateId": template_id or None,
        "note": "Message accepted by policy gates. Mail transport hook not yet attached.",
    }


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

    if req.skill == "playwright-scraper-skill" and req.action == "scrape":
        result = _handle_playwright_scrape(req.payload or {}, action_cfg)
        audit({
            "ts": now,
            "runner": RUNNER_NAME,
            "event": "executed",
            "skill": req.skill,
            "action": req.action,
            "result_ok": bool(result.get("ok")),
            "pagesCrawled": result.get("pagesCrawled"),
        })
        return {
            "runner": RUNNER_NAME,
            "skill": req.skill,
            "action": req.action,
            **result,
        }

    if req.skill == "automation-workflows" and req.action == "run":
        result = _handle_automation_run(req.payload or {}, action_cfg)
        audit({
            "ts": now,
            "runner": RUNNER_NAME,
            "event": "executed",
            "skill": req.skill,
            "action": req.action,
            "result_ok": bool(result.get("ok")),
            "workflowId": (req.payload or {}).get("workflowId"),
        })
        return {
            "runner": RUNNER_NAME,
            "skill": req.skill,
            "action": req.action,
            **result,
        }

    if req.skill == "agentmail" and req.action == "send":
        result = _handle_agentmail_send(req.payload or {}, action_cfg)
        audit({
            "ts": now,
            "runner": RUNNER_NAME,
            "event": "executed",
            "skill": req.skill,
            "action": req.action,
            "result_ok": bool(result.get("ok")),
            "to": (req.payload or {}).get("to"),
            "templateId": (req.payload or {}).get("templateId"),
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
