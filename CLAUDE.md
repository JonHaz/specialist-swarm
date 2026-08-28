# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A 60-minute hackathon build (Partner Basecamp 2026, "Option 3 — Specialist Swarm") demonstrating the
Anthropic **Managed Agents multi-agent** API: one coordinator agent fans an inbound RFP out to four
specialist sub-agents in parallel, each with its own uploaded Skill, then synthesises their replies
into a single deliverable. The visible parallelism in the event stream is the demo.

Everything runs against the Anthropic cloud API — there is no local server, no test suite, no build
step, and no lint config. All Python files are standalone `main()` scripts run in sequence.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
```

The multi-agent API is in research preview; the workspace behind the key must be granted access.

## Run order (READ THIS — the README's order is incomplete)

```bash
python setup_environment.py      # writes .environment_id   <- README omits this; run_deal_desk.py hard-fails without it
python create_specialists.py     # writes .specialist_ids.json
python upload_skills.py          # reads .specialist_ids.json, writes .skill_ids.json
python create_coordinator.py     # reads .specialist_ids.json, writes .coordinator_id
python run_deal_desk.py          # reads .coordinator_id + .environment_id
```

`upload_skills.py` and `create_coordinator.py` both depend only on `.specialist_ids.json` and are
independent of each other, so their relative order does not matter. The README, the "Next:" prints at
the end of each script, and `run_deal_desk.py`'s error message each suggest a *different* order —
none of them mention `setup_environment.py`. The dependency chain above is the authoritative one.

Other entry points:

```bash
python download_deliverable.py                # re-pull files from .last_session_id
python download_deliverable.py sesn_01ABC...  # pull files from any older session
python stretch_critic_subagent.py             # stretch goal: adds a 5th agent + rewrites coordinator prompt
```

## Architecture: scripts are coupled by dot-files, not imports

The pipeline communicates through untracked state files written to the repo root. This is the single
most important thing to understand before changing anything:

| File | Written by | Read by |
| --- | --- | --- |
| `.environment_id` | `setup_environment.py` | `run_deal_desk.py` |
| `.specialist_ids.json` | `create_specialists.py` (also mutated by `stretch_critic_subagent.py`) | `upload_skills.py`, `create_coordinator.py`, `stretch_critic_subagent.py` |
| `.skill_ids.json` | `upload_skills.py` | nothing (record only) |
| `.coordinator_id` | `create_coordinator.py` | `run_deal_desk.py`, `stretch_critic_subagent.py` |
| `.last_session_id` | `run_deal_desk.py` | `download_deliverable.py` |

The one exception to the no-imports rule is `session_files.py`, a shared helper imported by
`run_deal_desk.py` and `download_deliverable.py`. It owns the session-output contract in one place:
the `/mnt/session/outputs/` path constant, the dual-beta-header `files.list` call, the retry that
absorbs the 1-3s output indexing lag, and `report_deliverable()`, which fails loudly when the
expected `.docx` is absent. Change the output path there, not in the callers.

Adding a specialist means touching three places: the `SPECIALISTS` list in `create_specialists.py`,
the `SKILL_TO_SPECIALIST` map in `upload_skills.py` (if it needs a skill), and the coordinator's
`COORDINATOR_SYSTEM` roster prose in `create_coordinator.py`. The roster the API sees is built from
`.specialist_ids.json` automatically, but the coordinator only knows *what each specialist is for*
from that hand-written prompt text — the two must be kept in sync manually.

## Rerunning: which scripts are idempotent

- **Safe to rerun:** `setup_environment.py` (short-circuits if `.environment_id` exists),
  `upload_skills.py` (reuses skills matched by `display_name`, skips already-attached ones — the
  Skills API rejects duplicate names, so this reuse is load-bearing).
- **NOT safe to rerun:** `create_specialists.py`, `create_coordinator.py`,
  `stretch_critic_subagent.py`. Each unconditionally calls `agents.create` and overwrites the ID
  file, orphaning the previous agents. Delete stale agents server-side rather than assuming a rerun
  is free.

## API conventions used here

- **Beta header is applied inconsistently.** `create_specialists.py`, `create_coordinator.py`, and
  `stretch_critic_subagent.py` construct the client with
  `default_headers={"anthropic-beta": "managed-agents-2026-04-01"}`. The others construct a bare
  `Anthropic()` and pass `betas=["managed-agents-2026-04-01"]` per-call — but only on
  `files.list`. When adding a call that needs the beta, follow whichever pattern the surrounding
  file already uses.
- **`agents.update` requires optimistic concurrency:** retrieve the agent first and pass
  `version=current.version`. See `upload_skills.py` and `stretch_critic_subagent.py`.
- **Model IDs are hardcoded per agent**, not centralised — Sonnet for the three deep specialists,
  Haiku for the cheap Competitive analyst, Opus for the coordinator and critic. Changing models
  means editing each script.
- **Skills are uploaded from directories** via `files_from_dir()`; each `skills/<name>/SKILL.md`
  needs YAML frontmatter with `name` and `description`. The uploaded `display_name` is derived as
  `skill_name.replace("-", " ").title()`.

## Skills vs. inlined context

The coordinator carries Anthropic's pre-built `docx` skill (`skills=[{"type": "anthropic",
"skill_id": "docx"}]` in `create_coordinator.py`) because it is the agent that writes the
deliverable. Pre-built skills are referenced by name; custom ones by `skill_id` from the Skills API.

Only three of the four specialists get an uploaded Skill (`pricing-playbook` → pricing,
`legal-checklist` → legal, `competitive-intel` → competitive). The **Technical Fit specialist has no
skill by design** — its knowledge base, `synthetic-data/product-overview.md`, is inlined into the
user message instead. `scenario-cards.md` lists `product-overview` as if it were a skill; it is not.

Relatedly, `run_deal_desk.py` **inlines** the RFP, `past-wins.json`, and `product-overview.md` as
text blocks in the user message. The README's claim that it "uploads the synthetic RFP as a file" is
stale — the Files API is only used on the way back out, to download deliverables the agents produced
in the session container.

## Scenario cards

`scenario-cards.md` offers three scenarios. **Only Card A (Deal Desk) is implemented.** Cards B (M&A
Diligence) and C (Hire-to-Onboard) require writing new `synthetic-data/` fixtures and rewriting the
`SPECIALISTS` roster and coordinator prompt from scratch.

## Repo hygiene note

There is no `.gitignore`. The state dot-files above and the generated `outputs/` directory are
untracked but visible to git — avoid committing agent/session IDs and generated deliverables.
