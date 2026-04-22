"""Gemini 2.5 Flash batch classifier.

Feeds a chunk of screenshots + the classification prompt to Gemini, parses
back a JSON array with {category, caption, confidence} per image.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
from typing import Iterable

from google import genai
from google.genai import types

VALID_CATEGORIES = {"車宿", "AI新知", "對談", "記錄資料", "其他"}
BATCH_SIZE = 10
MODEL = "gemini-2.5-flash"


def _load_prompt() -> str:
    return pathlib.Path(__file__).parent.parent.joinpath("prompts/classify_prompt.txt").read_text(encoding="utf-8")


def _extract_json(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalize(raw: dict) -> dict:
    cat = raw.get("category", "其他")
    if cat not in VALID_CATEGORIES:
        cat = "其他"
    conf = float(raw.get("confidence", 0.0))
    if conf < 0.6:
        cat = "其他"
    return {
        "category": cat,
        "caption": (raw.get("caption") or "").strip()[:30],
        "confidence": conf,
    }


def classify_batch(paths: list[pathlib.Path]) -> list[dict]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts: list[types.Part] = [types.Part.from_text(text=_load_prompt())]
    for p in paths:
        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg"))

    resp = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    data = _extract_json(resp.text)
    if len(data) != len(paths):
        raise ValueError(f"Gemini returned {len(data)} items for {len(paths)} inputs")
    return [_normalize(d) for d in data]


def classify_all(paths: Iterable[pathlib.Path]) -> list[dict]:
    paths = list(paths)
    results: list[dict] = []
    for i in range(0, len(paths), BATCH_SIZE):
        chunk = paths[i : i + BATCH_SIZE]
        batch_res = classify_batch(chunk)
        for path, r in zip(chunk, batch_res):
            r["path"] = str(path)
            r["id"] = path.stem
            results.append(r)
    return results
