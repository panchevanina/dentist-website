# Related-repository workspace guidance

Template: copy as the coordinator's `AGENTS.md` and adapt paths. Universal rules are expected from global guidance or one explicitly linked shared rules file.

Installed kit: read `.project-kit/AGENTS.md` for shared agreements. Supporting paths below are relative to `.project-kit/` in the coordinator; adjust any explicit tool/config paths accordingly. Keep this coordinator file short and route to the canonical documents.

- Use `PROJECT_BRIEF.md` for the system overview and repository map. For a maintenance task, treat the requested change or linked issue as current scope; do not interpret the overview as permission to rebuild the system.
- At the start of ongoing work, read `STATE.md` and the relevant linked task/plan. Confirm important facts against current code and contracts.
- Identify the affected repositories and integration boundaries. Before editing each repository, read its root `AGENTS.md` and any applicable instructions along the path to the target files. Read related repositories only as needed.
- Include relevant shared Cursor guidance: discover `.cursor/rules/**/*.mdc`, legacy `.cursorrules` and task-relevant nested rule locations in the coordinator and affected repos. Select by metadata/file/workflow scope rather than loading every repo's rules. Preserve team files and report meaningful instruction conflicts; link the canonical `CURSOR_COMPATIBILITY.md` if available.
- Perform Git operations, builds, and tests in the intended repository. Confirm its branch/worktree and preserve unrelated local changes.
- If this workspace uses the shared multi-git manager, document its script/agent-guide paths and use this workspace's `multi-git.conf`. Inspect selected status first, use task-owned repo IDs, review diffs before supplying commit messages, and record relevant run IDs for guarded local rollback. Publish only when explicitly requested.
- For small compatible fixes/features, implement and verify directly. For material architecture, migration, authentication/data-boundary, or rollout decisions, prepare a concrete plan and wait for agreement before dependent implementation.
- After implementation, review the entire implementation diff across affected repos using the shared post-implementation checklist. Keep that review read-only and report findings before review-driven fixes; fix only when explicitly authorized. Do not commit unless explicitly asked.
- Preserve API/event compatibility unless a change is explicitly requested or agreed. Check affected providers/consumers and data ownership where relevant.
- Database work: use this workspace's canonical `DATABASES.md` and non-secret `database/ENVIRONMENTS.json`. Select an explicit target, verify state/ownership, use disposable local fixtures, and prepare shared-environment changes before any missing approval. Local clients consume private credentials outside all Git roots; never display those files, secret-bearing logs or private records to the agent or internet. Document actual guide/map paths if they differ.
- Keep durable task context when work spans sessions or repos: affected components, ownership, branch/revision, decisions, verification, and the next step. Use `STATE.md` as a short snapshot/index; link rather than duplicate details.
- Update shared context only when relevant facts or boundaries change. Record inferences and unknowns explicitly. Do not scan every repo or reread every document for each fix.
