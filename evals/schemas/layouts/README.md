# Layout fixtures

JSON files here are **`PresentationLayoutModel`** payloads (same shape as `servers/fastapi/templates/presentation_layout.py`).

## Usage in promptfoo tests

Set `layout_json` to a repo-relative pointer (resolved from the `evals/` directory):

```yaml
layout_json: file://schemas/layouts/eval-default.json
```

At runtime, `evals/layout_load.py` inlines the file so `PresentationLayoutModel.model_validate_json` always receives raw JSON text.

## Files

| File | Purpose |
|------|---------|
| `eval-default.json` | Three layouts (title, text, table) used by **`outline_then_structure_then_slide_content`** tests in `tests/slide-content/core.yaml` |
| `standard.json`, `swift.json`, `*.meta.json` | Generated from Next.js templates (`servers/nextjs/app/presentation-templates/<group>`). Regenerate: `cd servers/nextjs && npm run export-layout-eval-fixtures` (optional `-- standard,swift`). **`outline_then_structure`** tests in `tests/structure/core.yaml` use `standard.json`. |

Add new fixtures for richer templates (charts, images) as needed; reference them with `file://schemas/layouts/<name>.json`.
