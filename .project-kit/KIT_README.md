# Installed software-development kit

Start with [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) and [executable examples](USAGE_EXAMPLES.txt). Shared [working agreements](AGENTS.md) cover efficient context, planning agreement, verification, handoffs, report-first final review, and explicit commit authorization. Existing instruction conflicts must be reconciled before relying on new rules.

Context/templates: [project brief](PROJECT_BRIEF.md), [state](STATE.md), [tasks](tasks/TEMPLATE.md), [plans](plans/TEMPLATE.md), [multi-repo guidance](MULTI_REPO.md), [repo instruction template](multi-repo/REPOSITORY_AGENTS.md), [Cursor compatibility](CURSOR_COMPATIBILITY.md).

Tools: [usage collector](usage/README.md), [Git manager](multi-git/README.md), [Git agent guide](multi-git/AGENT_GUIDE.md), [database environments/privacy](DATABASES.md), [optional configuration](OPTIONAL_CONFIG.md), [initializer](INIT_README.md). Each included tool has tests; application behavior and deployment require their own project-specific verification. No model/DB/service/key is required for the initializer or local usage/Git tools.

Global preferences may be maintained separately, but this kit is self-contained and does not edit global configuration. Parent instructions are not automatically loaded inside independent Git roots: read the repo routing files explicitly. Keep shared context in durable/versioned storage; if a repo is cloned alone, make its shared context accessible. Avoid copying runtime ledgers, backups or secrets to another project.
