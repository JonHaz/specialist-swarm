"""
Create the coordinator agent that orchestrates the specialist swarm.

The coordinator's roster is the four specialists created by create_specialists.py.
The coordinator decides which specialists to consult, in what order, and how to
synthesise their outputs into the final deliverable.

Saves the coordinator's ID to .coordinator_id.

Usage:
    python3 create_coordinator.py                     # first build
    python3 create_coordinator.py --archive-existing  # replace the coordinator
"""

import argparse
import json
from pathlib import Path

from anthropic import Anthropic

from agent_state import add_rebuild_flags, guard
from config import model_config, require_api_key


COORDINATOR_ID_PATH = Path(".coordinator_id")


COORDINATOR_DESCRIPTION = (
    "Runs a full Deal Desk pass on an inbound RFP: reads the RFP, delegates to "
    "the pricing, legal, technical-fit, and competitive specialists in "
    "parallel, and synthesises their replies into a single branded proposal "
    "response saved as a Word document."
)


COORDINATOR_SYSTEM = """\
You are the Senior Partner running the Deal Desk. An inbound RFP has just
arrived. Your job is to orchestrate the specialists, synthesise their work,
and produce a single branded proposal response document.

# Your roster

You can call these specialists. Each carries its own skill — an authoritative
rule library for its domain — so take their outputs as the house position
rather than re-deriving them yourself:
- Pricing Specialist: commercial terms, discount bands, concessions
- Legal Reviewer: contract flags, severities, and counter-positions
- Technical Fit Specialist: capability fit, graded per requirement, honest
  about gaps
- Competitive Intel Analyst: who else is in the deal and how to position

# How to run a deal

1. Read the RFP yourself first. Note the customer, scope, and any obvious
   curveballs.

2. Delegate to ALL FOUR specialists in parallel. Each gets:
   - The full RFP text
   - A clear, narrow brief stating what you need from them
   - A deadline ("answer in one message, ~300 words")

3. Synthesise their outputs into a single proposal response. Follow the
   firm-voice skill for tone, section order, and how to phrase gaps and
   refusals — it is the house style and it overrides your own instincts about
   wording. In particular: state gaps plainly and early with the fix priced,
   and never round a capability figure up. The response should cover:
   - Executive summary (3 bullets)
   - Our understanding of the customer's need
   - Why we're the right fit (drawing on Technical Fit + Competitive Intel)
   - Commercial proposal (drawing on Pricing)
   - Contract approach (drawing on Legal)
   - Risks and how we mitigate them

4. Produce the final document as a Word document using the docx skill and
   save it to exactly this path:

       /mnt/session/outputs/proposal-response.docx

   This path is a hard requirement, not a preference. Only files under
   /mnt/session/outputs/ survive the session — anything written elsewhere in
   the container is discarded when the session ends, and a chat message is not
   a deliverable. Write the docx before you send your closing reply.

# How to talk to specialists

When delegating, be direct: "Pricing Specialist: for this RFP, recommend
terms. Include discount band and red-line concessions. Cite past-wins.json
where relevant."

When you receive a specialist's reply, accept it. Don't second-guess. If
you genuinely disagree, send the specialist a follow-up — but only if it
matters.

# Tone

Senior partner running a real deal. Confident, terse, decisive. You move
fast because the RFP deadline is real.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the Deal Desk coordinator agent.")
    args = add_rebuild_flags(parser).parse_args()
    api_key = require_api_key()

    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    # No default_headers: the SDK sets the managed-agents beta automatically for
    # client.beta.{agents,sessions,environments}.*.
    client = Anthropic(api_key=api_key)

    guard(COORDINATOR_ID_PATH, args, client)

    coordinator = client.beta.agents.create(
        name="Deal Desk Senior Partner",
        description=COORDINATOR_DESCRIPTION,
        model=model_config("coordinator"),
        system=COORDINATOR_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        # The coordinator writes the deliverable, so the document skill belongs
        # here rather than on any specialist. Anthropic's pre-built skills are
        # referenced by name; custom ones by the skill_id from the Skills API.
        skills=[{"type": "anthropic", "skill_id": "docx"}],
        multiagent={
            "type": "coordinator",
            "agents": [
                {"type": "agent", "id": agent_id}
                for agent_id in specialist_ids.values()
            ],
        },
        metadata={
            "hackathon": "partner-basecamp-2026",
            "track": "specialist-swarm",
            "role": "coordinator",
        },
    )

    COORDINATOR_ID_PATH.write_text(coordinator.id)
    print(f"Coordinator created: {coordinator.id}")
    print(f"Roster: {list(specialist_ids.keys())}")
    print("\nNext: python3 upload_skills.py, then python3 run_deal_desk.py")


if __name__ == "__main__":
    main()
