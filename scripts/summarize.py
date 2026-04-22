"""Claude Sonnet 4.6 deep summarizer.

Takes screenshots of a single category, asks Claude to read them and produce
3-6 concise Traditional Chinese bullet points. Uses prompt caching on the
system prompt to save cost across categories in the same run.
"""
from __future__ import annotations

import base64
import os
import pathlib

import anthropic

MODEL = "claude-sonnet-4-6"
MAX_IMAGES_PER_CALL = 20


def _load_prompt_template() -> str:
    return pathlib.Path(__file__).parent.parent.joinpath("prompts/summarize_prompt.txt").read_text(encoding="utf-8")


def _image_block(path: pathlib.Path) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        },
    }


def summarize_category(category: str, paths: list[pathlib.Path]) -> str:
    if not paths:
        return ""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = _load_prompt_template().replace("{category}", category)

    paths = paths[:MAX_IMAGES_PER_CALL]
    content: list[dict] = [_image_block(p) for p in paths]
    content.append({"type": "text", "text": f"請針對以上 {len(paths)} 張「{category}」類截圖做重點整理。"})

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
    )
    return resp.content[0].text.strip()
