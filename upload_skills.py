"""
Upload each skill in skills/ via the Skills API and attach it to the right
agent.

Uses `files_from_dir` (from anthropic.lib) to package the skill directory.
Each skill bundle must contain a SKILL.md at its root with proper YAML
frontmatter (`name` and `description`).

Most skills attach to a specialist. `firm-voice` attaches to the coordinator,
because the coordinator is the agent that writes the customer-facing document.
That makes this script depend on `.coordinator_id`, so it must run AFTER
create_coordinator.py -- see the run order in CLAUDE.md.

Identity is tracked by skill_id in .skill_ids.json, never by display_name.
See resolve_existing() for why that distinction is load-bearing.

Usage:
    python3 upload_skills.py
"""

import getpass
import hashlib
import json
import os
from pathlib import Path

from anthropic import Anthropic
from anthropic.lib import files_from_dir

from config import require_api_key


# Target key meaning "the coordinator", as opposed to a specialist key from
# .specialist_ids.json.
COORDINATOR = "coordinator"

# Map skill directory name -> the agent that should carry it.
SKILL_TO_AGENT = {
    "pricing-playbook": "pricing",
    "legal-checklist": "legal",
    "competitive-intel": "competitive",
    "technical-fit": "technical_fit",
    # The document voice belongs to whoever writes the document.
    "firm-voice": COORDINATOR,
}

SKILL_IDS_PATH = Path(".skill_ids.json")

# Skills live in a workspace shared with every other fork of this repo, and the
# Skills API does NOT enforce unique display names -- verified by creating two
# skills called "ZZ Probe" back to back, both of which succeeded. A display name
# is therefore a label, not an identifier. Namespacing it keeps the Console
# readable when several teammates build against one workspace; it is not what
# makes the lookup correct.
NAMESPACE = os.environ.get("SKILL_NAMESPACE") or getpass.getuser()


def resolve_agent_ids() -> dict[str, str]:
    """Build target-key -> agent-id from the state files written by the
    create_* scripts."""
    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    agent_ids: dict[str, str] = json.loads(specialist_ids_path.read_text())

    coordinator_path = Path(".coordinator_id")
    if not coordinator_path.exists():
        raise SystemExit(
            "Run create_coordinator.py first.\n"
            "`firm-voice` attaches to the coordinator, so this script now needs "
            "`.coordinator_id`. Correct order: setup_environment -> "
            "create_specialists -> create_coordinator -> upload_skills."
        )
    agent_ids[COORDINATOR] = coordinator_path.read_text().strip()

    missing = sorted(set(SKILL_TO_AGENT.values()) - set(agent_ids))
    if missing:
        raise SystemExit(
            f"No agent ID for target(s): {', '.join(missing)}.\n"
            "SKILL_TO_AGENT names a target that create_specialists.py did not "
            "create. Keep the two in sync."
        )
    return agent_ids


def load_records() -> dict[str, dict]:
    """Read .skill_ids.json, tolerating the older flat {name: id} shape."""
    if not SKILL_IDS_PATH.exists():
        return {}
    raw = json.loads(SKILL_IDS_PATH.read_text())
    records = {}
    for name, value in raw.items():
        if isinstance(value, str):
            records[name] = {"skill_id": value, "content_hash": None}
        else:
            records[name] = value
    return records


def content_hash(skill_dir: Path) -> str:
    """Fingerprint a skill bundle so an unchanged re-run pushes nothing."""
    digest = hashlib.sha256()
    for path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(skill_dir)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_existing(client: Anthropic, record: dict | None) -> str | None:
    """Return a still-live skill_id from our own records, or None.

    Deliberately does NOT search the workspace by display_name. An earlier
    version of this script did, and because display names are neither unique
    nor namespaced it silently adopted skills belonging to unrelated forks --
    four of this repo's five skills were resolving to bundles created three
    months earlier by someone else. The agents ran, the output looked
    plausible, and nothing failed. Only an ID we minted ourselves identifies
    our own skill.
    """
    if not record or not record.get("skill_id"):
        return None
    skill_id = record["skill_id"]
    try:
        client.beta.skills.retrieve(skill_id)
    except Exception:
        print(f"  recorded skill {skill_id} no longer exists -- creating a new one")
        return None
    return skill_id


def as_skill_dict(skill) -> dict:
    """Normalise an agent's existing skills entry to a plain dict.

    `agents.retrieve` returns pydantic models, not dicts, so calling .get() on
    them raises AttributeError. That never fired on a first run -- the list is
    empty -- but it crashed every re-run, which is exactly when this script is
    supposed to be safe.
    """
    if isinstance(skill, dict):
        return dict(skill)
    return skill.model_dump(exclude_none=True)


def main() -> None:
    require_api_key()

    agent_ids = resolve_agent_ids()
    previous = load_records()
    records: dict[str, dict] = {}

    client = Anthropic()
    print(f"Skill namespace: {NAMESPACE}\n")

    for skill_name, target_key in SKILL_TO_AGENT.items():
        skill_dir = Path("skills") / skill_name
        if not (skill_dir / "SKILL.md").exists():
            print(f"  Skipping {skill_name} -- no SKILL.md found")
            continue

        display_name = f"{skill_name.replace('-', ' ').title()} ({NAMESPACE})"
        digest = content_hash(skill_dir)
        prior = previous.get(skill_name)
        skill_id = resolve_existing(client, prior)

        # 1. Create the skill, or push a new version when the bundle changed.
        if skill_id is None:
            print(f"Uploading skill: {skill_name}...")
            skill = client.beta.skills.create(
                display_name=display_name,
                files=files_from_dir(str(skill_dir)),
            )
            skill_id = skill.id
            print(f"  -> {skill_id}")
        elif prior.get("content_hash") == digest:
            print(f"Unchanged: {skill_name} ({skill_id})")
        else:
            version = client.beta.skills.versions.create(
                skill_id, files=files_from_dir(str(skill_dir))
            )
            print(f"Updated {skill_name} ({skill_id}) -> {version.id}")

        records[skill_name] = {"skill_id": skill_id, "content_hash": digest}

        # 2. Attach to the matching agent by updating its skills array.
        agent_id = agent_ids[target_key]
        current = client.beta.agents.retrieve(agent_id)
        current_skills = [as_skill_dict(s) for s in (current.skills or [])]

        if any(s.get("skill_id") == skill_id for s in current_skills):
            print(f"  attached to `{target_key}` already ✓")
            continue

        print(f"  attaching to `{target_key}` ({agent_id})...")

        # Drop the id we previously recorded for this slot. Without this an
        # agent whose skill was recreated ends up carrying both the dead entry
        # and the new one.
        stale = (prior or {}).get("skill_id")
        kept = [s for s in current_skills if s.get("skill_id") != stale]
        if len(kept) != len(current_skills):
            print(f"  detaching superseded skill {stale}")

        # The skills array is replaced wholesale, so existing entries -- such as
        # the coordinator's pre-built `docx` -- must be carried through.
        client.beta.agents.update(
            agent_id,
            version=current.version,
            skills=kept + [{"type": "custom", "skill_id": skill_id, "version": "latest"}],
        )
        print("  attached ✓")

    SKILL_IDS_PATH.write_text(json.dumps(records, indent=2))
    print(f"\n{len(records)} skills uploaded and attached.")
    print("Next: python3 run_deal_desk.py")


if __name__ == "__main__":
    main()
