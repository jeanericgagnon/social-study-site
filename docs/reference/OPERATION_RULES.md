# Operation rules (Mac mini / local-only)

## Default permissions (approved)
Sys may, without asking each time:
- Create, edit, and organize **local files** on disk inside:
  - `~/.openclaw/workspace/` (including `docs/` and `vault/`)
- Create and maintain documentation (Markdown), indexes, and templates.
- Run **non-destructive** shell commands that support the above (e.g., mkdir, cp, mv, grep, git status).

## Outbound restrictions (do not do unless explicitly asked)
Sys must not:
- Send messages (WhatsApp/Telegram/etc.), emails, or post publicly.
- Upload/sync content to cloud services (Drive/Notion/etc.).
- Share files externally.

## Always ask first
- System-level changes (network, accounts, security settings, launch agents, sudo-required commands)
- Destructive actions (deleting data, wiping directories). Preference: move to a local `trash/` folder instead.

## Notes
- If a task requires browsing the web or using a cloud API, Sys will ask first.
