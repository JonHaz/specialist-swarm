"""
Shared constants for the Deal Desk swarm.

Model IDs, the managed-agents beta version, and the Console workspace live here
so that changing a model is a one-line edit rather than a grep across six
scripts. Nothing in this module touches the API; the one piece of I/O is
load_dotenv(), which runs at import so that every script sees .env.
"""

import os

from dotenv import load_dotenv


# Read .env into the environment before anything else looks at it. An already
# exported ANTHROPIC_API_KEY wins -- load_dotenv does not override by default --
# so this adds a convenience without taking away the export you already use.
load_dotenv()


def require_api_key() -> str:
    """Return ANTHROPIC_API_KEY, or exit with instructions.

    Every entry point needs this, and six near-identical copies of the check had
    drifted into three different error messages. One copy, one message.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set.\n"
            "Either export it:\n"
            '    export ANTHROPIC_API_KEY="sk-ant-..."\n'
            "or put it in a .env file at the repo root (gitignored):\n"
            "    printf 'ANTHROPIC_API_KEY=sk-ant-...\\n' >> .env"
        )
    return key


# The managed-agents research-preview beta. The SDK sets this automatically for
# client.beta.{agents,sessions,environments}.*, but session-scoped
# files.list(scope_id=...) needs it passed explicitly — see session_files.py.
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


# Model per role. Keys match the "key" field in create_specialists.py SPECIALISTS
# and the role names used by the coordinator and critic.
#
# Model IDs are used exactly as published and are never date-suffixed. The
# previous `claude-haiku-4-5-20251001` pin was the odd one out and is corrected
# here.
MODELS = {
    # Synthesis quality is what the deliverable is judged on.
    "coordinator": "claude-opus-5",
    # The critic's whole value is pushing back on the coordinator, so it needs
    # to be at least as sharp as the thing it reviews.
    "critic": "claude-opus-5",
    # The three deep specialists. Sonnet 5 is both more capable and cheaper per
    # token than the Sonnet 4.6 these were previously pinned to.
    "pricing": "claude-sonnet-5",
    "legal": "claude-sonnet-5",
    "technical_fit": "claude-sonnet-5",
    # A battlecard lookup against a skill — the cheapest model is the right one.
    "competitive": "claude-haiku-4-5",
}


# Reasoning effort, per role. Only set what we mean to set: a role absent from
# this map is created without an `effort` field and runs at the model default.
#
# This is the single biggest cost lever in the repo. The API applied `xhigh` to
# the coordinator by default, which is a large multiplier on Opus for an agent
# that fans out to four specialists over a long RFP. It is pinned explicitly
# here — same behaviour as before, but visible and tunable. Drop the coordinator
# to "high" if you are re-running the demo repeatedly and the output holds up.
#
# Effort is agent configuration only: setting it in a per-session model override
# is silently ignored, so it has to be right at agents.create time.
EFFORT = {
    "coordinator": "xhigh",
    "critic": "high",
}


def model_config(role: str) -> dict | str:
    """Return the `model` argument for agents.create for a given role.

    Returns a bare model-ID string when no effort is pinned for the role, and a
    {"id": ..., "effort": ...} object when one is. Both forms are accepted by
    the API; the bare string keeps the diff quiet for roles we have no opinion
    about.
    """
    model_id = MODELS[role]
    effort = EFFORT.get(role)
    if effort is None:
        return model_id
    return {"id": model_id, "effort": effort}


# The Console workspace the API key belongs to. The session response does not
# carry it and the Console has no workspace-agnostic session route, so a link
# built with the wrong workspace lands on "Session not found" rather than
# redirecting. Override with ANTHROPIC_WORKSPACE_ID; "default" is correct only
# when the key belongs to the org's Default workspace.
WORKSPACE_ID = os.environ.get("ANTHROPIC_WORKSPACE_ID", "default")


def console_session_url(session_id: str) -> str:
    """Build the Console trace-view URL for a session."""
    return (
        f"https://platform.claude.com/workspaces/{WORKSPACE_ID}"
        f"/sessions/{session_id}"
    )
