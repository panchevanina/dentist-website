# Agent use of the multi-repo manager

Keep this guide at the central tool installation. Add a short link and the actual script/config paths to your parent workspace's `AGENTS.md`. Do not copy the implementation into each repository or reread complete journals for routine operations.

1. Resolve requested repository IDs against the workspace's `multi-git.conf`. Read each affected repo's own instructions and the current task's affected-repo record. Use `status --repos ID...` first; use `--json` when parsing fields helps.
2. Map the user's request to the narrow command/selection. Preview it, then use `--execute` when the exact operation is already authorized. The CLI flag alone does not require another user confirmation. Unrequested publication still requires explicit authorization. Complex code workflows continue to follow the agreed planning rules.
3. Commit only when the user explicitly asked; implementation or review approval is not commit authorization. For requested commits, inspect both staged and unstaged diffs and relevant untracked files. Supply accurate per-repo messages in a JSON manifest outside the selected repos. Use `--all-changes` only when the user requested that scope. Explain unrelated edits that make scope uncertain.
4. For “repos we changed,” use the active task/state, then check Git evidence. `--changed` is a Git-state filter, not an authorship detector. Dirty files block rebase/pull/merge/switch; do not silently commit/stash/reset or force a result.
5. Use explicit base names/aliases. Remote-tracking refs may be stale until fetched. Rebase execution refreshes all configured remotes, and refuses protected/published/merge-commit history. Merge/rebase conflicts are reported from isolation; do not automatically choose a conflict side.
6. Report the actual run ID and each changed, blocked/skipped or restored repo. Mention remote publication or uncertainty when applicable. Offer `rollback RUN_ID --repos ...` for a specific eligible local result; its preview is not a guarantee until fresh publication/state checks pass. Never suggest force-push or remote deletion to make rollback proceed.
7. Update the current task/state with the run ID, affected repos and concise outcomes when useful for a handoff. Full recovery metadata stays in `.multi-git/`; do not paste binary index data into agent context. For incomplete/manual-review runs, inspect the report and original state before proposing recovery.

Example coordinator instruction (replace paths with the actual shared installation/workspace paths):

> Manage related repos with the shared `multi-git.sh` and this workspace's `multi-git.conf`. Read the linked central agent guide when performing multi-repo Git operations. Inspect status first, require explicit selected repo IDs for task-owned changes, preserve unrelated edits, and record run IDs for recovery. Do not publish without an explicit publishing request.

The script does not interpret natural language and makes no LLM calls. The agent supplies selection, change understanding and commit messages. See [the operating guide](README.md) for runnable examples and recovery limits.
