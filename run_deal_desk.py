"""
Run the Deal Desk swarm against the synthetic RFP.

Inlines the RFP + past-wins + product-overview into the user message (simpler
than Files API for hackathon-scale content). Streams events as they come in so
you can watch the parallel thread fan-out — this is the demo, narrate it live.

Saves the final transcript to outputs/.

Usage:
    python run_deal_desk.py
"""

import os
from pathlib import Path

from anthropic import Anthropic

from config import console_session_url
from session_files import (
    DELIVERABLE_PATH,
    download_session_files,
    report_deliverable,
)


RFP_PATH = Path("synthetic-data/rfp-acme-corp.md")
SUPPORTING_FILES = [
    Path("synthetic-data/past-wins.json"),
    Path("synthetic-data/product-overview.md"),
]
OUTPUT_DIR = Path("outputs")


def load_inputs_as_context() -> str:
    blocks = []
    for path in [RFP_PATH, *SUPPORTING_FILES]:
        if not path.exists():
            print(f"  WARNING: {path} missing — skipping")
            continue
        print(f"  including {path.name}")
        blocks.append(f"=====  DOCUMENT: {path.name}  =====\n{path.read_text()}")
    return "\n\n".join(blocks)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    if not Path(".coordinator_id").exists() or not Path(".environment_id").exists():
        raise SystemExit(
            "Missing .coordinator_id or .environment_id. Run "
            "create_specialists.py, upload_skills.py, then create_coordinator.py first."
        )

    coordinator_id = Path(".coordinator_id").read_text().strip()
    environment_id = Path(".environment_id").read_text().strip()

    client = Anthropic()

    print("Loading RFP + supporting docs...")
    context = load_inputs_as_context()

    print(f"\nStarting session against coordinator {coordinator_id}...")
    session = client.beta.sessions.create(
        agent=coordinator_id,
        environment_id=environment_id,
        title="Deal Desk — Acme Corp RFP",
    )
    Path(".last_session_id").write_text(session.id)

    # Print the trace view up front, not just at the end: if the run dies
    # mid-stream this link is the only way back to what the threads were doing.
    print(f"  watch it live: {console_session_url(session.id)}")

    user_message = (
        "An RFP has just landed. Please run the standard Deal Desk process:\n"
        "1. Read the RFP yourself.\n"
        "2. Delegate to all four specialists in parallel.\n"
        "3. Synthesise their replies.\n"
        "4. Produce the final proposal response as a Word document and save "
        f"it to {DELIVERABLE_PATH} — that exact path. Files written anywhere "
        "else are discarded when the session ends.\n\n"
        "Specialists have their own skills attached for their respective "
        "domains. Move fast — the RFP deadline is real.\n\n"
        f"{context}"
    )

    # Stream the events — this is the demo. Watch for parallel thread spawns.
    print("\n=== EVENT STREAM (this is the demo) ===\n")
    final_text_parts: list[str] = []

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": user_message}],
                }
            ],
        )
        for event in stream:
            t = event.type
            if t == "session.thread_created":
                print(f"  [thread spawned]   {event.agent_name}", flush=True)
            elif t == "session.thread_status_running":
                name = getattr(event, "agent_name", "?")
                print(f"  [thread running]   {name}", flush=True)
            elif t == "agent.thread_message_received":
                print(f"  [reply ←]          {event.from_agent_name}", flush=True)
            elif t == "agent.thread_message_sent":
                print(f"  [delegate →]       {event.to_agent_name}", flush=True)
            elif t == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        final_text_parts.append(block.text)
                        print(block.text, end="", flush=True)
            elif t == "agent.tool_use":
                print(f"\n  [tool: {getattr(event, 'name', '?')}]", flush=True)
            elif t == "agent.tool_result":
                # Only surface failures. Echoing every result would drown the
                # thread fan-out, and the fan-out is what the demo is for.
                # A failed write is otherwise invisible until outputs/ is empty.
                if getattr(event, "is_error", False):
                    name = getattr(event, "name", "?")
                    print(f"\n  [tool FAILED: {name}]", flush=True)
            elif t == "session.status_idle":
                print("\n\n[swarm finished]")
                break

    OUTPUT_DIR.mkdir(exist_ok=True)
    transcript_path = OUTPUT_DIR / "coordinator-transcript.txt"
    transcript_path.write_text("".join(final_text_parts))
    print(f"\nCoordinator transcript saved to {transcript_path}")

    # Pull every file the agents produced. Output files take 1-3s to index
    # after the session goes idle, so this retries rather than reporting an
    # empty result for a run that actually succeeded.
    print("\nDownloading deliverables from the session container...")
    written = download_session_files(client, session.id, OUTPUT_DIR)
    if written:
        print(f"\nDownloaded {len(written)} file(s) to {OUTPUT_DIR}/")
    report_deliverable(written)

    print(f"\nView the full session (including all sub-agent threads) at:")
    print(f"  {console_session_url(session.id)}")


if __name__ == "__main__":
    main()
