# Sandbox Skill Runners (Expandable)

This is an isolated local runner layer for skills. Your chat agents stay as-is; skills execute in separate containers and only receive payload you send.

## What this sets up
- `playwright-runner` on `127.0.0.1:19081`
- `automation-runner` on `127.0.0.1:19082`
- Per-runner policy file (`allowedSkills`)
- Read-only container filesystem + dropped Linux caps + no-new-privileges

## Start
```bash
cd sandbox-runners
cp .env.example .env
# Replace tokens in .env with long random values
docker compose --env-file .env up -d --build
```

## Health check
```bash
curl http://127.0.0.1:19081/health
curl http://127.0.0.1:19082/health
```

## Test call
```bash
curl -s -X POST http://127.0.0.1:19081/run \
  -H "Content-Type: application/json" \
  -H "X-Runner-Token: $PLAYWRIGHT_RUNNER_TOKEN" \
  -d '{"skill":"playwright-mcp","action":"smoke","payload":{"url":"https://example.com"}}'
```

## Expand with a new sandbox
1. Create `configs/<new-runner>/policy.json`
2. Copy a service block in `docker-compose.yml`
3. Add `<NEW_RUNNER>_TOKEN` to `.env`
4. `docker compose up -d --build`

## Important notes
- Same Ethernet/LAN is fine. Isolation is process/container policy, not physical network separation.
- `/run` is now **authenticated + allowlist-enforced** with secure-stub actions. It will reject unknown skills/actions.
- Concrete command/API handlers are intentionally not wired yet (safer default until each connector is reviewed).
- For strict outbound domain control, add a dedicated egress proxy/firewall allowlist layer.

## After policy/code updates
Rebuild and restart runners:
```bash
docker build -t sandbox-runner-base ./runner-base
docker rm -f playwright-runner automation-runner 2>/dev/null || true
# then re-run your docker run commands for both containers
```
