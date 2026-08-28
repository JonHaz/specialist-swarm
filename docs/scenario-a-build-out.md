# Scenario A (Deal Desk) — Build-Out Plan

**Status:** proposed — for team review
**Scope:** full build-out of Card A, including selected stretch goals
**Last updated:** 2026-08-28

---

## Context

`scenario-cards.md` calls Card A "the default scenario, fully wired in starter code," and the README's two-minute demo ends with *"open `outputs/proposal-response.docx`. Real document, branded, ready to send."*

That document cannot currently be produced. Three independent defects each block it on their own:

1. **No document skill is ever attached to anything.** `upload_skills.py` maps three custom skills to three *specialists*; the coordinator — the only agent that writes the deliverable — receives zero skills. The coordinator prompt hedges (`create_coordinator.py:60`, *"Use the BTS branding skill if available; otherwise use the standard docx skill"*) and the kickoff message hedges again (`run_deal_desk.py:78`, *"if you have access to a docx skill; otherwise output the response as structured markdown"*). Neither skill exists, so the markdown branch always wins.
2. **Nothing tells the agents where to write.** Session output files are only retrievable when written to `/mnt/session/outputs/`. No prompt in the repo names that path, so even a successful `.docx` would land somewhere the download step cannot see.
3. **The download races the indexer.** `run_deal_desk.py:121` lists session files immediately after the event loop breaks. There is a 1–3 second indexing lag between session-idle and files appearing; the script has no retry, so it prints *"no files found"* on runs that actually succeeded.

The scenario's *content* is in good shape and worth protecting — the RFP is deliberately loaded with traps that map cleanly onto each specialist skill (35% discount vs. a 20–25% band; MFN; Net 90; uncapped breach liability; no-notice audits ×4/yr; full IP assignment; subprocessor pre-approval). The gap is entirely in delivery and wiring.

**Intended outcome:** a teammate clones the fork, runs a documented sequence, and gets a branded Word document in `outputs/` — with all four specialists genuinely skill-backed, the parallel fan-out visible in the event stream, and a spend cap that makes the demo safe to re-run.

---

## Method

This plan was produced with an **evidence-first design discipline**. Four rules governed it, and they should govern execution too:

- **Cross-reference every claim about existing code before acting on it.** Every defect above is cited to a file and line. Two suspicions were *dropped* during this pass because the source disproved them: the `betas=["managed-agents-2026-04-01"]` argument on `files.list` looked like the wrong beta header but is explicitly the documented requirement for session-scoped listing; and `claude-opus-4-7` / `claude-sonnet-4-6` looked stale-to-the-point-of-invalid but are current, supported IDs.
- **Verify API surface against the authoritative reference, never recall.** Every API shape below (`skills=[{"type": "anthropic", "skill_id": "docx"}]`, the roster `description` requirement, the budget object, the `/mnt/session/outputs/` contract) was checked against the current managed-agents reference rather than assumed.
- **Turn fuzzy adjectives into operational numbers.** "Fast," "parallel," and "branded" are not acceptance criteria. Each workstream below states a check that passes or fails.
- **Prefer deterministic gates over judgement.** Where a property can be asserted by a script instead of eyeballed, it is (Workstream 7).

For the two new skills, the design follows a standard skill anatomy: classify the shape first (both are **reference/analysis** skills — they supply a rule library the agent reasons against, they do not generate the deliverable), then write a trigger-rich frontmatter description, then define the eval shape before the body.

---

## Current state: promised vs. actual

| Promise | Reality | Evidence |
| --- | --- | --- |
| Branded `.docx` in `outputs/` | Markdown text only | no skill on coordinator; `create_coordinator.py:60` |
| "Each specialist with its own skills" | 3 of 4 have a skill | `upload_skills.py` `SKILL_TO_SPECIALIST` |
| Technical Fit uses a `product-overview` skill | No such skill exists; file is inlined | `scenario-cards.md` Card A vs. `skills/` |
| Coordinator picks specialists from a roster | Roster carries no `description` fields | `create_specialists.py:114-118` |
| Clone → run works | Fails: `.environment_id` missing | `setup_environment.py` absent from README steps |
| Deliverables download | Races a 1–3s index lag; no retry | `run_deal_desk.py:121` |
| Console link to watch the session | Wrong URL shape → "Session not found" | `run_deal_desk.py:139`, `download_deliverable.py:57` |

---

## Workstreams

Seven workstreams. **1, 2, and 3 are independent and can run in parallel.** 4 depends on 2. 5–7 depend on 1–3 landing first.

### WS1 — API correctness and model policy
*Owner: ___ · ~1 hour · no dependencies*

- **Add `description` to every agent.** The coordinator selects delegates by reading each roster entry's `name` **and** `description`; today every `description` is absent (`create_specialists.py:114`, `create_coordinator.py:89`). Write these for the coordinator to read — say what the specialist is good at and what to hand it, e.g. *"Commercial terms for inbound RFPs. Give it the RFP text and past-wins data; it returns discount band, payment structure, and red-line concessions."* This is the single highest-leverage fix for delegation quality.
- **Centralise model IDs** in a new `config.py` and upgrade: coordinator and critic → `claude-opus-5`; Pricing, Legal, Technical Fit → `claude-sonnet-5`; Competitive analyst → `claude-haiku-4-5`. Drop the date suffix on the Haiku pin (`create_specialists.py:85`) — model IDs are used exactly as published and never date-suffixed. Sonnet 5 is both more capable and cheaper per token than the Sonnet 4.6 currently pinned.
- **Raise the SDK floor.** `requirements.txt:1` pins `anthropic>=0.40.0`, but session-scoped `files.list(scope_id=...)` requires `>=0.92.0`. A clean install honouring the current floor can produce an SDK that does not type `scope_id`.
- **Drop the redundant beta header.** `default_headers={"anthropic-beta": "managed-agents-2026-04-01"}` in `create_specialists.py`, `create_coordinator.py`, and `stretch_critic_subagent.py` is set automatically by the SDK for `client.beta.{agents,sessions,environments}.*`. Removing it also removes the inconsistency flagged in `CLAUDE.md`. Keep the explicit `betas=[...]` on `files.list` — that one **is** required.
- **Fix the Console URL** in both places to `https://platform.claude.com/workspaces/{workspace}/sessions/{session_id}`, sourcing the workspace ID from config.

**Passes when:** all five agents create cleanly with non-empty descriptions; `python -c "import config; print(config.MODELS)"` is the only place model strings appear.

### WS2 — The deliverable: docx skill + output-path contract
*Owner: ___ · ~1 hour · no dependencies · **highest priority***

- **Attach Anthropic's pre-built `docx` skill to the coordinator**, alongside the firm-voice skill from WS3:
  ```python
  skills=[{"type": "anthropic", "skill_id": "docx"},
          {"type": "custom", "skill_id": firm_voice_id, "version": "latest"}]
  ```
  Pre-built skills are referenced by name (`docx`, `pptx`, `xlsx`, `pdf`); custom skills by `skill_id`. Max 20 per agent.
- **Make the output path an explicit contract.** State `/mnt/session/outputs/proposal-response.docx` in the coordinator's system prompt *and* in the kickoff message. Threads share a filesystem but not conversation history, so any path a subagent must use has to be written into its brief.
- **Remove both "if available / otherwise markdown" hedges** (`create_coordinator.py:60`, `run_deal_desk.py:78`). Once the skill is genuinely attached, the fallback only invites the model to take the easy path. The docx becomes the required deliverable.
- **Add retry to the download.** Poll `files.list` up to three times with a ~2s backoff before reporting an empty result. Apply to both `run_deal_desk.py` and `download_deliverable.py`.

**Passes when:** `outputs/proposal-response.docx` exists after a run, opens in Word, and carries the firm's heading/colour styling.

### WS3 — Complete the specialist roster: two new skills
*Owner: ___ · ~1.5 hours · no dependencies*

Both are **reference/analysis** skills: a rule library the specialist reasons against, matching the shape of the three existing skills. Follow `skills/legal-checklist/SKILL.md` as the structural model — numbered rules, an explicit our-standard/common-deviations pattern, and a closing "how to format your output" section.

**3a. `skills/technical-fit/SKILL.md`** — closes the Card A inconsistency where a `product-overview` skill is promised but never existed. Promote `synthetic-data/product-overview.md` into a real skill so all four specialists are skill-backed and the capability map stops consuming context on every run. Must preserve the honest **"Where we're WEAK"** section — it is what makes the fit assessment credible, and it is what lets the specialist correctly flag the Acme real-time and Power BI questions. Add a fit-scoring rubric (full / partial / none, then high / medium / low overall) so output is comparable across runs.

**3b. `skills/firm-voice/SKILL.md`** — a clearly-marked **placeholder** voice, plus a short "make it yours" section so a teammate can swap in their own firm's positioning without touching the pipeline. Ships as a transformation-led template (confident, business-case-anchored, "what this means for you"). Keeps the fork public-safe while making stretch goal S1 a one-file change.

For each skill, write the frontmatter `description` with explicit trigger phrases — that string is the whole basis on which the model decides to load the skill. Then extend `SKILL_TO_SPECIALIST` in `upload_skills.py` (`technical-fit` → `technical_fit`) and attach `firm-voice` to the coordinator rather than a specialist.

**Passes when:** all five agents report a non-empty `skills` array on retrieve; a run visibly cites the capability map and the weak-list.

### WS4 — Repo hygiene and the documented path
*Owner: ___ · ~30 min · depends on WS2*

- **Add `.gitignore`** for `.environment_id`, `.specialist_ids.json`, `.coordinator_id`, `.skill_ids.json`, `.last_session_id`, `outputs/`. Today none of these are ignored; with several teammates on one fork, everyone's agent IDs collide in every commit.
- **Fix the run order in the README.** `setup_environment.py` is missing from the core build steps entirely, so a fresh clone fails at `run_deal_desk.py`. The README, each script's own "Next:" print, and the error text in `run_deal_desk.py:44` currently give three mutually inconsistent orders. Correct chain: `setup_environment` → `create_specialists` → (`upload_skills` ‖ `create_coordinator`) → `run_deal_desk`.
- **Make the create scripts idempotent** — or at minimum, refuse to run when the ID file already exists and point at a `--force` flag. `create_specialists.py` and `create_coordinator.py` unconditionally call `agents.create` and overwrite their ID files, orphaning the previous agents. `setup_environment.py` and `upload_skills.py` already do this correctly; copy their pattern.
- **Correct `scenario-cards.md`** to list Technical Fit's skill as `technical-fit` once WS3 lands.

**Passes when:** a fresh clone on a second machine reaches a `.docx` following only the README.

### WS5 — Critic sub-agent
*Owner: ___ · ~30 min · depends on WS1*

`stretch_critic_subagent.py` already exists and is close to correct. Bring it in line: add the `description` field, source its model from `config.py`, and note in the README that it must run **after** `create_coordinator.py` and that re-running it appends a duplicate critic to the roster each time.

One caveat to document: the roster limit is 1–20 entries with **one level of delegation only** — the critic cannot itself carry a `multiagent` roster, or the update fails validation.

**Passes when:** the event stream shows a `Deal Desk Critic` thread and the coordinator's draft changes in response to a REVISE verdict.

### WS6 — Make the parallelism visible
*Owner: ___ · ~30 min · depends on WS1*

The README stakes the demo on visible parallelism (*"the visible parallelism IS the demo"*). Two changes make it reliable rather than incidental:

- **Instruct an explicit single-message fan-out** in the coordinator prompt (stretch goal S4): delegate to all four specialists in one message, do not wait between them.
- **Fix the event-loop break condition.** `run_deal_desk.py:110` breaks on bare `session.status_idle` without inspecting `stop_reason`. It should continue on `requires_action` (a specialist awaiting a tool confirmation) and treat `budget_reached` as a distinct, non-terminal pause. As written, a single confirmation prompt ends the run early and silently.

Worth knowing before anyone tries to stream specialist text to a second monitor: **live text previews are thread-scoped and never cross-post to the session stream**, and a subagent's report to its coordinator rides `agent.thread_message_sent`, which is never previewed. Watching a specialist think live requires opening that thread's own stream. The current session-level view — thread spawns, running, replies flowing back — is the right demo surface and already works.

**Passes when:** four `session.thread_created` events appear within ~5 seconds of each other.

### WS7 — Session spend cap and smoke test
*Owner: ___ · ~45 min · depends on WS1–WS3*

- **Add a session budget** to `run_deal_desk.py`, defaulting to roughly $10 and overridable by env var:
  ```python
  budget={"type": "limit", "max_list_cost": {"amount": "1000", "currency": "USD"}}
  ```
  Amount is in **minor units as an integer string** — `"1000"` is $10.00; decimal forms like `"10.00"` are rejected. One cap is shared across all threads. It is **create-only** and removal is one-way, so set it deliberately. This matters more than it looks: five agents on Opus/Sonnet fanning out over a long RFP is the demo teammates will re-run repeatedly, and stretch goal S10 explicitly warns against running unbounded.
- **Add `smoke_test.py`** — a deterministic preflight that asserts, without burning a full run: every ID file exists; every agent retrieves successfully; every agent has a non-empty `description`; the coordinator's roster length matches `.specialist_ids.json`; the coordinator carries the `docx` skill; every specialist carries its mapped skill. Exit non-zero with a specific message on the first failure.

**Passes when:** `python smoke_test.py` exits 0 on a correctly built environment and fails loudly with an actionable message on each seeded defect.

---

## Verification

End-to-end, in order:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
python setup_environment.py
python create_specialists.py
python upload_skills.py
python create_coordinator.py
python stretch_critic_subagent.py   # optional, WS5
python smoke_test.py                # must exit 0 before spending on a run
python run_deal_desk.py
```

Acceptance checks, in priority order:

1. `outputs/proposal-response.docx` exists and opens in Word with firm styling. *(The demo fails without this — everything else is secondary.)*
2. Four specialist threads spawn within ~5 seconds of each other in the event stream.
3. The proposal correctly flags the RFP's planted traps — 35% discount against a 20–25% band, MFN, Net 90, uncapped breach liability, no-notice audits, full IP assignment.
4. The Technical Fit section is honest rather than claiming universal fit. Specifically it should surface the two checkable gaps: the RFP's 99.99% SLA demand against a 99.95% standard tier (99.99% is a paid add-on requiring multi-region active-active), and the 80k events/sec + real-time ask against ~250ms–1s streaming latency. Power BI is a *strength* here — a dedicated DirectQuery adapter — and the section should say so; the Microsoft-stack gap is the absent Power Apps connector.
5. The Console URL printed at the end actually resolves to the session.
6. Re-running `create_specialists.py` does not silently orphan the previous roster.
7. `python download_deliverable.py` re-fetches the same artifacts from `.last_session_id`.

Run once end-to-end against the unmodified upstream first, and keep that transcript. It is the before-shot for the demo, and it is the only way to prove the delivery gap was real rather than a misconfiguration on one machine.

---

## Suggested sequencing for a team

| Wave | Workstreams | Why |
| --- | --- | --- |
| 1 | WS1, WS2, WS3 in parallel | Independent; WS2 unblocks the demo's punchline |
| 2 | WS4 (needs WS2), WS5, WS6 | Hygiene and demo polish |
| 3 | WS7 | Needs the full roster to assert against |

WS2 is the one to staff first. Everything else improves a demo that WS2 makes possible at all.

---

## Decisions already made

- **All work stays on the fork.** No upstream PR to `rosscrooke/specialist-swarm` is planned. Commit freely against `JonHaz/specialist-swarm` and keep the branch history readable for teammates rather than for upstream review.
- **Workspace access is confirmed.** The API key in use has multi-agent research-preview access, so WS1 is not gated on an access request. Teammates using their own keys should confirm the same before starting.
- **Cards B and C are out of scope.** They stay unimplemented. Both would need new `synthetic-data/` fixtures and a rewritten specialist roster; nothing in this plan should be shaped around them.

## Committing this plan

Land the plan itself before any code changes, so teammates can pick workstreams while the first fixes are still in flight:

- Branch: `docs/scenario-a-plan`
- Path: `docs/scenario-a-build-out.md`
- Fill in the `Owner: ___` slots either in the commit or in the PR description.

Nothing gets pushed without a check-in first.
