"""
Preflight the built swarm without spending a run on it.

Every assertion here is one that used to be discovered halfway through a live
session -- an agent with no description that the coordinator therefore never
delegated to, a coordinator missing the docx skill that quietly emitted
markdown instead, a skill recorded in .skill_ids.json that was never actually
attached. Each of those cost a full fan-out to find out.

This checks the built state directly against the API. It creates nothing,
updates nothing, and starts no session, so it is safe to run as often as you
like. It stops at the first failure and says what to run to fix it.

Usage:
    python3 smoke_test.py
"""

import json
import sys
from pathlib import Path

from anthropic import Anthropic

from config import require_api_key
from upload_skills import COORDINATOR, SKILL_TO_AGENT


ENVIRONMENT_ID_PATH = Path(".environment_id")
SPECIALIST_IDS_PATH = Path(".specialist_ids.json")
COORDINATOR_ID_PATH = Path(".coordinator_id")
SKILL_IDS_PATH = Path(".skill_ids.json")

# Written by whom, so a failure can name the script that produces the file.
PRODUCED_BY = {
    ENVIRONMENT_ID_PATH: "python3 setup_environment.py",
    SPECIALIST_IDS_PATH: "python3 create_specialists.py",
    COORDINATOR_ID_PATH: "python3 create_coordinator.py",
    SKILL_IDS_PATH: "python3 upload_skills.py",
}

# The pre-built document skill the coordinator needs to produce the deliverable.
# Anthropic's pre-built skills are referenced by name, not by a skill_ prefix.
DOCX_SKILL_ID = "docx"


class CheckFailed(Exception):
    """A failed assertion, carrying a message the reader can act on."""


def fail(message: str) -> None:
    raise CheckFailed(message)


def skill_ids_on(agent) -> set[str]:
    """Every skill_id attached to an agent, pre-built and custom alike."""
    ids = set()
    for skill in agent.skills or []:
        entry = skill if isinstance(skill, dict) else skill.model_dump(exclude_none=True)
        if entry.get("skill_id"):
            ids.add(entry["skill_id"])
    return ids


def check_state_files(client: Anthropic, state: dict) -> None:
    """Every dot-file the chain writes exists."""
    for path, command in PRODUCED_BY.items():
        if not path.exists():
            fail(f"{path} is missing. Run: {command}")


def check_agents_retrieve(client: Anthropic, state: dict) -> None:
    """Every recorded agent ID still resolves, and carries a description.

    An agent with no description is the failure this repo is most likely to
    reintroduce: nothing errors, the roster still validates, and the
    coordinator simply stops picking that specialist because it has nothing to
    read but a name.
    """
    specialist_ids = json.loads(SPECIALIST_IDS_PATH.read_text())
    coordinator_id = COORDINATOR_ID_PATH.read_text().strip()

    agents = {}
    for key, agent_id in {**specialist_ids, COORDINATOR: coordinator_id}.items():
        try:
            agents[key] = client.beta.agents.retrieve(agent_id)
        except Exception as exc:
            fail(
                f"`{key}` ({agent_id}) does not resolve: {exc}\n"
                "  The recorded ID points at an archived or foreign agent. "
                "Rebuild with --archive-existing."
            )
        if not (agents[key].description or "").strip():
            fail(
                f"`{key}` ({agent_id}) has an empty description.\n"
                "  The coordinator picks delegates by reading each roster "
                "entry's name and description, so this agent will be skipped."
            )
    state["agents"] = agents


def check_roster(client: Anthropic, state: dict) -> None:
    """The coordinator's roster covers exactly the recorded specialists."""
    specialist_ids = json.loads(SPECIALIST_IDS_PATH.read_text())
    coordinator = state["agents"][COORDINATOR]

    multiagent = getattr(coordinator, "multiagent", None)
    roster_entries = getattr(multiagent, "agents", None) or []
    roster = {
        entry["id"] if isinstance(entry, dict) else entry.id
        for entry in roster_entries
    }
    expected = set(specialist_ids.values())

    missing = expected - roster
    extra = roster - expected
    if missing or extra:
        fail(
            "The coordinator's roster does not match .specialist_ids.json.\n"
            f"  recorded but not on the roster: {sorted(missing) or 'none'}\n"
            f"  on the roster but not recorded: {sorted(extra) or 'none'}\n"
            "  A specialist off the roster can never be delegated to. Rebuild "
            "the coordinator, or re-run stretch_critic_subagent.py."
        )


def check_skills(client: Anthropic, state: dict) -> None:
    """Every agent carries the skills it is supposed to carry."""
    agents = state["agents"]
    coordinator = agents[COORDINATOR]
    if DOCX_SKILL_ID not in skill_ids_on(coordinator):
        fail(
            "The coordinator does not carry the pre-built `docx` skill.\n"
            "  Without it the run produces markdown in the transcript and no "
            "deliverable. Rebuild the coordinator."
        )

    if not SKILL_IDS_PATH.exists():
        fail("`.skill_ids.json` is missing. Run: python3 upload_skills.py")
    records = json.loads(SKILL_IDS_PATH.read_text())

    for skill_name, target_key in SKILL_TO_AGENT.items():
        record = records.get(skill_name)
        if not record:
            fail(
                f"`{skill_name}` is not recorded in .skill_ids.json.\n"
                "  Run: python3 upload_skills.py"
            )
        skill_id = record["skill_id"] if isinstance(record, dict) else record

        agent = agents.get(target_key)
        if agent is None:
            fail(
                f"SKILL_TO_AGENT maps `{skill_name}` to `{target_key}`, which "
                "is not an agent this build created. Keep the map and "
                "create_specialists.py in sync."
            )
        if skill_id not in skill_ids_on(agent):
            fail(
                f"`{target_key}` ({agent.id}) is not carrying `{skill_name}` "
                f"({skill_id}).\n"
                "  The skill uploaded but never attached. Run: python3 "
                "upload_skills.py"
            )


CHECKS = [
    ("state files", check_state_files),
    ("agents resolve and are described", check_agents_retrieve),
    ("coordinator roster", check_roster),
    ("skill attachments", check_skills),
]


def main() -> None:
    require_api_key()
    client = Anthropic()

    # Checks share one dict so the expensive retrieve happens once and the
    # later checks read what it fetched.
    state: dict = {}
    for label, check in CHECKS:
        try:
            check(client, state)
        except CheckFailed as failure:
            print(f"FAIL  {label}")
            print("      " + str(failure).replace("\n", "\n      "))
            sys.exit(1)
        print(f"ok    {label}")

    print("\nAll preflight checks passed. Safe to run: python3 run_deal_desk.py")


if __name__ == "__main__":
    main()
