# Repository conventions

- Keep this tool independent of the neighboring math and editorial projects.
- Use Conventional Commits subjects (`feat:`, `fix:`, `chore:`, etc.) and a body
  explaining behavior, relevant validation, and material limitations.
- Use descriptive branch names without a `codex/` prefix.
- Preserve source documents, photographic image bytes, profiles, and nonblack
  colors. Publish the proof only after verification succeeds.
- Use disposable InDesign documents for native checks; do not modify user work.
- Run `.venv/bin/python -m unittest discover -s . -p 'test_*.py'` for converter
  changes. Native export/AppleScript changes also need an InDesign handoff check.
