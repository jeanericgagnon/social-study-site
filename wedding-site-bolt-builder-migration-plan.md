# Wedding Site Bolt — Builder Tab UI Migration Plan

## Scope Lock (Batch 0)

### In scope
- Builder tab in `wedding-site-Bolt` only.
- Adopt UI/UX patterns from `wedding-site-builder` for builder-related screens.
- Preserve existing `wedding-site-Bolt` functionality and behavior.
- Keep current Bolt templates/variants as source of truth.

### Out of scope
- Changes to non-builder areas of `wedding-site-Bolt`.
- Replacing Bolt templates with templates from `wedding-site-builder`.
- Removing existing builder functionality.

## Non‑Negotiables
- No functionality removal.
- Existing user flows must continue to work end-to-end.
- Any data-shape differences must be handled with adapters, not destructive schema changes.

## Flow Acceptance Checklist (must stay green)

1. Template browsing
   - Templates render from current Bolt data source.
   - Search/filter/sort behavior remains functional.

2. Template selection
   - Selecting/using a template triggers existing preload behavior.
   - Resulting editor state matches expected structure.

3. Variant browsing
   - Variant list/grid renders current Bolt variants.
   - Status badges/metadata remain accurate.

4. Variant preview
   - Preview modal opens correctly.
   - Keyboard and click navigation still work.

5. Review workflow
   - Approve/reject/status updates still persist and reflect immediately.

6. Persistence/integration
   - Existing persistence paths (Supabase/services) continue to work.
   - No regression in save/load/edit lifecycle.

7. Build health
   - Typecheck/build/lint pass.
   - Existing smoke checks run successfully in final QA phase.

## Delivery Approach
- Implement in small 3–5 minute batches.
- Each batch must be safe to stop/review.
- No broad refactors without parity checkpoints.

## Batch 1 — Inventory + Diff Map (completed)

### Current Bolt builder entry points
- Route: `/builder` (lazy loads `src/builder/BuilderPage.tsx`)
- Shell: `src/builder/components/BuilderShell.tsx`
- Template UX: `src/builder/components/TemplateGalleryPanel.tsx`
- Core edit surfaces:
  - `BuilderTopBar.tsx`
  - `BuilderCanvas.tsx`
  - `BuilderInspectorPanel.tsx`
- State/services preserved:
  - `src/builder/state/*`
  - `src/builder/services/*`
  - `src/builder/adapters/*`

### wedding-site-builder reference UI surfaces
- `src/components/builder/BuilderApp.tsx`
- `src/components/builder/TemplateGallery.tsx`
- `src/components/builder/VariantGallery.tsx`
- `src/components/builder/VariantPreviewModal.tsx`
- `src/components/builder/TemplateCard.tsx`
- `src/components/builder/VariantCard.tsx`

### Mapping plan (reference -> Bolt target)
- `BuilderApp` (header + tab framing) -> visual framing for Bolt builder shell/top regions
- `TemplateGallery` + `TemplateCard` -> visual structure for Bolt `TemplateGalleryPanel`
- `VariantGallery` + `VariantCard` -> visual structure for Bolt variant browsing surfaces (Builder tab only)
- `VariantPreviewModal` -> visual/interaction baseline for Bolt variant preview modal

### Keep-as-is (functionality contracts)
- Bolt template source + variant source remain canonical.
- Bolt apply-template behavior (content preservation + undo + autosave) remains unchanged.
- Bolt publish/save/readiness checks remain unchanged.
- Bolt state shape and service contracts remain unchanged.

### Integration strategy
- UI-first swap: replace visual components and layout primitives first.
- Adapter boundary: if reference UI props differ, map at component boundaries only.
- No backend/data contract edits in UI batches.

## Batch 2 — UI Shell Scaffold (completed)

### Implemented
- Added a Builder workspace sub-header in `src/builder/components/BuilderShell.tsx` directly under the existing top bar.
- Introduced lightweight view-pill controls inspired by `wedding-site-builder` framing:
  - `Editor` (active visual state)
  - `Templates` (opens existing Bolt template gallery flow)
  - `Variants` (disabled placeholder for upcoming batch wiring)

### Safety notes
- No state model changes.
- No service/backend changes.
- Existing canvas/editor/publish/save flows unchanged.
- Existing template data source and apply logic unchanged.

## Batch 3 — Template Gallery Skin Swap (completed)

### Implemented
- Upgraded template gallery panel UX in `src/builder/components/TemplateGalleryPanel.tsx` with a top search row aligned to `wedding-site-builder` browsing patterns.
- Added template search support over:
  - display name
  - description
  - mood tags
- Added live result count badge in the search row.

### Safety notes
- Existing Bolt template source remains unchanged.
- Existing template apply flow and content-preservation logic unchanged.
- Existing mood/color/season filters preserved and now compose with search.

## Batch 4 — “Use Template” flow wiring (completed)

### Implemented
- Standardized CTA wording to `Use Template` across the template gallery and confirmation flows for clearer parity with intended user behavior.
- Updated post-apply action in success modal:
  - `Use template and continue editing` now closes the template gallery and returns user to editor context.

### Safety notes
- No changes to preload/apply business logic.
- No changes to template data source.
- Existing content-preservation + undo behavior remains intact.

## Batch 5 — Variant browsing skin refresh (completed)

### Implemented
- Updated variant selection UI in `src/builder/components/BuilderInspectorPanel.tsx` from a compact dropdown to pill-style variant chips.
- Chips are now directly clickable and visibly reflect active variant state, aligning with gallery-style variant browsing patterns.

### Safety notes
- Variant source remains Bolt canonical manifests (`manifest.variantMeta`).
- `handleChangeVariant` action unchanged (same state update path).
- No data or service contract changes.

## Batch 6 — Variant picker navigation polish (completed)

### Implemented
- Enhanced `VariantPicker` in `src/builder/components/BuilderSidebarLibrary.tsx` with keyboard navigation:
  - `ArrowDown`/`ArrowUp` to move through variant cards
  - `Enter` to apply the currently active variant
- Added keyboard-active visual highlighting on variant cards so pointer and keyboard interactions share the same selection affordance.

### Safety notes
- Variant add/apply action still routes through existing `onSelect` behavior.
- No changes to variant data definitions or adapters.
- No persistence/service changes.

## Batch 7 — Control flow hardening (completed)

### Implemented
- Added `Escape` key handling in `TemplateGalleryPanel` to close the top-most layer first:
  - confirm modal
  - details modal
  - compare modal
  - apply-result modal
  - then the gallery panel
- Hardened `VariantPicker` keyboard navigation so it ignores key commands while typing in inputs/textareas/selects/contenteditable targets.

### Safety notes
- No business logic changes in template apply or variant selection flows.
- Changes are interaction safety/UX only.

## Batch 8 — Adapter/state hardening pass (completed)

### Implemented
- Hardened template search matching in `TemplateGalleryPanel` by introducing a normalized searchable text composition over:
  - `displayName`
  - `description` (safe optional fallback)
  - mood tags
  - template id
- This reduces UI fragility if optional fields are missing and improves search resilience without changing data contracts.

### Safety notes
- No changes to store shape or adapter contracts.
- No template application logic changes.
- Filtering behavior remains additive to existing mood/color/season filters.

## Batch 9 — Visual polish + responsive UX (completed)

### Implemented
- Polished Builder workspace sub-header responsiveness in `BuilderShell`:
  - better wrap behavior on narrow widths
  - horizontally scroll-safe control pills
- Improved Template Gallery empty state UX:
  - clearer message copy
  - `Reset filters` quick action that clears search + mood/color/season filters

### Safety notes
- UI-only updates.
- No state shape, service, or business logic changes.

## Batch 10 — Regression sweep prep (completed)

### Frozen parity checklist for QA/smoke
1. Template gallery opens/closes from builder shell controls.
2. Template search + mood/color/season filters compose correctly.
3. Use Template flow applies selected template and returns to editor context.
4. Existing content-preservation behavior still works on template apply.
5. Variant selection in inspector works via chip UI.
6. Variant picker supports hover/click + keyboard (↑/↓ + Enter).
7. Escape key closes top-most builder modal layer in template gallery.
8. Publish/save/top bar controls remain intact and reachable.
9. No changes to template/variant canonical Bolt data sources.

### QA execution note
- Next phase: run typecheck/build plus targeted functional smoke through builder tab flows.
