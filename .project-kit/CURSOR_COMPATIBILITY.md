# Shared instructions with Cursor users

This project must inspect its own applicable Cursor rules. The initializer preserves existing rules and does not infer their semantic compatibility. Follow the discovery and audit guidance below.

## File conventions

Cursor supports root and nested `AGENTS.md`; nested instructions apply to the relevant subtree. Its structured project rules are `.cursor/rules/*.mdc` files with frontmatter. Plain `.md` files there are not recognized as project rules. [Cursor rules reference](https://cursor.com/docs/rules).

| Frontmatter | Selection |
| --- | --- |
| `alwaysApply: true` | Always loaded |
| `alwaysApply: false` plus `globs` | Selected by matching files |
| `alwaysApply: false` plus `description`, no globs | Selected by relevance |
| `alwaysApply: false`, neither field | Manually selected with `@` |

These are Cursor loading semantics; our shared workflow explicitly routes agents to inspect relevant files rather than assuming another client implements the same selection engine. A rule file is instructional content, not executable shell configuration.

Legacy `.cursorrules` is being retired. Global preferences belong in Cursor's User Rules settings; they are separate from repository files. Rules are identified by full path: matching same-name rules can both apply, so filenames do not establish override order. [Cursor rules help](https://cursor.com/help/customization/rules).

## Recommended shared setup

Keep broad team agreements and repo commands in a small `AGENTS.md` that both teams can maintain. Keep useful existing `.mdc` files for stack, path or workflow-specific guidance. Link to canonical `PROJECT_BRIEF.md`, `STATE.md`, database guidance and tasks/plans instead of copying their bodies into both formats. These supporting documents keep their existing purpose; their content must be requested by the shared instructions when needed.

The proposed kit is therefore compatible in purpose with Cursor rules: conventions, checks and workflow expectations. State snapshots and briefs supply different context, rather than replacing instruction rules. Do not automatically migrate colleagues' files, adopt a second conflicting style guide, or create a Cursor adapter when shared `AGENTS.md` already supplies the needed instructions.

For related repos, retain a coordinator instruction file and short local instructions in each repo. Each agent should identify the affected repos, discover their relevant rule locations, inspect metadata first, then read only applicable bodies and task-relevant references. Do not apply a frontend rule to a Java backend merely because both repos are open. Keep always-on material small; use scoped rules for details that would otherwise consume context in unrelated tasks.

Where both formats overlap, designate one authoritative source in the shared guidance and reconcile conflicts with the team. Follow explicit user/higher-priority instructions; pause only dependent decisions when an unresolved contradiction matters. A rule suggesting credential output, automatic publication, or an unapproved production migration does not authorize those actions. Never include private credential files through rule references.

For new sessions, ask the agent to list the instruction/rule paths relevant to a named file or task and explain selection. In Cursor, also inspect the rules shown in Customize. Verify behavior in the installed app rather than assuming all workspace roots activate identically. Personal/team settings are not discoverable from a repository scan alone.

## Existing-rule audit

When actual repositories are available, report rule paths, metadata/scope, relevant constraints, duplicates and unresolved conflicts. Check referenced public project files without opening secret-bearing references. Preserve the rule files until a specific change is agreed. Record a brief rule-source note in the task when it helps handoff; do not repeat complete rule contents in state.

The reusable [AGENTS.md](AGENTS.md) and [workspace/repo templates](MULTI_REPO.md) now require this discovery. No new active Cursor rules were installed here. Validation checks documentation links and the updated discovery instructions; no application code changed.
