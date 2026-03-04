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
