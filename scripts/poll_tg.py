"""Poll Telegram getUpdates, download PDF documents into data/raw/.

Designed to be run as a long-lived loop on the build droplet (or locally).

Usage:
    TG_BOT_TOKEN=... TG_CHAT_ID=... python scripts/poll_tg.py [--once] [--target-dir data/raw]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def _api(token: str, method: str, params: dict | None = None) -> dict:
    qs = "&".join(f"{k}={quote(str(v))}" for k, v in (params or {}).items())
    url = f"https://api.telegram.org/bot{token}/{method}"
    if qs:
        url += f"?{qs}"
    with urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def download_file(token: str, file_id: str, dest: Path) -> Path:
    info = _api(token, "getFile", {"file_id": file_id})
    if not info.get("ok"):
        raise RuntimeError(f"getFile failed: {info}")
    file_path = info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(file_url, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def poll_once(token: str, chat_id: int, target_dir: Path,
              offset: int | None = None) -> tuple[list[Path], int | None]:
    params = {"timeout": 0, "limit": 50}
    if offset is not None:
        params["offset"] = offset
    res = _api(token, "getUpdates", params)
    if not res.get("ok"):
        raise RuntimeError(f"getUpdates failed: {res}")
    downloaded: list[Path] = []
    next_offset: int | None = offset
    for u in res["result"]:
        next_offset = u["update_id"] + 1
        msg = u.get("message") or u.get("channel_post") or {}
        if (msg.get("from", {}).get("id") != chat_id
                and msg.get("chat", {}).get("id") != chat_id):
            continue
        doc = msg.get("document")
        if not doc:
            continue
        name = doc.get("file_name", f"file_{doc['file_id'][:8]}.bin")
        size = doc.get("file_size", 0)
        dest = target_dir / name
        if dest.exists() and dest.stat().st_size == size:
            print(f"[skip] {name} already present ({size} B)")
            continue
        print(f"[grab] {name} ({size} B)")
        downloaded.append(download_file(token, doc["file_id"], dest))
    return downloaded, next_offset


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dir", default="data/raw")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv)
    token = os.environ["TG_BOT_TOKEN"]
    chat_id = int(os.environ["TG_CHAT_ID"])
    target = Path(args.target_dir)
    offset: int | None = None
    while True:
        try:
            downloaded, offset = poll_once(token, chat_id, target, offset)
            if downloaded:
                names = ", ".join(p.name for p in downloaded)
                print(f"  → downloaded {len(downloaded)}: {names}", flush=True)
        except Exception as e:
            print(f"  ! poll error: {e}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
