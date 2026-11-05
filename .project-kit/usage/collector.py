#!/usr/bin/env python3
"""Local Codex usage importer. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FILES = {"usage": "events.jsonl", "query": "queries.jsonl", "tool": "commands.jsonl",
         "turn": "turns.jsonl", "assessment": "assessments.jsonl", "diagnostic": "diagnostics.jsonl"}
COUNTS = {"input": "input_tokens", "cached_input": "cached_input_tokens",
          "cache_write_input": "cache_write_input_tokens", "output": "output_tokens",
          "reasoning_output": "reasoning_output_tokens", "total": "total_tokens"}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def ident(*parts):
    return hashlib.sha256(compact(parts).encode()).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def count(value):
    return value if type(value) is int and value >= 0 else None


@contextlib.contextmanager
def lock(path):
    """Kernel lock: automatically released even if the process is killed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.tell() == 0:
                stream.write(b".")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError(f"Collector lock busy: {path.name}; retry shortly.") from error
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(f"Collector lock busy: {path.name}; retry shortly.") from error
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def load_config(path):
    path = Path(path).expanduser().resolve()
    config = json.loads(path.read_text())
    if config.get("schema_version") != 1 or not isinstance(config.get("projects"), list):
        raise ValueError("Config must have schema_version 1 and a projects list.")
    seen = set()
    roots = set()
    for project in config["projects"]:
        if not isinstance(project, dict) or not isinstance(project.get("id"), str) or not project["id"]:
            raise ValueError("Every project needs a nonempty stable id.")
        if project["id"] in seen or not isinstance(project.get("roots"), list) or not project["roots"]:
            raise ValueError("Project IDs must be unique and have nonempty roots lists.")
        seen.add(project["id"])
        project["roots"] = [str(resolve_path(root, path.parent)) for root in project["roots"]]
        for root in project["roots"]:
            if root in roots:
                raise ValueError("The same directory cannot belong to two projects.")
            roots.add(root)
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    sources = config.get("session_roots", [str(codex_home / "sessions"), str(codex_home / "archived_sessions")])
    if not isinstance(sources, list) or not sources:
        raise ValueError("session_roots must be a nonempty list.")
    config["session_roots"] = [resolve_path(root, path.parent) for root in sources]
    config["output_dir"] = resolve_path(config.get("output_dir", "../../.usage"), path.parent)
    for source in config["session_roots"]:
        if source == config["output_dir"] or source in config["output_dir"].parents or config["output_dir"] in source.parents:
            raise ValueError("Source directories and derived output directories must not overlap.")
    config["timezone"] = config.get("timezone", "Europe/Sofia")
    try:
        ZoneInfo(config["timezone"])
    except (ZoneInfoNotFoundError, TypeError) as error:
        raise ValueError("Config timezone must be a valid IANA timezone name.") from error
    return config


def resolve_path(value, base):
    if not isinstance(value, str) or not value:
        raise ValueError("Paths must be nonempty strings.")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def project_for(cwd, config):
    if not isinstance(cwd, str):
        return None
    path = Path(cwd).expanduser().resolve()
    matches = []
    for project in config["projects"]:
        for root in project["roots"]:
            try:
                path.relative_to(root)
                matches.append((len(Path(root).parts), project["id"]))
            except ValueError:
                pass
    return max(matches)[1] if matches else None


class Store:
    """JSONL is authoritative; SQLite is a replayable index and cursor cache."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "index.sqlite3")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS journal(hash TEXT PRIMARY KEY, kind TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS latest(kind TEXT, id TEXT, at TEXT, payload TEXT,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS cursors(path TEXT PRIMARY KEY, state TEXT);
            CREATE TABLE IF NOT EXISTS ledger_offsets(kind TEXT PRIMARY KEY, offset INTEGER);
        """)
        self.replay()

    def close(self):
        self.db.close()

    def fingerprint(self, row):
        semantic = dict(row)
        semantic.pop("observed_at", None)
        if "source" in semantic:
            semantic["source"] = dict(semantic["source"])
            semantic["source"].pop("source_ref", None)
            semantic["source"].pop("line_number", None)
        return ident(semantic)

    def index(self, kind, row):
        fingerprint = self.fingerprint(row)
        self.db.execute("INSERT OR IGNORE INTO journal VALUES(?,?,?)", (fingerprint, kind, compact(row)))
        at = (row.get("source") or {}).get("timestamp") or row["observed_at"]
        self.db.execute("""INSERT INTO latest VALUES(?,?,?,?)
            ON CONFLICT(kind,id) DO UPDATE SET at=excluded.at,payload=excluded.payload
            WHERE excluded.at >= latest.at""", (kind, row["record_id"], at, compact(row)))

    def replay(self):
        for kind, filename in FILES.items():
            path = self.directory / filename
            if not path.exists():
                continue
            saved = self.db.execute("SELECT offset FROM ledger_offsets WHERE kind=?", (kind,)).fetchone()
            offset = saved[0] if saved else 0
            if path.stat().st_size < offset:
                raise RuntimeError("Usage ledger was truncated. Restore it or use rebuild after reviewing the data.")
            with path.open("rb") as stream:
                stream.seek(offset)
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    if not line.endswith(b"\n"):
                        # A crash may leave an unfinished final append, never a valid observation.
                        with path.open("r+b") as repair:
                            repair.truncate(offset)
                        break
                    try:
                        row = json.loads(line)
                        self.index(kind, row)
                    except (ValueError, KeyError, TypeError) as error:
                        raise RuntimeError(f"Invalid derived ledger {filename} at byte {offset}; restore before importing.") from error
                    offset = stream.tell()
            self.db.execute("INSERT OR REPLACE INTO ledger_offsets VALUES(?,?)", (kind, offset))
        self.db.commit()

    def add(self, kind, row):
        if self.db.execute("SELECT 1 FROM journal WHERE hash=?", (self.fingerprint(row),)).fetchone():
            return False
        if kind == "usage" and row["scope"] == "model_call":
            previous = self.db.execute("SELECT payload FROM latest WHERE kind=? AND id=?", (kind, row["record_id"])).fetchone()
            if previous and json.loads(previous[0])["session_id"] != row["session_id"]:
                # The same response can appear in fork/replayed history: it is not a new call.
                self.diagnostic(row["project_id"], row["session_id"], row["source"], "replayed_response",
                                "Response already attributed to another session; duplicate excluded.")
                return False
        path = self.directory / FILES[kind]
        with path.open("ab") as stream:
            stream.write((compact(row) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
            offset = stream.tell()
        self.index(kind, row)
        self.db.execute("INSERT OR REPLACE INTO ledger_offsets VALUES(?,?)", (kind, offset))
        return True

    def diagnostic(self, project, session, source, code, message):
        row = metadata("diagnostic", ident("diagnostic", session, source.get("timestamp"), source.get("line_number"), code),
                       project, session, None, source, {"code": code, "message": message})
        return self.add("diagnostic", row)

    def rows(self, kind):
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM latest WHERE kind=? ORDER BY at,id", (kind,))]


def metadata(kind, record_id, project, session, turn, source, data):
    return {"schema_version": 1, "kind": kind, "record_id": record_id, "observed_at": now(),
            "project_id": project, "session_id": session, "turn_id": turn, "source": source, "data": data}


def usage_row(project, session, turn, context, source, raw, scope="model_call", response=None):
    raw = raw if isinstance(raw, dict) else {}
    tokens = {name: count(raw.get(key)) for name, key in COUNTS.items()}
    status = "reported" if any(value is not None for value in tokens.values()) else "unavailable"
    return {"schema_version": 1, "record_id": ident("call", response) if scope == "model_call" else ident(scope, session, turn),
            "observed_at": now(), "project_id": project, "session_id": session, "turn_id": turn,
            "response_id": response, "agent_id": context.get("agent_id"), "scope": scope,
            "counter_kind": "delta" if scope == "model_call" else "cumulative", "measurement_status": status,
            "model": context.get("model"), "reasoning_effort": context.get("effort"), "tokens": tokens, "source": source}


def result_fields(output):
    """Only explicit status fields count as success/failure; no text guessing."""
    value = output
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = None
    if not isinstance(value, dict):
        return None, None
    exit_code = value.get("exit_code")
    exit_code = exit_code if type(exit_code) is int else None
    success = (exit_code == 0) if exit_code is not None else None
    if type(value.get("isError")) is bool:
        success = not value["isError"]
    return exit_code, success


def handle_event(event, context, source, store):
    payload = event.get("payload")
    if not isinstance(payload, dict):
        if event.get("type") not in {"world_state", "compacted", "compaction"}:
            store.diagnostic(context["project"], context["session"], source, "invalid_payload", "Event payload is not an object.")
        return
    kind = event.get("type")
    project, session = context["project"], context["session"]
    if kind == "turn_context":
        context["model"] = payload.get("model") if isinstance(payload.get("model"), str) else None
        context["effort"] = payload.get("effort") if isinstance(payload.get("effort"), str) else None
        context["turn"] = payload.get("turn_id")
        return
    if kind == "token_usage_record":
        turn = payload.get("turn_id")
        response = payload.get("response_id")
        if isinstance(response, str) and response:
            row = usage_row(project, session, turn, context, source, payload.get("usage"), response=response)
            store.add("usage", row)
            t = row["tokens"]
            if (t["input"] is not None and t["output"] is not None and t["total"] is not None
                    and t["input"] + t["output"] != t["total"]):
                store.diagnostic(project, session, source, "token_invariant", "Input plus output differs from reported total; retained unchanged.")
        else:
            store.diagnostic(project, session, source, "missing_response_id", "Model-call usage lacks a response ID; only available snapshots are usable.")
        for field, scope, snapshot_turn in [("turn_token_usage", "turn", turn), ("thread_token_usage", "session", None)]:
            if isinstance(payload.get(field), dict):
                snapshot(payload[field], scope, snapshot_turn, context, source, store)
        return
    if kind == "event_msg":
        subtype = payload.get("type")
        if subtype == "token_count":
            info = payload.get("info")
            raw = info.get("total_token_usage") if isinstance(info, dict) else None
            snapshot(raw, "session", None, context, source, store)
        elif subtype == "task_started":
            context["turn"] = payload.get("turn_id")
            context["query_ordinal"] = 0
            context["turn_start"] = source["timestamp"]
            turn_event("in_progress", payload, context, source, store)
        elif subtype in {"task_complete", "task_failed", "turn_aborted"}:
            status = {"task_complete": "completed", "task_failed": "failed", "turn_aborted": "interrupted"}[subtype]
            turn_event(status, payload, context, source, store)
        elif subtype == "user_message":
            message = payload.get("message")
            context["query_ordinal"] = context.get("query_ordinal", 0) + 1
            qid = ident("query", session, source["timestamp"], message, payload.get("client_id"))
            store.add("query", metadata("query", qid, project, session, context.get("turn"), source,
                      {"character_count": len(message) if isinstance(message, str) else None,
                       "image_count": len(payload.get("images") or []) + len(payload.get("local_images") or []),
                       "ordinal_in_turn": context["query_ordinal"], "attribution": "turn" if context.get("turn") else "unknown"}))
        # Most event_msg types are UI/progress messages; they are intentionally not copied.
        return
    if kind == "response_item":
        subtype = payload.get("type")
        call_id = payload.get("call_id")
        if subtype in {"function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"}:
            if not isinstance(call_id, str) or not call_id:
                store.diagnostic(project, session, source, "missing_call_id", "Tool item cannot be matched without a call ID.")
                return
            calls = context.setdefault("calls", {})
            turn = (payload.get("internal_chat_message_metadata_passthrough") or {}).get("turn_id") or context.get("turn")
            if subtype in {"function_call", "custom_tool_call"}:
                data = {"name": payload.get("name") if isinstance(payload.get("name"), str) else None,
                        "status": "in_progress", "started_at": source["timestamp"], "completed_at": None,
                        "duration_ms": None, "output_bytes": None, "exit_code": None, "success": None}
                calls[call_id] = {"data": data, "turn": turn}
            else:
                prior = calls.pop(call_id, {})
                data = prior.get("data", {"name": None, "status": "unknown", "started_at": None})
                turn = prior.get("turn") or turn
                output = payload.get("output")
                exit_code, success = result_fields(output)
                data.update(status="failed" if success is False else "completed", completed_at=source["timestamp"],
                            duration_ms=elapsed(data.get("started_at"), source["timestamp"]),
                            output_bytes=len((output if isinstance(output, str) else compact(output)).encode()),
                            exit_code=exit_code, success=success)
            store.add("tool", metadata("tool", ident("tool", session, call_id), project, session, turn, source, data))
        return
    if kind not in {"session_meta", "world_state", "compacted", "compaction"}:
        store.diagnostic(project, session, source, "unknown_event_type", "Unrecognized transcript event type; adapter may need updating.")


def elapsed(start, end):
    if not start or not end:
        return None
    duration = (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()
    return round(duration * 1000) if duration >= 0 else None


def turn_event(status, payload, context, source, store):
    turn = payload.get("turn_id") or context.get("turn")
    if not turn:
        store.diagnostic(context["project"], context["session"], source, "missing_turn_id", "Turn lifecycle event has no usable turn ID.")
        return
    duration = count(payload.get("duration_ms"))
    if duration is None and status != "in_progress":
        duration = elapsed(context.get("turn_start"), source["timestamp"])
    store.add("turn", metadata("turn", ident("turn", context["session"], turn), context["project"], context["session"], turn, source,
              {"status": status, "started_at": context.get("turn_start"), "completed_at": source["timestamp"] if status != "in_progress" else None,
               "duration_ms": duration}))


def snapshot(raw, scope, turn, context, source, store):
    if scope == "session" and isinstance(raw, dict):
        total = count(raw.get("total_tokens"))
        previous = context.get("last_total")
        previous_at = context.get("last_total_at")
        chronological = previous_at is None or (source["timestamp"] is not None and source["timestamp"] >= previous_at)
        if chronological and total is not None and previous is not None and total < previous:
            store.diagnostic(context["project"], context["session"], source, "counter_reset", "Cumulative counter decreased; fallback coverage is incomplete.")
        if chronological and total is not None:
            context["last_total"] = total
            context["last_total_at"] = source["timestamp"]
    store.add("usage", usage_row(context["project"], context["session"], turn, context, source, raw, scope=scope))


def import_sessions(config, store):
    stats = {"files_changed": 0, "new_observations": 0, "malformed_lines": 0, "missing_source_roots": 0,
             "unsupported_headers": 0}
    before = store.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
    config_key = ident(config["projects"])
    paths = set()
    for root in config["session_roots"]:
        if not root.is_dir():
            stats["missing_source_roots"] += 1
            continue
        paths.update(root.rglob("*.jsonl"))
    for path in sorted(paths):
        try:
            file_stat = path.stat()
        except FileNotFoundError:
            continue  # Sessions may move into the archive while the app is running.
        saved = store.db.execute("SELECT state FROM cursors WHERE path=?", (str(path),)).fetchone()
        state = json.loads(saved[0]) if saved else {}
        signature = [file_stat.st_dev, file_stat.st_ino]
        if (state.get("signature") != signature or state.get("offset", 0) > file_stat.st_size
                or state.get("config_key") != config_key):
            state = {}
        if state.get("size") == file_stat.st_size and state.get("mtime") == file_stat.st_mtime_ns:
            continue
        try:
            source_stream = path.open("rb")
        except FileNotFoundError:
            continue
        with source_stream as stream:
            if state.get("offset") and state.get("tail_hash"):
                stream.seek(max(0, state["offset"] - 128))
                tail = stream.read(min(128, state["offset"]))
                if hashlib.sha256(tail).hexdigest() != state["tail_hash"]:
                    state = {}  # In-place rewrite: replay safely rather than trusting an old cursor.
                stream.seek(0)
            context = state.get("context")
            if context is None:
                first = stream.readline()
                if not first.endswith(b"\n"):
                    continue
                try:
                    meta_event = json.loads(first)
                    meta = meta_event.get("payload", {})
                    if meta_event.get("type") != "session_meta" or not isinstance(meta, dict):
                        stats["unsupported_headers"] += 1
                        continue
                except (ValueError, AttributeError):
                    stats["unsupported_headers"] += 1
                    continue
                project = project_for(meta.get("cwd"), config)
                session = meta.get("id") or meta.get("session_id")
                if not project or not isinstance(session, str) or not session:
                    continue
                origin = meta.get("source")
                is_subagent = isinstance(origin, dict) and "subagent" in origin
                context = {"project": project, "session": session, "agent_id": session if is_subagent else None,
                           "version": meta.get("cli_version") if isinstance(meta.get("cli_version"), str) else None,
                           "calls": {}, "model": None, "effort": None, "turn": None}
                state.update(offset=stream.tell(), line=1)
            stream.seek(state["offset"])
            stats["files_changed"] += 1
            while True:
                line = stream.readline()
                if not line or not line.endswith(b"\n"):
                    break  # Incomplete last line is retried on the next poll.
                state["line"] += 1
                source = {"kind": "codex_session_log", "event_type": None, "source_ref": path.name,
                          "line_number": state["line"], "timestamp": None, "client_version": context["version"]}
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("Not an object")
                    source.update(timestamp=stamp(event.get("timestamp")), event_type=event.get("type") if isinstance(event.get("type"), str) else None)
                    handle_event(event, context, source, store)
                except (ValueError, TypeError, AttributeError, KeyError) as error:
                    stats["malformed_lines"] += 1
                    store.diagnostic(context["project"], context["session"], source, "malformed_line", f"Invalid source record ({type(error).__name__}); raw content omitted.")
                state["offset"] = stream.tell()
            state.update(context=context, signature=signature, config_key=config_key,
                         size=file_stat.st_size, mtime=file_stat.st_mtime_ns)
            stream.seek(max(0, state["offset"] - 128))
            state["tail_hash"] = hashlib.sha256(stream.read(min(128, state["offset"]))).hexdigest()
            store.db.execute("INSERT OR REPLACE INTO cursors VALUES(?,?)", (str(path), compact(state)))
    store.db.commit()
    stats["new_observations"] = store.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0] - before
    return stats


def sums(rows):
    partial = {name: sum(r["tokens"][name] for r in rows if r["tokens"][name] is not None) for name in COUNTS}
    unknown = {name: sum(r["tokens"][name] is None for r in rows) for name in COUNTS}
    return {"tokens": {name: partial[name] if not unknown[name] else None for name in COUNTS},
            "known_token_sums": partial, "unknown_measurements": unknown}


def summarize(config, store, group="project", project_filter=None):
    usage = [r for r in store.rows("usage") if not project_filter or r["project_id"] == project_filter]
    sessions = {}
    for row in usage:
        sessions.setdefault((row["project_id"], row["session_id"]), []).append(row)
    selected, coverage = [], []
    diagnostics = store.rows("diagnostic")
    all_turns = store.rows("turn")
    all_queries = store.rows("query")
    for (project, session), rows in sessions.items():
        calls = [r for r in rows if r["scope"] == "model_call"]
        snapshots = [r for r in rows if r["scope"] == "session"]
        snapshot_row = snapshots[-1] if snapshots else None
        totals = sums(calls)["tokens"] if calls else None
        matches = (all(totals[key] == snapshot_row["tokens"][key] for key in COUNTS
                       if snapshot_row["tokens"][key] is not None) if totals and snapshot_row else None)
        if not snapshot_row or snapshot_row["tokens"]["total"] is None:
            matches = None
        reset = any(d["session_id"] == session and d["data"]["code"] == "counter_reset" for d in diagnostics)
        turns = [r for r in all_turns if r["session_id"] == session]
        lifecycle_unknown = not turns or any(r["data"]["status"] == "in_progress" for r in turns)
        replayed = any(d["session_id"] == session and d["data"]["code"] == "replayed_response" for d in diagnostics)
        coverage.append({"project_id": project, "session_id": session, "model_calls": len(calls),
                         "basis": "model_calls" if calls else ("excluded_replay_snapshot" if replayed else "session_snapshot"), "reconciles": matches,
                         "counter_reset": reset, "live_or_unknown_lifecycle": lifecycle_unknown,
                         "complete": bool(calls and matches and not reset and not lifecycle_unknown)})
        selected.extend(calls if calls else ([snapshot_row] if snapshot_row and not replayed else []))
    groups = {}
    tz = ZoneInfo(config["timezone"])
    for row in selected:
        date = row["source"]["timestamp"]
        date = datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(tz).date().isoformat() if date else None
        value = {"project": row["project_id"], "session": row["session_id"], "turn": row["turn_id"],
                 "model": row["model"], "effort": row["reasoning_effort"], "date": date}[group]
        grouping = (row["session_id"], value) if group == "turn" else value
        groups.setdefault((row["project_id"], grouping), []).append(row)
    result = []
    for (project, key), rows in groups.items():
        session = key[0] if group == "turn" else None
        value = key[1] if group == "turn" else key
        query_count = sum(q["project_id"] == project and (group != "turn" or (q["turn_id"] == value and q["session_id"] == session))
                          for q in all_queries) if group in {"project", "turn"} else None
        result.append({"project_id": project, "group": value, "session_id": session, "observations": len(rows),
                       "model_calls": sum(r["scope"] == "model_call" for r in rows), "query_count": query_count,
                       "query_attribution": "shared_turn" if group == "turn" and query_count and query_count > 1 else "turn_or_unknown",
                       **sums(rows)})
    represented = {key for key in sessions}
    activities = all_queries + all_turns
    missing = sorted({(r["project_id"], r["session_id"]) for r in activities
                      if (not project_filter or r["project_id"] == project_filter) and (r["project_id"], r["session_id"]) not in represented})
    return {"schema_version": 1, "generated_at": now(), "timezone": config["timezone"], "group_by": group,
            "groups": result, "session_coverage": coverage,
            "sessions_without_usage": [{"project_id": p, "session_id": s} for p, s in missing],
            "note": "Reported usage, not an invoice. Snapshots and calls are never added together; live turns and source gaps may be incomplete."}


def advice(config, store, project_filter=None):
    report = summarize(config, store, "turn", project_filter)
    queries, tools = store.rows("query"), store.rows("tool")
    usage = store.rows("usage")
    assessments = {(r["project_id"], r["session_id"], r["turn_id"]): r for r in store.rows("assessment")}
    findings = []
    for group in report["groups"]:
        project, turn, session = group["project_id"], group["group"], group["session_id"]
        qs = [r for r in queries if r["project_id"] == project and r["turn_id"] == turn and r["session_id"] == session]
        ts = [r for r in tools if r["project_id"] == project and r["turn_id"] == turn and r["session_id"] == session]
        if len(qs) >= 3:
            findings.append({"project_id": project, "turn_id": turn, "rule": "multiple_query_inputs", "evidence_ids": [r["record_id"] for r in qs],
                             "suggestion": "Inspect whether these were intended steering updates or scope clarification. Try stating affected component, desired behavior, exclusions, and acceptance check in the first query."})
        input_tokens = group["tokens"]["input"]
        if input_tokens is not None and group["model_calls"] >= 5 and input_tokens / group["model_calls"] > 50000:
            findings.append({"project_id": project, "turn_id": turn, "rule": "large_repeated_context", "evidence_ids": [r["record_id"] for r in usage if r["session_id"] == session and r["turn_id"] == turn and r["scope"] == "model_call"],
                             "suggestion": "Review context size and broad reads. For a new independent task, consider a fresh session with a concise state handoff. Compare total usage and quality on similar tasks; cached input is still processed usage."})
        if len(ts) >= 20:
            findings.append({"project_id": project, "turn_id": turn, "rule": "many_tool_activities", "evidence_ids": [r["record_id"] for r in ts],
                             "suggestion": "Inspect this turn for repeated checks or reads. Tool count alone does not prove waste; batch independent operations when appropriate."})
        for (p, assessment_session, t), assessment in assessments.items():
            if p != project or t != turn or assessment_session != session:
                continue
            calls = [r for r in usage if r["session_id"] == session and r["turn_id"] == turn and r["scope"] == "model_call"]
            if assessment["data"]["task_type"] == "routine" and any(r["reasoning_effort"] in {"high", "xhigh", "max", "ultra"} for r in calls):
                findings.append({"project_id": p, "turn_id": t, "rule": "routine_high_effort", "evidence_ids": [assessment["record_id"]] + [r["record_id"] for r in calls],
                                 "suggestion": "Try lower effort on a comparable routine task and retain the same acceptance checks. Keep the change only if quality remains adequate."})
    return {"schema_version": 1, "generated_at": now(), "findings": findings,
            "assessments": [r for r in assessments.values() if not project_filter or r["project_id"] == project_filter],
            "note": "Local heuristics, no model calls. These are investigation suggestions, not rankings of prompt quality. Compare similar task types and check results using assessments."}


def write_result(value, path=None):
    encoded = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded)
        print(compact({"written": str(target)}))
    else:
        print(encoded, end="")


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--config", default=str(Path(__file__).with_name("config.json")), help="Project/source/output configuration.")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("import", help="Import available local history once, incrementally.")
    watch = commands.add_parser("watch", help="Poll local files until Ctrl+C; no API/model calls.")
    watch.add_argument("--interval", type=float, default=5, help="Poll interval in seconds, default 5.")
    watch.add_argument("--cycles", type=int, help="Stop after this many polls (useful for smoke checks).")
    summary = commands.add_parser("summary", help="JSON summary/export; import first for fresh data.")
    summary.add_argument("--group", choices=["project", "session", "turn", "model", "effort", "date"], default="project")
    summary.add_argument("--project")
    summary.add_argument("--out")
    report = commands.add_parser("advice", help="Local evidence-based workflow suggestions; no LLM call.")
    report.add_argument("--project")
    report.add_argument("--out")
    export = commands.add_parser("export", help="Export deduplicated current records for dashboard ingestion.")
    export.add_argument("--out", required=True)
    export.add_argument("--project")
    feedback = commands.add_parser("assess", help="Record user-approved task metadata and outcome feedback.")
    feedback.add_argument("--project", required=True)
    feedback.add_argument("--session", required=True)
    feedback.add_argument("--turn", required=True)
    feedback.add_argument("--task-type", default="unknown")
    feedback.add_argument("--outcome", choices=["success", "failed", "blocked", "unknown"], default="unknown")
    feedback.add_argument("--checks", choices=["passed", "failed", "not_run", "unknown"], default="unknown")
    feedback.add_argument("--rating", type=int, choices=range(1, 6))
    feedback.add_argument("--summary", default="", help="Optional redacted user-approved summary, max 240 characters.")
    feedback.add_argument("--tag", action="append", default=[])
    commands.add_parser("rebuild", help="Rebuild SQLite from the JSONL ledgers; then reimport source history.")
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        directory = config["output_dir"]
        if getattr(args, "out", None):
            target = Path(args.out).expanduser().resolve()
            if any(target == root or root in target.parents for root in config["session_roots"]):
                raise ValueError("Exports cannot overwrite source session directories.")
        if args.command == "watch":
            if not math.isfinite(args.interval) or args.interval <= 0 or (args.cycles is not None and args.cycles < 1):
                raise ValueError("Watch interval and cycles must be positive.")
            # SIGTERM shares the graceful Ctrl+C shutdown path; no child processes.
            def stop_watch(*_):
                raise KeyboardInterrupt
            signal.signal(signal.SIGINT, stop_watch)
            signal.signal(signal.SIGTERM, stop_watch)
            with lock(directory / "watch.lock"):
                print(compact({"watching": True, "interval_seconds": args.interval, "stop": "Ctrl+C", "output_dir": str(directory)}), flush=True)
                cycle = 0
                while True:
                    try:
                        with lock(directory / "collector.lock"):
                            store = Store(directory)
                            try:
                                result = import_sessions(config, store)
                            finally:
                                store.close()
                        if result["new_observations"] or result["malformed_lines"] or result["unsupported_headers"] or cycle == 0:
                            print(compact(result), flush=True)
                    except RuntimeError as error:
                        if "lock busy" not in str(error):
                            raise
                    cycle += 1
                    if args.cycles and cycle >= args.cycles:
                        return 0
                    time.sleep(args.interval)
        else:
            with lock(directory / "collector.lock"):
                if args.command == "rebuild":
                    # Only the derived index is removed; source files and ledgers are preserved.
                    for suffix in ["", "-journal", "-wal", "-shm"]:
                        index = directory / ("index.sqlite3" + suffix)
                        if index.exists():
                            index.unlink()
                store = Store(directory)
                try:
                    if args.command == "import":
                        write_result(import_sessions(config, store))
                    elif args.command == "summary":
                        write_result(summarize(config, store, args.group, args.project), args.out)
                    elif args.command == "advice":
                        write_result(advice(config, store, args.project), args.out)
                    elif args.command == "export":
                        write_result({"schema_version": 1, "generated_at": now(), "records": {
                            kind: [r for r in store.rows(kind) if not args.project or r["project_id"] == args.project] for kind in FILES}}, args.out)
                    elif args.command == "assess":
                        if args.project not in {p["id"] for p in config["projects"]}:
                            raise ValueError("Assessment project is not configured.")
                        if len(args.summary) > 240:
                            raise ValueError("Assessment summary must be at most 240 characters.")
                        matched = any(r["project_id"] == args.project and r["session_id"] == args.session and r["turn_id"] == args.turn
                                      for kind in ["usage", "query", "turn"] for r in store.rows(kind))
                        if not matched:
                            raise ValueError("Import this session/turn before adding an assessment.")
                        source = {"kind": "manual", "event_type": "assessment", "source_ref": None, "line_number": None,
                                  "timestamp": now(), "client_version": None}
                        row = metadata("assessment", ident("assessment", args.project, args.session, args.turn), args.project, args.session, args.turn, source,
                              {"task_type": args.task_type, "outcome": args.outcome, "check_status": args.checks,
                               "rating": args.rating, "redacted_summary": args.summary, "tags": args.tag})
                        store.add("assessment", row)
                        store.db.commit()
                        write_result({"recorded": row["record_id"]})
                    elif args.command == "rebuild":
                        write_result({"rebuilt": True, "observations": store.db.execute("SELECT COUNT(*) FROM journal").fetchone()[0],
                                      "next": "Run import to recreate incremental source cursors."})
                finally:
                    store.close()
        return 0
    except KeyboardInterrupt:
        print(compact({"stopped": True}), flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"Usage collector: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
