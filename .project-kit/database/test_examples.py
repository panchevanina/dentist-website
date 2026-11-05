"""Example guard checks: real temporary files, mocked mongosh/DB; no network."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

EXAMPLE = Path(__file__).parent / 'examples/mongodb-ping.js'
HARNESS = r'''
const fs = require('fs');
const vm = require('vm');
let result = {calls: 0, output: [], exit: null, telemetryDisabled: false};
const context = {
  require,
  process: {env: {DB_PROFILE_FILE: process.argv[2], DB_TARGET_ENV: process.argv[3]}, getuid: () => process.getuid()},
  disableTelemetry() {result.telemetryDisabled = true;},
  Mongo: function(uri) {
    result.calls++;
    if (process.argv[4] === 'error') throw new Error('client error with URI: ' + uri);
    return {getDB() {return {runCommand(command) {
      if (JSON.stringify(command) !== '{"ping":1}') throw new Error('unexpected operation');
      return {ok: 1};
    }}}};
  },
  print(text) {result.output.push(text);},
  quit(code) {result.exit = code;}
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
console.log(JSON.stringify(result));
'''


@unittest.skipUnless(shutil.which('node'), 'Node.js required for mocked mongosh checks')
class MongoExampleGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='db-instructions-test-')
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'mongodb.json'
        self.profile = {'configured': True, 'environment': 'local', 'database': 'fixture',
                        'connection_uri': 'mongodb://fixture:FAKE_SECRET_SENTINEL@db.example.invalid/fixture?tls=true'}

    def run_example(self, env='local', mode='success', permissions=0o600, raw=None, link=False):
        self.file.write_text(raw if raw is not None else json.dumps(self.profile))
        self.file.chmod(permissions)
        path = self.file
        if link:
            path = self.file.with_name('linked.json')
            path.symlink_to(self.file)
        result = subprocess.run(['node', '-e', HARNESS, str(EXAMPLE.resolve()), str(path), env, mode],
                                capture_output=True, text=True, check=True)
        self.assertNotIn('FAKE_SECRET_SENTINEL', result.stdout + result.stderr)
        self.assertNotIn('mongodb://', result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_fixed_ping_only_with_explicit_matching_profile(self):
        result = self.run_example()
        self.assertEqual((result['calls'], result['exit']), (1, 0))
        self.assertTrue(result['telemetryDisabled'])

    def test_environment_mismatch_never_connects(self):
        result = self.run_example(env='prod')
        self.assertEqual((result['calls'], result['exit']), (0, 1))

    def test_unconfigured_profile_never_connects(self):
        self.profile['configured'] = False
        self.assertEqual(self.run_example()['calls'], 0)

    def test_readable_credentials_and_symlinks_refused(self):
        self.assertEqual(self.run_example(permissions=0o644)['calls'], 0)
        self.assertEqual(self.run_example(link=True)['calls'], 0)

    def test_client_error_cannot_return_secret_uri(self):
        result = self.run_example(mode='error')
        self.assertEqual((result['calls'], result['exit']), (1, 1))
        self.assertEqual(result['output'], ['Database reachability check failed; review configuration privately.'])

    def test_insecure_or_ambiguous_transport_never_connects(self):
        for suffix in ('tls=false', 'tls=true&tlsAllowInvalidCertificates=true',
                       'tls=true&%74lsInsecure=true', 'tls=true&TLS=false', 'ssl=true'):
            with self.subTest(suffix=suffix):
                self.profile['connection_uri'] = 'mongodb://fixture:FAKE_SECRET_SENTINEL@db.example.invalid/?' + suffix
                self.assertEqual(self.run_example()['calls'], 0)

    def test_missing_environment_and_malformed_json_never_connect(self):
        self.assertEqual(self.run_example(env='')['calls'], 0)
        self.assertEqual(self.run_example(raw='{bad json with FAKE_SECRET_SENTINEL')['calls'], 0)


if __name__ == '__main__':
    unittest.main()
