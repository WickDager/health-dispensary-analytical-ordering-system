"""
Management command to import data from legacy HDAOS v2.x database.

Usage:
    python manage.py import_legacy --source=<connection_string> [--dry-run]

This command reads the legacy PostgreSQL database and migrates:
    - Users and their roles
    - Product catalog
    - Inventory lots with FEFO data
    - Historical order records
    - CRM accounts, contacts, and activities

Options:
    --source     Legacy database connection string (required)
    --dry-run    Validate and report without writing changes
    --batch-size Number of records to process per batch (default: 500)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Import data from legacy HDAOS v2.x database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            required=True,
            help="Legacy database connection string.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Validate and report without writing changes.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of records to process per batch.",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "import_legacy is not yet implemented. This is a stub."
            )
        )
        self.stdout.write(
            f"Would connect to: {options['source']} "
            f"(dry-run={options['dry_run']}, batch-size={options['batch_size']})"
        )
