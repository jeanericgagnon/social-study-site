# AGENTS.md — Discord Bot Workspace

This workspace is isolated for Discord activity.

## Purpose
- Keep Discord memory/context separate from Eric’s private main-session memory.
- Store only Discord-safe operational context here.

## Rules
- Do not read or reference the main workspace `MEMORY.md`.
- Keep memory scoped to Discord operations, channel norms, bot behavior, and safe preferences.
- No secrets, credentials, banking, or private personal notes.

## Sandbox skill routing (mandatory)
- For these skills, route execution through `sandbox-runners/run-skill.sh` (never direct shell/tool execution):
  - `playwright-mcp`
  - `automation-workflows`
  - `agentmail`
- Only pass minimal required payload fields.
- Respect runner policy denials; do not bypass with alternate direct commands.
- Keep runner endpoints localhost-only and token-authenticated.
