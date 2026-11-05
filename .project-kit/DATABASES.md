# Database environments, state and private connections

Unused environments stay `configured=false` and `disposable=false`; do not substitute NULL for profile/path strings. See [OPTIONAL_CONFIG.md](OPTIONAL_CONFIG.md) for a no-staging example and projects without databases.

Use this guide when a task depends on database state. It covers PostgreSQL and MongoDB, shared by a parent workspace containing related repositories. The current task authorizes a specific action; possession of credentials does not authorize access, exports, migrations or data changes.

## What belongs where

Keep one canonical environment map per parent workspace, for example `database/ENVIRONMENTS.json`, copied from [the template](database/ENVIRONMENTS.example.json). Record environment aliases, which component owns each database/schema/collection, migration ownership, safe connection-profile paths and operational rules. Profile paths in the map resolve against `private_root`; the guide link resolves against the map file. The map is metadata for humans/agents, not an enforcing database gateway. Its profiles start unconfigured and no environment is assumed disposable.

Keep credentials outside **every** Git root, for example `~/.config/project-databases/<project-id>/<environment>/`. Use separate files for `local`, `dev`, `staging` and `prod`; do not mix their credentials or wildcard credentials. The same private-storage/no-output rule applies to API keys and other project secrets. PostgreSQL uses `pg_service.conf` plus `pgpass`; MongoDB uses `mongodb.json`. Private keys, client certificates, CA references and private diagnostic output also belong in the local private area. A credential-bearing MongoDB URI is a secret in its entirety.

Agents may read the non-secret map and inspected connection code. The **local database client** reads the credential file. Agents must not display or ingest raw secrets through file-reading tools, `cat`, `rg`, `printenv`, shell tracing, exception dumps, URLs, arguments, screenshots, prompts or web requests. Store only file paths/aliases in `AGENTS.md`, plans, state and examples; never credential values. Do not source/eval credential files as shell code.

Place universal rules in global `AGENTS.md` if desired. Keep the environment map and project database facts in the parent workspace. Each repo links to that canonical guide/map and documents its owned schema/collections, migration tool and focused checks. Independent Git roots need their own [ignore protection](database/REPOSITORY_GITIGNORE.example) if private files ever live inside them; a parent's `.gitignore` does not protect a child repo. Ignore rules do not untrack existing files or prevent agent reads. Before displaying a diff, check filenames and use the project's local secret checks with value-redacted output; do not inspect suspected credential files by printing them.

## Access and environment selection

| Environment | Normal development behavior | Applying changes |
| --- | --- | --- |
| local | Prefer synthetic fixtures and an explicitly disposable database. Read-only credentials for inspection. | Routine tests may mutate/reset only a verified disposable target within task scope. A developer's persistent local database is not automatically disposable. |
| dev | Shared state: scoped read-only inspection when authorized. | Apply only a specific approved change/target, with recovery and coordination. |
| staging | Production-like behavior and potentially sensitive data: scoped read-only inspection. | Rehearse the approved migration/backfill and app rollout; avoid unrelated state changes. |
| prod | Explicit production access authorization, least privilege, bounded read-only diagnostics. | Exact reviewed change and explicit production rollout authorization, with verified recovery, timing and owner. |

Require a named environment on every database command, including schema inspection. Never infer it from a Git branch, current working directory, absent config, reachable server or reused URI. Missing/mismatched profiles fail closed; do not fall back to another environment or enable an unconfigured profile yourself.

Before any stateful task, establish engine/version/topology, logical database identity, schema or migration revision, data/tenant scope, replica versus primary, role privileges and whether state is disposable. Use a reviewed local check against a trusted deployment marker/identifier and expected migration metadata; keep raw identity output private. A file labeled `staging`, a successful ping, read preference or application profile name is not proof of environment identity or read-only privileges. Enforce least privilege with actual database grants and separate migration/write credentials.

Connect only to the approved database/VPN/tunnel target. Require verified TLS for remote access; no certificate/hostname validation bypass. An explicitly documented loopback-only disposable setup may use its existing local transport; the provided connection examples require TLS. Forwarded ports do not make a production database disposable. Authentication traffic to the authorized database is part of connecting; if **nothing may leave your computer**, use local-only databases and keep remote credentials unavailable.

Prepare concrete artifacts before requesting any missing approval: exact SQL/JS/migration IDs, target, predicates/expected counts, data/tenant scope, ordering, checks, performance/locking effects and recovery. Existing specific authorization persists within its scope; do not ask again for the same approved step. Approval to develop a feature or prepare a migration does not itself authorize applying it to shared environments. Record approval for the exact target/artifact; material revisions need renewed agreement.

## State-dependent development and testing

Read existing migrations, model mappings, constraints, indexes and relevant schema/collection validators before changing persistence code. Confirm live state only with authorized bounded diagnostics. Code and migration files describe intended history; deployed schema and data may differ. Record discrepancies without silently repairing or resetting them.

Prefer a minimal synthetic reproduction: engine/version/topology, schema/migration revision, fixture ID/seed and invariant that triggers the bug. Cover existing rows/documents, missing/null fields, duplicates, tenant isolation and concurrency as relevant. Do not copy production dumps or private records into fixtures, chats or test artifacts. Anonymization/export requires explicit authorization and a reviewed procedure.

Run database integration tests on a named isolated disposable target matching important production behavior. Tag the database/fixture ownership so cleanup cannot hit an unrelated database. Disable unrelated startup migrations, workers, scheduled jobs and external integrations where needed; running an app/test suite can write state even when the task sounds read-only. Never point broad tests at dev/staging/prod. Record what was actually tested; a test against another engine or topology is not equivalent evidence.

Query only necessary columns/fields, with selective predicates, explicit projections, bounded result sizes and timeouts. Avoid broad dumps and unbounded cursors. `LIMIT` alone does not bound work or make a result private. Query plans/profiling can execute expensive operations; inspect the exact command before treating them as harmless. Prefer approved aggregates or synthetic samples. Keep sensitive rows/documents and raw failures out of agent-visible output; return only reviewed allowlisted summaries.

## Migrations, backfills and related repositories

Use the project's existing migration mechanism and naming/checksum conventions. Keep applied migration history immutable; add a new versioned change. Design forward-compatible expansion, coordinated deployment/backfill, and later cleanup when consumers span repositories. Assign one migration owner per database and prevent competing deployers. Git operations do not update or restore database state.

Before execution, check drift, dependencies, migration history and all consuming app revisions. Specify transaction boundaries, retry/idempotence behavior, batch/checkpoint strategy, tenant scope, lock/timeout limits, index/constraint costs and expected affected counts. Rehearse on disposable representative state, including restart/retry and mixed application versions where relevant. Validate both the business invariant and migration bookkeeping afterward.

Recovery must match the operation: verified restore/PITR, a reviewed reverse migration, or a forward repair. Record backup/restore evidence and recovery ownership before a consequential change; an existing backup without a tested restore procedure is insufficient evidence. Do not assume DDL, index operations or arbitrary migration runners are one atomic transaction. A restore can discard newer writes and is its own consequential operation.

For PostgreSQL, use an actual restricted role plus a read-only transaction for inspection; transaction mode is an extra guard, not a complete authorization boundary. Verify engine-specific transactional/locking behavior of each schema/index operation against the deployed version. [PostgreSQL transaction modes](https://www.postgresql.org/docs/current/sql-set-transaction.html).

For MongoDB, account for document shape evolution, validators, indexes, partial writes and read/write concern. Single-document atomicity does not make a multi-document migration atomic. Transaction availability depends on topology; verify replica-set/sharded deployment behavior instead of assuming a local standalone matches production. [MongoDB transactions](https://www.mongodb.com/docs/manual/core/transactions/).

## Local credential setup

No actual credentials or profiles have been created or read here. Setup snippets and file-mode guards target Unix; adapt to restrictive owner-only ACLs on other systems. These are templates to populate **privately**, using a local editor that does not send content to a cloud agent or extension. Use one project ID for related repos, and different environment directories. On Unix, use private directories (`0700`) and files (`0600`), appropriate owner, restrictive umask, and protected storage/backups. Do not put the private root in a synced/shared folder. Existing corporate secret managers or native credential stores can replace files; keep the same no-output boundary.

```bash
# Human-run setup, from the instruction-kit directory; replace project ID.
# Do not paste real credential values into terminal commands or chat.
db_private_root="$HOME/.config/project-databases/REPLACE_WITH_PROJECT_ID"
umask 077
mkdir -p "$db_private_root/local" "$db_private_root/dev" "$db_private_root/staging" "$db_private_root/prod"
chmod 700 "$db_private_root" "$db_private_root/local" "$db_private_root/dev" "$db_private_root/staging" "$db_private_root/prod"
```

Copy only the needed example files into a chosen private environment directory **if they do not already exist**. Use `cp -i` in your own interactive terminal, or create new files in the private editor; do not run an unattended copy that overwrites credentials. Set file permissions before adding values. Update the non-secret environment map with the actual absolute private-root path, alias and configured state after verifying the connection configuration.

PostgreSQL: [service template](database/examples/pg_service.conf.example), [password template](database/examples/pgpass.example). The owner fills host/database/role/CA details and the password privately. Use exact host/port/database/user matching, escape colon/backslash in `pgpass`, and restrict it to `0600`. `PGSERVICEFILE` and `PGPASSFILE` select the private files; the command line contains only a service alias. Avoid `PGPASSWORD` and password-bearing DSNs. [Service files](https://www.postgresql.org/docs/current/libpq-pgservice.html), [password files](https://www.postgresql.org/docs/current/libpq-pgpass.html).

Use `sslmode=verify-full` and a trusted CA configuration for remote PostgreSQL. [Certificate verification](https://www.postgresql.org/docs/current/libpq-ssl.html).

MongoDB: [profile template](database/examples/mongodb.profile.example.json). Fill the URI/database privately, percent-encoding URI credentials correctly. Keep `configured=false` until the profile is verified. Supply actual CA/client-key paths privately if required; never disable TLS certificate/hostname validation. Use a DB-enforced read-only user for inspection. [MongoDB TLS](https://www.mongodb.com/docs/manual/core/security-transport-encryption/).

These profiles configure CLI inspection. Do not assume application drivers automatically consume the same files: use the project's existing application/framework secret loader, review its logging, and verify startup migration/worker behavior before using it.

The [MongoDB reachability example](database/examples/mongodb-ping.js) consumes the private file inside `mongosh`, refuses an unconfigured/mismatched environment or broadly readable file, requires explicit TLS, and emits fixed messages. It does not verify server identity beyond configured TLS, actual grants or migration state. `--nodb --norc --file` avoids a default startup connection and user startup scripts. It disables shell telemetry before connecting; review other local tools' telemetry separately. [Script execution](https://www.mongodb.com/docs/mongodb-shell/write-scripts/), [shell flags](https://www.mongodb.com/docs/mongodb-shell/reference/options/), [telemetry controls](https://www.mongodb.com/docs/mongodb-shell/telemetry/).

## Connection examples without secret output

These examples are fixed **reachability checks**, not migration/query runners. Only execute for an explicitly authorized environment using owner-verified profiles. PostgreSQL uses `psql`; MongoDB uses `mongosh`. Replace paths/aliases using the map; never substitute a URI/password into a command. Both streams go to a private log, and the agent receives only exit status. Do not read those raw logs back into agent context.

```bash
# From the instruction-kit directory, using a verified LOCAL PostgreSQL profile.
# Production/shared use requires its explicit access authorization and matching paths.
db_private_root="$HOME/.config/project-databases/REPLACE_WITH_PROJECT_ID"
umask 077
db_check_log=$(mktemp "$db_private_root/local/pg-check.XXXXXXXX")
if PGSERVICEFILE="$db_private_root/local/pg_service.conf" \
   PGPASSFILE="$db_private_root/local/pgpass" \
   psql -X -w --set=ON_ERROR_STOP=1 --dbname='service=project_local' \
   --file=.project-kit/database/examples/postgresql-ping.sql >"$db_check_log" 2>&1; then
  printf '%s\n' 'PostgreSQL reachability check succeeded.'
else
  printf '%s\n' 'PostgreSQL check failed; review the log privately.'
fi

# Independent LOCAL MongoDB profile; example requires explicit verified TLS.
db_check_log=$(mktemp "$db_private_root/local/mongo-check.XXXXXXXX")
if DB_PROFILE_FILE="$db_private_root/local/mongodb.json" DB_TARGET_ENV=local \
   mongosh --nodb --norc --quiet --file=.project-kit/database/examples/mongodb-ping.js \
   >"$db_check_log" 2>&1; then
  printf '%s\n' 'MongoDB reachability check succeeded.'
else
  printf '%s\n' 'MongoDB check failed; review the log privately.'
fi
```

Do not execute under `set -x`, in a logging CI job, or in a cloud task with copied private files. Do not dump environment variables, decoded connection options, raw errors, document samples or database backups into a report. The snippets require successful private-directory/log creation before continuing; stop on setup errors. They do not install clients, provision roles or select another target. The MongoDB example disables that shell's telemetry and may persist this preference; no global settings were changed during this kit's verification.

No service lifecycle is added: a check starts and exits; file changes apply on the next check. Existing apps/pools/services may require a restart after credential rotation; follow their actual documented lifecycle. Revoke/rotate exposed secrets, remove them from accessible artifacts, and assess prior disclosure with the owner; deleting the local file alone does not undo exposure.

## Limits and stronger enforcement

A local file and `.gitignore` do **not** guarantee secrets stay offline. Codex uses OpenAI inference; content returned to the model can leave the machine. Our no-output rule is a workflow safeguard, not a claim that the desktop app runs the model locally. [Official OpenAI documentation on the data boundary](https://learn.chatgpt.com/docs/hipaa-configuration).

For a strict technical boundary, keep raw secret files unreadable to the agent sandbox and expose only a separately trusted local broker or human-run command with fixed operations, allowlisted targets and sanitized results. A general shell with the same file access as the database client can otherwise display the file. A deny-read rule also blocks an ordinary client launched in that same sandbox; do not bypass it by copying secrets or loosening permissions. That stronger broker is not implemented by these documents.

Use app/OS permissions and network controls in addition to instructions. Codex shell permission profiles are separate from web, connectors and other tool surfaces; a shell network rule alone is not a universal exfiltration boundary. No app/global permission settings were changed here. [Official permission controls](https://learn.chatgpt.com/docs/permissions).

If a task cannot return diagnostics without exposing secrets or private data, stop that output path and have the owner review raw output privately or use the trusted broker. Treat database contents, backups and logs with the same care as credentials. Keep production credentials absent from normal development sessions unless specifically needed.

## Handoff and verification

For relevant work, record environment alias, database component, deployed/migration revision, fixture ID, affected app repos/revisions, approved artifact/operation, checks, result and next step. Use a small optional database section in the current task; do not create a separate plan for every query. Link a substantial migration/rollout plan when needed. Never place secret values, raw records or backup contents in `STATE.md`, tasks, usage ledgers or versioned reports.

Verification here: **7 MongoDB example guard tests passed**, using fake connections and synthetic credentials; JavaScript syntax, JSON/INI validation, shell parsing and documentation links are also checked. Run `python3 -m unittest discover -s .project-kit/database -p 'test_*.py' -v` from the kit directory (Node.js required for the mocked shell tests). No live databases are contacted. PostgreSQL client/server behavior and real MongoDB authentication/TLS/role checks must be verified in the actual project's isolated environment; they are not claimed tested by this kit.
