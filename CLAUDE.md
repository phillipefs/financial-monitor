# Financial Monitor Claude Guide

## Project Rules

- Treat `generate_dashboard.py` as the official dashboard generator and `dashboard.html` as generated output.
- Do not edit `dashboard.html` directly unless the user explicitly asks for a prototype or generated HTML patch.
- Keep unrelated user changes intact. Check `git status --short` before and after edits.
- Prefer narrow, verifiable changes. Run the smallest useful validation for the files touched.

## Shared Skills

- `.agents/skills/` is the canonical source for project skills.
- `.codex/skills/` and `.claude/skills/` are generated copies for each tool.
- Edit skills only in `.agents/skills/`.
- After changing a skill, run `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1`.
- Use `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1 -DryRun` to inspect the sync without writing.
- Do not edit `.claude/skills/` directly; the sync script will overwrite it.

## Dashboard Work

- After Python changes, run `python -m py_compile generate_dashboard.py`.
- After generator changes, run `python generate_dashboard.py` when data access is available.
- The generator may update `dashboard.html` and snapshot history as part of normal operation.
