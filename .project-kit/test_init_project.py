"""End-to-end initializer tests; isolated Git repos, no network/databases."""
import json
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import tempfile
import time
import unittest

KIT = Path(__file__).resolve().parent


class InitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.target = self.base / "new project"
        self.logs = self.base / "codex"
        (self.logs / "sessions").mkdir(parents=True)
        (self.logs / "archived_sessions").mkdir()
        self.env = dict(os.environ, CODEX_HOME=str(self.logs), PYTHONDONTWRITEBYTECODE="1")
        for key in list(self.env):
            if key.startswith("GIT_"):
                del self.env[key]
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.env["GIT_CONFIG_GLOBAL"] = os.devnull

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, *options, mode="single", target=None, kit=KIT, okay=True):
        result = subprocess.run([str(kit / "init-project.sh"), str(target or self.target),
                                 "--mode", mode, "--non-interactive", *options],
                                capture_output=True, text=True, env=self.env)
        if okay:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def git(self, repo, *args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                                text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def repo(self, relative="."):
        path = self.target / relative
        path.mkdir(parents=True, exist_ok=True)
        self.git(path, "init", "-b", "develop")
        self.git(path, "config", "user.name", "Fixture")
        self.git(path, "config", "user.email", "fixture@example.invalid")
        (path / "app.txt").write_text("unchanged application\n")
        self.git(path, "add", "app.txt")
        self.git(path, "commit", "-m", "Fixture")
        return path

    def latest_report(self):
        paths = list((self.target / ".project-kit/.project-init/runs").glob("*/report.json"))
        path = max(paths, key=lambda p: p.stat().st_mtime_ns)
        return json.loads(path.read_text())

    def test_new_project_files_configs_and_no_source_history(self):
        self.invoke("--project-id", "new-id", "--timezone", "UTC")
        config = json.loads((self.target / ".project-kit/usage/config.json").read_text())
        self.assertEqual(config["output_dir"], "../.usage")
        self.assertEqual(config["projects"], [{"id": "new-id", "roots": [str(self.target)]}])
        self.assertEqual(config["timezone"], "UTC")
        self.assertEqual({p.name for p in self.target.iterdir()}, {"AGENTS.md", ".project-kit"})
        for path in ["AGENTS.md", ".project-kit/AGENTS.md", ".project-kit/PROJECT_BRIEF.md", ".project-kit/STATE.md",
                     ".project-kit/plans/TEMPLATE.md", ".project-kit/tasks/TEMPLATE.md", ".project-kit/SETUP_CHECKLIST.md", ".project-kit/OPTIONAL_CONFIG.md",
                     ".project-kit/multi-git/multi_git.py", ".project-kit/database/ENVIRONMENTS.json", ".project-kit/usage/record.schema.json"]:
            self.assertTrue((self.target / path).is_file(), path)
        self.assertTrue(os.access(self.target / ".project-kit/multi-git/multi-git.sh", os.X_OK))
        self.assertTrue(os.access(self.target / ".project-kit/init-project.sh", os.X_OK))
        for path in [".usage", ".multi-git", ".git", "usage/initial-observations.jsonl",
                     "plans/project-init.md", "PROJECT_BRIEF_SECONDMENTS.md"]:
            self.assertFalse((self.target / path).exists(), path)
        env_map = json.loads((self.target / ".project-kit/database/ENVIRONMENTS.json").read_text())
        self.assertEqual(env_map["project_id"], "new-id")
        self.assertTrue(all(not e["configured"] and not e["disposable"] for e in env_map["environments"].values()))
        examples = (self.target / ".project-kit/USAGE_EXAMPLES.txt").read_text()
        self.assertIn("cd '" + str(self.target / ".project-kit") + "'", examples)
        self.assertNotIn("/home/deann/", examples)
        self.assertNotIn("post-implementation review and explicit-commit rules added", (self.target / ".project-kit/STATE.md").read_text())
        for path in self.target.rglob('*.md'):
            if '.project-init' in path.parts:
                continue
            value = path.read_text()
            self.assertEqual(value.count('```') % 2, 0, str(path))
            for ref in re.findall(r'\]\(([^)]+)\)', value):
                if re.match(r'[a-z]+://', ref) or ref.startswith('#'):
                    continue
                self.assertTrue((path.parent / ref.split('#')[0]).exists(), f'{path}: {ref}')

    def test_existing_files_preserved_and_agents_conflict_reported(self):
        self.target.mkdir()
        saved = {"AGENTS.md": "Team rules\n", ".gitignore": "team-secret.txt\n", "STATE.md": "Active task\n",
                 "PROJECT_BRIEF.md": "Real brief\n", "usage/config.json": '{"custom": true}\n',
                 "multi-git.conf": "existing config\n", ".project-kit/STATE.md": "Existing kit state\n",
                 ".project-kit/usage/config.json": '{"custom": true}\n', ".cursor/rules/team.mdc": "Team Cursor rule\n"}
        for name, text in saved.items():
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        before = {name: (self.target / name).stat() for name in saved}
        result = self.invoke()
        self.assertIn("POTENTIAL AGENTS INSTRUCTION CONFLICT", result.stdout)
        for name, text in saved.items():
            self.assertEqual((self.target / name).read_text(), text)
            self.assertEqual((self.target / name).stat().st_mtime_ns, before[name].st_mtime_ns)
            self.assertEqual((self.target / name).stat().st_mode, before[name].st_mode)
        self.assertIn("Manually reconcile", (self.target / ".project-kit/SETUP_CHECKLIST.md").read_text())

    def test_single_repository_config_status_and_no_git_state_changes(self):
        repo = self.repo()
        head = self.git(repo, "rev-parse", "HEAD")
        index = (repo / ".git/index").read_bytes()
        self.invoke()
        self.assertEqual(head, self.git(repo, "rev-parse", "HEAD"))
        self.assertEqual(index, (repo / ".git/index").read_bytes())
        result = subprocess.run([str(repo / ".project-kit/multi-git/multi-git.sh"), "--config", str(repo / ".project-kit/multi-git.conf"),
                                 "status", "--all", "--json"], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"branch": "develop"', result.stdout)
        self.assertIn("[repo:project]", (repo / ".project-kit/multi-git.conf").read_text())

    def test_multi_nested_repos_and_preserved_child_rules(self):
        frontend = self.repo("frontend")
        backend = self.repo("services/backend")
        (frontend / "AGENTS.md").write_text("Existing frontend rules\n")
        self.invoke("--repo", "services/backend", mode="multi")
        self.assertEqual((frontend / "AGENTS.md").read_text(), "Existing frontend rules\n")
        instructions = (backend / "AGENTS.md").read_text()
        self.assertIn("../../.project-kit/AGENTS.md", instructions)
        self.assertIn("../../.project-kit/multi-git.conf", instructions)
        config = (self.target / ".project-kit/multi-git.conf").read_text()
        self.assertIn("[repo:frontend]", config)
        self.assertIn("[repo:backend]", config)
        self.assertNotIn("[repo:services]", config)
        roots = json.loads((self.target / ".project-kit/usage/config.json").read_text())["projects"][0]["roots"]
        self.assertEqual(roots, [str(self.target)])
        self.assertEqual({p.name for p in backend.iterdir()}, {".git", "app.txt", "AGENTS.md"})

    def test_linked_worktrees_and_colliding_repository_ids(self):
        main = self.repo("backend app")
        self.git(main, "worktree", "add", "-b", "feature", str(self.target / "backend_app"))
        self.invoke(mode="multi")
        config = (self.target / ".project-kit/multi-git.conf").read_text()
        self.assertIn("[repo:backend_app]", config)
        self.assertIn("[repo:backend_app_]", config)
        self.assertTrue((self.target / "backend_app/AGENTS.md").is_file())
        self.assertTrue((self.target / "backend_app/.git").is_file())

    def test_rerun_retains_custom_config_and_modified_tools(self):
        self.invoke()
        config = self.target / ".project-kit/usage/config.json"
        tool = self.target / ".project-kit/usage/collector.py"
        config.write_text('{"user-customized": true}\n')
        tool.write_text("# User-customized implementation\n")
        self.invoke()
        self.assertIn("user-customized", config.read_text())
        self.assertEqual(tool.read_text(), "# User-customized implementation\n")
        self.assertEqual(len(list((self.target / ".project-kit/.project-init/runs").iterdir())), 2)

    def test_explicit_replacement_backed_up_and_other_files_preserved(self):
        self.target.mkdir()
        (self.target / "AGENTS.md").write_text("Original rules\n")
        (self.target / "STATE.md").write_text("Current progress\n")
        os.chmod(self.target / "AGENTS.md", 0o640)
        self.invoke("--overwrite", "AGENTS.md")
        row = next(row for row in self.latest_report()["files"] if row["path"] == "AGENTS.md")
        self.assertEqual(row["action"], "overwritten")
        backup = self.target / row["backup"]
        self.assertEqual(backup.read_text(), "Original rules\n")
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.target / "AGENTS.md").stat().st_mode & 0o777, 0o640)
        self.assertIn(".project-kit/AGENTS.md", (self.target / "AGENTS.md").read_text())
        self.assertIn("regressions", (self.target / ".project-kit/AGENTS.md").read_text())
        self.assertEqual((self.target / "STATE.md").read_text(), "Current progress\n")

    def test_dry_run_leaves_new_and_existing_targets_untouched(self):
        self.invoke("--dry-run")
        self.assertFalse(self.target.exists())
        self.target.mkdir()
        (self.target / "AGENTS.md").write_text("Keep\n")
        self.invoke("--dry-run", "--overwrite", "AGENTS.md")
        self.assertEqual(list(self.target.iterdir()), [self.target / "AGENTS.md"])
        self.assertEqual((self.target / "AGENTS.md").read_text(), "Keep\n")

    def test_unsafe_symlink_and_hardlink_destinations_refused_before_writes(self):
        self.target.mkdir()
        outside = self.base / "outside.txt"
        outside.write_text("Do not touch\n")
        (self.target / ".project-kit").mkdir()
        (self.target / ".project-kit/STATE.md").symlink_to(outside)
        self.invoke(okay=False)
        self.assertFalse((self.target / "AGENTS.md").exists())
        (self.target / ".project-kit/STATE.md").unlink()
        os.link(outside, self.target / ".project-kit/STATE.md")
        self.invoke(okay=False)
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertEqual(outside.read_text(), "Do not touch\n")

    def test_symlink_target_ancestor_and_directory_collisions_refused(self):
        actual = self.base / "actual"
        actual.mkdir()
        alias = self.base / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        self.invoke(target=alias / "child", okay=False)
        self.assertFalse((actual / "child").exists())
        self.target.mkdir()
        (self.target / ".project-kit").write_text("Collision\n")
        self.invoke(okay=False)
        self.assertFalse((self.target / "AGENTS.md").exists())

    def test_noninteractive_validation_and_missing_mode(self):
        for options in [("--timezone", "invalid/timezone"), ("--project-id", "../bad"),
                        ("--overwrite", "../../secret"), ("--repo", "../outside")]:
            self.invoke(*options, okay=False)
            self.assertFalse(self.target.exists())
        result = subprocess.run([str(KIT / "init-project.sh"), str(self.target), "--non-interactive"],
                                env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--mode", result.stderr)

    def test_interactive_mode_question_and_conflict_answers(self):
        for answer, overwritten in [("n", False), ("y", True)]:
            with self.subTest(answer=answer):
                target = self.base / ("interactive-" + answer)
                target.mkdir()
                (target / "AGENTS.md").write_text("Existing rules\n")
                master, slave = pty.openpty()
                process = subprocess.Popen([str(KIT / "init-project.sh"), str(target)],
                                           stdin=slave, stdout=slave, stderr=slave, env=self.env)
                os.close(slave)
                output = b""
                handled = set()
                deadline = time.monotonic() + 20
                try:
                    while time.monotonic() < deadline:
                        ready, _, _ = select.select([master], [], [], 0.1)
                        if ready:
                            try:
                                chunk = os.read(master, 65536)
                            except OSError:
                                break
                            if not chunk:
                                break
                            output += chunk
                            for prompt, response in [(b"parent folder for multiple repositories? [y/N]:", b"y\n"),
                                                     (b"Back up and overwrite AGENTS.md? [y/N]:", answer.encode() + b"\n")]:
                                if prompt in output and prompt not in handled:
                                    os.write(master, response)
                                    handled.add(prompt)
                        if process.poll() is not None and not ready:
                            break
                    self.assertEqual(process.wait(timeout=2), 0, output.decode(errors="replace"))
                    self.assertEqual(len(handled), 2)
                    self.assertEqual((target / "AGENTS.md").read_text() == "Existing rules\n", not overwritten)
                    if overwritten:
                        self.assertTrue(list((target / ".project-kit/.project-init/runs").glob("*/backups/AGENTS.md")))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    os.close(master)

    def test_concurrent_initializer_refuses_without_writing_files(self):
        self.target.mkdir()
        fd = os.open(self.target, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.invoke(okay=False)
            self.assertIn("Another initializer", result.stderr)
            self.assertEqual(list(self.target.iterdir()), [])
        finally:
            os.close(fd)

    def test_late_repo_discovery_keeps_config_until_manual_merge(self):
        self.invoke(mode="multi")
        original = (self.target / ".project-kit/multi-git.conf").read_bytes()
        new_repo = self.repo("later")
        self.invoke(mode="multi")
        self.assertTrue((new_repo / "AGENTS.md").is_file())
        self.assertEqual((self.target / ".project-kit/multi-git.conf").read_bytes(), original)
        report = self.latest_report()
        self.assertIn("later", report["repositories"])
        checklist = self.target / ".project-kit/.project-init/runs" / report["run_id"] / "SETUP.md"
        self.assertIn("manually", checklist.read_text())

    def test_existing_report_directory_permissions_not_modified(self):
        private = self.target / ".project-kit/.project-init"
        private.mkdir(parents=True)
        private.chmod(0o755)
        self.invoke(okay=False)
        self.assertEqual(private.stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.target / "AGENTS.md").exists())

    def test_installed_collector_import_export_and_advice(self):
        self.invoke("--project-id", "usage-fixture")
        events = [
            {"timestamp": "2026-10-06T10:00:00Z", "type": "session_meta",
             "payload": {"id": "fixture-session", "cwd": str(self.target), "cli_version": "fixture"}},
            {"timestamp": "2026-10-06T10:00:01Z", "type": "turn_context",
             "payload": {"turn_id": "turn1", "model": "fixture", "effort": "low"}},
            {"timestamp": "2026-10-06T10:00:02Z", "type": "token_usage_record",
             "payload": {"response_id": "r1", "turn_id": "turn1", "usage": {
                 "input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 20, "total_tokens": 120}}},
        ]
        (self.logs / "sessions/fixture.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        collector = self.target / ".project-kit/usage/collector.py"
        for options in [["import"], ["summary", "--group", "project"],
                        ["export", "--out", str(self.target / ".project-kit/.usage/export.json")], ["advice"]]:
            result = subprocess.run(["python3", str(collector), *options], cwd=self.base,
                                    env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            if options[0] == "summary":
                self.assertIn('"usage-fixture"', result.stdout)
                self.assertIn('120', result.stdout)
        self.assertTrue((self.target / ".project-kit/.usage/export.json").is_file())
        self.assertFalse((self.base / ".usage").exists())

    def test_installed_kit_reuse_excludes_user_brief_state_and_usage(self):
        self.invoke()
        (self.target / ".project-kit/PROJECT_BRIEF.md").write_text("PRIVATE PROJECT-SPECIFIC BRIEF\n")
        (self.target / ".project-kit/STATE.md").write_text("PRIVATE PROJECT PROGRESS\n")
        (self.target / ".project-kit/.usage").mkdir()
        (self.target / ".project-kit/.usage/events.jsonl").write_text("OLD USAGE\n")
        another = self.base / "another"
        self.invoke(target=another, kit=self.target / ".project-kit")
        self.assertNotIn("PRIVATE PROJECT", (another / ".project-kit/PROJECT_BRIEF.md").read_text())
        self.assertNotIn("PRIVATE PROJECT", (another / ".project-kit/STATE.md").read_text())
        self.assertFalse((another / ".project-kit/.usage").exists())
        self.assertNotIn("OLD USAGE", (another / ".project-kit/USAGE_EXAMPLES.txt").read_text())

    def test_installed_launcher_uses_config_and_safe_git_metadata_journals(self):
        repo = self.repo()
        self.invoke()
        launcher = self.target / ".project-kit/multi-git/multi-git.sh"
        before = self.git(repo, "rev-parse", "HEAD")
        result = subprocess.run([str(launcher), "status", "--all", "--json"], cwd=self.base,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"branch": "develop"', result.stdout)
        result = subprocess.run([str(launcher), "branch-create", "layout-fixture", "--all", "--execute"],
                                cwd=self.base, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), before)
        self.assertTrue(list((repo / ".git/multi-git-history").glob('*/run.json')))
        self.assertFalse((repo / ".project-kit/.multi-git").exists())
        self.assertFalse((repo / ".multi-git").exists())
        self.assertFalse((repo / ".usage").exists())

    def test_installed_initializer_can_rerun_its_own_workspace(self):
        self.invoke()
        existing = (self.target / ".project-kit/usage/config.json").read_bytes()
        self.invoke(kit=self.target / ".project-kit")
        self.assertEqual((self.target / ".project-kit/usage/config.json").read_bytes(), existing)
        self.assertEqual({p.name for p in self.target.iterdir()}, {"AGENTS.md", ".project-kit"})

    def test_multi_repo_journals_stay_inside_shared_kit(self):
        repo = self.repo("backend")
        self.invoke(mode="multi")
        result = subprocess.run([str(self.target / ".project-kit/multi-git/multi-git.sh"),
                                 "branch-create", "layout-fixture", "--all", "--execute"],
                                cwd=self.base, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(repo, "branch", "--show-current"), "layout-fixture")
        self.assertTrue(list((self.target / ".project-kit/.multi-git").glob('*/run.json')))
        self.assertEqual({p.name for p in self.target.iterdir()}, {"backend", "AGENTS.md", ".project-kit"})

    def test_legacy_flat_install_is_reported_and_preserved(self):
        self.target.mkdir()
        names = ["KIT_README.md", "init_project.py", "usage/collector.py", "multi-git/multi_git.py",
                 "usage/config.json", "multi-git.conf", "STATE.md", ".usage/events.jsonl"]
        for name in names:
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Existing customized contents\n")
        result = self.invoke()
        self.assertIn("Previous flat installation detected", result.stdout)
        for name in names:
            self.assertEqual((self.target / name).read_text(), "Existing customized contents\n")
        self.assertTrue(self.latest_report()["legacy_files"])
        self.assertIn("migrate your customized", (self.target / ".project-kit/SETUP_CHECKLIST.md").read_text())


if __name__ == "__main__":
    unittest.main()
