#!/usr/bin/env python3
"""
Airtable Sync CLI

Usage:
    python scripts/sync_airtable.py            # Interactive menu
    python scripts/sync_airtable.py --db       # Sync database only
    python scripts/sync_airtable.py --images   # Download images only
    python scripts/sync_airtable.py --both     # Sync database + images
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add project root to path so we can import services
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

load_dotenv()

from services.sync_airtable import run_sync  # noqa: E402


def get_config():
    """Build config dict from environment variables."""
    return {
        "airtable_token": os.getenv("AIRTABLE_SECRET_TOKEN"),
        "airtable_base_id": os.getenv("AIRTABLE_BASE_ID"),
        "mysql_host": os.getenv("MYSQL_HOST", "localhost"),
        "mysql_user": os.getenv("MYSQL_USER"),
        "mysql_password": os.getenv("MYSQL_PASSWORD"),
        "mysql_database": os.getenv("MYSQL_DATABASE"),
        "use_ssh_tunnel": os.getenv("USE_SSH_TUNNEL", "false").lower() == "true",
        "ssh_host": os.getenv("SSH_HOST", "ssh.pythonanywhere.com"),
        "ssh_user": os.getenv("SSH_USER"),
        "ssh_password": os.getenv("SSH_PASSWORD"),
    }


def validate_config(config):
    """Validate required config values."""
    if not config["airtable_token"] or not config["airtable_base_id"]:
        raise RuntimeError(
            "AIRTABLE_SECRET_TOKEN and AIRTABLE_BASE_ID must be set")

    if not config["mysql_user"] or not config["mysql_password"] or not config["mysql_database"]:
        raise RuntimeError("MySQL credentials must be set in .env")

    if config["use_ssh_tunnel"]:
        if not config["ssh_user"] or not config["ssh_password"]:
            raise RuntimeError(
                "SSH_USER and SSH_PASSWORD must be set when USE_SSH_TUNNEL is true")


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
    parser = argparse.ArgumentParser(
        description="Sync Airtable data to MySQL and download images")
    parser.add_argument("--db", action="store_true",
                        help="Sync database only")
    parser.add_argument("--images", action="store_true",
                        help="Download images only")
    parser.add_argument("--both", action="store_true",
                        help="Sync database + download images")

    args = parser.parse_args()

    config = get_config()
    validate_config(config)

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
