# Multi-repository Git manager

Installed layout: the launcher supplies `.project-kit/multi-git.conf`; run this guide's examples from the application workspace root. The initializer already creates the config: skip `init` unless preparing a different missing config.

Run Git workflows from a parent folder. Keep **one shared copy** of this tool; keep **one `multi-git.conf` and `.multi-git/` history per workspace**. The shell launcher runs its adjacent Python helper. Python 3.10+, Git 2.40+ and a Unix shell are required; Linux with Git 2.53 was tested. No Python packages, API calls, model tokens, database, watcher, or background service are required by this tool. An agent invoking it still consumes its normal tokens.

## Setup and inspection

From a parent folder containing your repositories, use the actual installed script path:

```bash
# This path is the delivered tool in this workspace; set it once per terminal.
multi_git_tool=./.project-kit/multi-git/multi-git.sh

# Run from YOUR parent workspace, not from a repository's subdirectory.
# cd /actual/path/to/your/parent-workspace
"$multi_git_tool" init --root . --config .project-kit/multi-git.conf
"$multi_git_tool" status --all
"$multi_git_tool" status --repos fnbrt_bo_fe fnbrt_server_be --json
"$multi_git_tool" branches --all
"$multi_git_tool" diff --repos fnbrt_bo_fe --stat
"$multi_git_tool" diff --repos fnbrt_bo_fe
"$multi_git_tool" diff --repos fnbrt_bo_fe --staged
"$multi_git_tool" log --all --limit 5
```

`init` discovers direct child non-bare repository roots, including linked worktrees. IDs derive from directory names, with spaces/punctuation converted to underscores. It does not overwrite a config, fetch, or change branches. Edit the generated INI to add nested repos, aliases, remotes, or groups; use [the example](multi-git.conf.example). Paths resolve against `[workspace].root`, which resolves against the config file. Config is data and must never be sourced as shell code. Empty repositories can be inspected but mutations require an existing commit and attached branch.

`status` reports each repo's branch/HEAD, upstream, ahead/behind counts and staged/unstaged/untracked paths, using Git's two-column status codes (`M ` staged, ` M` unstaged, `??` untracked). Counts are `null` when no usable upstream exists. These counts use **cached remote refs**; status itself never fetches. Refresh them explicitly:

```bash
"$multi_git_tool" fetch --all             # preview
"$multi_git_tool" fetch --all --execute
"$multi_git_tool" status --all
```

For another working directory, pass `--config /actual/path/to/multi-git.conf` before or after the subcommand. The installed launcher defaults to its adjacent kit's `multi-git.conf`; the Python helper alone defaults to `./multi-git.conf`. There is no upward config search or branch-name guessing.

If you move the installation, copy **both** `multi-git.sh` and `multi_git.py` together and update your saved path. An optional terminal function avoids repeating the path:

```bash
multi-git() { /REPLACE_WITH_ABSOLUTE_PROJECT_ROOT/.project-kit/multi-git/multi-git.sh "$@"; }
multi-git status --all
```

Add the function to your shell configuration only if you want it available in new terminals. No global installation or shell configuration changes have been made. There is nothing to start, restart, or stop: each command exits when finished. Config edits take effect on the next command. The separate token collector has its own watcher lifecycle.

## Selection and execution

Mutations require `--repos ID...`, `--all`, `--group NAME`, or `--changed`. These selector choices cannot be combined, except that `--changed` can filter an explicit selection. `--changed` means dirty files/untracked files or ahead commits against an upstream; it cannot identify which changes an agent authored. A clean repo without an upstream makes that filter refuse selection; use explicit IDs instead. A filter finding no changed repos performs no repo operations.

All mutation commands **preview by default**. Add `--execute` to apply. Preview does not fetch and may use stale refs. Execution validates again and fetches where required. `init` is the explicit configuration-writing exception. A preview showing a merge/rebase candidate is not a successful conflict check; execution performs the isolated preparation.

```bash
# Current branches: declared upstream only; fast-forward only.
"$multi_git_tool" pull --all
"$multi_git_tool" pull --all --execute

# Switch to each repo's develop alias, then update THAT branch.
"$multi_git_tool" switch develop --all --pull --execute

# Current HEAD: allows existing dirty files without changing their contents.
"$multi_git_tool" branch-create didos_bugfixes --repos fnbrt_bo_fe fnbrt_server_be fnbrt_cdm_be --execute

# Explicit base: requires clean trees. The base must already be available locally.
"$multi_git_tool" fetch --group bugfix --execute
"$multi_git_tool" branch-create next_bugfix --base develop --group bugfix --execute

# Integrate a locally available source into an existing local target branch.
"$multi_git_tool" merge didos_bugfixes --into develop --group bugfix --execute

# Linear, unpublished feature commits only; refreshes all configured remotes.
"$multi_git_tool" rebase --onto origin/develop --repos fnbrt_bo_fe fnbrt_cdm_be --execute

# Local lightweight or annotated tag; existing tags are refused.
"$multi_git_tool" tag v1.2.3 --group bugfix --execute
"$multi_git_tool" tag v1.2.4 --message 'Release 1.2.4' --group bugfix --execute

# Separate explicit publication: current branches or one named tag.
"$multi_git_tool" push --group bugfix --execute
"$multi_git_tool" push --tag v1.2.4 --group bugfix --execute
```

`switch` requires a clean tree. An absent local branch can be created from the exact configured remote-tracking branch, without automatically assigning an upstream. `switch --pull` requires an existing local branch with a declared upstream; it refuses to invent one. New branches similarly have no automatic upstream. Set an upstream explicitly with Git after reviewing it when needed. `pull` supports a local (`.`) upstream as well as a remote upstream.

`branch-create --base`, `merge` source/target, and local-reference rebase bases do not implicitly update those branches. Fetch updates remote-tracking refs; use a resolved `origin/develop` base or explicitly fast-forward the local base first when you want the latest remote base.

A branch push uses the configured push remote and, when that is also the tracking remote, its declared upstream branch; otherwise it uses the current local branch name. It pins the source object ID, uses ordinary fast-forward rules, and never force-pushes or deletes remote refs. It does not set an upstream. Multi-repository pushes can partially succeed; the report identifies each publication or uncertainty.

## Commits and agent requests

Inspect each selected repo's own `AGENTS.md`, status, staged/unstaged diffs and relevant untracked files before writing messages. Save a JSON message manifest outside the selected repos:

```json
{
  "fnbrt_bo_fe": "Describe the reviewed frontend change",
  "fnbrt_server_be": "Describe the reviewed backend change",
  "fnbrt_cdm_be": "Describe the reviewed data change"
}
```

Replace these placeholders with accurate messages about the actual diff. The manager requires a nonempty message for every selected repo and does not call an LLM or invent messages. Relative manifest paths resolve from your terminal working directory.

```bash
# Staged changes only; no automatic staging.
"$multi_git_tool" commit --group bugfix --messages commit-messages.json
"$multi_git_tool" commit --group bugfix --messages commit-messages.json --execute

# Explicitly include tracked and untracked non-ignored changes in selected repos.
"$multi_git_tool" commit --group bugfix --all-changes --messages commit-messages.json --execute
```

Natural-language requests go to the agent, which translates them into scoped CLI calls. Copy the short [agent guide](AGENT_GUIDE.md) into your coordinator's guidance or link to the central installation. No Codex skill needs installing for this version. Record affected repo IDs in the current task/state so “repos we changed” has a concrete meaning. A request to create a specified branch or commit specified changes authorizes that scoped operation; a tool preview is not a requirement to ask for the same permission repeatedly. Pushing still requires an explicit request to publish.

## Reports and selective rollback

Every executed mutation receives a run ID and private JSON journal under `.multi-git/RUN_ID/run.json`. Reports show changed/unchanged, blocked/skipped, restored, failed/manual-review, fetched or published outcomes. JSON includes before/after branch, HEAD, local refs, logical-index/content fingerprints, remote configuration hash, timestamps and recovery references. The commit journal additionally holds an original binary index snapshot; terminal JSON omits that large payload.

```bash
"$multi_git_tool" history
"$multi_git_tool" history --json

# Use an ACTUAL ID printed by an executed command or history.
read -r -p 'Run ID: ' multi_git_run_id
"$multi_git_tool" report "$multi_git_run_id"
"$multi_git_tool" report "$multi_git_run_id" --json

# Preview first; selective rollback leaves other repos alone.
"$multi_git_tool" rollback "$multi_git_run_id" --repos fnbrt_bo_fe
"$multi_git_tool" rollback "$multi_git_run_id" --repos fnbrt_bo_fe --execute
# Or all repos belonging to that run:
"$multi_git_tool" rollback "$multi_git_run_id" --all --execute
```

Rollback requires the recorded relevant post-state to still match, and refuses new edits, commits, local refs, changed branch/upstream/remote configuration, occupied branches, Git locks, or incomplete post-state. Execution refreshes **all configured remotes** before checking publication; unavailable remotes block rollback. It refuses removal of published commits or created branches/tags now published. Checks cover configured remotes, not unknown repositories elsewhere.

Undoing a supported local commit restores the original HEAD and original index while preserving your pre-existing working files, including staged/unstaged differences and untracked files. It does not run `reset --hard`, `clean`, stash, or delete your untracked files. Hook-created file changes require manual review. For clean branch/history operations it restores the prior checkout and affected refs. Created branches/tags are removed only at their expected IDs. Fetch/object downloads/cache freshness and published remote changes are retained.

Rollback operations themselves are recorded in the originating journal. Already restored entries are skipped. If a selected candidate is ineligible, none of that selected rollback is applied; narrow the selection to eligible repos. After a partial rollback failure, inspect the report before another attempt. Undo runs in reverse chronological order when multiple dependent runs affect the same repo: older snapshots intentionally refuse while newer changes remain.

## Safety boundaries and recovery

All selected repositories are checked before branch/history changes. Merge/rebase conflicts are probed in detached temporary worktrees; original files/index/branches remain untouched by ordinary conflicts. Git hooks and signing are respected. The manager explicitly disables rebase updates to other branches and automatic stash behavior. It locks against other manager instances, guards relevant state, and updates refs with expected old IDs. Git clients/editors can still race outside those locks; this is not a cross-repository atomic transaction or a guarantee of conflict-free history.

Dirty history operations, detached/unborn mutations, in-progress Git operations, existing locks, shared Git directories in a mutation selection, protected branch rebases, published commits, replaying merge commits, submodules, sparse checkout, hidden index changes (`assume-unchanged`/`skip-worktree`), and Git LFS attributes are refused. Use a separately reviewed native Git workflow for those cases. Custom filters, hooks, credentials and filesystem behavior can have external effects; those cannot be automatically inverted by this tool.

On ordinary failure, later repos are skipped and completed eligible local changes are restored where safe. Failed commit staging is restored only when hooks have not changed its recorded state. Unexpected hook/ref/file changes are preserved and reported for manual review. A rejected or interrupted push may have uncertain remote effects; inspect its report and the remote before repeating it. No automatic remote rollback is provided.

SIGINT/SIGTERM/SIGHUP stop Git and its ordinary hook process group before journaling recovery. A hook that detaches into its own process group, power loss, or SIGKILL can leave an incomplete journal or worktree/ref transition. The manager refuses automatic rollback without a verified post-state. Recovery data remains in the journal, `refs/multi-git/RUN_ID/REPO_ID/` and any reported temporary worktree. Inspect `report`, native `git status`, refs and reflogs before an explicitly reviewed manual recovery. Do not delete stale locks without checking their owner. No automatic destructive recovery or history garbage-collection command is offered.

Add `.multi-git/` to the parent workspace's `.gitignore` if the parent is versioned. Keep journals private: they contain repository paths, commit messages and index metadata. Recovery refs intentionally retain objects; remove history/refs only after deciding you no longer need recovery. The manager does not edit repository ignore files or retention settings.

For a single managed repository, history may use its dedicated private Git metadata directory `multi-git-history` (usually `.git/multi-git-history`; linked worktrees have a different private Git directory). This is outside Git's working files and excluded from their snapshots. The initializer configures it without writing Git metadata; executed manager commands create the journals. History elsewhere inside a selected working tree remains refused, even if ignored. In an initialized multi-repo parent, config/tools/history are normally under `.project-kit/`, outside the selected sibling working trees.

## Verification

From the instruction-kit directory:

```bash
python3 -m unittest discover -s .project-kit/multi-git -p 'test_*.py' -v
sh -n .project-kit/multi-git/multi-git.sh
```

**46 integration tests passed on 2026-10-05.** The integration suite creates temporary repositories and local bare remotes. It covers status, paths with spaces, aliases/groups, previews, dirty/staged/untracked/deleted files, conflicts, failed hooks/signing, ignored collisions, linked worktrees, divergent pulls, local commit/branch/tag undo, publication checks, offline refusal, concurrent-state/ref guards, partial pushes, interruption and retained recovery. No real application repos or external remotes were changed. Linux is verified; macOS and unusual filesystems/custom hooks are not independently tested.
