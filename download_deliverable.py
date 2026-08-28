"""
Download every file produced by a Deal Desk session.

By default reads the session ID from `.last_session_id` (written by
run_deal_desk.py). You can also pass the session ID as a CLI argument
to grab files from any older session.

Usage:
    python3 download_deliverable.py                       # last run
    python3 download_deliverable.py sesn_01ABC...         # specific session
"""

import sys
from pathlib import Path

from anthropic import Anthropic

from config import console_session_url, require_api_key
from session_files import download_session_files, report_deliverable


OUTPUT_DIR = Path("outputs")


def main() -> None:
    require_api_key()

    # Resolve session ID
    if len(sys.argv) > 1:
        session_id = sys.argv[1].strip()
    else:
        last = Path(".last_session_id")
        if not last.exists():
            raise SystemExit(
                "No session ID provided and `.last_session_id` not found.\n"
                "Usage: python3 download_deliverable.py <session_id>"
            )
        session_id = last.read_text().strip()

    client = Anthropic()

    print(f"Listing files for session {session_id}...")
    written = download_session_files(client, session_id, OUTPUT_DIR)

    if written:
        print(f"\nDownloaded {len(written)} file(s) to {OUTPUT_DIR}/")
    else:
        print("\nNo files found on that session.")
        print("Check the session in the Console:")
        print(f"  {console_session_url(session_id)}")
    report_deliverable(written)


if __name__ == "__main__":
    main()
