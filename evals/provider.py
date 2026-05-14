"""
Promptfoo provider: Presenton outline / structure / slide-content via llmai only.

Supported stages:
  - outline — user brief → outline JSON only
  - outline_then_structure — outline LLM, then per-slide layout indices (requires layout_json)
  - outline_then_structure_then_slide_content — outline → layout indices → slide JSON **for each chosen layout’s
    schema** (slide content step depends on structure: `response_schema` = selected layout’s `json_schema` per slide).
    Same sequencing as production `presentation.py`. Returns outline, structure, slides, rendered_slide_bodies.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _discover_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "app_data").exists() and (candidate / "evals").exists():
            return candidate
    return start.parent


_REPO_ROOT = _discover_repo_root(_ROOT)

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import env_sync  # noqa: E402
import layout_load  # noqa: E402
import llm_env  # noqa: E402
import messages_builder  # noqa: E402
import structured_gen  # noqa: E402
from contracts import (  # noqa: E402
    PresentationLayoutModel,
    PresentationOutlineModel,
    get_presentation_structure_model_with_n_slides,
)
from llmai import get_client  # noqa: E402
from llmai.shared import JSONSchemaResponse, WebSearchTool  # noqa: E402
from schema_tools import prepare_schema_for_json_schema_response  # noqa: E402


def _vars_bool(vars_: dict, key: str, default: bool = False) -> bool:
    return messages_builder._as_bool(vars_.get(key), default)


def _structure_vars_for_outline_chain(vars_: dict) -> dict:
    """Vars copy for structure after an outline: layout-only instructions unless structure_instructions is set."""
    structure_vars = dict(vars_)
    si = structure_vars.get("structure_instructions")
    if si is None or not str(si).strip():
        structure_vars["instructions"] = (
            "For each outline slide, choose the catalog layout index that best fits its markdown. "
            "Use TOC layouts only for real table-of-contents slides; use chart-capable layouts for "
            "numeric markdown tables when appropriate; prefer visual variety when multiple layouts fit."
        )
    else:
        structure_vars["instructions"] = str(si)
    return structure_vars


async def _generate_outline(client, model: str, vars_: dict) -> dict:
    messages = messages_builder.build_outline_messages(vars_)
    model_cls = messages_builder.outline_response_model_class(vars_)
    schema = prepare_schema_for_json_schema_response(model_cls.model_json_schema())
    response_format = JSONSchemaResponse(
        name="response",
        json_schema=schema,
        strict=True,
    )
    tools = [WebSearchTool()] if _vars_bool(vars_, "web_search") else None
    return await structured_gen.generate_structured(
        client,
        model,
        messages,
        response_format=response_format,
        tools=tools,
    )


async def _generate_structure(
    client,
    model: str,
    vars_: dict,
    outline_payload: dict,
) -> dict:
    structure_vars = dict(vars_)
    structure_vars["outline_slides_json"] = json.dumps(outline_payload, ensure_ascii=False)
    if structure_vars.get("n_slides") in (None, "", "auto", "auto-detect"):
        structure_vars["n_slides"] = len(outline_payload.get("slides", []))

    messages = messages_builder.build_structure_messages(structure_vars)
    n = int(structure_vars["n_slides"])
    model_cls = get_presentation_structure_model_with_n_slides(n)
    schema = prepare_schema_for_json_schema_response(model_cls.model_json_schema())
    response_format = JSONSchemaResponse(
        name="response",
        json_schema=schema,
        strict=True,
    )
    return await structured_gen.generate_structured(
        client,
        model,
        messages,
        response_format=response_format,
    )


def _prepare_slide_schema(raw_schema: dict) -> dict:
    """Mirror production behavior: remove image URL placeholders and require speaker note."""
    schema = deepcopy(raw_schema)
    removable = {"__image_url__", "__icon_url__"}

    def _walk(node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for field in removable:
                    props.pop(field, None)
            required = node.get("required")
            if isinstance(required, list):
                node["required"] = [field for field in required if field not in removable]
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(schema)
    props = schema.setdefault("properties", {})
    if not isinstance(props, dict):
        props = {}
        schema["properties"] = props
    props["__speaker_note__"] = {
        "type": "string",
        "minLength": 100,
        "maxLength": 500,
        "description": "Speaker note for the slide",
    }
    required = schema.setdefault("required", [])
    if not isinstance(required, list):
        required = []
        schema["required"] = required
    if "__speaker_note__" not in required:
        required.append("__speaker_note__")
    return prepare_schema_for_json_schema_response(schema)


async def _generate_slide_content(
    client,
    model: str,
    vars_: dict,
    *,
    slide_markdown: str,
    response_schema: dict,
) -> dict:
    slide_vars = dict(vars_)
    slide_vars["slide_markdown"] = slide_markdown
    slide_vars["response_schema_json"] = json.dumps(response_schema, ensure_ascii=False)
    if slide_vars.get("slide_instructions"):
        slide_vars["instructions"] = slide_vars.get("slide_instructions")

    messages = messages_builder.build_slide_messages(slide_vars)
    schema = prepare_schema_for_json_schema_response(response_schema)
    response_format = JSONSchemaResponse(
        name="response",
        json_schema=schema,
        strict=False,
    )
    return await structured_gen.generate_structured(
        client,
        model,
        messages,
        response_format=response_format,
    )


async def _run_stage(*, vars_: dict) -> str:
    env_sync.sync_user_config_into_env(_REPO_ROOT)
    llm = (os.environ.get("LLM") or "").strip().lower()
    if not llm:
        inferred = env_sync.infer_llm_provider()
        if not inferred:
            raise ValueError(
                "Set LLM (e.g. export LLM=anthropic) and the matching API key, "
                "or load userConfig.json via USER_CONFIG_PATH / APP_DATA_DIRECTORY."
            )
        os.environ["LLM"] = inferred

    client = get_client(config=llm_env.get_llm_config())
    model = llm_env.get_model()

    stage = str(vars_.get("stage", "outline")).strip().lower()
    if stage == "outline":
        content = await _generate_outline(client, model, vars_)
        return json.dumps(content, ensure_ascii=False)
    elif stage == "outline_then_structure":
        if not vars_.get("layout_json"):
            raise ValueError("outline_then_structure requires layout_json")
        outline_payload = await _generate_outline(client, model, vars_)
        structure_vars = _structure_vars_for_outline_chain(vars_)
        structure_payload = await _generate_structure(
            client, model, structure_vars, outline_payload
        )
        return json.dumps(
            {"outline": outline_payload, "structure": structure_payload},
            ensure_ascii=False,
        )
    elif stage == "outline_then_structure_then_slide_content":
        # Same sequencing as production presentation generation (see presentation.py):
        #   1) outline  2) structure (layout index per slide)  3) slide content — each slide’s structured output
        #   uses the JSON schema of **that slide’s chosen layout** (layout index from step 2), not a fixed schema.
        if not vars_.get("layout_json"):
            raise ValueError("outline_then_structure_then_slide_content requires layout_json")
        outline_payload = await _generate_outline(client, model, vars_)
        outline_model = PresentationOutlineModel.model_validate(outline_payload)
        structure_vars = _structure_vars_for_outline_chain(vars_)
        structure_payload = await _generate_structure(
            client, model, structure_vars, outline_payload
        )
        structure_slides = list(structure_payload.get("slides", []))
        if len(structure_slides) != len(outline_model.slides):
            raise ValueError(
                "outline_then_structure_then_slide_content mismatch: structure slide count != outline slide count"
            )
        layout = PresentationLayoutModel.model_validate_json(
            layout_load.resolve_layout_json(vars_["layout_json"])
        )
        rendered_slides: list[dict] = []
        for i, slide_outline in enumerate(outline_model.slides):
            layout_index = int(structure_slides[i])
            if layout_index < 0 or layout_index >= len(layout.slides):
                raise ValueError(
                    f"outline_then_structure_then_slide_content invalid layout index {layout_index} at slide {i + 1}"
                )
            selected_layout = layout.slides[layout_index]
            response_schema = _prepare_slide_schema(selected_layout.json_schema)
            slide_body = await _generate_slide_content(
                client,
                model,
                vars_,
                slide_markdown=slide_outline.content,
                response_schema=response_schema,
            )
            rendered_slides.append(
                {
                    "slide_number": i + 1,
                    "layout_index": layout_index,
                    "layout_id": selected_layout.id,
                    "content": slide_body,
                }
            )
        rendered_slide_bodies: list[dict] = [row["content"] for row in rendered_slides]
        return json.dumps(
            {
                "outline": outline_payload,
                "structure": structure_payload,
                "slides": rendered_slides,
                "rendered_slide_bodies": rendered_slide_bodies,
            },
            ensure_ascii=False,
        )
    else:
        raise ValueError(f"Unknown stage: {stage}")


def call_api(prompt: str, options: dict, context: dict) -> dict:
    del prompt
    del options
    vars_ = context.get("vars") or {}

    try:
        out = asyncio.run(_run_stage(vars_=vars_))
        json.loads(out)
        return {"output": out}
    except Exception as e:
        return {"output": "", "error": str(e)}
