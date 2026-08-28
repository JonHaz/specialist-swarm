"""
Shared helpers for retrieving the files a session's agents wrote.

Two things about session outputs are easy to get wrong, so they live here once
rather than being re-derived in every caller:

1. Only files written to `/mnt/session/outputs/` are captured. A file written
   anywhere else in the container is lost when the session ends.
2. Session-scoped `files.list` needs BOTH beta headers. The SDK sets
   `files-api-2025-04-14` automatically on `client.beta.files.*`; the caller
   must add `managed-agents-2026-04-01` for the `scope_id` filter to work.
   That is why `betas=[...]` is passed explicitly below.

There is also a 1-3 second indexing lag between a session going idle and its
outputs becoming listable, so a single immediate call regularly returns an
empty list for a run that actually succeeded. Always go through
`list_session_files` rather than calling `files.list` directly.
"""

import time
from pathlib import Path


MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"

# The contract. Stated in the coordinator's system prompt and in the kickoff
# message; repeated here so the instruction side and the retrieval side cannot
# drift apart without this constant being touched too.
SESSION_OUTPUT_DIR = "/mnt/session/outputs"
DELIVERABLE_NAME = "proposal-response.docx"
DELIVERABLE_PATH = f"{SESSION_OUTPUT_DIR}/{DELIVERABLE_NAME}"

# Waits between list attempts. Three attempts total, ~5s of patience.
DEFAULT_BACKOFF_SECONDS = (2.0, 3.0)


def list_session_files(client, session_id, backoff=DEFAULT_BACKOFF_SECONDS):
    """List a session's output files, retrying past the indexing lag.

    Returns the first non-empty result, or [] once the retries are exhausted.
    Only an empty list is retried — an API error is a real error and is allowed
    to propagate immediately rather than being swallowed by the retry loop.
    """
    attempts = len(backoff) + 1
    for attempt in range(attempts):
        files = client.beta.files.list(
            scope_id=session_id,
            betas=[MANAGED_AGENTS_BETA],
        )
        if files.data:
            return list(files.data)
        if attempt < len(backoff):
            wait = backoff[attempt]
            print(
                f"  nothing indexed yet — retrying in {wait:.0f}s "
                f"(attempt {attempt + 2} of {attempts})"
            )
            time.sleep(wait)
    return []


def download_session_files(client, session_id, output_dir: Path):
    """Download every output file from a session. Returns the paths written."""
    files = list_session_files(client, session_id)
    output_dir.mkdir(exist_ok=True)

    written = []
    for f in files:
        out_path = output_dir / f.filename
        print(f"  {f.filename}  ->  {out_path}")
        client.beta.files.download(f.id).write_to_file(str(out_path))
        written.append(out_path)
    return written


def report_deliverable(written, expected=DELIVERABLE_NAME) -> bool:
    """Say plainly whether the required deliverable arrived.

    The output path is enforced by prompt text alone, so nothing at the API
    level stops the coordinator writing elsewhere or falling back to a chat
    message. Without this check an empty `outputs/` reads as a quiet success.
    Returns True when the deliverable is present.
    """
    names = [p.name for p in written]
    if expected in names:
        print(f"\nDeliverable present: {expected}")
        return True

    print(f"\nMISSING DELIVERABLE: expected {expected}")
    if names:
        print(f"  The session produced: {', '.join(names)}")
        print(f"  Files reached {SESSION_OUTPUT_DIR}/, but none is named {expected}.")
        print("  Rename it in the coordinator prompt, or update DELIVERABLE_NAME here.")
    else:
        print("  The session produced no retrievable files at all.")
        print("  Most likely the coordinator answered in chat instead of writing to")
        print(f"  {SESSION_OUTPUT_DIR}/, or the docx skill is not attached to it.")
        print("  Verify with: client.beta.agents.retrieve(<coordinator_id>).skills")
    return False
