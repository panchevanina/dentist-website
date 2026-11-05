#!/usr/bin/env python3
"""Install the local development kit; preserve existing files by default."""
from __future__ import annotations

import argparse
import configparser
import datetime as dt
import fcntl
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SOURCE = Path(__file__).resolve().parent
KIT_DIR = ".project-kit"
IGNORES = [".usage/", ".multi-git/", ".project-init/", "__pycache__/", "*.pyc"]
TOOL_FILES = {
    "usage": ["collector.py", "test_collector.py", "record.schema.json", "metadata.schema.json"],
    "multi-git": ["multi-git.sh", "multi_git.py", "test_multi_git.py", "README.md",
                  "AGENT_GUIDE.md", "multi-git.conf.example"],
    "database": ["ENVIRONMENTS.example.json", "REPOSITORY_GITIGNORE.example", "test_examples.py",
                 "examples/pg_service.conf.example", "examples/pgpass.example",
                 "examples/mongodb.profile.example.json", "examples/postgresql-ping.sql",
                 "examples/mongodb-ping.js"],
    "multi-repo": ["WORKSPACE_AGENTS.md", "REPOSITORY_AGENTS.md"],
}


class SetupError(Exception):
    pass


def dumps(value):
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def public_text(name):
    # An installed kit may be reused; never propagate its customized brief/state.
    canonical = SOURCE / "templates" / name
    if not canonical.is_file():
        canonical = SOURCE / ".project-kit/templates" / name
    return (canonical if canonical.is_file() else SOURCE / name).read_text()


def safe_path(path):
    """Reject symlinks in the destination and all existing ancestors."""
    for item in [path, *path.parents]:
        if any(ord(char) < 32 or ord(char) == 127 for char in str(item)):
            raise SetupError("Control characters in destination paths are unsupported.")
        if item.is_symlink():
            raise SetupError(f"Symlink destination/ancestor refused: {item}")
        if item != path and item.exists() and not item.is_dir():
            raise SetupError(f"Destination parent is not a directory: {item}")


def git_result(path, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(["git", "-C", str(path), *args], env=env, capture_output=True,
                          text=True, timeout=15)


def is_repo(path):
    if not path.is_dir() or not (path / ".git").exists():
        return False
    result = git_result(path, "rev-parse", "--show-toplevel")
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == path


def prerequisites():
    if sys.version_info < (3, 10):
        raise SetupError("Python 3.10+ is required.")
    if not shutil.which("git"):
        raise SetupError("Git 2.40+ is required; install Git before initializing.")
    version = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
    match = re.search(r"(\d+)\.(\d+)", version.stdout)
    if not match or tuple(map(int, match.groups())) < (2, 40):
        raise SetupError("Git 2.40+ is required.")


def discover(root, mode, requested):
    if mode == "single":
        if requested:
            raise SetupError("--repo is only for multi-repository mode.")
        return [root] if is_repo(root) else []
    paths = []
    if root.exists():
        for child in sorted(root.iterdir()):
            if child.name.startswith(".") or child.is_symlink():
                continue
            if is_repo(child):
                paths.append(child)
    for relative in requested:
        candidate = root / relative
        safe_path(candidate)
        if not candidate.is_relative_to(root) or candidate == root:
            raise SetupError("--repo must name a repository below the target workspace.")
        if not is_repo(candidate):
            raise SetupError(f"Not a repository root: {candidate}")
        if candidate not in paths:
            paths.append(candidate)
    return sorted(paths)


def git_config(root, repos):
    cfg = configparser.ConfigParser(interpolation=None)
    history = KIT_DIR + "/.multi-git"
    if root in repos:
        private = git_result(root, "rev-parse", "--absolute-git-dir")
        if private.returncode:
            raise SetupError("Cannot locate repository Git metadata for safe recovery history.")
        history = str(Path(private.stdout.strip()).resolve() / "multi-git-history")
    cfg["workspace"] = {"schema_version": "1", "root": "..", "history_dir": history,
                        "protected_branches": "main, master, develop, development, staging"}
    ids = {}
    for path in repos:
        safe_path(path)
        relative_path = os.path.relpath(path, root)
        if relative_path != relative_path.strip():
            raise SetupError(f"Repository path cannot have leading/trailing whitespace in INI: {path}")
        name = path.name if path != root else "project"
        rid = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        if not rid or not re.match(r"[A-Za-z0-9_]", rid):
            rid = "repo_" + rid
        while rid in ids:
            rid += "_"
        ids[rid] = path
        remotes = git_result(path, "remote")
        if remotes.returncode:
            raise SetupError(f"Cannot inspect remote names for {path}; inspect Git locally.")
        names = remotes.stdout.splitlines()
        remote = "origin" if "origin" in names else names[0] if len(names) == 1 else "origin"
        cfg["repo:" + rid] = {"path": relative_path, "enabled": "true",
                             "fetch_remote": remote, "push_remote": remote}
    stream = io.StringIO()
    stream.write("# Data only. Review actual remotes, branch aliases and groups; never source this file.\n")
    cfg.write(stream)
    return stream.getvalue(), ids


def routing(prefix, child=False):
    return f"""\n## Installed development kit

- Read `{prefix}AGENTS.md` for shared working agreements, including planning, verification, report-first final diff review and explicit commit authorization. Read applicable existing local/nested AGENTS and Cursor rules; report material conflicts instead of silently choosing an instruction set.
- Shared context: `{prefix}PROJECT_BRIEF.md`, `{prefix}STATE.md`, and task-relevant `{prefix}tasks/` / `{prefix}plans/`. {'Keep component-specific commands/ownership local; do not create a competing shared state.' if child else 'The current task defines scope; the brief does not authorize rebuilding the system.'}
- Git operations: read `{prefix}multi-git/AGENT_GUIDE.md`; invoke `{prefix}multi-git/multi-git.sh` with `--config {prefix}multi-git.conf` and explicit task-owned repo IDs. Run builds/tests in the affected repo.
- Database work: `{prefix}DATABASES.md` and `{prefix}database/ENVIRONMENTS.json`. Use explicit configured environments; local clients consume private credentials outside all Git roots without exposing them.
- Usage collector runs separately; see `{prefix}usage/README.md`. Do not run it per agent command or invent token costs.
- Commands/checklist: `{prefix}USAGE_EXAMPLES.txt`, `{prefix}SETUP_CHECKLIST.md` and `{prefix}OPTIONAL_CONFIG.md`. Ask only about facts that affect the task; keep unknowns explicit.
"""


def examples(root, project_id, repo_ids):
    quoted = shlex.quote(str(root / KIT_DIR))
    ids = " ".join(shlex.quote(rid) for rid in repo_ids) or "REPLACE_WITH_CONFIGURED_REPO_ID"
    return f"""PROJECT OPERATIONS — {project_id}

Working directory: {root / KIT_DIR} (the kit folder, not the application root)
Prerequisites: Unix shell, Python 3.10+, Git 2.40+; no pip install/API key.
cd {quoted}

USAGE: run on the machine with Codex desktop session logs.
python3 usage/collector.py import
python3 usage/collector.py watch
watch polls every 5 seconds. Stop: Ctrl+C in its terminal. Restart: repeat watch.
Restart after changing usage/config.json; no restart per chat/desktop restart.
import runs once and exits; later imports catch up from retained logs.
Do not overlap with another collector for the same dataset. Instructions do not
launch Python. Counts depend on logged evidence; exact shell-command token
charges may be unavailable. No dashboard UI or subscription bill is generated.
python3 usage/collector.py summary --group project --project {shlex.quote(project_id)}
python3 usage/collector.py summary --group turn --project {shlex.quote(project_id)}
python3 usage/collector.py export --project {shlex.quote(project_id)} --out .usage/dashboard-data.json
python3 usage/collector.py advice --project {shlex.quote(project_id)} --out .usage/advice.json
Feedback: use actual session/turn IDs from summary and the assess command;
python3 usage/collector.py assess --help
Stop watch before: python3 usage/collector.py rebuild
Then: python3 usage/collector.py import

GIT: inspect multi-git.conf first (paths, remotes, aliases, groups).
./multi-git/multi-git.sh status --all
./multi-git/multi-git.sh status --repos {ids} --json
Status uses cached refs; it does not fetch. Empty configs need repos registered.
Preview: ./multi-git/multi-git.sh pull --all
Execute an authorized operation: ./multi-git/multi-git.sh pull --all --execute
Other commands: fetch, switch, branch-create, commit, merge, rebase, tag,
push, history, report and rollback; exact options in multi-git/README.md.
Commits/pushes need explicit requests. Merge/rebase require clean guarded trees.
Each Git-manager command exits; nothing to start/restart/stop. Config changes
apply next invocation. Rollback requires actual run IDs and matching state;
remote changes and database state are not automatically undone.
From another directory, pass an absolute --config path and actual script path.

DATABASES: all environments initially unavailable (configured=false).
Read DATABASES.md, database/ENVIRONMENTS.json and OPTIONAL_CONFIG.md.
For needed profiles only, use the placeholder formats in database/examples/.
Create/fill secrets privately outside ALL Git roots, never in agent context.
No database command has run. Profiles do not automatically configure apps.
PostgreSQL examples require psql; MongoDB examples require mongosh. Read the
guide's protected-output connection examples before running an authorized check.
Unused staging/prod/engine: leave unconfigured; never insert NULL or fall back.

KIT CHECKS (disposable fixtures, no actual project deployment):
python3 -m unittest discover -s usage -p 'test_*.py'
python3 -m unittest discover -s multi-git -p 'test_*.py'
python3 -m unittest discover -s database -p 'test_*.py'
Database guard tests also require Node.js; they mock connections.
python3 -m unittest discover -s . -p 'test_init_project.py'

APPLICATION SETUP / START / STOP / TEST / DEPLOY:
Not configured by the kit. Add real project commands from maintained READMEs,
build files and deployment tooling; record working directory, prerequisites,
environment selection, expected outcome and executed verification.
Run application commands from their actual repository roots, not this kit folder.
No application services, watcher, Git mutation, deployment or database access
are started by initialization. Global Codex/Cursor settings stay unchanged.

REUSE: keep init-project.sh + init_project.py with the whole kit. Re-run against
another target (do not copy only the launcher). Existing files are preserved
unless individually approved for replacement; approved replacements get backups.
"""


def usage_readme():
    return """# Project-local Codex usage collector

See [executable examples](../USAGE_EXAMPLES.txt), [configuration](config.json), [unused values](../OPTIONAL_CONFIG.md), [usage schema](record.schema.json) and [metadata schema](metadata.schema.json). Python 3.10+, standard library only. No API/model calls. Run on the machine holding desktop logs; default sources are `$CODEX_HOME/sessions` and `$CODEX_HOME/archived_sessions`, or `~/.codex` when unset.

The initializer configures this project and its repository roots under one stable ID, with output in `../.usage` relative to this config: `.project-kit/.usage` in the application workspace. External worktrees need their own root entries. You can instead use one central collector for multiple projects; do not run overlapping collectors and do not add duplicate exports together. Relative config paths resolve against the config directory. Restart a watcher after editing config.

From `.project-kit/`, `python3 usage/collector.py import` catches up and exits; `python3 usage/collector.py watch` polls every five seconds in a separate terminal. From the application root, use `python3 .project-kit/usage/collector.py ...`. Stop with Ctrl+C, restart with the same command. It creates no auto-start service. An AGENTS file does not start it. No tracking ran during initialization.

JSONL observations and a rebuildable SQLite index go to `.usage/`. Queries/tools retain metadata, not prompt text, arguments or command output. User-approved assessments can contain redacted summaries; never supply secrets. `summary` reports project/session/turn/model/effort/date groups; `export --out` produces deduplicated dashboard JSON; `advice` makes local evidence-based suggestions; `assess` records actual human feedback. Stop watch before `rebuild`, then import again. See `--help` for options.

Prefer reported model-response usage; snapshots reconcile/fill coverage gaps and must not be added again. Cached input is included in input, reasoning in output. Missing counts remain null and coverage diagnostics are explicit. Multiple queries may share turn attribution. Exact per-shell-command charges may be unavailable, including nested orchestration. Logs vary by app version; unknown/reset/partial records are diagnostic evidence. This is no subscription invoice or dashboard UI. Lost/unrecorded logs cannot be recovered. Check coverage before interpreting totals or advice.

Regression tests are included; no original history/design-stage observations are installed. Unix is the target; Windows locking and remote log access require separate validation. No global settings are modified.
"""


def payloads(root, mode, project_id, timezone, repos):
    files = {}
    agreement_path = SOURCE / ".project-kit/AGENTS.md"
    agreements = agreement_path.read_text() if agreement_path.is_file() else public_text("AGENTS.md")
    files["AGENTS.md"] = agreements
    root_agents = "# Project instructions\n"
    if mode == "multi":
        root_agents += "\nThis folder coordinates independent repositories. Identify the task-owned components and read each affected repo's AGENTS/nested guidance and relevant Cursor rules before editing. Keep one shared brief/state and record cross-repo contracts, data ownership and integration dependencies. Run Git/tests in the intended repo and preserve unrelated edits. Repository count alone does not require a plan; the shared planning rules govern complexity.\n"
    external = {"AGENTS.md": root_agents + routing(KIT_DIR + "/")}
    for name in ["PROJECT_BRIEF.md", "plans/TEMPLATE.md", "tasks/TEMPLATE.md"]:
        template = public_text(name)
        files[name] = template
        files["templates/" + name] = template
    for name in ["DATABASES.md", "CURSOR_COMPATIBILITY.md", "MULTI_REPO.md", "OPTIONAL_CONFIG.md"]:
        text = (SOURCE / name).read_text()
        if name == "DATABASES.md":
            text = text.replace("proposed_setup/", KIT_DIR + "/")
        if name == "CURSOR_COMPATIBILITY.md":
            lines = text.splitlines()
            lines[2] = "This project must inspect its own applicable Cursor rules. The initializer preserves existing rules and does not infer their semantic compatibility. Follow the discovery and audit guidance below."
            text = "\n".join(lines) + "\n"
        files[name] = text
    for folder, names in TOOL_FILES.items():
        for name in names:
            text = (SOURCE / folder / name).read_text()
            if folder == "multi-git" and name == "README.md":
                text = text.replace("/home/deann/projects/playground/gpt_instructions_in_use/proposed_setup/multi-git/multi-git.sh", "./.project-kit/multi-git/multi-git.sh")
                text = text.replace("proposed_setup/", KIT_DIR + "/")
                text = text.replace("multi-git() { ./.project-kit/multi-git/multi-git.sh", "multi-git() { /REPLACE_WITH_ABSOLUTE_PROJECT_ROOT/.project-kit/multi-git/multi-git.sh")
                text = text.replace('"$multi_git_tool" init --root .\n', '"$multi_git_tool" init --root . --config .project-kit/multi-git.conf\n')
                text = text.replace("The default config is `./multi-git.conf`.", "The installed launcher defaults to its adjacent kit's `multi-git.conf`; the Python helper alone defaults to `./multi-git.conf`.")
                notice = "Installed layout: the launcher supplies `.project-kit/multi-git.conf`; run this guide's examples from the application workspace root. The initializer already creates the config: skip `init` unless preparing a different missing config.\n\n"
                if notice not in text:
                    heading, rest = text.split("\n", 1)
                    text = heading + "\n\n" + notice + rest.lstrip("\n")
            if folder == "multi-git" and name == "multi-git.sh":
                text = '#!/bin/sh\n# Installed kit: default to this kit config from any working directory.\nset -eu\nscript_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec python3 "$script_dir/multi_git.py" --config "$script_dir/../multi-git.conf" "$@"\n'
            files[folder + "/" + name] = text
    for name in ["init-project.sh", "init_project.py", "test_init_project.py", "INIT_README.md"]:
        files[name] = (SOURCE / name).read_text()
    files["usage/README.md"] = usage_readme()
    files["usage/config.json"] = dumps({"schema_version": 1, "output_dir": "../.usage", "timezone": timezone,
                                       "projects": [{"id": project_id, "roots": [str(root)]}]})
    environments = json.loads(files["database/ENVIRONMENTS.example.json"])
    environments["project_id"] = project_id
    files["database/ENVIRONMENTS.json"] = dumps(environments)
    config, ids = git_config(root, repos)
    files["multi-git.conf"] = config
    files["STATE.md"] = f"""# Current state

Status: development kit installed; project-specific setup pending.

- Project: `{project_id}`; layout: {mode}.
- Shared context: [PROJECT_BRIEF.md](PROJECT_BRIEF.md); complete task-relevant facts from existing code/docs, with business assumptions confirmed by the user.
- Setup: [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md), [OPTIONAL_CONFIG.md](OPTIONAL_CONFIG.md), [USAGE_EXAMPLES.txt](USAGE_EXAMPLES.txt).
- No application implementation, Git mutation, deployment, database connection or usage import was performed by initialization.
- Next: reconcile any preserved AGENTS/ignore/config files, verify repository roles/commands and usage source paths; configure only needed database profiles privately.
- Current task/plan: none approved by initialization. Use small maintenance requests directly; seek agreement for complex work.
- Verification: initializer fixture tests do not establish this application's correctness. Record actual project checks as work proceeds.

Replace this snapshot at meaningful milestones; keep it short and link task evidence.
"""
    ignore = "# Development-kit local runtime data (not an agent access boundary)\n" + "\n".join(IGNORES) + "\n"
    ignore += files["database/REPOSITORY_GITIGNORE.example"]
    files[".gitignore"] = ignore
    files["ROOT_GITIGNORE.example"] = ignore
    for repo in repos:
        if repo == root:
            continue
        relative = repo.relative_to(root).as_posix()
        prefix = Path(os.path.relpath(root / KIT_DIR, repo)).as_posix() + "/"
        external[relative + "/AGENTS.md"] = "# Repository guidance\n\nRead the shared agreements and context below. Add this component's role, owned contracts/data, actual setup/tests and deployment commands after inspecting its maintained docs.\n" + routing(prefix, child=True)
    files["USAGE_EXAMPLES.txt"] = examples(root, project_id, ids)
    files["KIT_README.md"] = """# Installed software-development kit

Start with [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) and [executable examples](USAGE_EXAMPLES.txt). Shared [working agreements](AGENTS.md) cover efficient context, planning agreement, verification, handoffs, report-first final review, and explicit commit authorization. Existing instruction conflicts must be reconciled before relying on new rules.

Context/templates: [project brief](PROJECT_BRIEF.md), [state](STATE.md), [tasks](tasks/TEMPLATE.md), [plans](plans/TEMPLATE.md), [multi-repo guidance](MULTI_REPO.md), [repo instruction template](multi-repo/REPOSITORY_AGENTS.md), [Cursor compatibility](CURSOR_COMPATIBILITY.md).

Tools: [usage collector](usage/README.md), [Git manager](multi-git/README.md), [Git agent guide](multi-git/AGENT_GUIDE.md), [database environments/privacy](DATABASES.md), [optional configuration](OPTIONAL_CONFIG.md), [initializer](INIT_README.md). Each included tool has tests; application behavior and deployment require their own project-specific verification. No model/DB/service/key is required for the initializer or local usage/Git tools.

Global preferences may be maintained separately, but this kit is self-contained and does not edit global configuration. Parent instructions are not automatically loaded inside independent Git roots: read the repo routing files explicitly. Keep shared context in durable/versioned storage; if a repo is cloned alone, make its shared context accessible. Avoid copying runtime ledgers, backups or secrets to another project.
"""
    installed = {KIT_DIR + "/" + name: text for name, text in files.items()}
    installed.update(external)
    return installed, ids


def setup_text(root, mode, project_id, ids, actions):
    preserved = [row["path"] for row in actions if row["action"] == "preserved"]
    conflicts = [name for name in preserved if Path(name).name == "AGENTS.md"]
    return f"""# Project setup checklist

Project `{project_id}`; mode `{mode}`; target `{root}`.
All initializer-created kit files, usage data and installation reports/backups live in `.project-kit/`; only short AGENTS routing files are placed outside it. Single-repo Git recovery journals use dedicated Git metadata for working-tree safety; multi-repo journals live in the shared kit outside affected repos. Run the relative tool commands below from `{root / KIT_DIR}`. File paths in installation reports are relative to the application workspace root.

## Required checks and edits

- [ ] Review preserved files: {', '.join('`' + p + '`' for p in preserved) or 'none'}. New files do not override preserved configuration. Potential AGENTS instruction conflicts: {', '.join('`' + p + '`' for p in conflicts) or 'none'}. Manually reconcile/merge routing with `.project-kit/AGENTS.md`; byte differences are a warning, not proof of semantic conflict. Existing Cursor rules remain unchanged; inspect their relevant scopes and conflicts.
- [ ] The kit's `.gitignore` excludes its runtime ledgers/journals/backups. If that file was preserved, reconcile its patterns. For accidental private files elsewhere, manually merge relevant `ROOT_GITIGNORE.example` patterns into the root AND each independent repo; the initializer creates no root/child ignore files. Ignore rules neither untrack existing files nor prevent agent reads. Keep shareable kit instructions/tools versioned rather than ignoring the entire folder.
- [ ] Fill task-relevant `PROJECT_BRIEF.md`: purpose, repo roles/technologies, contracts/data ownership, authoritative docs and unknowns. Ask the agent to draft it from relevant code/docs without modifying application code. Keep `STATE.md` current. Small bug fixes need no new plan/brief; substantial work requires an agreed plan.
- [ ] Verify `usage/config.json`: stable ID `{project_id}`, absolute project root, timezone, `output_dir=../.usage`. It already covers nested repos; add external worktree roots. Preserved configs need manual review. Default session directories come from CODEX_HOME or ~/.codex; if this machine lacks desktop logs, run the collector where logs exist or set `session_roots` to their actual directories. Never run overlapping collectors for one dataset. See `usage/README.md` for counts/coverage limits.
- [ ] Initialization does not start or stop usage tracking. Check whether a collector already runs here or centrally before starting another. If none does, run `python3 usage/collector.py import` once, or `watch` in a separate terminal; Ctrl+C stops; repeat watch restarts. Restart after config edits. Export JSON/dashboard advice with commands in `USAGE_EXAMPLES.txt`. Dashboard UI is not installed. Exact per-command token costs are not guaranteed by logs.
- [ ] Verify `multi-git.conf`: discovered repo IDs {', '.join('`' + rid + '`' for rid in ids) or 'none; add repos when available'}. `[workspace].root=..` resolves from the kit config to the application root. For a managed root repository, `history_dir` uses its private Git metadata `multi-git-history` directory (update the absolute path after moving/cloning the project). For sibling repos it uses `.project-kit/.multi-git` relative to the workspace, outside their working files. Check paths, actual remotes/upstreams, protected branches, aliases and groups. The installed launcher supplies this config from any working directory. Run `./multi-git/multi-git.sh status --all` only after a nonempty enabled selection exists. Mutations preview unless --execute; commits/pushes require explicit requests.
- [ ] New/nested repos: re-run `init-project.sh` with the same mode; use repeated `--repo relative/path` for nested multi-repo roots. Existing `multi-git.conf` and brief are preserved, so add new `[repo:ID]` sections manually (or approve a backed-up replacement after reviewing custom aliases/groups). Route each new repo's AGENTS to canonical shared context. If the parent is unversioned, store shared docs durably so teammates/clones can access them.
- [ ] Database map `database/ENVIRONMENTS.json`: all environments begin `configured=false`, `disposable=false`. No DBs/no staging: leave them false; no null/NULL values. Set the private-root placeholder only if DBs are needed. Privately create only needed PostgreSQL/MongoDB profiles outside ALL Git roots, with restrictive permissions and verified TLS/target/grants. Never expose secret files/logs/keys to an agent or the internet. No profiles, broker or DB service were created. Read `DATABASES.md`; maps/instructions are not access-control enforcement.
- [ ] Read `OPTIONAL_CONFIG.md` for omitted aliases/groups, disabled repos, inactive usage, and Not applicable/Unknown prose. Do not use literal NULL for string config fields.
- [ ] Add actual application setup/start/restart/stop/tests/deploy commands to `USAGE_EXAMPLES.txt` from this project's maintained tooling. Deployment targets and secrets are project-specific; initialization does not deploy or authorize deployment. Optional psql/mongosh are needed only for relevant database checks; Node.js is needed for mocked database guard tests.

## Installation evidence and recovery

The initializer performs read-only Git discovery and copies/generated files only. It does not fetch/switch/commit/push, connect to databases, import transcripts, start services or change global Codex/Cursor settings. Existing files are preserved unless individually authorized. Approved overwrite originals are stored in this run's private backups; inspect the JSON report's backup paths and restore manually only after comparing subsequent edits. Interrupted runs may leave partial additions; inspect the report, then rerun safely. No automatic deletion/rollback of project files.

Keep the whole kit with `init-project.sh` and `init_project.py` to initialize another project. No initializer start/stop/restart service exists. Per-project tools/configs work locally; alternatively maintain one central collector and map projects there. Do not copy this project's runtime ledgers, profiles, state or backups to another project.
"""


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="new or existing project directory")
    parser.add_argument("--mode", choices=["single", "multi"], help="omit to ask interactively")
    parser.add_argument("--project-id", help="stable usage project ID; defaults to target directory name")
    parser.add_argument("--timezone", default="Europe/Sofia", help="IANA timezone (default Europe/Sofia)")
    parser.add_argument("--repo", action="append", default=[], help="additional nested repo path below target (multi only)")
    parser.add_argument("--dry-run", action="store_true", help="inspect/report without writing anything")
    parser.add_argument("--non-interactive", action="store_true", help="require target/mode, preserve all conflicts")
    parser.add_argument("--overwrite", action="append", default=[], metavar="RELATIVE_FILE",
                        help="explicitly authorize replacement of this one differing file; repeat as needed (backs up originals)")
    return parser.parse_args()


def main():
    args = parse_args()
    interactive = sys.stdin.isatty() and not args.non_interactive
    if not args.target:
        if not interactive:
            raise SetupError("Provide a target directory (and --mode for noninteractive use).")
        args.target = input("New/existing project directory: ").strip()
    if not args.target:
        raise SetupError("Target directory cannot be empty.")
    if not args.mode:
        if not interactive:
            raise SetupError("Provide --mode single or --mode multi for noninteractive use.")
        answer = input("Is this a parent folder for multiple repositories? [y/N]: ").strip().lower()
        if answer not in {"", "y", "yes", "n", "no"}:
            raise SetupError("Answer yes or no, or use --mode.")
        args.mode = "multi" if answer in {"y", "yes"} else "single"
    root = Path(os.path.abspath(os.path.expanduser(args.target)))
    safe_path(root)
    if root.exists() and not root.is_dir():
        raise SetupError("Target must be a directory.")
    own_workspace = SOURCE.name == KIT_DIR and root == SOURCE.parent
    if root == SOURCE or root.is_relative_to(SOURCE) or (SOURCE.is_relative_to(root) and not own_workspace):
        raise SetupError("Target and source kit must not overlap.")
    for value in args.repo:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise SetupError("--repo requires a relative path without '..'.")
    project_id = args.project_id or re.sub(r"[^A-Za-z0-9_.-]", "-", root.name).strip("-")
    if not project_id or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", project_id):
        raise SetupError("Use a stable --project-id containing letters, digits, underscores, dots or hyphens.")
    try:
        ZoneInfo(args.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise SetupError("--timezone must be a valid IANA timezone name.")
    prerequisites()
    repos = discover(root, args.mode, args.repo)
    files, ids = payloads(root, args.mode, project_id, args.timezone, repos)
    checklist_name = KIT_DIR + "/SETUP_CHECKLIST.md"
    files[checklist_name] = ""  # Render after conflict decisions, before writes.
    authorized = set(args.overwrite)
    for name in authorized:
        if name not in files:
            raise SetupError(f"--overwrite must name a planned relative file: {name}")
    actions = []
    originals = {}
    for name in files:
        path = root / name
        safe_path(path)
        if path.exists() and not path.is_file():
            raise SetupError(f"File destination is not a regular file: {path}")
        if path.exists() and path.stat().st_nlink != 1:
            raise SetupError(f"Hard-linked destination refused: {path}")
        original = path.read_bytes() if path.exists() else None
        originals[name] = original
        if original is None:
            action = "created"
        elif name != checklist_name and original == files[name].encode():
            action = "unchanged"
        else:
            warning = " POTENTIAL AGENTS INSTRUCTION CONFLICT." if path.name == "AGENTS.md" else ""
            print(f"Existing differing file: {name}.{warning} Preserve recommended; manual merge may be needed.")
            overwrite = name in authorized
            if interactive and not overwrite and not args.dry_run:
                overwrite = input(f"Back up and overwrite {name}? [y/N]: ").strip().lower() in {"y", "yes"}
            action = "overwritten" if overwrite else "preserved"
        actions.append({"path": name, "action": action})
    checklist = setup_text(root, args.mode, project_id, ids, actions)
    legacy = [name for name in ["KIT_README.md", "init_project.py", "usage/collector.py", "multi-git/multi_git.py"]
              if (root / name).is_file()]
    if len(legacy) >= 3:
        note = "\n## Previous flat installation detected\n\nOld root-level kit files are preserved. Before using the new tools, migrate your customized brief/state/tasks/plans/configs into .project-kit, update the Git workspace/history paths, and stop the old usage watcher before reusing its ledger or starting a new one. Retain old journals/configs together for Git recovery; initialization does not relocate or delete them. See INIT_README.md for the migration checklist. Do not combine old/new usage exports as separate charges.\n"
        checklist += note
        print("Previous flat installation detected. Root-level files retained; migrate customized context/config/runtime state before using the new kit.")
    files[checklist_name] = checklist
    checklist_row = next(row for row in actions if row["path"] == checklist_name)
    if originals[checklist_name] == checklist.encode():
        checklist_row["action"] = "unchanged"
    report = {"schema_version": 1, "target": str(root), "mode": args.mode,
              "project_id": project_id, "repositories": {rid: str(path) for rid, path in ids.items()},
              "dry_run": args.dry_run, "files": actions, "status": "preview", "legacy_files": legacy if len(legacy) >= 3 else []}
    if args.dry_run:
        print(dumps(report))
        print(checklist)
        return 0
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    kit_root = root / KIT_DIR
    run = kit_root / ".project-init/runs" / run_id
    safe_path(run)
    for directory in [kit_root / ".project-init", kit_root / ".project-init/runs"]:
        if directory.exists() and (not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077):
            raise SetupError(f"Existing report directory must be private (0700); change permissions yourself: {directory}")
    # Lock an existing directory, not an existing file. No lock-file modification.
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    completed = []
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SetupError("Another initializer holds this target; retry after it exits.") from error
        # Catch changes between decisions and writes before applying any candidate.
        for name, original in originals.items():
            path = root / name
            safe_path(path)
            now = path.read_bytes() if path.exists() else None
            if now != original:
                raise SetupError(f"Destination changed during setup; rerun: {name}")
        kit_root.mkdir(exist_ok=True)
        (kit_root / ".project-init").mkdir(mode=0o700, exist_ok=True)
        run.parent.mkdir(mode=0o700, exist_ok=True)
        run.mkdir(mode=0o700)
        report["run_id"] = run_id
        report["status"] = "in_progress"
        report_path = run / "report.json"
        report_path.write_text(dumps(report))
        os.chmod(report_path, 0o600)
        for row in actions:
            name = row["path"]
            if row["action"] not in {"created", "overwritten"}:
                continue
            path = root / name
            safe_path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if row["action"] == "overwritten":
                # Verify again just before replacing; don't discard intervening edits.
                if path.read_bytes() != originals[name]:
                    raise SetupError(f"File changed before replacement; preserved: {name}")
                backup = run / "backups" / name
                backup.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                for parent in backup.parents:
                    if parent == run:
                        break
                    os.chmod(parent, 0o700)
                backup.write_bytes(originals[name])
                os.chmod(backup, 0o600)
                row["backup"] = str(backup.relative_to(root))
                mode_bits = stat.S_IMODE(path.stat().st_mode)
                # Atomic replacement from an exclusive sibling file.
                temporary = path.with_name(".init-" + uuid.uuid4().hex)
                try:
                    with temporary.open("xb") as stream:
                        stream.write(files[name].encode())
                    os.chmod(temporary, mode_bits)
                    safe_path(path)
                    if path.read_bytes() != originals[name]:
                        raise SetupError(f"File changed during replacement; preserved: {name}")
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
            else:
                with path.open("xb") as stream:
                    stream.write(files[name].encode())
            if name in {KIT_DIR + "/init-project.sh", KIT_DIR + "/multi-git/multi-git.sh"}:
                path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            completed.append(name)
            report["completed_files"] = completed
            report_path.write_text(dumps(report))
        report["status"] = "complete"
        report_path.write_text(dumps(report))
        (run / "SETUP.md").write_text(checklist)
        os.chmod(run / "SETUP.md", 0o600)
    except BaseException:
        if run.exists():
            report["status"] = "partial_failure"
            report["completed_files"] = completed
            (run / "report.json").write_text(dumps(report))
            print(f"Partial installation; existing unapproved files were preserved. Inspect {run / 'report.json'}; rerun to complete missing files.", file=sys.stderr)
        raise
    finally:
        os.close(fd)
    counts = {action: sum(row["action"] == action for row in actions)
              for action in ["created", "overwritten", "unchanged", "preserved"]}
    print(f"Installed: {counts}. No watcher, Git mutation, database access or deployment ran.")
    print(f"Report: {run / 'report.json'}\nCurrent checklist: {run / 'SETUP.md'}")
    print(checklist)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SetupError, OSError, subprocess.SubprocessError) as error:
        print(f"Initialization stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
    except (EOFError, KeyboardInterrupt):
        print("Initialization cancelled; inspect any reported partial installation.", file=sys.stderr)
        raise SystemExit(130)
