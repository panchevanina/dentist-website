# Initialize a new or existing project

Run the executable launcher with its adjacent helper and the whole kit. Unix, Python 3.10+ and Git 2.40+ are required; no pip packages, keys or global installation. Git repository discovery is read-only.

```bash
# From the reusable kit directory; quote paths containing spaces.
./init-project.sh /actual/path/to/project
```

It installs everything under `<project>/.project-kit/`, with only a short `AGENTS.md` routing file in the project root and each discovered repository root. No root/child `.gitignore` or example files are created. Existing routing files still require overwrite approval or a manual merge.

```text
project/
  AGENTS.md                 # small routing file
  .project-kit/
    AGENTS.md               # canonical shared agreements
    PROJECT_BRIEF.md
    STATE.md
    SETUP_CHECKLIST.md
    USAGE_EXAMPLES.txt
    multi-git.conf
    usage/                  # collector, schemas, config, tests
    multi-git/              # Git manager, guides, tests
    database/               # non-secret map and private-profile examples
    plans/                  # task plans and template
    tasks/                  # task records and template
    templates/              # clean templates for reuse
    .gitignore              # excludes runtime data below
    .usage/                 # created by usage collector
    .multi-git/             # multi-repo journals, outside selected repos
    .project-init/          # private reports/backups
    init-project.sh         # reusable launcher and adjacent helper
  backend/                  # multi-repo example
    AGENTS.md               # routes to ../.project-kit/
```

The actual kit also contains compatibility, database, optional-config and initializer guides. The root routing files let sessions opened at a repository find the shared kit; root `AGENTS.md` is the deliberate exception to the single-folder layout.

It asks whether the target is a multi-repository parent. Single mode registers the target itself if it is a Git root. Multi mode discovers immediate child Git roots/worktrees; add nested roots with repeated `--repo relative/path`. It accepts a nonexistent directory without running git init or cloning repositories.

```bash
./init-project.sh /actual/path/to/project --mode multi --project-id my-product --dry-run
./init-project.sh /actual/path/to/project --mode multi --repo services/backend --non-interactive
./init-project.sh /actual/path/to/repository --mode single --timezone Europe/Sofia --non-interactive
```

Dry-run performs inspection only and prints planned actions/checklist. No target/report directories are created. Noninteractive use needs a target and mode; conflicting files are preserved. Timezone defaults to Europe/Sofia; choose an actual IANA name. Stable project ID defaults to a sanitized target directory name; use distinct explicit IDs for distinct products, especially when consolidating exports.

## Existing files and instructions

Every existing file stays unchanged unless you individually authorize a replacement. Identical files are left alone. Differing files produce a message; an existing `AGENTS.md` produces a **potential instruction conflict** warning. Differences cannot establish semantic compatibility automatically. Interactive runs ask `Back up and overwrite ...? [y/N]`; Enter/no preserves it. Do not use a blanket yes command. Existing Cursor rules, `.git` contents and global settings are untouched.

For automation, an already authorized replacement names a specific planned relative file:

```bash
# Review the preview and original file first; this replaces the whole file.
./init-project.sh /actual/path/to/project --mode multi --non-interactive --overwrite AGENTS.md
```

Repeat `--overwrite` only for other individually approved files. There is no force-all option. Defaults preserve existing configs, state, briefs, examples and ignore files, including on reruns. Preserved configuration must be reconciled manually: new tools do not override it. Preserving existing `AGENTS.md` means its new routing/agreements must be merged explicitly before relying on them. `.project-kit/AGENTS.md` is the canonical supplied rule set. The kit contains its own `.gitignore` for runtime artifacts and `ROOT_GITIGNORE.example` for manually merging private-file patterns into repository ignore files when relevant. Do not ignore the entire kit if its shareable instructions/tools belong in version control.

Approved replacements have private original-byte backups under `.project-kit/.project-init/runs/RUN_ID/backups/`, with paths in `report.json`. Original permission bits are retained on replacement except executable launchers are made executable. Restore manually only after comparing subsequent changes; no automatic deletion or rollback of project files is provided. Symlink destinations/ancestors and hard-linked destination files are refused before installation. Initializers using the same root are locked; unmanaged editors/filesystem changes cannot be made transactional by this script. It rechecks content before replacement and reports partial failures.

Reports/checklists for each run are new files under `.project-kit/.project-init/runs/RUN_ID/`. A preserved `.project-kit/SETUP_CHECKLIST.md` can be stale: use the current report's `SETUP.md` path printed at the end. A failure/interruption can leave some newly added files; inspect `report.json`, then rerun to complete missing files. SIGKILL/power loss may leave an incomplete last report; inspect actual files before retrying. Keep reports/backups private and out of version control.

## What is installed

- Small root routing instructions and a canonical shared copy inside the kit; shared project brief/state, task/plan templates and repo routing files in discovered repos.
- Cursor discovery/compatibility guidance; existing team rules are not replaced.
- Usage collector, schemas and tests; generated `usage/config.json` maps the actual project root with the correct local output path. No old usage records are copied.
- Git manager, agent guide/examples/tests and generated `multi-git.conf`, including a single-repo entry in single mode. No fetch/branch/index/commit operations run.
- PostgreSQL/MongoDB instructions, examples/guard tests, and a project-specific non-secret database map. All environments start unavailable; no secrets/profiles or connections are created.
- Executable operation examples, [optional configuration guidance](OPTIONAL_CONFIG.md), `KIT_README.md` in installed projects, setup checklist and private JSON installation report. The launcher/helper/test and clean templates are included so the whole installed kit can initialize another project.

Source-project observations, current task/approval history, application-specific briefs, runtime data and credentials are excluded. No global Codex/Cursor rules, dashboard UI, enforcing credential broker, deployment or automatic services are installed.

## After initialization

Follow the printed checklist and `.project-kit/USAGE_EXAMPLES.txt`. Relative tool commands in those files run from `.project-kit/`; application commands still run from their actual repository directories. Reconcile preserved files, fill task-relevant brief/repo commands, and verify Git remotes/upstreams/aliases. New repos cloned later need entries in an existing `multi-git.conf`; reruns preserve the config rather than silently regenerate it. Nested repos need explicit `--repo`; external worktrees need manually added context/config/root paths.

Usage: from the application root run `python3 .project-kit/usage/collector.py import` for catch-up or `python3 .project-kit/usage/collector.py watch` in a separate terminal. Stop with Ctrl+C; restart with the same watch command after config edits. Run on the machine holding desktop logs; missing logs need the actual `session_roots` or a collector on that machine. One collector per dataset; do not overlap central and per-project collectors. The installed Git launcher `./.project-kit/multi-git/multi-git.sh status --all` supplies `.project-kit/multi-git.conf` from any working directory. Its workspace root is `..` relative to that config; multi-repo history is `.project-kit/.multi-git` relative to the workspace. For a single managed root repository, recovery journals instead use its dedicated private Git metadata `multi-git-history` directory (usually `.git/multi-git-history`; linked worktrees differ). This preserves the safeguard against writing history into a managed working tree; no extra root file/directory is created by initialization. Check the configured metadata path after moving/cloning the project or adding the first Git repo to an initially empty folder. The Git manager and initializer each exit after a command; nothing to start/stop. Config changes affect the next invocation. Database clients/app services require their own documented setup.

No staging/no databases? Keep database environments `configured=false` and `disposable=false`; do not insert `NULL`. Omit unused Git aliases/groups, disable repos with `enabled=false`, and delete unused usage roots while keeping valid nonempty configured roots. Prose can say `Not applicable — reason`. See [OPTIONAL_CONFIG.md](OPTIONAL_CONFIG.md).

Application setup, testing and deployment cannot be inferred from a generic kit. Add actual commands and verification from the project tooling. Shared docs need durable storage; a child repository cloned alone needs an accessible shared context location. General global preferences remain optional: this installation works without editing `~/.codex/AGENTS.md`.

## Existing flat installations

Re-running creates the contained kit and preserves the old root-level kit. If legacy markers are detected, the report/checklist explicitly flags migration. It does not silently copy customized old configs/context into new defaults or delete old files.

1. Stop the old watcher with Ctrl+C before switching collectors. Keep the same project ID/roots, migrate safe source/timezone settings into `.project-kit/usage/config.json`, and use `output_dir=../.usage`. If keeping history, copy the complete stopped ledger/index from the old output directory into `.project-kit/.usage` before importing. Do not combine old/new exports or run both collectors for the same dataset.
2. Merge the existing brief, state, tasks/plans and application examples into the corresponding kit files. Merge root/child AGENTS routing to the new kit without discarding local/team rules. Existing Cursor files remain in their established locations.
3. Carry forward actual repo IDs, aliases, groups and remotes into `.project-kit/multi-git.conf`; set `[workspace].root=..`. For sibling-repo workspaces use `history_dir=.project-kit/.multi-git`; for a managed root repo use the dedicated `multi-git-history` directory beneath its actual private Git metadata, as reported by `git rev-parse --absolute-git-dir`. History inside selected working trees remains refused even if ignored. New runs journal there. Keep old Git tools/config/history together for recovery of old run IDs; do not assume moving old recovery journals is sufficient for rollback.
4. Copy only the non-secret database map, keeping private profiles outside every Git root. Review all paths and configured environments; no credentials should be copied into the kit.
5. Verify usage coverage, Git `status`, context routing and ignore behavior. Remove redundant old files only after explicitly reviewing them and deciding that recovery is no longer needed. The initializer never performs this cleanup.

The entire installed `.project-kit/` can initialize another project through its launcher, and can be rerun against its own parent workspace. Clean templates are used instead of copying the source project's customized brief/state or runtime data. Back up customizations before upgrades; use explicit relative paths such as `--overwrite .project-kit/usage/README.md` for individually reviewed replacements.

## Verification

```bash
# From the reusable source kit, or an installed .project-kit/ directory:
python3 -m unittest discover -s . -p 'test_init_project.py' -v
sh -n init-project.sh
```

Initializer tests use disposable projects and local Git repos, no network or databases. They exercise new/existing/single/multi/nested projects, spaces, preserved files, approved backups, reruns, symlink/hard-link refusal, preview, installed-tool smoke checks and reuse. Refer to tool tests for their own behavior coverage; project deployment/native database authentication still need project-specific validation.
