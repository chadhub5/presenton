# Layout fixtures

JSON here is the **`PresentationLayoutModel`** payload for evals (same shape as `servers/fastapi/templates/presentation_layout.py`).

## File

| File | Purpose |
|------|---------|
| `standard.json` | Built-in **standard** template catalog for evals. Regenerate from the app: `cd servers/nextjs && npm run export-layout-eval-fixtures -- standard` (writes into `evals/schemas/layouts/` per project script). |
| `standard.meta.json` | Indices / layout count for assertions (`num_layouts`, `indices_by_id`). Keep in sync when you regenerate `standard.json`. |

## Usage in promptfoo tests

```yaml
layout_json: file://schemas/layouts/standard.json
```

At runtime, `evals/layout_load.py` resolves `file://…` paths relative to the `evals/` directory.

## Structure prompt context (aligned with production)

Outline-driven structure uses the same message shape as **`generate_presentation_structure.get_messages`**: the user message contains **`presentation_layout.to_string()`** (each layout’s **name** and **description** only) plus the outline text — **not** the full per-layout `json_schema` blobs. Slide content generation still uses each chosen layout’s **`json_schema`** when filling fields (see `provider.py`).
