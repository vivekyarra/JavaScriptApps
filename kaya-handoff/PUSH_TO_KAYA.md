# Push the KNOCK-ON app to kittu181707/kaya (about 30 seconds)

`kaya.bundle` is the full git history of the app: the existing initial commit plus 9 commits authored by vivekyarra, no co-author lines. It fast-forwards from the current `main` of `kittu181707/kaya`, so nothing there is overwritten.

Run this on your own machine, where you are signed in to GitHub as vivekyarra (for example with `gh auth login`):

```bash
git clone --depth 1 -b claude/wonderful-cannon-z8cnd0 https://github.com/vivekyarra/JavaScriptApps.git handoff
git clone handoff/kaya-handoff/kaya.bundle kaya -b main
cd kaya
git remote set-url origin https://github.com/kittu181707/kaya.git
git push -u origin main
```

Check afterwards: `git log --oneline | wc -l` shows 10 and `ls` shows `README.md run.sh knockon ui samples docs`.

Why it was not pushed from the cloud session: the session's GitHub link is gated at the identity level (`repo_not_connected`), so pushes to that repository are refused even though vivekyarra has write access. To let the session push directly, reconnect GitHub at https://claude.ai/connect-github while signed in as vivekyarra, and have the owner of `kittu181707/kaya` install the Claude GitHub App on that repository.
