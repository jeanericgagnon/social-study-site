#!/usr/bin/env node
/**
 * Mailchimp → Astro newsletter sync
 *
 * Usage:
 *   MAILCHIMP_API_KEY=... node scripts/mailchimp-sync.mjs
 * Optional:
 *   MAILCHIMP_FOLDER_NAME=ArticleSends
 *   MAILCHIMP_LIST_COUNT=200
 */

import fs from 'node:fs';
import path from 'node:path';

const API_KEY = process.env.MAILCHIMP_API_KEY;
const FOLDER_NAME = process.env.MAILCHIMP_FOLDER_NAME || 'ArticleSends';
const LIST_COUNT = Number(process.env.MAILCHIMP_LIST_COUNT || '200');

if (!API_KEY) {
  console.error('Missing MAILCHIMP_API_KEY env var.');
  process.exit(1);
}

const dc = API_KEY.split('-').pop();
if (!dc || dc === API_KEY) {
  console.error('MAILCHIMP_API_KEY must end with datacenter suffix like -us2');
  process.exit(1);
}

const API_BASE = `https://${dc}.api.mailchimp.com/3.0`;
const AUTH = Buffer.from(`anystring:${API_KEY}`).toString('base64');

function qs(params = {}) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : '';
}

async function apiFetch(p, params) {
  const url = `${API_BASE}${p}${qs(params)}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Basic ${AUTH}`,
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Mailchimp API ${res.status} ${res.statusText} for ${p}: ${body.slice(0, 500)}`);
  }
  return res.json();
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function slugify(s) {
  return String(s)
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 80);
}

function yyyyMmDd(iso) {
  try {
    return new Date(iso).toISOString().slice(0, 10);
  } catch {
    return 'unknown-date';
  }
}

function stripTags(html) {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function excerptFrom(html, n = 180) {
  const t = stripTags(html);
  return t.length > n ? `${t.slice(0, n).trim()}…` : t;
}

function astroPage({ title, description, html, canonicalPath }) {
  // IMPORTANT: html is untrusted external content; we do not execute it.
  // We render it as raw HTML for display.
  const safeHtmlLiteral = JSON.stringify(html);
  return `---
import BaseLayout from '../../../layouts/BaseLayout.astro';
import SiteHeader from '../../../components/SiteHeader.astro';
import '../../../styles/global.css';

const title = ${JSON.stringify(title)};
const description = ${JSON.stringify(description)};
const html = ${safeHtmlLiteral};
const canonical = Astro.site ? new URL(${JSON.stringify(canonicalPath)}, Astro.site).toString() : undefined;
---

<BaseLayout title={title} description={description} canonical={canonical}>
  <SiteHeader />
  <main class="mx-auto max-w-3xl px-4 pb-20">
    <header class="mt-6">
      <h1 class="h-brand text-5xl">{title}</h1>
      <p class="mt-4 text-lg text-slate-700">{description}</p>
    </header>

    <article class="mt-10 rounded-[26px] border-[3px] border-black bg-white p-6 md:p-10">
      <div class="newsletter-html" set:html={html} />
    </article>

    <footer class="mt-16 border-t border-slate-200 pt-8 text-sm text-slate-600">
      <a class="underline" href="../../privacy/">Privacy</a>
    </footer>
  </main>
</BaseLayout>

<style>
  /* Light normalization for Mailchimp HTML */
  .newsletter-html :global(img){ max-width:100%; height:auto; }
  .newsletter-html :global(a){ text-decoration: underline; }
  .newsletter-html :global(table){ max-width:100%; }
  .newsletter-html :global(p){ margin: 0.75rem 0; }
</style>
`;
}

async function main() {
  // 1) Find folder by name
  const folders = await apiFetch('/campaign-folders', { count: 1000 });
  const folder = (folders.folders || []).find((f) => f.name === FOLDER_NAME);
  if (!folder) {
    const names = (folders.folders || []).map((f) => f.name).sort();
    throw new Error(`Folder not found: ${FOLDER_NAME}. Existing folders: ${names.join(', ')}`);
  }

  // 2) List sent campaigns in that folder
  const campaignsRes = await apiFetch('/campaigns', {
    folder_id: folder.id,
    status: 'sent',
    count: LIST_COUNT,
    sort_field: 'send_time',
    sort_dir: 'DESC',
  });

  const campaigns = campaignsRes.campaigns || [];
  console.log(`Found ${campaigns.length} sent campaigns in folder ${FOLDER_NAME}.`);

  const outDataDir = path.join(process.cwd(), 'src', 'data');
  ensureDir(outDataDir);

  const outPagesDir = path.join(process.cwd(), 'src', 'pages', 'newsletter');
  ensureDir(outPagesDir);

  const indexItems = [];

  for (const c of campaigns) {
    const sendTime = c.send_time || c.create_time;
    const date = yyyyMmDd(sendTime);
    const subject = c.settings?.subject_line || c.settings?.title || 'Newsletter';
    const slug = `${date}-${slugify(subject)}`;
    const canonicalPath = `/newsletter/${slug}/`;

    const content = await apiFetch(`/campaigns/${c.id}/content`);
    const html = content?.html || '';

    const title = subject;
    const description = excerptFrom(html, 180) || 'Interview-style Q&A with Social Study speakers.';

    const pageDir = path.join(outPagesDir, slug);
    ensureDir(pageDir);
    fs.writeFileSync(path.join(pageDir, 'index.astro'), astroPage({ title, description, html, canonicalPath }), 'utf8');

    indexItems.push({
      id: c.id,
      slug,
      title,
      description,
      date,
      send_time: sendTime,
      web_id: c.web_id,
    });
  }

  fs.writeFileSync(
    path.join(outDataDir, 'newsletters.json'),
    JSON.stringify({
      folder: { id: folder.id, name: folder.name },
      generatedAt: new Date().toISOString(),
      items: indexItems,
    }, null, 2),
    'utf8'
  );

  console.log(`Wrote ${indexItems.length} pages + src/data/newsletters.json`);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
