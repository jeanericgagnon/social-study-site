# The Social Study — Website (Astro)

## Local dev

```bash
cd social-study-site
npm install
npm run dev -- --host 127.0.0.1 --port 4321
```

Open: http://127.0.0.1:4321

## Newsletter archive (Mailchimp)

We auto-generate `/newsletter/<slug>/` pages from Mailchimp campaigns located in the Mailchimp folder:

- **ArticleSends**

### Manual sync

```bash
cd social-study-site
MAILCHIMP_API_KEY="..." npm run sync:mailchimp
npm run build
```

### Auto sync (GitHub Actions)

A scheduled GitHub Action runs daily and commits new newsletter pages into the repo.

Required repo secret:
- `MAILCHIMP_API_KEY`

Security note:
- Do **not** commit API keys.
- Rotate/revoke any key if it’s ever pasted into chat or committed by accident.
