"""Telegram Bot notifier.

Splits long messages to satisfy the 4096-char limit and posts them in order.
"""
from __future__ import annotations

import os
import time

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4000


def _chunks(text: str) -> list[str]:
    if len(text) <= MAX_LEN:
        return [text]
    parts, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > MAX_LEN:
            parts.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        parts.append(buf)
    return parts


def send(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = API.format(token=token)
    for part in _chunks(text):
        r = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": part,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        r.raise_for_status()
        time.sleep(0.3)


CATEGORY_ICON = {
    "車宿": "🚐",
    "AI新知": "🤖",
    "對談": "🗑️",
    "記錄資料": "📋",
    "其他": "📦",
}


def build_report(date_str: str, total: int, buckets: dict[str, list[dict]], summaries: dict[str, str]) -> str:
    lines = [f"📸 <b>{date_str} 截圖整理</b>（共 {total} 張）", ""]

    order = ["車宿", "AI新知", "記錄資料", "對談", "其他"]
    for cat in order:
        items = buckets.get(cat, [])
        if not items:
            continue
        icon = CATEGORY_ICON[cat]
        lines.append(f"{icon} <b>{cat}</b>（{len(items)} 張）")
        if cat == "對談":
            lines.append("內容為聊天對話，建議直接刪除。")
            lines.append("👉 <a href=\"https://photos.google.com/search/screenshots\">在 Google Photos 檢視</a>")
        else:
            summary = summaries.get(cat, "").strip()
            if summary:
                lines.append(summary)
            else:
                for it in items[:5]:
                    lines.append(f"• {it.get('caption', '')}")
        lines.append("")
    return "\n".join(lines).rstrip()
