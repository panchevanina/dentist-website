#!/usr/bin/env python3
"""Conservative multi-repository Git workflows. Python 3.10+, Git 2.40+, Unix."""
from __future__ import annotations

import argparse
import base64
import configparser
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import uuid


class Blocked(Exception):
    pass


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def git_result(path, *args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    # Caller-supplied Git environment must not redirect operations into another repo.
    for key in tuple(env):
        if key.startswith("GIT_") and key not in {"GIT_TERMINAL_PROMPT", "GIT_SSH_COMMAND", "GIT_SSH", "GIT_ASKPASS"}:
            env.pop(key)
    command = ["git", "-C", str(path), *map(str, args)]
    # Stop Git and its ordinary hooks together before recording interrupted state.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, start_new_session=True)
    try:
        stdout, stderr = process.communicate()
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def git(path, *args, check=True, binary=False):
    result = git_result(path, *args)
    if check and result.returncode:
        error = result.stderr.decode(errors="replace").strip() or result.stdout.decode(errors="replace").strip()
        # Avoid retaining URL userinfo in journals or terminal errors.
        error = re.sub(r"(https?://)[^/\s]+@", r"\1[redacted]@", error)
        raise Blocked(f"git {args[0]}: {error}")
    if binary:
        return result.stdout
    return result.stdout.decode(errors="replace").strip()


def exists_ref(path, ref):
    return git(path, "show-ref", "--verify", "--hash", ref, check=False) or None


def commit_oid(path, ref):
    if ref.startswith("-") or any(c.isspace() for c in ref):
        raise Blocked(f"Invalid revision: {ref!r}")
    return git(path, "rev-parse", "--verify", f"{ref}^{{commit}}")


def valid_name(path, name, kind="heads"):
    if name.startswith("-") or not name:
        raise Blocked(f"Invalid {kind} name: {name!r}")
    result = git_result(path, "check-ref-format", f"refs/{kind}/{name}")
    if result.returncode:
        raise Blocked(f"Invalid {kind} name: {name!r}")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".journal-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def repo_identity(path):
    if git(path, "rev-parse", "--is-bare-repository") != "false":
        raise Blocked(f"Bare repository is unsupported: {path}")
    root = Path(git(path, "rev-parse", "--show-toplevel")).resolve()
    if root != path.resolve():
        raise Blocked(f"Configured path must be a repository root: {path}")
    common = Path(git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    private = Path(git(path, "rev-parse", "--absolute-git-dir")).resolve()
    return common, private


def refs(path):
    lines = git(path, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/", "refs/tags/").splitlines()
    return dict(line.split(" ", 1) for line in lines)


def index_path(path):
    return Path(git(path, "rev-parse", "--path-format=absolute", "--git-path", "index"))


def fingerprint(path):
    # Track content, file modes and symlinks; exclude ignored directories such as node_modules.
    names = set(git(path, "ls-files", "-z", "--cached", "--others", "--exclude-standard", binary=True).split(b"\0"))
    digest = hashlib.sha256()
    for name in sorted(names - {b""}):
        file = path / os.fsdecode(name)
        if not file.exists() and not file.is_symlink():
            # Missing tracked files must hash like their post-commit absence.
            continue
        digest.update(name + b"\0")
        if file.is_symlink():
            digest.update(b"link:" + os.fsencode(os.readlink(file)))
        elif file.is_file():
            digest.update(str(file.stat().st_mode & 0o777).encode())
            with file.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        elif file.is_dir():
            digest.update(b"directory")
    idx = index_path(path)
    # Refreshing stat caches is harmless, so compare the logical index, not its raw stat bytes.
    logical_index = git(path, "ls-files", "--stage", "-z", binary=True)
    return {"files": digest.hexdigest(), "index": hashlib.sha256(logical_index).hexdigest(),
            "index_exists": idx.exists()}


def snapshot(path):
    return {"head": git(path, "rev-parse", "--verify", "HEAD", check=False) or None,
            "branch": git(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False) or None,
            "refs": refs(path), "fingerprint": fingerprint(path),
            "branch_config": git(path, "config", "--local", "--get-regexp", r"^branch\.", check=False),
            "remote_config_hash": hashlib.sha256(git(path, "config", "--get-regexp", r"^remote\.", check=False).encode()).hexdigest(),
            "remotes": git(path, "remote").splitlines()}


def status(path):
    branch = git(path, "symbolic-ref", "--quiet", "--short", "HEAD", check=False) or None
    head = git(path, "rev-parse", "--verify", "HEAD", check=False) or None
    upstream = git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False) or None
    counts = None
    if head and upstream:
        result = git(path, "rev-list", "--left-right", "--count", f"HEAD...{upstream}", check=False)
        if result:
            counts = [int(n) for n in result.split()]
    raw = git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all", binary=True).split(b"\0")
    changes, i = [], 0
    while i < len(raw) and raw[i]:
        entry = raw[i].decode(errors="replace")
        item = {"status": entry[:2], "path": entry[3:]}
        if "R" in entry[:2] or "C" in entry[:2]:
            i += 1
            item["from"] = raw[i].decode(errors="replace")
        changes.append(item)
        i += 1
    return {"branch": branch, "head": head, "upstream": upstream,
            "ahead": counts[0] if counts else None, "behind": counts[1] if counts else None,
            "changes": changes, "remote_state": "cached; use fetch to refresh"}


def busy(path):
    common, private = repo_identity(path)
    markers = ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "BISECT_LOG", "sequencer"]
    if any((private / marker).exists() for marker in markers):
        raise Blocked("Git operation already in progress; finish/abort it explicitly")
    locks = [private / "index.lock", private / "HEAD.lock", common / "packed-refs.lock", common / "config.lock"]
    locks.extend((common / "refs").rglob("*.lock"))
    if any(lock.exists() for lock in locks):
        raise Blocked("Git lock exists; investigate its owner (manager will not delete it)")
    if git(path, "ls-files", "--unmerged"):
        raise Blocked("Unmerged index entries exist")
    staged = git(path, "ls-files", "--stage")
    if staged.startswith("160000 ") or "\n160000 " in staged:
        raise Blocked("Submodules require their own workflow; mutation is unsupported")
    sparse = git(path, "config", "--bool", "core.sparseCheckout", check=False)
    if sparse == "true":
        raise Blocked("Sparse checkout mutation is unsupported")
    flagged = git(path, "ls-files", "-v").splitlines()
    if any(line and (line[0] == "S" or line[0].islower()) for line in flagged):
        raise Blocked("skip-worktree/assume-unchanged entries hide changes; clear explicitly first")


def require_clean(path):
    if status(path)["changes"]:
        raise Blocked("Working tree/index is dirty; commit or stash explicitly first")


def occupied(path, branch):
    for block in git(path, "worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        if fields.get("branch") == "refs/heads/" + branch:
            if Path(fields["worktree"]).resolve() != path.resolve():
                raise Blocked(f"Branch {branch} is checked out in another worktree")


def collision_check(path, new_oid):
    if any(line.startswith("160000 ") for line in git(path, "ls-tree", "-r", new_oid).splitlines()):
        raise Blocked("Target contains submodules; mutation requires a separate workflow")
    require_no_lfs(path, new_oid)
    current = set(git(path, "ls-files", "-z", binary=True).split(b"\0"))
    targets = git(path, "ls-tree", "-r", "--name-only", "-z", new_oid, binary=True).split(b"\0")
    for name in targets:
        if not name or name in current:
            continue
        file = path / os.fsdecode(name)
        if file.exists() or file.is_symlink():
            raise Blocked(f"Checkout would overwrite an untracked/ignored path: {os.fsdecode(name)}")
        for parent in file.parents:
            if parent == path:
                break
            if parent.is_file() or parent.is_symlink():
                raise Blocked(f"Checkout path is obstructed: {parent.relative_to(path)}")


def remote_name(value):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value or ""):
        raise Blocked(f"Unsupported/invalid remote name: {value!r}")
    return value


def require_no_lfs(path, oid):
    if git(path, "grep", "-I", "-e", "filter=lfs", oid, "--", ".gitattributes", ":(glob)**/.gitattributes", check=False):
        raise Blocked("Git LFS attributes require a separate verified workflow; mutation is unsupported")
    names = git(path, "ls-files", "-z", "--cached", "--others", "--exclude-standard", binary=True).split(b"\0")
    attributes = {path / ".gitattributes"}
    attributes.update(path / os.fsdecode(name) for name in names if name and Path(os.fsdecode(name)).name == ".gitattributes")
    for file in attributes:
        if file.is_file() and "filter=lfs" in file.read_text(errors="replace"):
            raise Blocked("Working Git LFS attributes require a separate verified workflow")


class Workspace:
    def __init__(self, config):
        self.config_path = Path(config).resolve()
        self.config = configparser.ConfigParser(interpolation=None)
        if not self.config.read(self.config_path):
            raise Blocked(f"Missing config: {self.config_path}; run init first")
        if self.config.get("workspace", "schema_version", fallback="") != "1":
            raise Blocked("Unsupported/missing config schema_version")
        self.root = (self.config_path.parent / self.config.get("workspace", "root", fallback=".")).resolve()
        self.history = (self.root / self.config.get("workspace", "history_dir", fallback=".multi-git")).resolve()
        self.protected = set(split(self.config.get("workspace", "protected_branches", fallback="main,master,develop,development,staging")))
        self.repos = {}
        for section in self.config.sections():
            if not section.startswith("repo:"):
                continue
            rid = section[5:]
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", rid):
                raise Blocked(f"Invalid repository ID: {rid!r}")
            cfg = self.config[section]
            if not cfg.getboolean("enabled", fallback=True):
                continue
            if not cfg.get("path"):
                raise Blocked(f"Missing path for {rid}")
            path = (self.root / cfg["path"]).resolve()
            self.repos[rid] = {"id": rid, "path": path, "config": cfg}

    def select(self, args, optional=False):
        selectors = bool(args.repos) + bool(args.all) + bool(args.group)
        if selectors > 1 or (not selectors and not optional and not args.changed):
            raise Blocked("Choose exactly one of --repos, --all, --group (or --changed alone)")
        ids = list(self.repos) if not selectors or args.all else args.repos
        if args.group:
            section = "group:" + args.group
            if section not in self.config:
                raise Blocked(f"Unknown group: {args.group}")
            ids = split(self.config[section].get("repos", ""))
        if not ids or len(set(ids)) != len(ids):
            raise Blocked("Empty or duplicate repository selection")
        missing = set(ids) - set(self.repos)
        if missing:
            raise Blocked("Unknown/disabled repository IDs: " + ", ".join(sorted(missing)))
        selected = [self.repos[rid] for rid in ids]
        common_dirs = set()
        for repo in selected:
            common, _ = repo_identity(repo["path"])
            if common in common_dirs and args.command not in READ_COMMANDS:
                raise Blocked("Selected repos share a Git directory; operate on one worktree at a time")
            common_dirs.add(common)
        if args.changed:
            filtered = []
            for repo in selected:
                item = status(repo["path"])
                if item["changes"] or (item["ahead"] or 0) > 0:
                    filtered.append(repo)
                elif item["upstream"] is None:
                    raise Blocked(f"{repo['id']}: --changed has no baseline; select explicitly")
            selected = filtered
        return selected

    def alias(self, repo, name):
        return repo["config"].get("alias." + name, name)


def split(value):
    return [part.strip() for part in value.split(",") if part.strip()]


def init(args):
    root = Path(args.root).resolve()
    destination = Path(args.config).resolve() if args.config else root / "multi-git.conf"
    cfg = configparser.ConfigParser(interpolation=None)
    cfg["workspace"] = {"schema_version": "1", "root": os.path.relpath(root, destination.parent),
                        "history_dir": ".multi-git", "protected_branches": "main, master, develop, development, staging"}
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            repo_identity(child)
        except Blocked:
            continue
        rid = re.sub(r"[^A-Za-z0-9_.-]", "_", child.name)
        if not rid or not rid[0].isalnum() and rid[0] != "_":
            rid = "repo_" + rid
        while "repo:" + rid in cfg:
            rid += "_"
        remotes = git(child, "remote").splitlines()
        default = "origin" if "origin" in remotes else (remotes[0] if len(remotes) == 1 else "origin")
        cfg["repo:" + rid] = {"path": os.path.relpath(child, root), "enabled": "true",
                             "fetch_remote": default, "push_remote": default}
    with destination.open("x") as stream:
        stream.write("# Data only; do not source. Review paths, remotes, aliases and groups.\n")
        cfg.write(stream)
    print(f"Created {destination}; {len(cfg.sections()) - 1} repositories. No fetch or branch changes.")


def fetch_remote(path, remote):
    remote_name(remote)
    if remote not in git(path, "remote").splitlines():
        raise Blocked(f"Remote is not configured: {remote}")
    # Explicit refspecs prevent dangerous user fetch mappings into local branches/tags.
    git(path, "fetch", "--no-tags", "--no-recurse-submodules", remote,
        f"+refs/heads/*:refs/remotes/{remote}/*", f"+refs/tags/*:refs/multi-git/published/{remote}/*")


def fetch_every_remote(path):
    for remote in git(path, "remote").splitlines():
        fetch_remote(path, remote)


def unpublished(path, commits):
    for oid in commits:
        found = git(path, "for-each-ref", "--contains", oid, "--format=%(refname)",
                    "refs/remotes/", "refs/multi-git/published/").splitlines()
        if found:
            raise Blocked(f"Commit {oid[:12]} is reachable from {found[0]}; published history cannot be rewound")


def upstream_info(path, branch):
    remote = git(path, "config", "--get", f"branch.{branch}.remote", check=False)
    source = git(path, "config", "--get", f"branch.{branch}.merge", check=False)
    if not remote or not source.startswith("refs/heads/") or "\n" in source:
        raise Blocked(f"Branch {branch} has no unambiguous branch upstream")
    if remote == ".":
        return remote, source
    remote_name(remote)
    return remote, f"refs/remotes/{remote}/{source[11:]}"


def ancestor(path, old, new):
    result = git_result(path, "merge-base", "--is-ancestor", old, new)
    if result.returncode not in (0, 1):
        raise Blocked("Could not verify ancestry")
    return result.returncode == 0


def assert_state(path, expected):
    if snapshot(path) != expected:
        raise Blocked("Repository changed since its snapshot; refusing to overwrite concurrent changes")


@contextlib.contextmanager
def locked(workspace, repos):
    for repo in repos:
        if workspace.history.is_relative_to(repo["path"]):
            _, private = repo_identity(repo["path"])
            if workspace.history != (private / "multi-git-history").resolve():
                raise Blocked("history_dir must be outside selected working trees or in their dedicated Git metadata multi-git-history directory")
    workspace.history.mkdir(parents=True, exist_ok=True, mode=0o700)
    handles = []
    try:
        locations = [workspace.history / "manager.lock"]
        locations += [repo_identity(repo["path"])[0] / "multi-git-manager.lock" for repo in repos]
        for location in sorted(set(locations)):
            handle = location.open("a")
            handles.append(handle)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Blocked(f"Another manager owns {location}")
        yield
    finally:
        for handle in handles:
            handle.close()


def prepare(workspace, repo, args, execute):
    path, cmd = repo["path"], args.command
    busy(path)
    before = snapshot(path)
    if not before["head"] or not before["branch"]:
        raise Blocked("Mutation requires an existing commit and a checked-out branch")
    branch = before["branch"]
    require_no_lfs(path, before["head"])
    if cmd in {"pull", "rebase", "commit"}:
        occupied(path, branch)
    plan = {"id": repo["id"], "path": str(path), "before": before, "status": "prepared",
            "action": cmd, "old": before["head"], "branch": branch}
    if cmd not in {"commit", "tag", "push", "fetch"} and not (cmd == "branch-create" and not args.base):
        require_clean(path)
    if cmd in {"fetch", "push"}:
        plan["remote"] = remote_name(repo["config"].get("fetch_remote" if cmd == "fetch" else "push_remote", "origin"))
    if cmd == "branch-create":
        valid_name(path, args.name)
        if exists_ref(path, "refs/heads/" + args.name):
            raise Blocked(f"Branch already exists: {args.name}")
        occupied(path, args.name)
        plan.update(branch=args.name, new=commit_oid(path, workspace.alias(repo, args.base)) if args.base else before["head"], created_branch=True)
    elif cmd in {"switch", "merge"}:
        target = workspace.alias(repo, args.name if cmd == "switch" else args.into)
        valid_name(path, target)
        occupied(path, target)
        old = exists_ref(path, "refs/heads/" + target)
        if not old:
            if cmd == "merge":
                raise Blocked(f"Merge target must exist locally: {target}")
            remote = remote_name(repo["config"].get("fetch_remote", "origin"))
            if execute and args.pull:
                fetch_remote(path, remote)
            old = commit_oid(path, "refs/remotes/" + remote + "/" + target)
            plan["created_branch"] = True
        plan.update(branch=target, old=old, new=old)
        if cmd == "merge":
            plan["source"] = commit_oid(path, workspace.alias(repo, args.name))
        if cmd == "switch" and args.pull:
            if plan.get("created_branch"):
                raise Blocked("switch --pull requires a local branch with configured upstream; create/configure it explicitly first")
            remote, upstream = upstream_info(path, target)
            if execute and remote != ".":
                fetch_remote(path, remote)
            plan["new"] = commit_oid(path, upstream)
            if not ancestor(path, old, plan["new"]):
                raise Blocked(f"Branch {target} diverged; pull is fast-forward only")
    elif cmd == "pull":
        remote, upstream = upstream_info(path, branch)
        if execute and remote != ".":
            fetch_remote(path, remote)
        plan["new"] = commit_oid(path, upstream)
        if not ancestor(path, before["head"], plan["new"]):
            raise Blocked("Current branch diverged; pull is fast-forward only")
    elif cmd == "rebase":
        if branch in workspace.protected:
            raise Blocked(f"Rebase of protected branch is forbidden: {branch}")
        if execute:
            fetch_every_remote(path)
        if args.onto:
            onto = workspace.alias(repo, args.onto)
        else:
            _, onto = upstream_info(path, branch)
        plan["onto"] = commit_oid(path, onto)
        candidates = git(path, "rev-list", plan["onto"] + "..HEAD").splitlines()
        if git(path, "rev-list", "--merges", plan["onto"] + "..HEAD"):
            raise Blocked("Replaying merge commits requires a separate reviewed rebase workflow")
        unpublished(path, candidates)
        plan["publication"] = "verified against configured remotes" if execute else "cached only; execution will fetch all remotes"
    elif cmd == "commit":
        if not args.messages:
            raise Blocked("commit requires --messages JSON file with a message for each selected repo")
        messages = json.loads(Path(args.messages).read_text())
        message = messages.get(repo["id"]) if isinstance(messages, dict) else None
        if not isinstance(message, str) or not message.strip() or "\0" in message:
            raise Blocked(f"Missing/empty/invalid commit message for {repo['id']}")
        plan["message"] = message
        plan["index_before"] = base64.b64encode(index_path(path).read_bytes()).decode()
        if not args.all_changes and not git(path, "diff", "--cached", "--name-only"):
            raise Blocked("No staged changes; use --all-changes explicitly if intended")
        if args.all_changes and not status(path)["changes"]:
            raise Blocked("No changes to commit")
    elif cmd == "tag":
        valid_name(path, args.name, "tags")
        if exists_ref(path, "refs/tags/" + args.name):
            raise Blocked(f"Tag already exists: {args.name}")
        plan["tag"] = args.name
    elif cmd == "push":
        remote = plan["remote"]
        if execute:
            fetch_remote(path, remote)
        if args.tag:
            valid_name(path, args.tag, "tags")
            source = exists_ref(path, "refs/tags/" + args.tag)
            if not source:
                raise Blocked(f"Missing local tag: {args.tag}")
            destination = "refs/tags/" + args.tag
        else:
            source = before["head"]
            configured_remote = git(path, "config", "--get", f"branch.{branch}.remote", check=False)
            configured_branch = git(path, "config", "--get", f"branch.{branch}.merge", check=False)
            destination = configured_branch if configured_remote == remote and configured_branch else "refs/heads/" + branch
        if not destination.startswith(("refs/heads/", "refs/tags/")) or "\n" in destination:
            raise Blocked("Invalid push destination")
        plan.update(source=source, destination=destination)
        if execute:
            remote_oid = remote_tip(path, remote, destination)
            plan["remote_before"] = remote_oid
            if remote_oid and remote_oid != source:
                if args.tag or not ancestor(path, remote_oid, source):
                    raise Blocked("Remote destination is not a fast-forward; force push is unavailable")
    if "new" in plan:
        collision_check(path, plan["new"])
    assert_state(path, before)
    return plan


def remote_tip(path, remote, destination):
    output = git(path, "ls-remote", "--refs", remote, destination)
    matches = [line.split()[0] for line in output.splitlines() if line.split()[1] == destination]
    if len(matches) > 1:
        raise Blocked("Ambiguous remote ref")
    return matches[0] if matches else None


def isolate(plan, args, run_dir, save):
    if plan["action"] not in {"merge", "rebase"}:
        return
    path = Path(plan["path"])
    worker = run_dir / ("worktree-" + plan["id"])
    plan["worker"] = str(worker)
    save()
    git(path, "worktree", "add", "--detach", str(worker), plan["old"])
    try:
        if plan["action"] == "merge":
            git(worker, "merge", "--no-edit", "--no-autostash", "--no-squash", "--", plan["source"])
        else:
            git(worker, "rebase", "--no-fork-point", "--no-update-refs", "--no-autostash", plan["onto"])
        require_clean(worker)
        plan["new"] = commit_oid(worker, "HEAD")
        collision_check(path, plan["new"])
        git(path, "update-ref", f"refs/multi-git/{run_dir.name}/{plan['id']}/prepared", plan["new"], "")
        git(path, "worktree", "remove", str(worker))
        plan.pop("worker", None)
    except BaseException:
        # Only the disposable worktree is aborted. Original checkout is untouched.
        abort_command = "merge" if plan["action"] == "merge" else "rebase"
        git(worker, abort_command, "--abort", check=False)
        # Never force-remove hook-created/untracked files; retain them for examination.
        try:
            git(path, "worktree", "remove", str(worker))
            plan.pop("worker", None)
        except Blocked:
            pass
        raise
    finally:
        save()


def apply_head(path, old, new):
    if old == new:
        return
    ref = git(path, "symbolic-ref", "HEAD")
    collision_check(path, new)
    # read-tree checks index/files, then the expected-old CAS detects external ref writers.
    git(path, "read-tree", "-m", "-u", old, new)
    intermediate = fingerprint(path)
    try:
        git(path, "update-ref", "-m", "multi-git guarded update", ref, new, old)
    except BaseException:
        if exists_ref(path, ref) == old and fingerprint(path) == intermediate:
            git(path, "read-tree", "-m", "-u", new, old)
        raise


def apply(plan, args, save):
    path = Path(plan["path"])
    assert_state(path, plan["before"])
    busy(path)
    plan["status"] = "applying"
    save()
    cmd = plan["action"]
    if cmd in {"branch-create", "switch", "merge", "pull", "rebase"}:
        branch = plan["branch"]
        if plan.get("created_branch"):
            git(path, "update-ref", "-m", "multi-git create", "refs/heads/" + branch, plan["old"] if cmd == "switch" else plan["new"], "")
        if plan["before"]["branch"] != branch:
            git(path, "switch", "--no-overwrite-ignore", "--", branch)
        if git(path, "symbolic-ref", "--quiet", "--short", "HEAD") != branch:
            raise Blocked("Checkout changed unexpectedly before ref application")
        current = commit_oid(path, "HEAD")
        expected = plan["new"] if cmd == "branch-create" else plan["old"]
        if current != expected:
            raise Blocked("Target branch moved before application")
        if cmd != "branch-create":
            require_clean(path)
            apply_head(path, plan["old"], plan["new"])
    elif cmd == "commit":
        if args.all_changes:
            try:
                git(path, "add", "--all", "--", ".")
            finally:
                plan["staged_fingerprint"] = fingerprint(path)
                save()
            if any(change["status"][1] != " " for change in status(path)["changes"]):
                raise Blocked("Some requested changes could not be staged; commit was not attempted")
        plan["staged_fingerprint"] = fingerprint(path)
        save()
        git(path, "commit", "-m", plan["message"])
    elif cmd == "tag":
        # git tag honors configured signing and refuses existing refs.
        parameters = ["tag"]
        if args.message is not None:
            parameters += ["-a", "-m", args.message]
        parameters += ["--", plan["tag"], plan["before"]["head"]]
        git(path, *parameters)
    elif cmd == "fetch":
        fetch_remote(path, plan["remote"])
    elif cmd == "push":
        plan["remote_outcome"] = "push attempted; publication uncertain without a verified receipt"
        save()
        git(path, "push", "--porcelain", "--no-follow-tags", "--recurse-submodules=no", plan["remote"],
            f"{plan['source']}:{plan['destination']}")
        plan["published"] = True
        plan["remote_after"] = remote_tip(path, plan["remote"], plan["destination"])
        if plan["remote_after"] != plan["source"]:
            raise Blocked("Remote changed after push; inspect remote before further action")
        plan["remote_outcome"] = "published; remote ref verified"
    after = snapshot(path)
    verify_owned_changes(plan, after)
    plan["after"] = after
    plan["ownership_verified"] = True
    save()
    # Protect resulting objects from garbage collection after an undo.
    namespace = f"refs/multi-git/{plan['run_id']}/{plan['id']}"
    git(path, "update-ref", namespace + "/after", after["head"], "")
    for number, (_, new) in enumerate(changed_refs(plan).values()):
        if new:
            git(path, "update-ref", f"{namespace}/ref-after-{number}", new, "")
    assert_state(path, after)
    plan["status"] = "changed" if plan["after"] != plan["before"] else "unchanged"
    if cmd == "push":
        plan["status"] = "published"
    elif cmd == "fetch":
        plan["status"] = "fetched"
    save()


def verify_owned_changes(plan, after):
    """Do not attribute unexpected hook/concurrent changes to this run."""
    before, cmd = plan["before"], plan["action"]
    allowed = set()
    if cmd in {"branch-create", "switch", "merge", "pull", "rebase", "commit"}:
        allowed.add("refs/heads/" + plan["branch"])
    elif cmd == "tag":
        allowed.add("refs/tags/" + plan["tag"])
    changed = {ref for ref in before["refs"].keys() | after["refs"].keys()
               if before["refs"].get(ref) != after["refs"].get(ref)}
    if (changed - allowed or before["branch_config"] != after["branch_config"]
            or before["remote_config_hash"] != after["remote_config_hash"]):
        raise Blocked("Unexpected refs/config changed (hook or concurrent writer); manual review required")
    expected_branch = plan["branch"] if cmd in {"branch-create", "switch", "merge", "pull", "rebase"} else before["branch"]
    if after["branch"] != expected_branch:
        raise Blocked("Unexpected checkout changed; manual review required")
    if cmd == "commit":
        parents = git(Path(plan["path"]), "rev-list", "--parents", "-n", "1", after["head"]).split()[1:]
        if parents != [before["head"]]:
            raise Blocked("Commit did not produce one ordinary child of the original HEAD; manual review required")
    elif after["head"] != plan.get("new", before["head"]):
        raise Blocked("Unexpected HEAD changed; manual review required")
    if cmd in {"tag", "push", "fetch"} or (cmd == "branch-create" and plan["new"] == before["head"]):
        if before["fingerprint"] != after["fingerprint"]:
            raise Blocked("Unexpected file/index changes; manual review required")
    elif cmd != "commit":
        require_clean(Path(plan["path"]))


def changed_refs(plan):
    before, after = plan["before"]["refs"], plan["after"]["refs"]
    return {ref: (before.get(ref), after.get(ref)) for ref in before.keys() | after.keys() if before.get(ref) != after.get(ref)}


def rollback_check(plan, refresh):
    if plan["action"] in {"push", "fetch"}:
        raise Blocked("Remote publication/fetch state is not reversible by this manager")
    if "after" not in plan:
        raise Blocked("Incomplete run has no verified post-state; inspect report and recovery refs manually")
    path = Path(plan["path"])
    busy(path)
    assert_state(path, plan["after"])
    changes = changed_refs(plan)
    if refresh:
        fetch_every_remote(path)
    for ref, (old, new) in changes.items():
        if ref.startswith("refs/heads/"):
            occupied(path, ref[11:])
            if old and new:
                removed = git(path, "rev-list", new, "--not", old).splitlines()
                unpublished(path, removed)
            elif new:
                branch = ref[11:]
                for remote in git(path, "remote").splitlines():
                    if exists_ref(path, f"refs/remotes/{remote}/{branch}"):
                        raise Blocked(f"Created branch {branch} was published; local rollback refused")
        elif ref.startswith("refs/tags/"):
            for remote in git(path, "remote").splitlines():
                if exists_ref(path, f"refs/multi-git/published/{remote}/{ref[10:]}"):
                    raise Blocked(f"Tag {ref[10:]} was published; rollback refused")
    original_branch = plan["before"]["branch"]
    occupied(path, original_branch)
    if plan["action"] == "commit":
        if plan["after"]["fingerprint"]["files"] != plan["before"]["fingerprint"]["files"]:
            raise Blocked("Commit hooks changed file content; restore needs manual review")
    else:
        if plan["before"]["fingerprint"]["files"] != plan["after"]["fingerprint"]["files"]:
            require_clean(path)
            collision_check(path, plan["before"]["head"])
    return changes


def restore(plan, refresh=True):
    changes = rollback_check(plan, refresh)
    path = Path(plan["path"])
    before = plan["before"]
    # A commit undo changes only HEAD/index; preserve the user's original dirty file bytes.
    if plan["action"] == "commit":
        old, new = changes["refs/heads/" + before["branch"]]
        idx = index_path(path)
        lock = idx.with_name("index.lock")
        with lock.open("xb") as stream:
            try:
                stream.write(base64.b64decode(plan["index_before"]))
                stream.flush()
                os.fsync(stream.fileno())
                git(path, "update-ref", "-m", "multi-git undo commit", "refs/heads/" + before["branch"], old, new)
                os.replace(lock, idx)
            finally:
                lock.unlink(missing_ok=True)
    else:
        current_branch = plan["after"]["branch"]
        current_ref = "refs/heads/" + current_branch
        if current_ref in changes and changes[current_ref][0] is not None:
            old, new = changes.pop(current_ref)
            apply_head(path, new, old)
        if current_branch != before["branch"]:
            git(path, "switch", "--no-overwrite-ignore", "--", before["branch"])
        for ref, (old, new) in changes.items():
            if old is None:
                git(path, "update-ref", "-d", ref, new)
            else:
                git(path, "update-ref", "-m", "multi-git rollback", ref, old, new)
    if snapshot(path) != before:
        raise Blocked("Rollback did not exactly reproduce the relevant original state; inspect report")
    plan["status"] = "restored"
    plan["restored_at"] = utc()


def recover_failure(plan):
    path = Path(plan["path"])
    if plan.get("ownership_verified") and plan["action"] not in {"push", "fetch"}:
        restore(plan)
        return
    now = snapshot(path)
    if plan["action"] == "commit" and now["head"] == plan["before"]["head"]:
        staged = plan.get("staged_fingerprint")
        if (staged and now["fingerprint"] == staged
                and staged["files"] == plan["before"]["fingerprint"]["files"]):
            idx = index_path(path)
            with idx.with_name("index.lock").open("xb") as stream:
                stream.write(base64.b64decode(plan["index_before"]))
            os.replace(idx.with_name("index.lock"), idx)
            if snapshot(path) == plan["before"]:
                plan["status"] = "failed; original index restored"
                return
    if now == plan["before"]:
        plan["status"] = "failed; original state preserved"
        return
    # Record observable partial state, but do not treat arbitrary hook changes as owned.
    plan["observed_after_failure"] = now
    plan["status"] = "partial; manual review required"


def execute(workspace, repos, args):
    if not args.execute:
        records = []
        errors = False
        for repo in repos:
            try:
                record = prepare(workspace, repo, args, False)
                records.append({"id": repo["id"], "action": args.command, "status": "preview",
                                **{key: record[key] for key in ("branch", "old", "new", "onto", "source", "remote", "destination", "tag") if key in record}})
            except (Blocked, OSError, ValueError) as error:
                records.append({"id": repo["id"], "status": "blocked", "error": str(error)})
                errors = True
        output(records, args.json)
        if not args.json:
            print("Preview only; cached remote state. --execute fetches where required and validates again.")
        return 1 if errors else 0
    with locked(workspace, repos):
        run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
        run_dir = workspace.history / run_id
        run_dir.mkdir(mode=0o700)
        journal = {"schema_version": 1, "run_id": run_id, "created_at": utc(), "action": args.command,
                   "config": str(workspace.config_path), "status": "preparing", "repos": [],
                   "selection": [repo["id"] for repo in repos],
                   "remote_cache_note": "Fetched objects/remote tracking refs are retained; configured remotes define publication checks."}
        save = lambda: write_json(run_dir / "run.json", journal)
        save()
        active = None
        try:
            # Prepare every repo (including isolated integrations) before any checkout/history mutation.
            for repo in repos:
                active = {"id": repo["id"], "path": str(repo["path"]), "status": "preparing", "action": args.command}
                journal["repos"].append(active)
                save()
                prepared = prepare(workspace, repo, args, True)
                active.update(prepared)
                active["run_id"] = run_id
                git(repo["path"], "update-ref", f"refs/multi-git/{run_id}/{repo['id']}/before", prepared["before"]["head"], "")
                if prepared.get("old") != prepared["before"]["head"]:
                    git(repo["path"], "update-ref", f"refs/multi-git/{run_id}/{repo['id']}/target-before", prepared["old"], "")
                save()
                isolate(active, args, run_dir, save)
            for active in journal["repos"]:
                apply(active, args, save)
            journal["status"] = "complete"
        except (Blocked, OSError, ValueError, KeyboardInterrupt) as error:
            journal["error"] = str(error) or "Interrupted"
            journal["status"] = "failed"
            if active:
                active["error"] = journal["error"]
                if active.get("status") == "applying":
                    try:
                        recover_failure(active)
                    except (Blocked, OSError) as recovery_error:
                        active["recovery_error"] = str(recovery_error)
                        active["status"] = "partial; manual review required"
                else:
                    active["status"] = "blocked"
            for previous in reversed(journal["repos"]):
                if previous is active or previous.get("status") not in {"changed", "unchanged"}:
                    continue
                try:
                    restore(previous)
                except (Blocked, OSError) as recovery_error:
                    previous["recovery_error"] = str(recovery_error)
            for entry in journal["repos"]:
                if entry.get("status") == "prepared":
                    entry["status"] = "skipped"
            recorded = {entry["id"] for entry in journal["repos"]}
            journal["repos"].extend({"id": repo["id"], "path": str(repo["path"]),
                                     "action": args.command, "status": "skipped"}
                                    for repo in repos if repo["id"] not in recorded)
            save()
        finally:
            journal["finished_at"] = utc()
            save()
        output(journal, args.json)
        return 0 if journal["status"] == "complete" else 1


def output(value, as_json):
    if as_json:
        # Keep terminal/agent output compact; binary index recovery lives only in run.json.
        def public(item):
            if isinstance(item, dict):
                return {key: public(val) for key, val in item.items() if key != "index_before"}
            if isinstance(item, list):
                return [public(val) for val in item]
            return item
        print(json.dumps(public(value), indent=2, ensure_ascii=True))
        return
    if isinstance(value, dict) and "run_id" in value:
        print(f"Run {value['run_id']} — {value['action']}: {value['status']}")
        records = value["repos"]
        if value.get("error"):
            print(value["error"])
        print(f"Report: multi-git.sh report {value['run_id']}")
        if value["action"] in {"push", "fetch"}:
            print("Push/fetch effects are retained; local rollback is unavailable for this action.")
        else:
            print(f"Rollback preview: multi-git.sh rollback {value['run_id']} --all")
    else:
        records = value if isinstance(value, list) else [value]
    for item in records:
        branch = item.get("branch") or ("detached" if item.get("head") else "unborn")
        if "changes" in item:
            upstream = item.get("upstream") or "none"
            print(f"{item['id']}: {branch} | upstream={upstream} | ahead={item.get('ahead')} behind={item.get('behind')} | {len(item['changes'])} changed paths")
            for change in item["changes"]:
                print(f"  {change['status']} {json.dumps(change['path'], ensure_ascii=False)}")
        else:
            print(f"{item.get('id', '')}: {item.get('status', '')} {item.get('action', '')} {item.get('branch', '')}")
            if item.get("new"):
                print(f"  {str(item.get('old', ''))[:12]} -> {item['new'][:12]}")
            for key in ("error", "recovery_error", "worker", "remote_outcome"):
                if item.get(key):
                    print(f"  {key}: {item[key]}")


def rollback(workspace, args):
    run_dir = workspace.history / args.run_id
    journal = json.loads((run_dir / "run.json").read_text())
    selected = workspace.select(args)
    by_id = {item["id"]: item for item in journal["repos"]}
    missing = {repo["id"] for repo in selected} - by_id.keys()
    if missing and not args.all:
        raise Blocked("Selected repositories not in run: " + ", ".join(sorted(missing)))
    selected = [repo for repo in selected if repo["id"] in by_id]
    records, failures = [], False
    with locked(workspace, selected):
        # Validate all selected candidates before applying a selective rollback.
        ready = []
        for repo in selected:
            entry = by_id[repo["id"]]
            record = {"id": repo["id"], "status": "eligible", "action": "rollback"}
            try:
                if Path(entry["path"]).resolve() != repo["path"]:
                    raise Blocked("Config path differs from journal path")
                if entry.get("status") == "restored":
                    record["status"] = "already restored"
                else:
                    rollback_check(entry, args.execute)
                    ready.append(entry)
            except (Blocked, OSError) as error:
                record.update(status="refused", error=str(error))
                failures = True
            records.append(record)
        if args.execute and not failures:
            journal.setdefault("rollback_attempts", []).append({"at": utc(), "repos": [item["id"] for item in ready], "status": "applying"})
            write_json(run_dir / "run.json", journal)
            for entry in reversed(ready):
                try:
                    restore(entry, refresh=False)
                    next(item for item in records if item["id"] == entry["id"])["status"] = "restored"
                    write_json(run_dir / "run.json", journal)
                except (Blocked, OSError, KeyboardInterrupt) as error:
                    next(item for item in records if item["id"] == entry["id"]).update(status="refused", error=str(error))
                    failures = True
                    break
            journal["rollback_attempts"][-1]["status"] = "partial" if failures else "complete"
            write_json(run_dir / "run.json", journal)
    output(records, args.json)
    if not args.execute and not args.json:
        print("Preview only; publication checks use cached refs. --execute refreshes all configured remotes.")
    return 1 if failures else 0


READ_COMMANDS = {"status", "branches", "diff", "log"}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", help="workspace config (default ./multi-git.conf)")
    sub = result.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("init", help="discover direct child repositories; never overwrite config")
    setup.add_argument("--root", default=".")
    setup.add_argument("--config", default=argparse.SUPPRESS)
    for name in sorted(READ_COMMANDS | {"fetch", "pull", "switch", "branch-create", "merge", "rebase", "commit", "tag", "push", "rollback"}):
        command = sub.add_parser(name)
        command.add_argument("--config", default=argparse.SUPPRESS)
        command.add_argument("--repos", nargs="+")
        command.add_argument("--all", action="store_true")
        command.add_argument("--group")
        command.add_argument("--changed", action="store_true")
        command.add_argument("--json", action="store_true")
        if name not in READ_COMMANDS:
            command.add_argument("--execute", action="store_true", help="apply; without this flag preview only")
        if name in {"switch", "branch-create", "merge", "tag"}:
            command.add_argument("name")
        if name == "switch":
            command.add_argument("--pull", action="store_true")
        if name == "branch-create":
            command.add_argument("--base")
        if name == "merge":
            command.add_argument("--into", required=True)
        if name == "rebase":
            command.add_argument("--onto")
        if name == "commit":
            command.add_argument("--all-changes", action="store_true")
            command.add_argument("--messages")
        if name == "tag":
            command.add_argument("--message")
        if name == "push":
            command.add_argument("--tag")
        if name == "rollback":
            command.add_argument("run_id")
        if name == "log":
            command.add_argument("--limit", type=int, default=10)
        if name == "diff":
            command.add_argument("--staged", action="store_true")
            command.add_argument("--stat", action="store_true")
    for name in ("history", "report"):
        command = sub.add_parser(name)
        command.add_argument("--config", default=argparse.SUPPRESS)
        command.add_argument("--json", action="store_true")
        if name == "report":
            command.add_argument("run_id")
    return result


def main():
    args = parser().parse_args()
    version = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout
    match = re.search(r"(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (2, 40):
        raise Blocked("Git 2.40+ is required (tested here with Git 2.53)")
    if hasattr(args, "run_id") and not re.fullmatch(r"[0-9]{8}T[0-9]{6}-[0-9a-f]{10}", args.run_id):
        raise Blocked("Invalid run ID")
    if args.command == "init":
        init(args)
        return 0
    workspace = Workspace(args.config or "multi-git.conf")
    if args.command == "report":
        output(json.loads((workspace.history / args.run_id / "run.json").read_text()), args.json)
        return 0
    if args.command == "history":
        records = []
        for file in sorted(workspace.history.glob("*/run.json")):
            run = json.loads(file.read_text())
            records.append({key: run[key] for key in ("run_id", "created_at", "action", "status")})
        if args.json:
            print(json.dumps(records, indent=2))
        else:
            for record in records:
                print(f"{record['run_id']} {record['action']} {record['status']}")
        return 0
    if args.command == "rollback":
        return rollback(workspace, args)
    repos = workspace.select(args, optional=args.command in READ_COMMANDS)
    if args.command in READ_COMMANDS:
        records = []
        for repo in repos:
            if args.command == "status":
                records.append({"id": repo["id"], "path": str(repo["path"]), **status(repo["path"])})
            else:
                parameters = {"branches": ["branch", "-vv", "--no-color"],
                              "diff": ["diff", "--no-ext-diff", "--no-textconv", "--no-color"] + (["--stat"] if getattr(args, "stat", False) else []) + (["--cached"] if getattr(args, "staged", False) else []),
                              "log": ["log", "--oneline", "--no-decorate", "-n", str(getattr(args, "limit", 10))]}[args.command]
                records.append({"id": repo["id"], "text": git(repo["path"], *parameters)})
        if args.command == "status" or args.json:
            output(records, args.json)
            if args.command == "status" and not args.json:
                print("Ahead/behind uses cached refs. Run fetch --all --execute to refresh.")
        else:
            for record in records:
                print(record["id"] + ":\n" + record["text"])
        return 0
    return execute(workspace, repos, args)


if __name__ == "__main__":
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Interrupted by signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        sys.exit(main())
    except (Blocked, OSError, ValueError, configparser.Error) as error:
        print(f"Blocked: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted; inspect history/report before continuing.", file=sys.stderr)
        sys.exit(130)
