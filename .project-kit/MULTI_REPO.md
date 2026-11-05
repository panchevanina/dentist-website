# Related repositories and ongoing maintenance

Use shared system context plus small repository-specific instructions. This is a recommendation for future workspaces, not a claim that the application repositories were inspected here.

## Placement

| Scope | What belongs there |
| --- | --- |
| `~/.codex/AGENTS.md` | Universal preferences: quality, verification, resource use, and planning agreement |
| Workspace `AGENTS.md` | Short routing to `.project-kit/AGENTS.md` and affected repos' instructions |
| Each repository's `AGENTS.md` | Its role, commands, conventions, compatibility/data constraints, and links to shared context |
| Shared `.project-kit/PROJECT_BRIEF.md` | Current system purpose, repository map, main flows, ownership boundaries, and confirmed constraints |
| Repository README/docs | Component-specific setup, design detail, interfaces, and operating commands |
| Shared `.project-kit/tasks/` and `.project-kit/plans/` | The current requested change and coordination across repositories |

Keep one authoritative copy of each fact. Do not copy universal rules into every repository, or copy the entire shared brief into local briefs. Update local guidance when a recurring mistake or important convention justifies it.

An illustrative layout:

```text
product-workspace/
  AGENTS.md
  .project-kit/
    AGENTS.md             # canonical agreements
    PROJECT_BRIEF.md
    STATE.md
    tasks/                # persistent tasks only when useful
    plans/                # substantial work needing agreement
    usage/                # collector/config/schemas
    multi-git/            # manager/guides
    multi-git.conf
    database/             # non-secret map/examples
  backend/               # separate Git repository
    AGENTS.md
    README.md
  private-data/          # separate Git repository
    AGENTS.md
  auth-server/           # separate Git repository
    AGENTS.md
  frontend-admin/        # separate Git repository
    AGENTS.md
  frontend-client/       # separate Git repository
    AGENTS.md
  processor/             # separate Git repository
    AGENTS.md
```

Shared docs need durable storage. If the grouping folder is not versioned, keep canonical shared docs in a small context repository or an existing maintained documentation repository, and route to that location. Relative paths such as `../.project-kit/PROJECT_BRIEF.md` work only for the demonstrated sibling layout; nested repos need more parent segments. If a repository is cloned alone or used by another person, provide an accessible shared-context location or maintain a concise local fallback. Report missing context when it affects the task; do not silently invent it.

The initializer installs all supporting files in the shared kit and only short root/repo AGENTS routing files outside it. Existing flat installations remain untouched and are flagged for manual migration. Usage/runtime and initializer backup/report directories are kept inside the kit; single-repo Git recovery history uses private Git metadata to stay outside managed working files. See [initializer guide](INIT_README.md).

Copy [WORKSPACE_AGENTS.md](multi-repo/WORKSPACE_AGENTS.md) to the workspace's `AGENTS.md`, and adapt [REPOSITORY_AGENTS.md](multi-repo/REPOSITORY_AGENTS.md) for each repo. Those filenames are templates; rename them when installing. Universal working rules come from the global file, or one explicitly linked shared rules file when global configuration is unavailable.

## Discovery and access

In the desktop app, choose the coordinator folder as primary for work across the system and attach/access the repositories needed by the task. A repo may instead be primary for a localized fix; explicitly provide its shared context location. Secondary folders are available for work, but their project instruction files are not automatically discovered. The coordinator must tell the agent to read each affected repo's `AGENTS.md` before editing. See [official multiple-folder behavior](https://learn.chatgpt.com/docs/projects).

Instruction discovery normally walks from the applicable project/Git root to the current working directory. Launching inside a separate repository does not guarantee loading instructions from an outer grouping folder. Starting in the coordinator also does not load all descendant `AGENTS.md` files automatically. See [official discovery rules](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Folder access and permissions still apply. Linking a path is not granting access. In a coordinator session, perform Git, builds, and tests explicitly in the intended repository rather than relying on the primary folder's default Git target.

## Shared Cursor rule files

For projects maintained by Cursor users, follow [CURSOR_COMPATIBILITY.md](CURSOR_COMPATIBILITY.md): check the coordinator and each affected repo for existing `.cursor/rules/**/*.mdc`, legacy `.cursorrules` and task-relevant nested locations. Inspect metadata first, then the applicable bodies/references. Preserve colleagues' files, avoid copying the same rules into multiple formats, and report material conflicts. The coordinator and repo templates include this discovery rule; an absent rule file is not a reason to scan unrelated projects or personal settings.

## Briefs for an existing system

One shared brief is usually enough. It should describe the system as it exists, not turn every maintenance task into a new product build. Include:

- Product purpose and the business constraints the code cannot explain.
- Repository roles and technologies, with paths and links to local docs.
- The important API/event/data flows and who owns each boundary.
- Authentication, authorization, tenant/private-data boundaries, and compatibility expectations where relevant.
- The authoritative sources for contracts, startup, tests, and deployment.
- Confirmed facts, separately labeled inferences, and open questions.

Use per-repository briefs only when a component has substantial distinct product scope or ownership that deserves its own document. Otherwise, its README and `AGENTS.md` cover local context.

The agent can draft the shared brief. A useful bootstrap request:

> Inspect existing READMEs, build files, and interface definitions to draft a concise system brief and repository map. Trace only the important integration boundaries needed for that overview. Link to evidence, separate facts from inferences, list unknowns, and ask me about missing business intent. Do not change application code.

Review the draft's important business, security, and ownership assumptions. Source code shows current behavior; it cannot establish all intended behavior. Prefer linking maintained API specifications and existing docs over creating duplicate contracts. A brief can grow from task-relevant discoveries; a complete system audit is not a prerequisite to fixing a bug.

## Tasks, plans, and state

The brief is stable context. A task specifies the requested delta. A plan specifies how substantial work will be performed. State records current progress and evidence.

| Change | Recommended workflow |
| --- | --- |
| Localized bug or small compatible feature | Chat request or existing issue with desired behavior and acceptance check; inspect, implement, review, and run relevant checks |
| Work spanning sessions or needing repository coordination | Keep one `tasks/<id>.md` or use the existing issue tracker; record affected repos, steps, evidence, and status |
| Significant refactor, uncertain architecture, migration, auth/data-boundary change, or coordinated rollout | Draft a concrete plan and obtain agreement before dependent implementation |

Repository count alone does not establish complexity. A small compatible UI/backend change can use a short outline; a one-repo security or data migration may need a reviewed plan. Once the user has agreed, proceed through routine steps without repeated approval. Meaningful scope/risk changes require renewed agreement.

Avoid duplicate task/plan/state prose. A substantial task can link to its plan or contain the plan itself if the required choices, checks, and approval are explicit. Keep `STATE.md` as a short current snapshot or an index linking to active task files. Concurrent workers should have separate task files/ownership, not overwrite one shared task narrative. Delegation still requires the user's explicit request under this kit's default.

For work across repos, record relevant branch/worktree/revision, changed interfaces, remaining integration checks, and release order when necessary. Read consumers/providers/contracts as the task requires; being allowed to change one repo does not imply permission to expand scope across the whole system. Run affected component checks and relevant integration/contract checks, then stop without rebuilding every unrelated service.

Example maintenance request:

> Fix tenant A seeing tenant B's report. Start with backend and private-data; inspect auth-server's token/claim contract if needed. Preserve existing APIs. Reproduce the isolation failure, add regression coverage, fix it, and run affected checks. If the fix changes the authorization model or requires a migration, write a plan and ask for agreement first. Record a handoff if the task spans sessions.

## Usage attribution

The existing collector can map the coordinator and all related repositories/worktrees to one stable product ID using its `projects[].roots` list. One collector is enough. Current totals are grouped by the session's recorded working directory, not apportioned by files edited. A coordinator turn touching several repos remains product-level usage; per-repository causal token allocation is not available. See [the collector guide](usage/README.md).
