#!/usr/bin/env python3
"""
Airtable Sync CLI

Usage:
    python scripts/sync_airtable.py            # Interactive menu
    python scripts/sync_airtable.py --db       # Sync database only
    python scripts/sync_airtable.py --images   # Download images only
    python scripts/sync_airtable.py --both     # Sync database + images
"""

import argparse
import os
import sys
from pathlib import Path

# Setup path for local imports (parent of scripts/)
_root = Path(__file__).parent.parent
sys.path.append(str(_root))
os.chdir(_root)


def get_airtable_config():
    """Build Airtable-specific config."""
    return {
        "airtable_token": os.getenv("AIRTABLE_SECRET_TOKEN"),
        "airtable_base_id": os.getenv("AIRTABLE_BASE_ID"),
        # We still need these for run_sync which is not yet fully ORM-based
        "mysql_host": os.getenv("MYSQL_HOST", "localhost"),
        "mysql_user": os.getenv("MYSQL_USER"),
        "mysql_password": os.getenv("MYSQL_PASSWORD"),
        "mysql_database": os.getenv("MYSQL_DATABASE"),
        "use_ssh_tunnel": os.getenv("USE_SSH_TUNNEL", "false").lower() == "true",
    }


def validate_airtable_config(config):
    """Validate required Airtable values."""
    if not config["airtable_token"] or not config["airtable_base_id"]:
        raise RuntimeError("AIRTABLE_SECRET_TOKEN and AIRTABLE_BASE_ID must be set")


def interactive_menu():
    """Show interactive menu and return (sync_db, sync_images)."""
    print("\n" + "=" * 40)
    print("  Airtable Sync")
    print("=" * 40)
    print("  1. Sync database only")
    print("  2. Download images only")
    print("  3. Sync database + images")
    print("  q. Quit")
    print("=" * 40)

    while True:
        choice = input("\nChoose an option: ").strip().lower()
        if choice == "1":
            return True, False
        elif choice == "2":
            return False, True
        elif choice == "3":
            return True, True
        elif choice == "q":
            print("Bye!")
            sys.exit(0)
        else:
            print("Invalid choice, try again.")


def main():
    # IMPORTS LOCAUX pour éviter que Ruff ne les déplace et ne casse le sys.path
    from services.sync_airtable import run_sync
    from utils.scripts_helper import build_minimal_app

    parser = argparse.ArgumentParser(description="Sync Airtable data to MySQL and download images")
    parser.add_argument("--db", action="store_true", help="Sync database only")
    parser.add_argument("--images", action="store_true", help="Download images only")
    parser.add_argument("--both", action="store_true", help="Sync database + download images")

    args = parser.parse_args()

    # Initialize App & Tunnel
    app, tunnel = build_minimal_app()

    with app.app_context():
        config = get_airtable_config()
        validate_airtable_config(config)

        # Determine mode
        if args.both:
            sync_db, sync_images = True, True
        elif args.db:
            sync_db, sync_images = True, False
        elif args.images:
            sync_db, sync_images = False, True
        else:
            # No argument → interactive menu
            sync_db, sync_images = interactive_menu()

        # Summary
        modes = []
        if sync_db:
            modes.append("Database")
        if sync_images:
            modes.append("Images")

        print(f"\n🚀 Starting sync: {' + '.join(modes)}")
        print("=" * 60)

        run_sync(config, sync_db=sync_db, sync_images=sync_images)

    print("\n" + "=" * 60)
    print("✅ Sync completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
