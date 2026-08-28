"""
Create four specialist sub-agents for the Deal Desk swarm.

Each specialist gets:
- A narrow system prompt
- A description, which is how the coordinator decides whom to delegate to
- The agent toolset (file ops, web search, web fetch, bash)
- A skill that matches its domain (uploaded separately by upload_skills.py)

Saves the resulting agent IDs to .specialist_ids.json so create_coordinator.py
can reference them.

Usage:
    python3 create_specialists.py                     # first build
    python3 create_specialists.py --archive-existing  # replace the current roster
"""

import argparse
import json
from pathlib import Path

from anthropic import Anthropic

from agent_state import add_rebuild_flags, guard
from config import MODELS, require_api_key


SPECIALIST_IDS_PATH = Path(".specialist_ids.json")


# The coordinator picks delegates by reading each roster entry's name and
# description, so "description" is written for the coordinator, not for humans:
# what this specialist is good at, and what to hand it.
SPECIALISTS = [
    {
        "key": "pricing",
        "name": "Pricing Specialist",
        "description": (
            "Commercial terms for inbound RFPs. Give it the RFP text and the "
            "past-wins data; it returns a discount band, term and payment "
            "structure, which concessions to accept or refuse, and margin risks."
        ),
        "system": (
            "You are the Pricing Specialist in a Deal Desk. Your job is to "
            "recommend commercial terms for inbound RFPs.\n\n"
            "Inputs you'll receive:\n"
            "- The RFP text\n"
            "- The pricing-playbook skill (your authoritative pricing rules)\n"
            "- past-wins.json (recent comparable deals)\n\n"
            "Your output: a one-page commercial recommendation covering:\n"
            "1. List price + recommended discount band\n"
            "2. Term and payment structure\n"
            "3. Any commercial concessions you'd accept and which you'd refuse\n"
            "4. Risks to the margin\n\n"
            "Be specific about numbers. Cite the past-wins data when you use it."
        ),
    },
    {
        "key": "legal",
        "name": "Legal Reviewer",
        "description": (
            "Contract risk on inbound RFPs. Give it the RFP text; it returns "
            "every clause that conflicts with our standard negotiation "
            "positions, each with a recommended counter and a severity of "
            "blocker, negotiable, or acceptable."
        ),
        "system": (
            "You are the Legal Reviewer in a Deal Desk. Your job is to read "
            "an RFP and flag every clause that conflicts with our standard "
            "negotiation positions.\n\n"
            "Inputs you'll receive:\n"
            "- The RFP text\n"
            "- The legal-checklist skill (your authoritative position library)\n\n"
            "Your output: a structured list of flags, each with:\n"
            "1. The RFP requirement\n"
            "2. Why it conflicts with our standard\n"
            "3. Our recommended counter-position\n"
            "4. Severity: blocker / negotiable / acceptable\n\n"
            "Be precise. Don't flag boilerplate just because it's there — "
            "only call out things that genuinely deviate from our checklist."
        ),
    },
    {
        "key": "technical_fit",
        "name": "Technical Fit Specialist",
        "description": (
            "Product capability fit. Give it the RFP's technical requirements; "
            "it returns which we meet fully, partially, or not at all, an "
            "overall fit score, and the single biggest risk. It is briefed to "
            "be honest about gaps rather than claim universal fit."
        ),
        "system": (
            "You are the Technical Fit Specialist. You decide whether our "
            "product actually does what the RFP asks for.\n\n"
            "Inputs:\n"
            "- The RFP text\n"
            "- product-overview.md (the canonical capability map)\n\n"
            "Output: a structured fit assessment:\n"
            "1. Requirements we meet fully\n"
            "2. Requirements we meet partially (and what's missing)\n"
            "3. Requirements we don't meet at all\n"
            "4. Overall fit score: high / medium / low\n"
            "5. The single most important risk to flag to the coordinator"
        ),
    },
    {
        "key": "competitive",
        "name": "Competitive Intel Analyst",
        "description": (
            "Competitive positioning. Give it the RFP's scope and named "
            "vendors; it returns the most likely competitors, their strengths "
            "and weaknesses on this specific deal, our best positioning "
            "angles, and one trap to avoid. Fast and cheap — a battlecard "
            "lookup, not a deep analysis."
        ),
        "system": (
            "You are the Competitive Intel Analyst. You identify who else "
            "is likely competing for this RFP and how we should position.\n\n"
            "Inputs:\n"
            "- The RFP text\n"
            "- The competitive-intel skill (your battlecard library)\n\n"
            "Output:\n"
            "1. The 2-3 most likely competitors based on the RFP shape\n"
            "2. For each: their probable strengths and weaknesses on THIS deal\n"
            "3. Our two best positioning angles\n"
            "4. One trap to avoid"
        ),
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the four specialist sub-agents.")
    args = add_rebuild_flags(parser).parse_args()
    api_key = require_api_key()

    # No default_headers: the SDK sets the managed-agents beta automatically for
    # client.beta.{agents,sessions,environments}.*.
    client = Anthropic(api_key=api_key)

    guard(SPECIALIST_IDS_PATH, args, client)

    specialist_ids: dict[str, str] = {}
    for spec in SPECIALISTS:
        agent = client.beta.agents.create(
            name=spec["name"],
            description=spec["description"],
            model=MODELS[spec["key"]],
            system=spec["system"],
            tools=[{"type": "agent_toolset_20260401"}],
            metadata={
                "hackathon": "partner-basecamp-2026",
                "track": "specialist-swarm",
                "role": spec["key"],
            },
        )
        specialist_ids[spec["key"]] = agent.id
        print(f"  Created {spec['name']:32s} -> {agent.id}")

    SPECIALIST_IDS_PATH.write_text(json.dumps(specialist_ids, indent=2))
    print(f"\nSaved {len(specialist_ids)} specialist IDs to {SPECIALIST_IDS_PATH}")
    print("Next: python3 create_coordinator.py")


if __name__ == "__main__":
    main()
