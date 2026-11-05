# Unused and incomplete configuration

In initialized projects, this guide and all configurations live in `.project-kit/`. Paths below are relative to that kit folder. Root `AGENTS.md` routes agents here; private credentials still belong outside every Git root.

There is no universal disabled value. Do not insert `NULL`, `null`, `None`, `N/A` or an empty string into executable configuration unless that field explicitly supports it. JSON `null` is a value, not a comment; uppercase `NULL` is invalid JSON. Markdown descriptions can say `Not applicable — reason` or `Unknown — next check`.

## Database environment map

For an unused environment such as staging, keep its entry in `database/ENVIRONMENTS.json` with `"configured": false` and `"disposable": false`. Leave its example profile paths as strings; they do not activate connections. Do not create private profiles for unused environments. Describe the reason in the project brief if useful. Keep unused engines unconfigured by leaving their private profiles absent; document which engine each component actually uses. The environment-level flag does not authorize either engine or replace checks of its selected profile.

```json
"staging": {
  "configured": false,
  "disposable": false,
  "inspection_requires": "Unavailable: this project has no staging database",
  "writes_require": "Unavailable: this project has no staging database",
  "postgresql": {
    "service": "project_staging",
    "service_file": "staging/pg_service.conf",
    "password_file": "staging/pgpass"
  },
  "mongodb": {"profile_file": "staging/mongodb.json"}
}
```

This is an entry fragment, not a complete JSON file. No databases at all? Leave all environments false, use `private_root`'s unconfigured placeholder, and write `Database: not applicable` in the brief. No secret directories need creating. If databases are used, set `private_root` to an actual absolute private directory outside every Git repository, create only required environment profiles privately, and enable an environment only after verifying its target. Keep `disposable=false` except for a verified disposable test database. Do not infer an environment from a branch or fall back from an unavailable one. See [DATABASES.md](DATABASES.md).

## Usage tracking

In `usage/config.json`, project IDs, root paths, output paths and timezone must remain valid strings. Each configured project needs a nonempty roots list. Delete unused project/root entries rather than replacing them with null. You may omit `session_roots` to use the collector's default Codex directories; if supplied it must be a nonempty list. Missing log directories produce no usage evidence: run on the machine containing the desktop logs or configure their real paths. Do not invent counts.

Tracking is optional: do not run `import` or `watch` if you do not want it. Leaving a valid config in place does not launch anything. Stop an existing watcher with Ctrl+C. Keep one collector per dataset; a central collector can map several projects. Restart watch after config edits. Unavailable measured counts in exported records may legitimately be JSON null; that does not make null valid in configuration fields.

## Git manager

`multi-git.conf` is INI, not JSON. Disable a configured repository with `enabled = false`, or remove its entire `[repo:...]` section. Omit unused `alias.*` keys and `[group:...]` sections; update groups when removing repos. Do not set branch aliases, remotes or paths to `NULL`: that would be a literal name/path. Keep actual protected branch names; the default list may include nonexistent branches harmlessly. An empty workspace config is valid, but repo commands need a nonempty enabled selection. A repository without a remote can use local inspection/branch commands; fetch/pull/push need real configuration. Do not use a fabricated remote or upstream.

## Project documents

Fill facts needed for the current task, linking existing README/build/contract sources. Mark irrelevant prose sections `Not applicable — reason`; unknown facts are `Unknown`, with a next check. For maintenance, a small task needs no new plan/brief; complex work follows the agreed planning rule. Commands for application tests, startup and deployment must come from that project's actual tooling. Templates do not implement or authorize deployment.

Optional docs/tools may remain unused. If a team chooses to remove them, update instruction links deliberately so agents do not chase missing files. Retain applicable quality, security, final-review and explicit-commit rules.
