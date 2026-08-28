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
python3 setup_environment.py     # writes .environment_id
python3 create_specialists.py    # writes .specialist_ids.json
python3 create_coordinator.py    # reads .specialist_ids.json, writes .coordinator_id
python3 upload_skills.py         # reads BOTH ID files, writes .skill_ids.json
python3 run_deal_desk.py         # reads .coordinator_id + .environment_id
```

`upload_skills.py` must run **after** `create_coordinator.py`. It used to depend only on
`.specialist_ids.json`, but `firm-voice` attaches to the coordinator, so it now needs
`.coordinator_id` too and exits with the correct order if that file is missing.

Only `python3` is on PATH on some machines; the scripts are invoked that way throughout.

Other entry points:

```bash
python3 download_deliverable.py                # re-pull files from .last_session_id
python3 download_deliverable.py sesn_01ABC...  # pull files from any older session
python3 stretch_critic_subagent.py             # stretch goal: adds a 5th agent + rewrites coordinator prompt
```

## Architecture: scripts are coupled by dot-files, not imports

The pipeline communicates through untracked state files written to the repo root. This is the single
most important thing to understand before changing anything:

| File | Written by | Read by |
| --- | --- | --- |
| `.environment_id` | `setup_environment.py` | `run_deal_desk.py` |
| `.specialist_ids.json` | `create_specialists.py` (also mutated by `stretch_critic_subagent.py`) | `upload_skills.py`, `create_coordinator.py`, `stretch_critic_subagent.py` |
| `.skill_ids.json` | `upload_skills.py` | `upload_skills.py` (its own skill-identity record) |
| `.coordinator_id` | `create_coordinator.py` | `run_deal_desk.py`, `upload_skills.py`, `stretch_critic_subagent.py` |
| `.last_session_id` | `run_deal_desk.py` | `download_deliverable.py` |

The one exception to the no-imports rule is `session_files.py`, a shared helper imported by
`run_deal_desk.py` and `download_deliverable.py`. It owns the session-output contract in one place:
the `/mnt/session/outputs/` path constant, the dual-beta-header `files.list` call, the retry that
absorbs the 1-3s output indexing lag, and `report_deliverable()`, which fails loudly when the
expected `.docx` is absent. Change the output path there, not in the callers.

Adding a specialist means touching three places: the `SPECIALISTS` list in `create_specialists.py`,
the `SKILL_TO_AGENT` map in `upload_skills.py` (if it needs a skill), and the coordinator's
`COORDINATOR_SYSTEM` roster prose in `create_coordinator.py`. The roster the API sees is built from
`.specialist_ids.json` automatically, and the coordinator picks delegates by reading each entry's
`name` and `description` — so the `description` in `create_specialists.py` is functional, not
documentation. `COORDINATOR_SYSTEM`'s roster prose is separate and must be kept in sync by hand.

## Rerunning: which scripts are idempotent

- **Safe to rerun:** `setup_environment.py` (short-circuits if `.environment_id` exists),
  `upload_skills.py` (reuses the skill IDs recorded in `.skill_ids.json`, pushes a new version only
  when the bundle's hash changed, and skips already-attached agents).
- **Guarded:** `create_specialists.py` and `create_coordinator.py` refuse to run when their ID file
  exists, because a second `agents.create` would orphan the first set — and agents have no delete,
  only a permanent `archive`. `--archive-existing` archives then recreates; `--force` recreates and
  names the orphans it left behind. The shared logic is `agent_state.py`.
- **NOT guarded:** `stretch_critic_subagent.py` still appends a duplicate critic on every run.

## API conventions used here

- **`config.require_api_key()` is the only place the key is read.** It calls `load_dotenv()` at
  import, so a `.env` at the repo root works without an export, and it raises one consistent error.
  Six copies of this check had drifted into three different messages.
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
  needs YAML frontmatter with `name` and `description`.
- **A skill's identity is its `skill_id`, never its `display_name`.** Display names are *not*
  unique-enforced — creating two skills called "ZZ Probe" back to back both succeed. This workspace
  is shared with many other forks of this repo, so `upload_skills.py` resolves each skill from the
  ID in `.skill_ids.json` and appends `SKILL_NAMESPACE` (default: the OS username) to the display
  name for Console readability only. Do not reintroduce lookup-by-name: the previous version did
  that, and four of the five skills silently resolved to bundles uploaded by strangers three months
  earlier. Everything ran and the output looked plausible.
- **Skill content is pushed with `skills.versions.create(skill_id, files=...)`**, not by re-creating
  the skill. Agents attach with `{"type": "custom", "skill_id": ..., "version": "latest"}` so they
  pick the new version up without an agent update.

## Skills vs. inlined context

The coordinator carries Anthropic's pre-built `docx` skill (`skills=[{"type": "anthropic",
"skill_id": "docx"}]` in `create_coordinator.py`) because it is the agent that writes the
deliverable. Pre-built skills are referenced by name; custom ones by `skill_id` from the Skills API.

All four specialists carry an uploaded Skill (`pricing-playbook` → pricing, `legal-checklist` →
legal, `competitive-intel` → competitive, `technical-fit` → technical_fit), and the coordinator
additionally carries `firm-voice` because it is the agent that writes the customer-facing document.
`skills/technical-fit/` is a promotion of `synthetic-data/product-overview.md` into a real skill,
plus a fit-scoring rubric and a claim-discipline section; `product-overview.md` is kept as the
source fixture but is **no longer inlined**, since the only agent that needs it now loads it as a
skill.

`run_deal_desk.py` still **inlines** the RFP and `past-wins.json` as text blocks in the user message
— the coordinator quotes precedent deals directly during synthesis. The README's claim that it
"uploads the synthetic RFP as a file" is stale: the Files API is only used on the way back out, to
download deliverables the agents produced in the session container.

## Scenario cards

`scenario-cards.md` offers three scenarios. **Only Card A (Deal Desk) is implemented.** Cards B (M&A
Diligence) and C (Hire-to-Onboard) require writing new `synthetic-data/` fixtures and rewriting the
`SPECIALISTS` roster and coordinator prompt from scratch.

## Repo hygiene note

`.gitignore` covers `.env`, all five state dot-files, and `outputs/`. Those state files hold
server-side IDs personal to whoever ran the build chain: committing them collides across teammates
and a stale one silently points a run at somebody else's agents. Regenerate them by re-running the
chain rather than sharing them.
