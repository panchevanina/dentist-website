"""Integration tests. All repositories/remotes live inside TemporaryDirectory."""
import configparser
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name('multi-git.sh').resolve()
spec = importlib.util.spec_from_file_location('multi_git', SCRIPT.with_name('multi_git.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FIXTURE_ENV = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
FIXTURE_ENV.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')


def g(path, *args, check=True):
    result = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True, env=FIXTURE_ENV)
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class MultiGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='multi-git-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.make_repo('alpha')
        self.b = self.make_repo('beta space')
        self.call('init', '--root', str(self.root), json_output=False)
        self.config = self.root / 'multi-git.conf'

    def make_repo(self, name):
        path = self.root / name
        path.mkdir()
        g(path, 'init', '--template=', '-b', 'develop')
        (path / '.git/hooks').mkdir(exist_ok=True)
        g(path, 'config', 'core.hooksPath', str(path / '.git/hooks'))
        g(path, 'config', 'user.name', 'Fixture')
        g(path, 'config', 'user.email', 'fixture@example.invalid')
        g(path, 'config', 'commit.gpgsign', 'false')
        g(path, 'config', 'tag.gpgsign', 'false')
        g(path, 'config', 'core.autocrlf', 'false')
        (path / 'file.txt').write_text('initial\n')
        g(path, 'add', '.')
        g(path, 'commit', '-m', 'initial')
        return path

    def call(self, *args, ok=True, json_output=True, env=None):
        # Installed launchers have a project config default. Always pin fixtures.
        command = [str(SCRIPT), '--config', str(self.root / 'multi-git.conf'), *args]
        if json_output:
            command.append('--json')
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout) if json_output and result.stdout else result

    def create(self, name='feature', repos=None):
        return self.call('branch-create', name, '--repos', *(repos or ['alpha', 'beta_space']), '--execute')

    def test_history_inside_working_tree_refused_but_dedicated_git_metadata_allowed(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config)
        working_history = self.a / '.project-kit/.multi-git'
        config['workspace']['history_dir'] = str(working_history)
        with self.config.open('w') as stream:
            config.write(stream)
        result = self.call('branch-create', 'blocked-history', '--repos', 'alpha', '--execute',
                           ok=False, json_output=False)
        self.assertIn('history_dir must be outside', result.stderr)
        self.assertFalse(working_history.exists())
        self.assertEqual(g(self.a, 'branch', '--show-current'), 'develop')
        private_history = self.a / '.git/multi-git-history'
        config['workspace']['history_dir'] = str(private_history)
        with self.config.open('w') as stream:
            config.write(stream)
        outcome = self.call('branch-create', 'metadata-history', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'branch', '--show-current'), 'metadata-history')
        self.assertTrue(list(private_history.glob('*/run.json')))
        run_id = outcome['run_id']
        self.call('rollback', run_id, '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'branch', '--show-current'), 'develop')

    def messages(self):
        path = self.root / 'messages.json'
        path.write_text(json.dumps({'alpha': 'Update alpha', 'beta_space': 'Update beta'}))
        return str(path)

    def remote(self, path, name='remote.git'):
        bare = self.root / name
        bare.mkdir()
        g(bare, 'init', '--bare', '--template=')
        (bare / 'hooks').mkdir(exist_ok=True)
        g(bare, 'config', 'core.hooksPath', str(bare / 'hooks'))
        g(path, 'remote', 'add', 'origin', str(bare))
        g(path, 'push', '-u', 'origin', 'develop')
        return bare

    def clone(self, bare, name='peer'):
        path = self.root / name
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--template=', '-b', 'develop', str(bare), str(path)], capture_output=True, check=True, env=FIXTURE_ENV)
        g(path, 'config', 'user.name', 'Peer')
        g(path, 'config', 'user.email', 'peer@example.invalid')
        g(path, 'config', 'core.hooksPath', str(path / '.git/hooks'))
        g(path, 'config', 'commit.gpgsign', 'false')
        return path

    def commit_file(self, path, text, message='change'):
        (path / 'file.txt').write_text(text)
        g(path, 'add', '.')
        g(path, 'commit', '-m', message)
        return g(path, 'rev-parse', 'HEAD')

    def hook(self, path, name, body):
        hook = path / '.git' / 'hooks' / name
        hook.write_text('#!/bin/sh\n' + body + '\n')
        hook.chmod(0o755)
        return hook

    def test_init_status_space_path_and_no_overwrite(self):
        data = self.call('status', '--all')
        self.assertEqual([row['id'] for row in data], ['alpha', 'beta_space'])
        (self.a / 'untracked.txt').write_text('new')
        data = self.call('status', '--repos', 'alpha')
        self.assertEqual(data[0]['changes'], [{'status': '??', 'path': 'untracked.txt'}])
        self.call('init', '--root', str(self.root), ok=False, json_output=False)

    def test_preview_does_not_mutate(self):
        before = module.snapshot(self.a)
        self.call('branch-create', 'feature', '--all')
        self.assertEqual(module.snapshot(self.a), before)
        self.assertFalse((self.root / '.multi-git').exists())

    def test_branch_create_dirty_preserved_and_selective_rollback(self):
        (self.a / 'file.txt').write_text('dirty')
        g(self.a, 'add', '.')
        (self.a / 'file.txt').write_text('unstaged on staged')
        (self.a / 'new').write_text('untracked')
        before = module.snapshot(self.a)
        run = self.create()
        self.call('rollback', run['run_id'], '--repos', 'alpha', '--execute')
        self.assertEqual(module.snapshot(self.a), before)
        self.assertEqual(g(self.b, 'branch', '--show-current'), 'feature')
        self.call('rollback', run['run_id'], '--all', '--execute')

    def test_all_preflight_blocks_before_other_repo_changes(self):
        g(self.b, 'branch', 'feature')
        before = module.snapshot(self.a)
        self.create_invalid = self.call('branch-create', 'feature', '--all', '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)
        self.assertEqual(self.create_invalid['status'], 'failed')

    def test_dirty_switch_and_base_refused(self):
        g(self.a, 'branch', 'other')
        (self.a / 'file.txt').write_text('dirty')
        self.call('switch', 'other', '--repos', 'alpha', '--execute', ok=False)
        self.call('branch-create', 'new', '--base', 'develop', '--repos', 'alpha', '--execute', ok=False)

    def test_switch_alias_and_rollback(self):
        g(self.a, 'branch', 'development')
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.config)
        cfg['repo:alpha']['alias.dev'] = 'development'
        with self.config.open('w') as stream:
            cfg.write(stream)
        before = module.snapshot(self.a)
        run = self.call('switch', 'dev', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'branch', '--show-current'), 'development')
        self.call('rollback', run['run_id'], '--all', '--execute')
        self.assertEqual(module.snapshot(self.a), before)

    def test_pull_current_upstream_fast_forward_and_rollback_publication_refusal(self):
        bare = self.remote(self.a)
        peer = self.clone(bare)
        tip = self.commit_file(peer, 'remote new')
        g(peer, 'push')
        run = self.call('pull', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'rev-parse', 'HEAD'), tip)
        result = self.call('rollback', run['run_id'], '--repos', 'alpha', '--execute', ok=False)
        self.assertIn('published', result[0]['error'])

    def test_divergent_pull_refused(self):
        bare = self.remote(self.a)
        peer = self.clone(bare)
        self.commit_file(peer, 'remote')
        g(peer, 'push')
        self.commit_file(self.a, 'local')
        before = module.snapshot(self.a)
        self.call('pull', '--repos', 'alpha', '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)

    def test_switch_pull_updates_target_not_original_branch(self):
        bare = self.remote(self.a)
        peer = self.clone(bare)
        tip = self.commit_file(peer, 'remote new')
        g(peer, 'push')
        g(self.a, 'switch', '-c', 'feature')
        old_feature = self.commit_file(self.a, 'feature content')
        self.call('switch', 'develop', '--pull', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'rev-parse', 'HEAD'), tip)
        self.assertEqual(g(self.a, 'rev-parse', 'feature'), old_feature)

    def test_commit_all_messages_and_exact_index_rollback(self):
        (self.a / 'file.txt').write_text('stage me')
        g(self.a, 'add', '.')
        (self.a / 'file.txt').write_text('unstaged delta')
        (self.a / 'untracked').write_text('new')
        (self.b / 'file.txt').write_text('beta')
        before = module.snapshot(self.a)
        raw_index = (self.a / '.git/index').read_bytes()
        run = self.call('commit', '--all', '--all-changes', '--messages', self.messages(), '--execute')
        self.assertEqual(g(self.a, 'log', '-1', '--format=%s'), 'Update alpha')
        self.assertEqual(g(self.b, 'log', '-1', '--format=%s'), 'Update beta')
        self.call('rollback', run['run_id'], '--repos', 'alpha', '--execute')
        self.assertEqual(module.snapshot(self.a), before)
        self.assertEqual((self.a / '.git/index').read_bytes(), raw_index)

    def test_staged_commit_preserves_unstaged_and_deleted_files_rollback(self):
        (self.a / 'file.txt').unlink()
        g(self.a, 'add', '.')
        before = module.snapshot(self.a)
        run = self.call('commit', '--repos', 'alpha', '--messages', self.messages(), '--execute')
        self.call('rollback', run['run_id'], '--all', '--execute')
        self.assertEqual(module.snapshot(self.a), before)

    def test_failed_hook_restores_staging_and_previous_repos(self):
        (self.a / 'file.txt').write_text('alpha')
        (self.b / 'file.txt').write_text('beta')
        before_a, before_b = module.snapshot(self.a), module.snapshot(self.b)
        self.hook(self.b, 'pre-commit', 'exit 1')
        run = self.call('commit', '--all', '--all-changes', '--messages', self.messages(), '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before_a)
        self.assertEqual(module.snapshot(self.b), before_b)
        self.assertEqual(run['repos'][0]['status'], 'restored')

    def test_hook_modified_file_not_discarded(self):
        (self.a / 'file.txt').write_text('user edit')
        self.hook(self.a, 'pre-commit', 'echo hook-content > file.txt\nexit 1')
        run = self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute', ok=False)
        self.assertEqual((self.a / 'file.txt').read_text(), 'hook-content\n')
        self.assertIn('manual review', run['repos'][0]['status'])

    def test_rollback_refuses_new_edits_or_commits(self):
        run = self.create(repos=['alpha'])
        (self.a / 'new').write_text('new edit')
        self.call('rollback', run['run_id'], '--repos', 'alpha', '--execute', ok=False)
        g(self.a, 'add', '.')
        g(self.a, 'commit', '-m', 'new')
        self.call('rollback', run['run_id'], '--repos', 'alpha', '--execute', ok=False)

    def test_merge_conflict_does_not_touch_original(self):
        g(self.a, 'switch', '-c', 'feature')
        self.commit_file(self.a, 'feature')
        g(self.a, 'switch', 'develop')
        self.commit_file(self.a, 'develop')
        before = module.snapshot(self.a)
        run = self.call('merge', 'feature', '--into', 'develop', '--repos', 'alpha', '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)
        self.assertNotIn('worker', run['repos'][0])

    def test_merge_success_from_other_branch_and_rollback(self):
        g(self.a, 'switch', '-c', 'feature')
        tip = self.commit_file(self.a, 'feature')
        before = module.snapshot(self.a)
        run = self.call('merge', 'feature', '--into', 'develop', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'rev-parse', 'develop'), tip)
        self.call('rollback', run['run_id'], '--repos', 'alpha', '--execute')
        self.assertEqual(module.snapshot(self.a), before)

    def test_rebase_success_and_rollback(self):
        g(self.a, 'switch', '-c', 'feature')
        (self.a / 'feature.txt').write_text('feature')
        g(self.a, 'add', '.')
        g(self.a, 'commit', '-m', 'feature')
        old = g(self.a, 'rev-parse', 'HEAD')
        g(self.a, 'switch', 'develop')
        self.commit_file(self.a, 'develop advanced')
        g(self.a, 'switch', 'feature')
        before = module.snapshot(self.a)
        run = self.call('rebase', '--onto', 'develop', '--repos', 'alpha', '--execute')
        self.assertNotEqual(g(self.a, 'rev-parse', 'HEAD'), old)
        self.call('rollback', run['run_id'], '--all', '--execute')
        self.assertEqual(module.snapshot(self.a), before)

    def test_rebase_conflict_and_protection(self):
        self.call('rebase', '--onto', 'develop', '--repos', 'alpha', '--execute', ok=False)
        g(self.a, 'switch', '-c', 'feature')
        self.commit_file(self.a, 'feature')
        g(self.a, 'switch', 'develop')
        self.commit_file(self.a, 'develop')
        g(self.a, 'switch', 'feature')
        before = module.snapshot(self.a)
        self.call('rebase', '--onto', 'develop', '--repos', 'alpha', '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)

    def test_published_rebase_refused(self):
        self.remote(self.a)
        g(self.a, 'switch', '-c', 'feature')
        self.commit_file(self.a, 'feature')
        g(self.a, 'push', '-u', 'origin', 'feature')
        self.call('rebase', '--onto', 'develop', '--repos', 'alpha', '--execute', ok=False)

    def test_tag_collision_rollback_and_published_tag_refusal(self):
        run = self.call('tag', 'v1', '--message', 'Release', '--repos', 'alpha', '--execute')
        self.call('tag', 'v1', '--repos', 'alpha', '--execute', ok=False)
        self.call('rollback', run['run_id'], '--all', '--execute')
        self.assertFalse(g(self.a, 'tag'))
        self.remote(self.a)
        run = self.call('tag', 'v2', '--repos', 'alpha', '--execute')
        self.call('push', '--tag', 'v2', '--repos', 'alpha', '--execute')
        self.call('rollback', run['run_id'], '--all', '--execute', ok=False)

    def test_worktree_occupancy_and_duplicate_common_dir(self):
        worker = self.root / 'linked'
        g(self.a, 'worktree', 'add', '-b', 'elsewhere', str(worker))
        self.call('switch', 'elsewhere', '--repos', 'alpha', '--execute', ok=False)
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.config)
        cfg['repo:linked'] = {'path': 'linked'}
        with self.config.open('w') as stream:
            cfg.write(stream)
        self.call('branch-create', 'shared', '--repos', 'alpha', 'linked', '--execute', ok=False, json_output=False)

    def test_ignored_collision_refused_and_preserved(self):
        (self.a / '.gitignore').write_text('ignored.txt\n')
        g(self.a, 'add', '.')
        g(self.a, 'commit', '-m', 'ignore')
        g(self.a, 'switch', '-c', 'other')
        (self.a / 'ignored.txt').write_text('tracked')
        g(self.a, 'add', '-f', 'ignored.txt')
        g(self.a, 'commit', '-m', 'track')
        g(self.a, 'switch', 'develop')
        (self.a / 'ignored.txt').write_text('precious ignored')
        self.call('switch', 'other', '--repos', 'alpha', '--execute', ok=False)
        self.assertEqual((self.a / 'ignored.txt').read_text(), 'precious ignored')

    def test_empty_detached_missing_remote_and_invalid_names(self):
        self.call('branch-create', '../escape', '--repos', 'alpha', '--execute', ok=False)
        self.call('branch-create', '-x', '--repos', 'alpha', ok=False, json_output=False)
        self.call('fetch', '--repos', 'alpha', '--execute', ok=False)
        g(self.a, 'switch', '--detach')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)
        empty = self.root / 'empty'
        empty.mkdir()
        g(empty, 'init', '-b', 'develop')
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.config)
        cfg['repo:empty'] = {'path': 'empty'}
        with self.config.open('w') as stream:
            cfg.write(stream)
        self.call('branch-create', 'new', '--repos', 'empty', '--execute', ok=False)
        self.assertIsNone(self.call('status', '--repos', 'empty')[0]['head'])

    def test_changed_baseline_and_groups(self):
        self.call('status', '--changed', ok=False, json_output=False)
        self.remote(self.a)
        self.remote(self.b, 'remote-b.git')
        (self.a / 'file.txt').write_text('dirty')
        self.assertEqual([row['id'] for row in self.call('status', '--changed')], ['alpha'])
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.config)
        cfg['group:pair'] = {'repos': 'alpha, beta_space'}
        with self.config.open('w') as stream:
            cfg.write(stream)
        self.call('status', '--group', 'pair')
        self.call('status', '--group', 'missing', ok=False, json_output=False)

    def test_push_partial_failure_reports_earlier_publication(self):
        bare_a = self.remote(self.a)
        bare_b = self.remote(self.b, 'remote-b.git')
        tip = self.commit_file(self.a, 'a local')
        self.commit_file(self.b, 'b local')
        hook = bare_b / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        run = self.call('push', '--all', '--execute', ok=False)
        self.assertEqual(g(bare_a, 'rev-parse', 'develop'), tip)
        self.assertEqual(run['repos'][0]['status'], 'published')
        self.assertEqual(run['status'], 'failed')

    def test_missing_messages_lock_and_hidden_changes(self):
        (self.a / 'file.txt').write_text('edit')
        self.call('commit', '--repos', 'alpha', '--all-changes', '--execute', ok=False)
        (self.a / '.git/index.lock').write_text('lock')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)
        (self.a / '.git/index.lock').unlink()
        g(self.a, 'update-index', '--assume-unchanged', 'file.txt')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)

    def test_network_failure_during_rollback_refuses_rewind(self):
        bare = self.remote(self.a)
        (self.a / 'file.txt').write_text('edit')
        run = self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute')
        bare.rename(self.root / 'offline.git')
        before = module.snapshot(self.a)
        self.call('rollback', run['run_id'], '--all', '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)

    def test_concurrent_state_guard(self):
        expected = module.snapshot(self.a)
        self.commit_file(self.a, 'external commit')
        with self.assertRaises(module.Blocked):
            module.assert_state(self.a, expected)

    def test_unstaged_deletion_commit_can_be_undone(self):
        (self.a / 'file.txt').unlink()
        before = module.snapshot(self.a)
        run = self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute')
        self.call('rollback', run['run_id'], '--all', '--execute')
        self.assertEqual(module.snapshot(self.a), before)
        self.assertFalse((self.a / 'file.txt').exists())

    def test_successful_hook_unexpected_ref_not_owned_by_manager(self):
        (self.a / 'file.txt').write_text('user change')
        self.hook(self.a, 'post-commit', 'git branch hook-created')
        run = self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute', ok=False)
        self.assertIn('manual review', run['repos'][0]['status'])
        self.assertTrue(g(self.a, 'show-ref', 'refs/heads/hook-created'))
        self.call('rollback', run['run_id'], '--all', '--execute', ok=False)

    def test_recovery_ref_hook_side_effect_is_detected(self):
        self.hook(self.a, 'reference-transaction', '''if [ "$1" = committed ]; then
while read old new ref; do
case "$ref" in refs/multi-git/*/after) git branch hook-side-effect ;; esac
done
fi''')
        run = self.call('branch-create', 'feature', '--repos', 'alpha', '--execute', ok=False)
        self.assertIn('manual review', run['repos'][0]['status'])
        self.assertTrue(g(self.a, 'show-ref', 'refs/heads/hook-side-effect'))

    def test_signing_failure_restores_original_index(self):
        (self.a / 'file.txt').write_text('change')
        before = module.snapshot(self.a)
        g(self.a, 'config', 'commit.gpgsign', 'true')
        g(self.a, 'config', 'gpg.program', str(self.root / 'nonexistent-gpg'))
        self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)

    def test_conditional_ref_update_failure_restores_transitioned_index(self):
        old = g(self.a, 'rev-parse', 'HEAD')
        new = self.commit_file(self.a, 'target')
        g(self.a, 'reset', '--hard', old)  # Fixture setup only; manager never uses this.
        before = module.snapshot(self.a)
        original = module.git

        def injected(path, *args, **kwargs):
            if args and args[0] == 'update-ref':
                raise module.Blocked('injected CAS failure')
            return original(path, *args, **kwargs)

        with mock.patch.object(module, 'git', injected):
            with self.assertRaises(module.Blocked):
                module.apply_head(self.a, old, new)
        self.assertEqual(module.snapshot(self.a), before)

    def test_inherited_git_directory_cannot_redirect_repo(self):
        env = dict(os.environ, GIT_DIR=str(self.b / '.git'), GIT_WORK_TREE=str(self.b))
        result = self.call('status', '--repos', 'alpha', env=env)
        self.assertEqual(result[0]['path'], str(self.a))
        self.assertEqual(result[0]['head'], g(self.a, 'rev-parse', 'HEAD'))

    def test_history_report_and_read_commands(self):
        run = self.create(repos=['alpha'])
        self.assertEqual(self.call('history')[0]['run_id'], run['run_id'])
        self.assertEqual(self.call('report', run['run_id'])['status'], 'complete')
        self.assertIn('feature', self.call('branches', '--repos', 'alpha')[0]['text'])
        (self.a / 'file.txt').write_text('edited')
        self.assertIn('+edited', self.call('diff', '--repos', 'alpha')[0]['text'])
        self.assertIn('initial', self.call('log', '--repos', 'alpha')[0]['text'])

    def test_fetch_without_upstream_does_not_change_checkout(self):
        bare = self.remote(self.a)
        peer = self.clone(bare)
        self.commit_file(peer, 'fresh')
        g(peer, 'push')
        before = module.snapshot(self.a)
        self.call('fetch', '--repos', 'alpha', '--execute')
        self.assertEqual(module.snapshot(self.a), before)
        data = self.call('status', '--repos', 'alpha')[0]
        self.assertEqual(data['behind'], 1)

    def test_manager_lock_prevents_concurrent_manager(self):
        import fcntl
        with (self.a / '.git/multi-git-manager.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False, json_output=False)

    def test_remote_removal_blocks_rollback(self):
        self.remote(self.a)
        (self.a / 'file.txt').write_text('edit')
        run = self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute')
        g(self.a, 'remote', 'remove', 'origin')
        self.call('rollback', run['run_id'], '--all', '--execute', ok=False)

    def test_rebase_does_not_update_other_shared_branches(self):
        g(self.a, 'switch', '-c', 'feature')
        (self.a / 'feature.txt').write_text('feature')
        g(self.a, 'add', '.')
        g(self.a, 'commit', '-m', 'feature')
        g(self.a, 'branch', 'other-feature')
        original = g(self.a, 'rev-parse', 'other-feature')
        g(self.a, 'switch', 'develop')
        self.commit_file(self.a, 'develop advanced')
        g(self.a, 'switch', 'feature')
        g(self.a, 'config', 'rebase.updateRefs', 'true')
        self.call('rebase', '--onto', 'develop', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'rev-parse', 'other-feature'), original)

    def test_lfs_attributes_refused(self):
        (self.a / '.gitattributes').write_text('*.bin filter=lfs diff=lfs merge=lfs -text\n')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)
        g(self.a, 'add', '.')
        g(self.a, 'commit', '-m', 'lfs attributes')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)

    def test_staging_filter_failure_preserves_original_index_and_files(self):
        (self.a / '.gitattributes').write_text('*.bad filter=bad\n')
        g(self.a, 'add', '.')
        g(self.a, 'commit', '-m', 'attributes')
        g(self.a, 'config', 'filter.bad.required', 'true')
        g(self.a, 'config', 'filter.bad.clean', 'false')
        g(self.a, 'config', 'add.ignoreErrors', 'true')
        (self.a / 'file.txt').write_text('good change')
        (self.a / 'zzz.bad').write_text('filter failure')
        before = module.snapshot(self.a)
        self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)

    def test_mutations_in_submodule_and_sparse_checkout_refused(self):
        g(self.a, 'update-index', '--add', '--cacheinfo', '160000', g(self.b, 'rev-parse', 'HEAD'), 'submodule')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)
        g(self.a, 'update-index', '--force-remove', 'submodule')
        g(self.a, 'config', 'core.sparseCheckout', 'true')
        self.call('branch-create', 'new', '--repos', 'alpha', '--execute', ok=False)

    def test_new_branch_with_explicit_base_and_remote_switch(self):
        bare = self.remote(self.a)
        peer = self.clone(bare)
        g(peer, 'switch', '-c', 'staging')
        tip = self.commit_file(peer, 'staging contents')
        g(peer, 'push', '-u', 'origin', 'staging')
        self.call('fetch', '--repos', 'alpha', '--execute')
        before = module.snapshot(self.a)
        run = self.call('branch-create', 'bugfix', '--base', 'origin/staging', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'rev-parse', 'HEAD'), tip)
        self.call('rollback', run['run_id'], '--all', '--execute')
        self.assertEqual(module.snapshot(self.a), before)
        self.call('switch', 'staging', '--repos', 'alpha', '--execute')
        self.assertEqual(g(self.a, 'rev-parse', 'HEAD'), tip)
        self.assertEqual(g(self.a, 'branch', '--show-current'), 'staging')

    def test_published_commit_undo_refused(self):
        self.remote(self.a)
        (self.a / 'file.txt').write_text('committed')
        run = self.call('commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute')
        self.call('push', '--repos', 'alpha', '--execute')
        before = module.snapshot(self.a)
        self.call('rollback', run['run_id'], '--all', '--execute', ok=False)
        self.assertEqual(module.snapshot(self.a), before)

    def test_interruption_stops_successful_hook_before_late_commit(self):
        (self.a / 'file.txt').write_text('edit')
        marker = self.root / 'hook-started'
        self.hook(self.a, 'pre-commit', f'touch "{marker}"\nsleep 1\necho late > late-file\nexit 0')
        before = module.snapshot(self.a)
        process = subprocess.Popen([str(SCRIPT), '--config', str(self.config), 'commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute', '--json'], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(marker.exists())
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        self.assertNotEqual(process.returncode, 0)
        time.sleep(1.1)
        self.assertEqual(module.snapshot(self.a), before)
        self.assertFalse((self.a / 'late-file').exists())

    def test_interrupted_run_retains_journal_and_original(self):
        (self.a / 'file.txt').write_text('edit')
        marker = self.root / 'hook-started'
        self.hook(self.a, 'pre-commit', f'touch "{marker}"\nsleep 1\nexit 1')
        before = module.snapshot(self.a)
        process = subprocess.Popen([str(SCRIPT), '--config', str(self.config), 'commit', '--repos', 'alpha', '--all-changes', '--messages', self.messages(), '--execute', '--json'], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(marker.exists())
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        self.assertNotEqual(process.returncode, 0)
        journal = json.loads(stdout)
        self.assertEqual(journal['status'], 'failed')
        self.assertEqual(module.snapshot(self.a), before)
        self.assertTrue((self.root / '.multi-git' / journal['run_id'] / 'run.json').exists())


if __name__ == '__main__':
    unittest.main()
