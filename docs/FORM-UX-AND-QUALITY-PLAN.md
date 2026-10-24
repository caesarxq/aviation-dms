# Form UX and Test Quality Plan

## Audit scope

The frontend contains **101 form controls across 22 TSX files**, including modal forms, inline operational forms, filters, selectors, upload controls, and document-editor controls.

### Current improvements applied

- Added `FormGuide`, a shared guidance component for concise user instructions.
- Added default guidance text to every shared `Modal`, so modal forms no longer open without context.
- Added accessible modal labelling with `aria-labelledby` and `aria-describedby`.
- Added domain-specific guidance to document creation, personnel licenses, aircraft insurance/documents, credential uploads, and document proposals.
- Existing operational inline forms already provide contextual instructions for missions, occurrences, dangerous goods, quality audits, and security incidents.

## Remaining form-quality gaps

The static audit identified many controls without explicit `id`/`name` attributes, particularly:

- Filter and selector controls in catalogue, missions, quality, notifications, insurance, and version-diff views.
- Date, checkbox, file, and select controls in personnel, aircraft, upload, and document forms.
- Several modal inputs that rely on placeholder text instead of an associated visible label.

### Recommended remediation standard

Every user-editable control should have:

1. A stable `id` and `name`.
2. A visible `<label htmlFor="...">`.
3. A short field-level helper or example where the correct value is not obvious.
4. `aria-describedby` linked to the helper text when applicable.
5. Explicit required/optional status.
6. Inline validation that explains how to correct the value.
7. A safe empty-state and loading state for dependent selectors.

## Priority enhancements

### P0 — usability and safety

- Replace placeholder-only labels with visible labels throughout all data-entry forms.
- Add field-level help for dates, classifications, KCAA approval, license types, insurance coverage, document types, and dangerous-goods fields.
- Add `required`, `min`, `max`, and format validation at the HTML and API layers.
- Prevent accidental loss of entered data when closing or navigating away from a dirty form.
- Add confirmation and clear success/error feedback for every destructive or state-changing action.

### P1 — workflow quality

- Introduce a shared form schema layer (Zod or Pydantic-generated metadata) so frontend and backend validation do not drift.
- Add draft autosave only for non-authoritative user input; never autosave directly into a controlled published version.
- Add reusable dependent selectors for aircraft, personnel, document, version, and role references.
- Add contextual regulatory guidance links for KCAA-controlled records.
- Add form completion summaries before submission for high-risk workflows.

### P2 — accessibility and maintainability

- Add automated accessibility checks with axe/Playwright for labels, descriptions, focus order, keyboard operation, and contrast.
- Replace repeated ad-hoc form markup with shared `Field`, `SelectField`, `DateField`, `FileField`, and `FormSection` components.
- Add a form inventory test that fails when a new input/select/textarea lacks `id`/`name` and accessible labelling.
- Add story-level or component-level tests for validation, errors, disabled/loading state, and reset-after-success behavior.

## Mutation testing assessment

StrykerJS is appropriate for the TypeScript/Vitest utility and workflow logic, but not as the first test for the entire React application. Mutating every page creates a slow and noisy run because many pages depend on API state, routing, and browser behavior.

### Pilot configuration

The repository now includes:

```bash
npm run mutation:pilot
```

The pilot targets `DocumentOutline.tsx` and its focused unit tests. It completed in approximately 86 seconds and produced:

- 133 mutants instrumented
- 38% mutation score
- 38 mutants killed
- 57 mutants survived
- 5 mutants with no coverage
- 33 errors reported by the runner/mutant combinations

The pilot passed because the break threshold is intentionally `0`; the score is diagnostic, not an acceptance gate.

### Interpretation

The low score is useful: the outline tests cover the main happy paths but do not sufficiently exercise:

- Empty/undefined DOM parser behavior.
- Whitespace normalization edge cases.
- Heading-number parsing boundaries.
- Duplicate-heading deduplication behavior.
- Invalid or malformed converted-manual structures.
- Fallback behavior when page wrappers are absent or incomplete.

### Recommended rollout

1. Improve unit tests for `DocumentOutline` and `diff.ts` until the pilot score is at least 70–80%.
2. Add mutation testing for proposal grouping and stale/ambiguous application logic.
3. Add mutation testing for backend workflow transition helpers where tests are deterministic and fast.
4. Keep full-page React mutation testing out of CI initially; cover those behaviors with Playwright and contract tests instead.
5. Raise the Stryker break threshold gradually: `0 → 60 → 70 → 80`.

## Dependency note

Adding StrykerJS introduced nine npm audit findings in the current dependency tree (eight moderate, one high). These should be triaged separately before making mutation testing a mandatory CI gate; do not use `npm audit fix --force` without reviewing breaking dependency changes.
