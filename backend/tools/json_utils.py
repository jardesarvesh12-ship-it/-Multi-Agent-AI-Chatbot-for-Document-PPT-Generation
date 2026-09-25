"""
json_utils.py — Robust JSON parsing and repair utilities for LLM outputs.
Handles common LLM JSON syntax issues such as unescaped quotes, trailing commas,
control characters, markdown blocks, and truncated JSON.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any, Optional, Union

from loguru import logger


def parse_llm_json(raw: str, default: Union[dict, list, None] = None) -> Any:
    """
    Safely parse JSON from LLM output, applying multiple repair strategies.

    Args:
        raw: Raw string response from LLM.
        default: Fallback value if parsing completely fails.

    Returns:
        Parsed JSON object (dict or list), or default value.
    """
    if not raw or not isinstance(raw, str):
        return default if default is not None else {}

    cleaned = raw.strip()

    # 1. Strip markdown code fences if present
    if "```" in cleaned:
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = re.sub(r"```(?:json)?", "", cleaned).replace("```", "").strip()

    # 2. Extract JSON container bounds ([...] or {...})
    first_bracket = cleaned.find("[")
    first_brace = cleaned.find("{")

    start = -1
    end = -1
    is_array = False

    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        start = first_bracket
        end = cleaned.rfind("]") + 1
        is_array = True
    elif first_brace != -1:
        start = first_brace
        end = cleaned.rfind("}") + 1
        is_array = False

    if start != -1:
        if end > start:
            json_str = cleaned[start:end]
        else:
            json_str = cleaned[start:]
            # Append missing closing brackets if truncated
            open_brackets = json_str.count("[") - json_str.count("]")
            open_braces = json_str.count("{") - json_str.count("}")
            json_str += "}" * max(0, open_braces) + "]" * max(0, open_brackets)
    else:
        json_str = cleaned

    if default is None:
        default = [] if is_array else {}

    # Attempt 1: Direct json.loads
    try:
        return json.loads(json_str)
    except Exception:
        pass

    # Attempt 2: Clean trailing commas before closing braces/brackets
    repaired = re.sub(r",\s*([}\]])", r"\1", json_str)
    try:
        return json.loads(repaired)
    except Exception:
        pass

    # Attempt 3: Fix unescaped control characters (newlines/tabs inside string values)
    try:
        # strict=False allows unescaped control chars like \n inside strings in json.loads
        return json.loads(repaired, strict=False)
    except Exception:
        pass

    # Attempt 4: Clean control characters manually
    repaired_ctrl = re.sub(r"[\x00-\x1F\x7F]", " ", repaired)
    try:
        return json.loads(repaired_ctrl, strict=False)
    except Exception:
        pass

    # Attempt 5: Safe ast.literal_eval fallback
    try:
        py_str = (
            repaired.replace("true", "True")
            .replace("false", "False")
            .replace("null", "None")
        )
        res = ast.literal_eval(py_str)
        if isinstance(res, (dict, list)):
            return res
    except Exception:
        pass

    # Attempt 6: Regex extraction for objects inside arrays
    if is_array:
        items = []
        obj_matches = re.finditer(r"\{[^{}]*\}", repaired, re.DOTALL)
        for m in obj_matches:
            try:
                items.append(json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)), strict=False))
            except Exception:
                pass
        if items:
            return items

    logger.warning(f"[JSON Utils] Failed to parse JSON from LLM output. Raw snippet: {raw[:150]}...")
    return default
