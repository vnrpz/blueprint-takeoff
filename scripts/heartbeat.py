"""Telegram heartbeat — send a status ping every N minutes.

Usage:
    TG_BOT_TOKEN=... TG_CHAT_ID=... python scripts/heartbeat.py --interval 120 \
        --status-file runs/status.json
"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


def send(token: str, chat: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat}&parse_mode=Markdown&text={quote(text)}"
    with urlopen(url, timeout=15) as r:
        r.read()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=120, help="seconds")
    ap.add_argument("--status-file", default="runs/status.json")
    args = ap.parse_args(argv)
    token = os.environ["TG_BOT_TOKEN"]
    chat = int(os.environ["TG_CHAT_ID"])
    while True:
        status = {}
        sf = Path(args.status_file)
        if sf.exists():
            try:
                status = json.loads(sf.read_text())
            except Exception:
                pass
        text = "*heartbeat* — " + ", ".join(f"{k}={v}" for k, v in status.items() if k != "raw")
        try:
            send(token, chat, text or "*heartbeat* idle")
        except Exception as e:
            print(f"send error: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
