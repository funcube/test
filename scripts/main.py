"""Orchestrate: fetch → classify → rename → summarize → notify → persist state."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import classify
import google_photos
import rename as rename_mod
import summarize
import telegram_notify

ROOT = pathlib.Path(__file__).parent.parent
STATE_FILE = ROOT / "state" / "processed.json"
MANIFEST_FILE = ROOT / "state" / "last_batch.json"
TMP_DIR = ROOT / "tmp_shots"
SUMMARIZE_CATEGORIES = {"車宿", "AI新知", "記錄資料"}
MAX_PROCESSED_IDS = 5000


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_manifest(entries: list[dict]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "items": entries,
    }
    MANIFEST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Skip Telegram push, print to stdout instead")
    args = parser.parse_args()

    load_dotenv()
    lookback = int(os.environ.get("LOOKBACK_DAYS", "2"))
    archive_env = os.environ.get("ARCHIVE_DIR", "").strip()
    archive_dir = pathlib.Path(archive_env).expanduser() if archive_env else None

    state = load_state()
    processed: set[str] = set(state.get("processed_ids", []))

    print(f"[fetch] listing screenshots from the last {lookback} day(s)...")
    creds = google_photos.load_credentials()
    items = [it for it in google_photos.list_recent_screenshots(creds, lookback) if it["id"] not in processed]
    print(f"[fetch] {len(items)} new screenshot(s) to process")

    if not items:
        msg = f"📸 過去 {lookback} 天沒有新截圖，休息一下。"
        if args.dry_run:
            print(msg)
        else:
            telegram_notify.send(msg)
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return 0

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    items_map: dict[str, dict] = {}
    paths: list[pathlib.Path] = []
    for it in items:
        try:
            path = google_photos.download_item(it, TMP_DIR)
            paths.append(path)
            items_map[it["id"]] = {"item": it, "path": path}
        except Exception as e:
            print(f"[download] skip {it['id']}: {e}")

    print(f"[classify] running Gemini on {len(paths)} image(s)...")
    results = classify.classify_all(paths)

    print(f"[rename] renaming {len(results)} file(s){' + archiving to ' + str(archive_dir) if archive_dir else ''}...")
    for r in results:
        meta = items_map.get(r["id"])
        if not meta:
            continue
        creation_time = meta["item"].get("mediaMetadata", {}).get("creationTime") or datetime.now(timezone.utc).isoformat()
        new_name = rename_mod.compute_name(creation_time, r["category"], r["caption"])
        new_path = rename_mod.rename_and_archive(meta["path"], new_name, archive_dir)
        r["path"] = str(new_path)
        r["filename"] = new_path.name
        r["product_url"] = meta["item"].get("productUrl", "")

    buckets: dict[str, list[dict]] = {}
    for r in results:
        buckets.setdefault(r["category"], []).append(r)

    print(f"[classify] distribution: { {k: len(v) for k, v in buckets.items()} }")

    summaries: dict[str, str] = {}
    for cat, entries in buckets.items():
        if cat not in SUMMARIZE_CATEGORIES:
            continue
        print(f"[summarize] {cat}: {len(entries)} image(s)")
        cat_paths = [pathlib.Path(e["path"]) for e in entries]
        try:
            summaries[cat] = summarize.summarize_category(cat, cat_paths)
        except Exception as e:
            print(f"[summarize] {cat} failed: {e}")
            summaries[cat] = "（摘要失敗，請手動檢視）"

    date_str = datetime.now().strftime("%Y-%m-%d")
    report = telegram_notify.build_report(date_str, len(results), buckets, summaries)

    if args.dry_run:
        print("\n" + "=" * 40 + " REPORT " + "=" * 40)
        print(report)
    else:
        telegram_notify.send(report)
        print("[notify] sent to Telegram")

    save_manifest(results)
    print(f"[manifest] saved to {MANIFEST_FILE}")

    new_ids = [r["id"] for r in results]
    all_ids = list(processed) + new_ids
    state["processed_ids"] = all_ids[-MAX_PROCESSED_IDS:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print(f"[state] saved ({len(state['processed_ids'])} ids tracked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
