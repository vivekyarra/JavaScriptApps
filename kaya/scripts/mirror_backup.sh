#!/usr/bin/env bash
# Mirror the working tree into the session repo's designated branch (backup while upstream push is unavailable).
set -euo pipefail
SRC=/home/user/kaya
DST=/home/user/JavaScriptApps
cd "$DST"
mkdir -p kaya
rm -rf kaya && mkdir -p kaya
(cd "$SRC" && tar --exclude=.git --exclude=.venv --exclude=data --exclude=node_modules --exclude=__pycache__ --exclude=.pytest_cache -cf - .) | (cd kaya && tar -xf -)
git add -A kaya
if git diff --cached --quiet; then echo "nothing to mirror"; exit 0; fi
git -c user.name="vivekyarra" -c user.email="vivek@tabularis.dev" commit -q -m "${1:-Update KNOCK-ON app}"
git push -q -u origin claude/wonderful-cannon-z8cnd0 2>&1 | tail -3
git log --format='%h %an | %s' -1
