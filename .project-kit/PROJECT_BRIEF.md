# Project brief

Status: template; adapt for a new product or an existing system. One shared brief can cover related repositories. It supplies context; the current task defines the requested change.

## Goal and users

- Problem to solve:
- Intended users:
- Existing behavior, or first useful milestone for a new product:

## System and repository map

For each repository, record its path, role, technology, owned data/contracts, key providers/consumers, and link to its local README/instructions. Keep detailed component guidance local.

Describe the important API/event/data flows and authentication/private-data boundaries. Link to authoritative contract definitions rather than copying them.

For database-dependent systems, link the canonical `DATABASES.md` and non-secret environment map. Record logical databases, schema/collection and migration ownership, important state invariants, supported engine/topology sources, related consumers, disposable fixture setup and recovery owner. Keep actual credentials, private keys and sensitive records in private local storage; do not duplicate connection secrets here.

## Evidence and confidence

Label confirmed behavior, code-derived inferences, intended business rules confirmed by the user, and unresolved questions. The agent may draft this brief from relevant code/docs; it cannot infer all business intent. Grow it as needed instead of auditing the entire system before every fix.

## Current scope

- Required user journeys:
- Explicitly excluded features:

## Constraints

- Stack and supported versions:
- Repository/component layout:
- Language and design references:
- Data, authentication, and authorization requirements:
- Deployment target and operational constraints:
- Source material and assets, including access paths:

## Acceptance criteria

List system-level outcomes and constraints when useful. Specific bug/feature acceptance belongs in its request, issue, or task file; do not rewrite this brief for every change. Mark proposed new product criteria pending agreement.

## Decisions and open questions

Record confirmed decisions and their reasons. List material unknowns to resolve before the affected implementation. Put task sequencing and approval in a plan, and current progress in `STATE.md`.

## Future ideas

List deferred features. They inform compatible choices but do not authorize implementation or speculative frameworks.
