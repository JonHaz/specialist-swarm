"""
Stretch: add a Critic sub-agent to the coordinator's roster.

The critic's job is to review the coordinator's draft before it goes out.
It must produce one of three verdicts:
- "ship it" (with a brief why)
- "revise" (with specific revisions)
- "stop" (with reason — e.g., we shouldn't pursue this deal)

This script creates the critic agent, adds it to the coordinator's roster, and
appends critic instructions to the coordinator's system prompt.

Run it AFTER create_coordinator.py — it reads `.coordinator_id` and mutates the
coordinator in place.

A critic is a plain roster entry, so it inherits the roster's constraints: 1–20
entries, and **one level of delegation only**. The critic cannot itself carry a
`multiagent` roster; adding one fails validation.

Usage:
    python3 stretch_critic_subagent.py                     # first run
    python3 stretch_critic_subagent.py --archive-existing  # replace the critic
"""

import argparse
import json
from pathlib import Path

from anthropic import Anthropic

from agent_state import add_rebuild_flags
from config import model_config, require_api_key


SPECIALIST_IDS_PATH = Path(".specialist_ids.json")
COORDINATOR_ID_PATH = Path(".coordinator_id")

# Sentinel for the block this script appends to the coordinator's system prompt.
# Without it, a second run appended the instructions again, so the coordinator
# read two copies of a rule about consulting one critic.
CRITIC_BLOCK_HEADING = "# Critic"

CRITIC_DESCRIPTION = (
    "Adversarial reviewer for a finished proposal draft. Give it the draft and "
    "the RFP; it returns one verdict — SHIP IT, REVISE (with up to five "
    "specific fixes), or STOP (with the reason not to bid). Consult it after "
    "synthesis and before writing the document, never instead of a specialist."
)

CRITIC_SYSTEM = """\
You are the Deal Desk Critic. You don't write proposals. You review them.

When the coordinator asks for your review, you'll receive:
- The draft proposal
- The RFP (for context)

Your job: deliver one of three verdicts.

1. **SHIP IT** — the proposal is solid, with at most cosmetic suggestions.
2. **REVISE** — specific issues that need fixing. List them tersely. No more
   than 5 issues; if there are more, the proposal isn't ready.
3. **STOP** — we shouldn't pursue this deal. Reasons might include: terms
   we can't deliver, mismatched scale, regulatory issues, strategic conflict.

Be sceptical. Your value to the coordinator is that you push back. A senior
partner who never gets pushback gets sloppy.

Lead your reply with: VERDICT: SHIP IT / REVISE / STOP.
"""

CRITIC_BLOCK = f"""

{CRITIC_BLOCK_HEADING}

Before producing the final document, send your draft to the Deal Desk Critic.
The Critic will reply with one of: SHIP IT, REVISE, or STOP.
- If SHIP IT: produce the final docx.
- If REVISE: address the issues and re-submit to the Critic. Repeat at most
  twice.
- If STOP: report to the user with the Critic's reasoning. Do NOT produce the
  final docx.
"""


def as_entry(entry) -> dict:
    """Normalise a roster entry to a plain dict.

    `agents.retrieve` returns BetaManagedAgentsAgentReference models. The
    previous version built the new roster as `list(models) + [dict]`, mixing
    two shapes in one array.
    """
    if isinstance(entry, dict):
        return dict(entry)
    return entry.model_dump(exclude_none=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a Critic sub-agent to the roster.")
    args = add_rebuild_flags(parser).parse_args()
    api_key = require_api_key()

    if not COORDINATOR_ID_PATH.exists() or not SPECIALIST_IDS_PATH.exists():
        raise SystemExit(
            "Run create_specialists.py and create_coordinator.py first — this "
            "script mutates an existing coordinator."
        )

    coordinator_id = COORDINATOR_ID_PATH.read_text().strip()
    specialist_ids = json.loads(SPECIALIST_IDS_PATH.read_text())

    # No default_headers: the SDK sets the managed-agents beta automatically for
    # client.beta.{agents,sessions,environments}.*.
    client = Anthropic(api_key=api_key)

    # A critic already recorded means this script has run before. Appending a
    # second one is never the intent, so make the choice explicit.
    previous = specialist_ids.get("critic")
    if previous:
        if args.archive_existing:
            client.beta.agents.archive(previous)
            print(f"Archived the previous critic: {previous}")
        elif args.force:
            print(f"--force: replacing critic {previous}. It is now orphaned.")
        else:
            raise SystemExit(
                f"A critic is already recorded: {previous}\n\n"
                "Re-running would add a SECOND critic to the roster and append the\n"
                "critic instructions to the coordinator's system prompt again.\n"
                "  --archive-existing   archive that critic, then create a replacement\n"
                "  --force              create a replacement and keep the old one"
            )

    critic = client.beta.agents.create(
        name="Deal Desk Critic",
        description=CRITIC_DESCRIPTION,
        model=model_config("critic"),
        system=CRITIC_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        metadata={
            "hackathon": "partner-basecamp-2026",
            "track": "specialist-swarm",
            "role": "critic",
        },
    )
    print(f"Critic created: {critic.id}")

    specialist_ids["critic"] = critic.id
    SPECIALIST_IDS_PATH.write_text(json.dumps(specialist_ids, indent=2))

    coordinator = client.beta.agents.retrieve(coordinator_id)

    # Replace, don't append: drop any entry for the critic we are superseding,
    # then add the new one.
    roster = [
        entry
        for entry in (as_entry(e) for e in coordinator.multiagent.agents)
        if entry.get("id") not in {previous, critic.id}
    ]
    roster.append({"type": "agent", "id": critic.id})

    if CRITIC_BLOCK_HEADING in coordinator.system:
        system = coordinator.system
        print("Coordinator prompt already carries the critic block — leaving it.")
    else:
        system = coordinator.system + CRITIC_BLOCK

    client.beta.agents.update(
        coordinator_id,
        version=coordinator.version,
        system=system,
        multiagent={"type": "coordinator", "agents": roster},
    )

    print(f"Coordinator roster updated — {len(roster)} agents, critic included.")
    print("Next: python3 run_deal_desk.py to see the critic in action.")


if __name__ == "__main__":
    main()
