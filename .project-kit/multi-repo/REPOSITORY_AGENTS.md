# Repository guidance

Template: copy as this repository's `AGENTS.md` and fill in the fields. This template is instructional, not an executable project configuration.

- Role: describe this component's responsibility and data it owns.
- Shared agreements: `../.project-kit/AGENTS.md` in the illustrated sibling-repo layout; read these explicitly.
- Shared system context: `../.project-kit/PROJECT_BRIEF.md` in that layout. Replace with the actual accessible canonical location; nested repos need more parent segments.
- Shared task/state location: specify the coordinator's location. If shared context is missing and affects the change, report it rather than inferring critical business or authorization rules.
- Local context: name maintained README/design/contract files and when they are relevant.
- Stack/version source: point to actual build/runtime configuration instead of duplicating versions that will go stale.
- Working directory and checks: document the actual setup, focused test, required lint/build, and integration commands for this repo. State dependencies or services required to run them; do not invent commands.
- Final review: review the entire implementation diff using the shared checklist, including new/staged/unstaged files. Report findings in a read-only review before any review-driven fixes; fixes require explicit authorization. Never commit unless explicitly asked.
- Compatibility and boundaries: specify important API/event contracts, data/tenant ownership, authentication expectations, and related consumers/providers.
- Database context: link the coordinator's canonical `DATABASES.md` and environment map (replace illustrative `../` paths). Record owned schemas/collections, migration ownership/tool, state-dependent checks and disposable fixture setup. Keep only private connection-profile paths/aliases here; local clients read secrets without displaying them. No shared/prod writes from routine tests or startup migrations.
- Local conventions: record only useful repository-specific patterns or recurring review corrections; inherit universal rules instead of copying them.
- Shared Cursor conventions: link existing `.cursor/rules` or legacy `.cursorrules` and note relevant scope/authoritative sources. Read applicable rules alongside this file; do not copy their bodies or silently rewrite them. Resolve material contradictions against explicit user/higher-priority instructions; request clarification only when an unresolved choice affects the task.
- Ongoing tasks: link to shared task context when this repo participates in coordinated work. Record its branch/revision and check results in that task; avoid a second competing progress narrative.
