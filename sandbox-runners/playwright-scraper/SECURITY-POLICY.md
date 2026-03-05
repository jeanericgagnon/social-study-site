# Playwright Scraper Sandbox Policy

## Goal
Run web scraping tasks with strict outbound/network and data-handling controls.

## Required Controls

1. **URL allowlist required**
   - Only scrape approved domains.
   - Default deny for all unlisted domains.

2. **Block internal/private targets**
   - Deny localhost and loopback (`localhost`, `127.0.0.0/8`, `::1`)
   - Deny RFC1918/private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
   - Deny link-local/metadata ranges (`169.254.0.0/16`, cloud metadata endpoints)

3. **No credentialed scraping by default**
   - Do not auto-login.
   - Do not pass cookies/tokens unless explicitly approved.

4. **Rate and scope limits**
   - Max pages per run (default 50)
   - Max runtime (default 10m)
   - Crawl delay between requests (default 500ms+)

5. **Output hygiene**
   - Store output under `.scrapes/` in workspace
   - Avoid raw HTML dumps unless needed
   - Do not store secrets in output/logs

6. **Operational guardrails**
   - Use low-privilege runtime
   - Keep dependencies updated
   - Record target domains and run time in logs

## Quick Approval Model

- **Safe by default**: public docs/marketing pages from allowlisted domains.
- **Needs explicit approval**: authenticated pages, form submissions, or broad crawls.

## Incident Response

If a run attempts blocked hosts or looks suspicious:
- stop run immediately
- preserve logs
- review URL resolution/redirection chain
- rotate any exposed credentials if applicable
