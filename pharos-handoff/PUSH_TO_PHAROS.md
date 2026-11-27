# Getting this into kittu181707/pharos

The build session could not push to `kittu181707/pharos` (403: no GitHub access for that repo from the session). The full work is here two ways:

1. `pharos.bundle` — 19 commits on top of the repo's existing commit `4976cc4` (the teammate's calculators), authored by vivekyarra.
2. `../pharos/` — a plain copy of the working tree (no `.git`, no `.venv`, no database).

## From the bundle (keeps history)

```sh
git clone https://github.com/kittu181707/pharos && cd pharos
git fetch /path/to/pharos.bundle main
git merge --ff-only FETCH_HEAD        # fast-forward from 4976cc4
git push origin main
```

## Verify after pushing

```sh
uv sync --locked && uv run --locked pytest -q     # 176 tests
uv run --locked python scripts/fetch_public_docs.py   # optional: fetch 14 public PDFs for the invariant tests
```

Facts to fill in before submitting (nothing in the repo invents them): team names and affiliations, Students/Professionals division, repository link, video upload link, IP terms.
