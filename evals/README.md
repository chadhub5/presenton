# Presenton evals

[Promptfoo](https://www.promptfoo.dev/) runs tests against a **Python provider** (`provider.py`) that calls the same outline / structure / slide prompts as production (`messages_builder.py` + `prompts/*.txt`).

## What runs today

| Suite | Config | `stage` in tests |
|-------|--------|------------------|
| Outline | `promptfooconfig.yaml` | `outline` |
| Layout indices | `promptfooconfig.structure.yaml` | `outline_then_structure` |
| Slide bodies (per chosen layout schema) | `promptfooconfig.slides.yaml` | `outline_then_structure_then_slide_content` |

`provider.py` only exposes **`outline`**, **`outline_then_structure`**, and **`outline_then_structure_then_slide_content`**. There is no separate one-shot **`structure`** or **`slide_content`** stage: those steps always run after an outline in the same call.

---

## Prerequisites

### 1. Promptfoo (CLI)

Install globally so `promptfoo` is on your `PATH`:

```bash
npm install -g promptfoo
```

If you prefer not to install globally, use `npx promptfoo@latest` instead of `promptfoo` in the commands below.

### 2. Python environment (required for `provider.py`)

The provider uses **Python 3.11** and dependencies from `evals/pyproject.toml` (notably `llmai`). From the **repo root**:

```bash
cd evals
uv sync
source .venv/bin/activate
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
```

On Windows (PowerShell): `.\.venv\Scripts\Activate.ps1` — on Windows you can set `PROMPTFOO_PYTHON` to the full path of `.venv\Scripts\python.exe` instead.

**Important:** Promptfoo runs the Python provider with the interpreter in **`PROMPTFOO_PYTHON`** when set (recommended). Otherwise it uses whatever `python3` is on your `PATH`, so activate the venv above or exports will not match the env where `llmai` is installed.

### 3. API keys and model settings

`promptfooconfig.yaml` sets `LLM` and `OPENAI_MODEL` for the default setup. You must export the matching API key in your shell (see `llm_env.py` for other providers).

**OpenAI (default in config):**

```bash
export OPENAI_API_KEY="sk-..."
# Optional overrides (see llm_env.py):
# export PRESENTON_MODEL="gpt-4o"
```

If you change `LLM` in the config or in the shell (e.g. `anthropic`), set the corresponding key (`ANTHROPIC_API_KEY`, etc.) instead.

You can also load keys from the app’s `userConfig.json` via `env_sync` if `USER_CONFIG_PATH` / `APP_DATA_DIRECTORY` point at your Presenton data directory—same behavior as the server.

---

## Run evaluations

Always run from the **`evals/`** directory so relative paths in the config resolve.

```bash
cd evals
source .venv/bin/activate   # if not already active
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
export OPENAI_API_KEY="sk-..."
promptfoo eval -c promptfooconfig.yaml --no-cache --no-share
```

- **`-c` / `--config`** — Path to your config file. Other configs in this folder: `promptfooconfig.structure.yaml`, `promptfooconfig.slides.yaml`.
- **`--no-cache`** — Skips disk cache so you see fresh model outputs.
- **`--no-share`** — Avoids uploading results to promptfoo cloud (good default for private keys).

Validate the config and provider wiring without calling the model (as far as `validate config` allows):

```bash
cd evals
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
promptfoo validate config -c promptfooconfig.yaml
```

### Smaller runs

```bash
promptfoo eval -c promptfooconfig.yaml --filter-pattern '\[(best|poor)\]' --no-cache
promptfoo eval -c promptfooconfig.yaml --filter-pattern '\[best\]' --no-cache
promptfoo eval -c promptfooconfig.yaml --filter-pattern '\[poor\]' --no-cache
```

---

## View results in the browser

After an `eval`, start the local UI (latest results by default):

```bash
cd evals
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
promptfoo view
```

Useful flags:

- **`promptfoo view -y`** — Skip prompts and open the browser.
- **`promptfoo view -n`** — Do not auto-open a browser tab.
- **`promptfoo view -p 15500`** — Pick a port (default is `15500`).

There is no separate “evaluation” subcommand name—**`eval`** runs tests and **`view`** opens them.

---

## How it works

1. **`promptfooconfig.yaml`** — Declares env defaults, the stub prompt, the custom provider, optional `defaultTest` assertions, and the **`tests:`** list (YAML files under `tests/`).
2. **`provider.py`** — Promptfoo passes `vars` per case. **`stage`** selects:
   - **`outline`** — Brief → outline JSON only.
   - **`outline_then_structure`** — Outline LLM, then layout indices for that outline. Needs **`layout_json`**. Returns `{ "outline", "structure" }`. Config: **`promptfooconfig.structure.yaml`** (catalog: **`schemas/layouts/standard.json`**).
   - **`outline_then_structure_then_slide_content`** — Outline → **layout indices (structure)** → **slide JSON per slide**. The last step **depends on structure**: for each slide, the model fills the fields of **`json_schema` for the layout index chosen for that slide** (see `provider.py`: `response_schema` comes from `selected_layout.json_schema`). Same order as production `presentation.py`. Needs **`layout_json`**. Returns **`outline`**, **`structure`**, **`slides`**, **`rendered_slide_bodies`**. Config: **`promptfooconfig.slides.yaml`**.

3. **Assertions** — Per test or `defaultTest`. For slide-chain tests, grade **`rendered_slide_bodies`** only when checking final copy quality. `llm-rubric` needs grader API access per promptfoo.

### Test files (each suite: one `core.yaml`)

| Path | `stage` | Run with |
|------|---------|----------|
| `tests/outline/core.yaml` | `outline` | `promptfooconfig.yaml` |
| `tests/structure/core.yaml` | `outline_then_structure` | `promptfooconfig.structure.yaml` |
| `tests/slide-content/core.yaml` | `outline_then_structure_then_slide_content` | `promptfooconfig.slides.yaml` |

---

## Structure eval (`outline_then_structure`)

Optional var **`structure_instructions`** applies only to the structure (layout) step.

```bash
cd evals
source .venv/bin/activate
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
export OPENAI_API_KEY="sk-..."
promptfoo eval -c promptfooconfig.structure.yaml --no-cache --no-share
```

```bash
cd evals
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
promptfoo validate config -c promptfooconfig.structure.yaml
```

---

## Slide bodies eval (`outline_then_structure_then_slide_content`)

Full chain: same outline **`vars`** plus **`layout_json`**. After structure picks an index per slide, **slide generation uses that layout’s schema** (not a single global schema). Tests in `tests/slide-content/core.yaml` use the small **`eval-default.json`** catalog. Rubrics target **`rendered_slide_bodies`** only.

```bash
cd evals
source .venv/bin/activate
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
export OPENAI_API_KEY="sk-..."
promptfoo eval -c promptfooconfig.slides.yaml --no-cache --no-share
```

```bash
cd evals
export PROMPTFOO_PYTHON="$PWD/.venv/bin/python"
promptfoo validate config -c promptfooconfig.slides.yaml
```

---

## Repo layout

| Path | Purpose |
|------|---------|
| `promptfooconfig.yaml` | Default entrypoint: env, provider, assertions, **outline-only** `tests` list |
| `promptfooconfig.structure.yaml` | Outline → structure (layout) chain; loads `tests/structure/core.yaml` |
| `provider.py` | Builds LLM messages from each test’s `vars` and `stage` |
| `tests/outline/core.yaml` | Twelve outline tests (six from `Best.csv`, six from `Poor.csv`) |
| `tests/structure/core.yaml` | Eleven chained outline→layout scenarios (`standard.json`) |
| `promptfooconfig.slides.yaml` | Outline → structure → slide bodies; loads `tests/slide-content/core.yaml` |
| `tests/slide-content/core.yaml` | Three chained deck scenarios (`eval-default.json` catalog) |
| `data/user-prompts/` | `Best.csv` / `Poor.csv` — source library text for curated outline tests |
| `schemas/layouts/` | Canonical layout JSON; tests use `layout_json: file://schemas/layouts/...` |
| `prompts/` | System/user templates + `provider_placeholder.txt` |

Shared Python modules (`contracts.py`, `messages_builder.py`, …) live next to `provider.py` and are importable because the provider adds this directory to `sys.path`.

---

## Outline `vars` contract

See the header comment in `tests/outline/core.yaml`. Values align with `servers/fastapi/models/generate_presentation_request.py`, tone/verbosity enums, plus eval-only `stage` and `web_search`.

For **`outline_then_structure`** and **`outline_then_structure_then_slide_content`**, add **`layout_json`** (and optional **`structure_instructions`** for the layout step only).
