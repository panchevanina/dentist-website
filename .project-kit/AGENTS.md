# Software development working agreements

## Context and efficiency

- Briefly state the outcome for substantial tasks. Use `PROJECT_BRIEF.md` for system context; the current request/task defines the change. Read `STATE.md` and relevant linked task/plan when starting or resuming ongoing work. Confirm facts against relevant code/contracts.
- Search before broad reads. Read other documents only as needed; avoid rereading unchanged material, unnecessary browsing, and verbose output.
- Follow existing conventions and implement the agreed scope with the simplest maintainable solution. Avoid unrelated refactors and speculative features.
- Across repositories, read each affected repo's `AGENTS.md` before editing, including applicable nested guidance. Run Git/checks in that repo; inspect relevant providers/consumers without scanning unrelated components.
- Also check the coordinator and each affected repo for `.cursor/rules/**/*.mdc` and legacy `.cursorrules`, including task-relevant nested locations. Read metadata to select applicable always-on, file-scoped, relevant workflow or explicitly requested rules; treat their bodies as shared project guidance. Use `CURSOR_COMPATIBILITY.md` when interpreting scope. Preserve colleagues' rules, avoid duplicating them, and flag meaningful conflicts; they do not override the user's instructions, higher-priority requirements or secret/access boundaries.
- State reversible assumptions and continue. Group questions about materially different requirements, public contracts, or data models.
- Use one agent by default; delegate only on explicit user request. Give agents bounded tasks and relevant context, and record ownership and integration status.

## Planning and agreement

- Implement and verify small, localized, reversible changes without separate plan approval.
- For complex work—new applications, significant refactors, consequential migrations, or material API/data/security/rollout decisions—investigate and write `plans/<task>.md` using `plans/TEMPLATE.md`. Repository count alone does not require a formal plan.
- A small maintenance request needs no new brief or task file. Use the existing issue or `tasks/<id>.md` when work spans sessions or needs coordination; link to a substantial plan instead of duplicating it.
- Present its key choices and ask for agreement. Wait for explicit agreement before dependent implementation; read-only investigation and drafting may continue.
- Record agreement and constraints, then complete routine steps without repeated approval. Obtain renewed agreement for material changes to scope, architecture, cost, or risk.

## Code and verification

- Use clear names, cohesive functions, and existing formatting. Comment non-obvious intent and constraints.
- Validate untrusted input and handle expected failures at boundaries. Preserve useful errors; avoid blanket catches, silent failures, and logging secrets.
- Run required project checks and focused checks of affected behavior. Add regression coverage for bugs and tests for consequential new behavior; avoid low-impact tests that merely repeat the implementation.
- Fix implementation/test failures within the authorized task and rerun affected checks. Broaden or repeat verification only when changes, failures, or unresolved risks justify it. Keep the final review below separate from implementation fixes.
- Distinguish executed checks from manual review and checks not run. Record blockers and exact next checks; never claim unexecuted checks passed. Briefly explain material bug causes and flag unrelated findings separately.

## Post-implementation diff review

- After implementation and relevant checks, review the entire implementation diff as if reviewing a pull request. Include staged and unstaged changes and new files across every affected repository; distinguish pre-existing unrelated edits and preserve secret-file boundaries.
- Look specifically for regressions, edge cases, concurrency issues, incorrect null handling, backwards compatibility, security issues, unnecessary changes, and missing tests.
- Keep this review read-only: do not modify files or silently fix findings. Report findings first, with severity, file/location, impact and supporting evidence; distinguish confirmed defects from questions. If none are found, say so and identify material verification gaps without claiming the code is error-free.
- Apply review-driven fixes only when explicitly authorized by the user, either in the existing task or a subsequent instruction. Otherwise stop with the findings report. A review-only request does not authorize fixes. After authorized fixes, rerun affected checks and review the resulting diff again.
- Do not commit anything unless explicitly asked. Approval to plan, implement, test or review is not permission to create commits.

## Continuity

- Update `STATE.md` at meaningful milestones, blockers, and before ending or handing off substantial work. Skip bookkeeping for trivial tasks unrelated to ongoing work.
- Keep a current 150–300-word snapshot: goal, completed work, decisions/reasons, active plan/approval, changed files, verification evidence, blockers, and next step. Link to details and replace stale entries.
- For concurrent work, let `STATE.md` index separate task files/owners; preserve other tasks' entries. Track relevant branches/revisions and integration dependencies for coordinated changes.
- Use this snapshot for handoffs; avoid duplicate compression summaries. Respect resource limits and report when further progress requires missing access, information, or external changes.
- Usage tracking runs in a separate local collector. Consult its guide only when needed; do not invoke it per agent command. Keep unavailable counts as `null` and estimates separate. Never invent per-command costs or reread the usage ledger for each task.

## Database state and secrets

- For database-dependent work, read `DATABASES.md` and the canonical non-secret environment map; confirm each repo's data/migration ownership. Select an explicit environment and verify target identity, schema/migration baseline, privileges and data scope before acting. Never infer environment from a Git branch or fall back to another profile.
- Prefer synthetic fixtures on verified disposable local databases. Do not run broad tests or automatic startup migrations against shared environments. Prepare exact artifacts, checks and recovery before requesting any missing authorization for dev/staging/prod changes; existing specific approval persists within scope. Production access must be explicitly authorized.
- Credentials and keys belong in private local files outside every Git root. The local client consumes them; do not return their contents through file reads, shell output, arguments, prompts, web requests, logs or screenshots. Read only non-secret connection metadata. Capture raw client output privately and expose reviewed allowlisted summaries; never read raw credential-bearing logs into agent context.
- Use database-enforced least privilege and verified remote TLS. Keep deployed-state/fixture evidence and environment aliases in task/state files without raw data or secrets. Git rollback does not restore database state. Instructions and ignored files are not a technical secret-isolation boundary; respect configured access controls.

## Multi-repository Git operations

- When a workspace configures the shared multi-git manager, read its linked agent guide for Git workflows. Inspect selected repo status, use explicit task-owned repo IDs, preserve unrelated edits, and record relevant run IDs for recovery. Commit only when explicitly asked; messages must reflect reviewed diffs. Publish only when explicitly requested.

## Usage and completion

- Update `USAGE_EXAMPLES.txt` when operations change. Cover setup, start/restart/stop, tests, and deployment as applicable, with working directory, prerequisites, relevant defaults/values, expected results, and verification status.
- Use implemented commands; mark pending operations. Explain sources for user-specific values and environment secrets without exposing credentials.
- Prepare and check deployment artifacts before seeking any missing authorization to deploy or perform an irreversible action.
- Finish with changes, check results, limitations, and next action if needed. Claim completion only when acceptance criteria and required checks are satisfied; otherwise state what remains blocked.
