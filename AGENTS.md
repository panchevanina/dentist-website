# Project instructions

## Installed development kit

- Read `.project-kit/AGENTS.md` for shared working agreements, including planning, verification, report-first final diff review and explicit commit authorization. Read applicable existing local/nested AGENTS and Cursor rules; report material conflicts instead of silently choosing an instruction set.
- Shared context: `.project-kit/PROJECT_BRIEF.md`, `.project-kit/STATE.md`, and task-relevant `.project-kit/tasks/` / `.project-kit/plans/`. The current task defines scope; the brief does not authorize rebuilding the system.
- Git operations: read `.project-kit/multi-git/AGENT_GUIDE.md`; invoke `.project-kit/multi-git/multi-git.sh` with `--config .project-kit/multi-git.conf` and explicit task-owned repo IDs. Run builds/tests in the affected repo.
- Database work: `.project-kit/DATABASES.md` and `.project-kit/database/ENVIRONMENTS.json`. Use explicit configured environments; local clients consume private credentials outside all Git roots without exposing them.
- Usage collector runs separately; see `.project-kit/usage/README.md`. Do not run it per agent command or invent token costs.
- Commands/checklist: `.project-kit/USAGE_EXAMPLES.txt`, `.project-kit/SETUP_CHECKLIST.md` and `.project-kit/OPTIONAL_CONFIG.md`. Ask only about facts that affect the task; keep unknowns explicit.
