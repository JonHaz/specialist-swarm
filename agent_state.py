"""
Guard the agent-ID state files against accidental overwrite.

`create_specialists.py`, `create_coordinator.py`, and `stretch_critic_subagent.py`
each called `agents.create` unconditionally and overwrote their ID file. A second
run therefore left the previous agents alive server-side with nothing pointing at
them. That is worse than it sounds: agents have no delete, only `archive`, and
archiving is permanent -- so the cleanup is manual and irreversible either way.

The guard makes the choice explicit rather than silent:

    (no flag)            refuse, and print what already exists
    --force              create new agents anyway, naming the orphans
    --archive-existing   archive the recorded agents first, then create

`setup_environment.py` and `upload_skills.py` do not use this: they are already
idempotent by reusing what their state file records.
"""

import argparse
import json
from pathlib import Path


def add_rebuild_flags(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach the two rebuild flags to a script's parser."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--force",
        action="store_true",
        help="create new agents even though a state file exists, orphaning the old ones",
    )
    group.add_argument(
        "--archive-existing",
        action="store_true",
        help="permanently archive the recorded agents, then create replacements",
    )
    return parser


def recorded_ids(path: Path) -> dict[str, str]:
    """Agent IDs a state file holds, as {label: agent_id}. Empty if absent."""
    if not path.exists():
        return {}
    raw = path.read_text().strip()
    if not raw:
        return {}
    if path.suffix == ".json":
        return json.loads(raw)
    return {path.name.lstrip(".").removesuffix("_id"): raw}


def guard(path: Path, args: argparse.Namespace, client) -> None:
    """Decide whether this script may create agents and overwrite `path`.

    Returns normally when it is safe to proceed; raises SystemExit otherwise.
    """
    ids = recorded_ids(path)
    if not ids:
        return

    listing = "\n".join(f"    {label:16s} {agent_id}" for label, agent_id in ids.items())

    if getattr(args, "archive_existing", False):
        print(f"Archiving the agents recorded in {path} (this is permanent):")
        for label, agent_id in ids.items():
            client.beta.agents.archive(agent_id)
            print(f"    archived {label:16s} {agent_id}")
        path.unlink()
        print()
        return

    if getattr(args, "force", False):
        print(f"--force: creating replacements. These agents are now orphaned:\n{listing}")
        print(
            "  Nothing points at them any more. Archive them in the Console if you\n"
            "  do not want them, or use --archive-existing next time to have this\n"
            "  script do it before creating.\n"
        )
        return

    raise SystemExit(
        f"{path} already exists:\n{listing}\n\n"
        "Re-running would create a second set of agents and overwrite this file,\n"
        "leaving the ones above orphaned. Pick one:\n"
        "  --archive-existing   archive those agents, then create replacements\n"
        "  --force              create replacements and keep the old ones\n"
        f"or delete {path} yourself if you have already cleaned up."
    )
