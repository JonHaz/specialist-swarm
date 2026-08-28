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

- **Never set the beta header by hand.** The SDK applies `managed-agents-2026-04-01` automatically
  to `client.beta.{agents,sessions,environments}.*`, so every script constructs a bare
  `Anthropic()`. The **one** place an explicit `betas=[...]` is required is the session-scoped
  `files.list(scope_id=...)` in `session_files.py`: it is a Files endpoint taking a Managed Agents
  parameter, so the SDK's automatic `files-api-2025-04-14` is not enough and the call needs both.
- **`agents.update` requires optimistic concurrency:** retrieve the agent first and pass
  `version=current.version`. See `upload_skills.py` and `stretch_critic_subagent.py`.
- **Model IDs and reasoning effort live in `config.py`**, never inline. `MODELS` maps a role key to
  a model ID and `model_config(role)` returns the `model=` argument for `agents.create` — a bare
  string, or `{"id", "effort"}` when `EFFORT` pins one for that role. Add a new agent by adding its
  role to `MODELS`, not by typing a model string into a script. Model IDs are used exactly as
  published and are never date-suffixed.
- **`effort` is agent configuration only.** Setting it inside a per-session `model` override is
  silently ignored — the session runs at the agent's effort. It has to be right at `agents.create`
  time. The coordinator is pinned to `xhigh`, which is the repo's single largest cost lever.
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

`.gitignore` covers `.env`, all five state dot-files, and `outputs/`. Those state files hold
server-side IDs personal to whoever ran the build chain: committing them collides across teammates
and a stale one silently points a run at somebody else's agents. Regenerate them by re-running the
chain rather than sharing them.
