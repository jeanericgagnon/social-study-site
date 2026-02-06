# The Social Study — Website rebuild plan (Astro + Netlify)

Goals
- Rank quickly for **San Diego**, **Orange County**, **Denver** queries.
- Keep a **minimal/single-page feel** while still being SEO-crawlable.
- Fast (low JS, optimized images).
- Support newsletter archive (Mailchimp) and speaker/host forms (HubSpot).

Canonical
- Primary: https://www.thesocial.study
- 301 redirect non-www → www

Core IA (SEO)
- / (home)
- /events (all cities → Eventship host page CTAs)
- /san-diego
- /orange-county
- /denver
- /newsletter (archive index)
- /newsletter/YYYY/MM/slug (posts)
- /speak (speaker application; city options)
- /host (venue host form)
- /bring-to-your-city
- /mc-denver
- /privacy (basic)

Forms
## Mailchimp newsletter
Base: https://study.us2.list-manage.com/subscribe/post
u=c6eb1678fc547ca9e3efb3d6f
id=2e70c821de

Location forms:
- San Diego: f_id=006de6e3f0 tags=1853334,1853469
- Orange County: f_id=001ae6e3f0 tags=1853487
- Denver: f_id=0034e6e3f0 tags=1853740
- General: f_id=0019e6e3f0 tags=1853488

## HubSpot forms
Portal 49143429 (na1)
- Speaker:
  - SD cd909a62-610c-44e3-9759-460913af5652
  - OC ae0e15d7-e7f1-4610-82c7-a584c99e0419
  - DEN 1c1c9692-139b-42e1-87d5-2f0adbf5fdbc
- Host event:
  - SD b0000866-2430-4ab0-a65b-97a1227c7ee0
  - OC 8d103262-de08-4d75-862b-064cf672d04a
  - DEN 40f87040-8264-4404-9deb-0efb6d2ea12b
- Bring to your city:
  - 2f792adc-cf3e-4361-8889-b5c5913463e7

Portal 244844478 (na2)
- MC Denver:
  - 55dabb14-634a-4302-9c6b-f322f0010445

SEO technical
- Astro SSG
- @astrojs/sitemap
- robots.txt + sitemap.xml
- JSON-LD:
  - Organization (sitewide)
  - WebSite
  - Breadcrumbs
  - (Later) Event schema if/when we create first-party event detail pages
- Per-page title/description + canonical
- Image optimization (Netlify / build-time)

Data sources
- Events: Eventship host page (no API yet)
- Newsletter: start with manual MDX posts; later add Mailchimp RSS/API ingestion

Open questions
- Need Google Drive **folder** link for ~10 images.
- Decide whether to add venue pages / FAQ page.
