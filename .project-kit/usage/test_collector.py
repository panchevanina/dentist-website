"""Accounting and privacy regression tests; Python standard library only."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import signal
import sys
import unittest

spec = importlib.util.spec_from_file_location("collector", Path(__file__).with_name("collector.py"))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def tokens(value=100, cached=60):
    return {"input_tokens": value, "cached_input_tokens": cached, "cache_write_input_tokens": 0,
            "output_tokens": 20, "reasoning_output_tokens": 5, "total_tokens": value + 20}


def event(kind, payload, seconds=0):
    return {"timestamp": f"2026-10-05T12:00:{seconds:02d}Z", "type": kind, "payload": payload}


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = self.base / "sessions"
        self.source.mkdir()
        self.project_root = self.base / "project"
        self.config = {"projects": [{"id": "example", "roots": [str(self.project_root)]}],
                       "session_roots": [self.source], "output_dir": self.base / "output", "timezone": "Europe/Sofia"}
        self.path = self.source / "session.jsonl"
        self.store = collector.Store(self.config["output_dir"])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def append(self, rows):
        with self.path.open("a") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")

    def basic(self, session="session1"):
        return [event("session_meta", {"id": session, "cwd": str(self.project_root), "cli_version": "fixture"}),
                event("event_msg", {"type": "task_started", "turn_id": "turn1"}, 1),
                event("turn_context", {"turn_id": "turn1", "model": "gpt-6.1-sol", "effort": "medium"}, 1),
                event("event_msg", {"type": "user_message", "message": "PRIVATE_PROMPT_DO_NOT_COPY", "client_id": "client"}, 2),
                event("token_usage_record", {"response_id": "response1", "turn_id": "turn1", "usage": tokens(),
                                            "turn_token_usage": tokens(), "thread_token_usage": tokens()}, 3)]

    def summary(self):
        return collector.summarize(self.config, self.store)

    def total(self):
        return self.summary()["groups"][0]["tokens"]["total"]

    def test_idempotence_and_snapshot_exclusion(self):
        self.append(self.basic())
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 120)
        self.assertEqual(collector.import_sessions(self.config, self.store)["new_observations"], 0)
        self.assertEqual(self.total(), 120)
        self.append(self.basic()[4:])  # replayed event at a new line
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 120)
        self.assertEqual(len([r for r in self.store.rows("usage") if r["scope"] == "model_call"]), 1)

    def test_corrections_and_out_of_order_updates(self):
        self.append(self.basic())
        collector.import_sessions(self.config, self.store)
        correction = self.basic()[4]
        correction["timestamp"] = "2026-10-05T12:00:05Z"
        for key in ["usage", "turn_token_usage", "thread_token_usage"]:
            correction["payload"][key] = tokens(150)
        self.append([correction])
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 170)
        self.assertFalse(self.summary()["session_coverage"][0]["counter_reset"])
        self.append(self.basic()[4:])
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 170)

    def test_partial_and_malformed_source_lines(self):
        self.append(self.basic()[:4])
        line = json.dumps(self.basic()[4])
        with self.path.open("a") as stream:
            stream.write("bad-json\n" + line[:len(line)//2])
        result = collector.import_sessions(self.config, self.store)
        self.assertEqual(result["malformed_lines"], 1)
        self.assertEqual(len(self.store.rows("usage")), 0)
        with self.path.open("a") as stream:
            stream.write(line[len(line)//2:] + "\n")
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 120)

    def test_unknown_usage_remains_null_and_unreconciled(self):
        rows = self.basic()[:4] + [event("event_msg", {"type": "token_count", "info": None}, 3)]
        self.append(rows)
        collector.import_sessions(self.config, self.store)
        self.assertIsNone(self.total())
        self.assertEqual(self.summary()["groups"][0]["unknown_measurements"]["total"], 1)
        self.assertFalse(self.summary()["session_coverage"][0]["complete"])

    def test_fallback_and_counter_reset_are_flagged(self):
        self.append(self.basic()[:4])
        for second, value in [(3, 100), (4, 20)]:
            self.append([event("event_msg", {"type": "token_count", "info": {"total_token_usage": tokens(value, 0)}}, second)])
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 40)  # latest snapshot, not 120 + 40 or a clamped delta
        coverage = self.summary()["session_coverage"][0]
        self.assertEqual(coverage["basis"], "session_snapshot")
        self.assertTrue(coverage["counter_reset"])
        self.assertFalse(coverage["complete"])

    def test_steering_tools_privacy_and_failure(self):
        self.append(self.basic() + [
            event("event_msg", {"type": "user_message", "message": "MORE_PRIVATE_TEXT"}, 4),
            event("response_item", {"type": "function_call", "call_id": "call1", "name": "exec_command",
                                    "arguments": "SECRET_ARGUMENT"}, 5),
            event("response_item", {"type": "function_call_output", "call_id": "call1",
                                    "output": json.dumps({"exit_code": 1, "output": "SECRET_OUTPUT"})}, 6),
            event("event_msg", {"type": "turn_aborted", "turn_id": "turn1"}, 7)])
        collector.import_sessions(self.config, self.store)
        tool = self.store.rows("tool")[0]
        self.assertEqual(tool["data"]["status"], "failed")
        self.assertEqual(tool["data"]["duration_ms"], 1000)
        self.assertNotIn("tokens", tool)
        group = collector.summarize(self.config, self.store, "turn")["groups"][0]
        self.assertEqual(group["query_count"], 2)
        self.assertEqual(group["query_attribution"], "shared_turn")
        self.assertEqual(self.store.rows("turn")[0]["data"]["status"], "interrupted")
        self.store.db.commit()
        for path in self.config["output_dir"].iterdir():
            if path.is_file():
                content = path.read_bytes()
                for private in [b"PRIVATE_PROMPT", b"MORE_PRIVATE_TEXT", b"SECRET_ARGUMENT", b"SECRET_OUTPUT"]:
                    self.assertNotIn(private, content, path.name)

    def test_subagent_and_fork_replay(self):
        rows = self.basic()
        rows[0]["payload"]["source"] = {"subagent": {"thread_spawn": {"parent_thread_id": "parent"}}}
        self.append(rows)
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.store.rows("usage")[0]["agent_id"], "session1")
        replay = self.basic("fork1")
        other = self.source / "z-fork.jsonl"
        other.write_text("".join(json.dumps(r) + "\n" for r in replay))
        collector.import_sessions(self.config, self.store)
        # Fork snapshot is preserved as evidence but must not introduce a second charge.
        calls = [r for r in self.store.rows("usage") if r["scope"] == "model_call"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.total(), 120)
        self.assertTrue(any(r["data"]["code"] == "replayed_response" for r in self.store.rows("diagnostic")))

    def test_rebuild_and_crash_recovery(self):
        self.append(self.basic())
        collector.import_sessions(self.config, self.store)
        self.store.close()
        (self.config["output_dir"] / "index.sqlite3").unlink()
        self.store = collector.Store(self.config["output_dir"])
        self.assertEqual(self.total(), 120)
        self.assertEqual(collector.import_sessions(self.config, self.store)["new_observations"], 0)
        self.assertEqual(self.total(), 120)

    def test_project_mapping_worktrees_and_boundary(self):
        self.config["projects"].append({"id": "nested", "roots": [str(self.project_root / "nested"), str(self.base / "worktree")]})
        self.assertEqual(collector.project_for(str(self.project_root / "nested" / "src"), self.config), "nested")
        self.assertEqual(collector.project_for(str(self.base / "worktree" / "src"), self.config), "nested")
        self.assertIsNone(collector.project_for(str(self.base / "project-other"), self.config))

    def test_source_rewrite_and_unknown_event(self):
        self.append(self.basic())
        collector.import_sessions(self.config, self.store)
        self.path.write_text("".join(json.dumps(row) + "\n" for row in self.basic()))
        self.append([event("future_event", {"secret": "SHOULD_NOT_COPY"}, 9)])
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 120)
        self.assertTrue(any(d["data"]["code"] == "unknown_event_type" for d in self.store.rows("diagnostic")))

    def test_no_usage_session_is_visible(self):
        self.append(self.basic()[:4])
        collector.import_sessions(self.config, self.store)
        report = self.summary()
        self.assertEqual(report["groups"], [])
        self.assertEqual(len(report["sessions_without_usage"]), 1)

    def test_retries_are_separate_response_ids(self):
        self.append(self.basic())
        retry = self.basic()[4]
        retry["timestamp"] = "2026-10-05T12:00:04Z"
        retry["payload"]["response_id"] = "response-retry"
        retry["payload"]["thread_token_usage"] = {key: value * 2 for key, value in tokens().items()}
        self.append([retry])
        collector.import_sessions(self.config, self.store)
        self.assertEqual(self.total(), 240)
        self.assertTrue(self.summary()["session_coverage"][0]["reconciles"])
        self.assertFalse(self.summary()["session_coverage"][0]["complete"])  # still in progress

    def test_truncated_derived_tail_is_recovered(self):
        self.append(self.basic())
        collector.import_sessions(self.config, self.store)
        self.store.close()
        with (self.config["output_dir"] / "events.jsonl").open("ab") as stream:
            stream.write(b'{"unfinished":')
        self.store = collector.Store(self.config["output_dir"])
        self.assertEqual(self.total(), 120)
        self.assertTrue((self.config["output_dir"] / "events.jsonl").read_bytes().endswith(b"\n"))

    def test_assessment_cli_and_local_advice(self):
        rows = self.basic()
        rows[2]["payload"]["effort"] = "high"
        self.append(rows)
        collector.import_sessions(self.config, self.store)
        path = self.base / "config.json"
        path.write_text(json.dumps({"schema_version":1, "projects":self.config["projects"],
                                   "session_roots":[str(self.source)], "output_dir":str(self.config["output_dir"])}))
        with contextlib.redirect_stdout(io.StringIO()):
            status = collector.main(["--config",str(path),"assess","--project","example","--session","session1",
                                     "--turn","turn1","--task-type","routine","--outcome","success","--checks","passed","--rating","4"])
        self.assertEqual(status, 0)
        report = collector.advice(self.config, self.store)
        self.assertEqual(report["assessments"][0]["data"]["rating"], 4)
        self.assertIn("routine_high_effort", [finding["rule"] for finding in report["findings"]])

    def test_cross_session_turn_ids_are_not_merged(self):
        self.append(self.basic())
        other_rows = self.basic("session2")
        other_rows[4]["payload"]["response_id"] = "response2"
        (self.source / "z-session2.jsonl").write_text("".join(json.dumps(row)+"\n" for row in other_rows))
        collector.import_sessions(self.config, self.store)
        report = collector.summarize(self.config, self.store, "turn")
        self.assertEqual(len(report["groups"]), 2)
        self.assertTrue(all(group["query_count"] == 1 for group in report["groups"]))

    def test_config_source_and_output_must_not_overlap(self):
        path = self.base / "config.json"
        path.write_text(json.dumps({"schema_version":1,"projects":self.config["projects"],
                                   "session_roots":[str(self.source)],"output_dir":str(self.source / "derived")}))
        with self.assertRaises(ValueError):
            collector.load_config(path)

    @unittest.skipIf(sys.platform == "win32", "POSIX signal lifecycle test")
    def test_watch_stop_and_restart_release_lock(self):
        self.append(self.basic())
        path = self.base / "config.json"
        path.write_text(json.dumps({"schema_version":1,"projects":self.config["projects"],
                                   "session_roots":[str(self.source)],"output_dir":str(self.config["output_dir"])}))
        for stop_signal in [signal.SIGINT, signal.SIGTERM]:
            process = subprocess.Popen([sys.executable, str(Path(collector.__file__)), "--config",str(path),"watch","--interval","0.1"],
                                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                first_line = process.stdout.readline()
                self.assertIn('"watching":true', first_line)
                process.send_signal(stop_signal)
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertIn('"stopped":true', stdout)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
