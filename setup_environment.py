"""
Create the cloud Environment that the Deal Desk session runs in.

Safe to run multiple times — if `.environment_id` already exists, it's reused.

Usage:
    python setup_environment.py
"""

from pathlib import Path

from anthropic import Anthropic

from config import require_api_key


def main() -> None:
    require_api_key()

    env_path = Path(".environment_id")
    if env_path.exists():
        existing = env_path.read_text().strip()
        print(f"Environment already exists: {existing}")
        print("(remove .environment_id if you want to provision a new one)")
        return

    client = Anthropic()
    environment = client.beta.environments.create(
        name="specialist-swarm-env",
        config={
            "type": "cloud",
            "networking": {"type": "unrestricted"},
        },
    )
    env_path.write_text(environment.id)
    print(f"Environment created: {environment.id}")


if __name__ == "__main__":
    main()
