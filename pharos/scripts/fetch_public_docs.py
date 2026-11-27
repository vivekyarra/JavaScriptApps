"""Download the public documents used for the real-document regression and verify their hashes.

Files are NOT committed (they are the publishers' copyrighted documents). Usage:
    python scripts/fetch_public_docs.py [--dest .cache/public_docs]
A document whose hash no longer matches is reported, never silently accepted: publishers revise files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / ".cache" / "public_docs"))
    args = ap.parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    bad = 0
    for m in json.loads((ROOT / "data" / "public_docs_manifest.json").read_text(encoding="utf-8")):
        target = dest / m["file"]
        if not target.exists():
            try:
                req = urllib.request.Request(m["url"], headers={"User-Agent": "Mozilla/5.0 (pharos regression fetch)"})
                target.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            except Exception as exc:
                print(f"FAILED  {m['file']}: {exc}")
                bad += 1
                continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        status = "ok" if digest == m["sha256"] else "HASH CHANGED (publisher revised the file; results not comparable)"
        bad += status != "ok"
        print(f"{status:8} {m['file']}  {m['url']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
