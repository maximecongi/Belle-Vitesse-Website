#!/usr/bin/env python3
"""Preview and safely remove explicitly approved test records from MySQL.

Default mode is read-only and writes a review manifest. Applying the manifest
requires its SHA-256, the exact database name, production configuration, and a
fresh verified SQL dump. The script never removes files or calls Airtable or
kDrive APIs. SignatureEvent rows are deliberately preserved.

Typical VPS use (inside bv_flask_app):
    python scripts/cleanup_test_records.py --manifest-out /app/backups/test-cleanup.json
    python scripts/cleanup_test_records.py --apply \\
      --manifest /app/backups/test-cleanup.json \\
      --confirm-database BelleVitesse --confirm-selection <sha256-from-preview>
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if os.getenv("FLASK_ENV") != "production":
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

from config import config  # noqa: E402
from models import (  # noqa: E402
    CalendarSubscription,
    CheckinSignedDocument,
    CheckinToken,
    CheckinVehicle,
    CheckoutSignedDocument,
    CheckoutToken,
    CheckoutVehicle,
    Contact,
    GripCategory,
    GripProduct,
    Head,
    Incident,
    IncidentSignedDocument,
    IncidentToken,
    InspectionCheckpoint,
    KDriveObject,
    McpApiToken,
    McpAuditLog,
    Project,
    ProjectReport,
    Production,
    SignatureEvent,
    Static,
    User,
    Vehicle,
    Waiver,
    WaiverSignedDocument,
    WaiverToken,
    Config as CatalogConfig,
    db,
)

TEST_WORD = re.compile(r"(?<![^\W_])test(?![^\W_])", re.IGNORECASE)
TEST_10_NAME = "test 10"

CATALOG_MODELS = (
    Vehicle,
    Head,
    GripCategory,
    GripProduct,
    CatalogConfig,
    Static,
)

DELETE_ORDER = (
    "inspection_checkpoints",
    "waiver_tokens",
    "waiver_signed_documents",
    "checkout_tokens",
    "checkout_signed_documents",
    "checkin_tokens",
    "checkin_signed_documents",
    "incident_tokens",
    "incident_signed_documents",
    "project_reports",
    "kdrive_objects",
    "incidents",
    "waivers",
    "checkout_vehicles",
    "checkin_vehicles",
    "project_bv_referents",
    "projects",
    "mcp_audit_logs",
    "mcp_api_tokens",
    "calendar_subscriptions",
    "users",
    "contacts",
    "productions",
    "vehicles",
    "heads",
    "grips_categories",
    "grip_products",
    "configs",
    "static",
)


def normalize_name(value: object) -> str:
    """Normalize a displayed name for the TEST 10 exception."""
    return " ".join(str(value or "").split()).casefold()


def is_test_name(value: object) -> bool:
    """Match TEST as a standalone name token, case-insensitively."""
    return bool(value and TEST_WORD.search(str(value)))


def is_test_10(value: object) -> bool:
    return normalize_name(value) == TEST_10_NAME


def _json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _sort_records(records):
    return sorted(records, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))


def _model_rows(session: Session, model):
    return session.execute(select(model)).unique().scalars().all()


def _primary_key_records(model, records):
    columns = tuple(model.__table__.primary_key.columns)
    return _sort_records([
        {column.name: _json_value(getattr(record, column.name)) for column in columns}
        for record in records
    ])


def _table_key_records(table, rows):
    columns = tuple(table.primary_key.columns)
    return _sort_records([
        {column.name: _json_value(row[column.name]) for column in columns}
        for row in rows
    ])


def _root_entry(table: str, record_id, name: str):
    return {"table": table, "id": _json_value(record_id), "name": str(name or "")}


def _contact_name(contact: Contact) -> str:
    return " ".join(part for part in (contact.first_name, contact.last_name) if part).strip()


def _user_name(user: User) -> str:
    return " ".join(part for part in (user.firstname, user.lastname) if part).strip()


def is_test_user(user: User) -> bool:
    name = _user_name(user)
    mail = str(user.mail or "")
    if is_test_name(name) or is_test_name(mail):
        return True
    if user.id in (901, 902, 903, 904, 999):
        return True
    if user.id is not None and user.id >= 900 and ("test" in mail.lower() or "example.com" in mail.lower() or "test" in name.lower()):
        return True
    return False


def _catalog_name(record) -> str:
    fields = record.fields
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except (TypeError, json.JSONDecodeError):
            fields = None
    return str(fields.get("name") or "") if isinstance(fields, dict) else ""


def _project_contact_ids(project: Project) -> set[int]:
    return {
        contact_id
        for contact_id in (
            project.pilot_contact_id,
            project.production_contact_id,
            project.dop_contact_id,
            project.first_ac_contact_id,
            project.key_grip_contact_id,
        )
        if contact_id is not None
    }


def _name_matches(rows, name_getter):
    matches = []
    exact_test_10 = []
    for row in rows:
        name = str(name_getter(row) or "")
        if is_test_10(name):
            exact_test_10.append(row)
        elif is_test_name(name):
            matches.append(row)
    return matches, exact_test_10


def discover_cleanup(
    session: Session,
    database_name: str,
    database_host: str | None = None,
    database_port: int | None = None,
) -> dict:
    """Build a read-only selection, dependency manifest, and safety warnings."""
    productions = _model_rows(session, Production)
    projects = _model_rows(session, Project)
    contacts = _model_rows(session, Contact)
    incidents = _model_rows(session, Incident)
    checkouts = _model_rows(session, CheckoutVehicle)
    checkins = _model_rows(session, CheckinVehicle)
    waivers = _model_rows(session, Waiver)
    reports = _model_rows(session, ProjectReport)
    kdrive_objects = _model_rows(session, KDriveObject)
    users = _model_rows(session, User)
    mcp_tokens = _model_rows(session, McpApiToken)
    mcp_logs = _model_rows(session, McpAuditLog)
    calendar_subscriptions = _model_rows(session, CalendarSubscription)

    test_productions, test10_productions = _name_matches(productions, lambda row: row.name)
    test_projects, test10_projects = _name_matches(projects, lambda row: row.name)
    test_contacts, test10_contacts = _name_matches(contacts, _contact_name)
    test_incidents, test10_incidents = _name_matches(incidents, lambda row: row.title)

    test_users = []
    test10_users = []
    for row in users:
        name = _user_name(row)
        if is_test_10(name):
            test10_users.append(row)
        elif is_test_user(row):
            test_users.append(row)

    catalog_rows = {model.__tablename__: _model_rows(session, model) for model in CATALOG_MODELS}
    test_catalog = {}
    test10_catalog = {}
    for table_name, rows in catalog_rows.items():
        matched, exact = _name_matches(rows, _catalog_name)
        test_catalog[table_name] = matched
        test10_catalog[table_name] = exact

    production_by_id = {row.id: row for row in productions}
    project_by_id = {row.id: row for row in projects}
    contact_by_id = {row.id: row for row in contacts}

    protected_production_ids = {row.id for row in test10_productions}
    protected_project_ids = {row.id for row in test10_projects}
    protected_contact_ids = {row.id for row in test10_contacts}
    protected_user_ids = {row.id for row in test10_users}
    protected_incident_ids = {row.id for row in test10_incidents}
    protected_catalog_keys = {
        (table_name, row.id)
        for table_name, rows in test10_catalog.items()
        for row in rows
    }

    # Protect the complete production group for an exact TEST 10 project,
    # production, contact, or project-linked incident.
    for row in test10_projects:
        if row.production_id in production_by_id:
            protected_production_ids.add(row.production_id)
    for row in test10_contacts:
        if row.production_id in production_by_id:
            protected_production_ids.add(row.production_id)
        for project in projects:
            if row.id in _project_contact_ids(project):
                protected_project_ids.add(project.id)
                if project.production_id in production_by_id:
                    protected_production_ids.add(project.production_id)
    for row in test10_incidents:
        project = project_by_id.get(row.project_id)
        if project:
            protected_project_ids.add(project.id)
            if project.production_id in production_by_id:
                protected_production_ids.add(project.production_id)

    protected_project_ids.update(
        project.id for project in projects
        if project.production_id in protected_production_ids
    )
    protected_contact_ids.update(
        contact.id for contact in contacts
        if contact.production_id in protected_production_ids
    )
    protected_contact_ids.update(
        contact_id for project in projects if project.id in protected_project_ids
        for contact_id in _project_contact_ids(project)
    )
    protected_incident_ids.update(
        incident.id for incident in incidents if incident.project_id in protected_project_ids
    )

    candidate_project_ids = {
        row.id for row in test_projects if row.id not in protected_project_ids
    }
    candidate_production_ids = {
        row.id for row in test_productions if row.id not in protected_production_ids
    }
    all_project_contact_ids = {
        project.id: _project_contact_ids(project) for project in projects
    }
    retained_project_ids = {row.id for row in projects} - candidate_project_ids
    retained_contact_ids = {
        contact_id
        for project_id in retained_project_ids
        for contact_id in all_project_contact_ids[project_id]
    }

    warnings = []
    candidate_productions = set()
    mixed_productions = []
    for production_id in candidate_production_ids:
        attached_projects = [row for row in projects if row.production_id == production_id]
        noncandidate_projects = [row for row in attached_projects if row.id not in candidate_project_ids]
        shared_contacts = [
            row for row in contacts
            if row.production_id == production_id and row.id in retained_contact_ids
        ]
        if noncandidate_projects or shared_contacts:
            production = production_by_id[production_id]
            mixed_productions.append({
                "id": production.id,
                "name": production.name,
                "retained_project_ids": sorted(row.id for row in noncandidate_projects),
                "contacts_used_by_retained_projects": sorted(row.id for row in shared_contacts),
            })
            continue
        candidate_productions.add(production_id)

    if mixed_productions:
        warnings.append({
            "type": "mixed_production",
            "message": "Production TEST conservée car elle contient des projets conservés ou des contacts partagés.",
            "records": mixed_productions,
        })

    # Explicit TEST contacts and contacts belonging to a fully removable TEST
    # production are removable only when no retained project refers to them.
    candidate_contact_ids = {
        row.id for row in test_contacts if row.id not in protected_contact_ids
    }
    candidate_contact_ids.update(
        row.id for row in contacts if row.production_id in candidate_productions
    )
    shared_test_contacts = sorted(candidate_contact_ids & retained_contact_ids)
    candidate_contact_ids.difference_update(retained_contact_ids)
    if shared_test_contacts:
        warnings.append({
            "type": "shared_contact",
            "message": "Contacts TEST conservés car ils sont utilisés par des projets conservés.",
            "contact_ids": shared_test_contacts,
        })

    # A production with any contact used by a retained project cannot be
    # deleted because contacts.production_id is a live foreign key.
    for production_id in list(candidate_productions):
        shared_contact_ids = {
            row.id for row in contacts
            if row.production_id == production_id and row.id in retained_contact_ids
        }
        if shared_contact_ids:
            candidate_productions.remove(production_id)
            candidate_contact_ids.difference_update(
                row.id for row in contacts if row.production_id == production_id
            )

    project_ids = candidate_project_ids
    production_ids = candidate_productions
    contact_ids = candidate_contact_ids

    checkout_ids = {row.id for row in checkouts if row.project_id in project_ids}
    checkin_ids = {row.id for row in checkins if row.project_id in project_ids}
    checkout_numbers = {row.inspection_number for row in checkouts if row.id in checkout_ids}
    checkin_numbers = {row.inspection_number for row in checkins if row.id in checkin_ids}

    selected_incidents = {
        row.id for row in incidents
        if (
            row.project_id in project_ids
            or row.checkout_id in checkout_ids
            or row.checkin_id in checkin_ids
            or (is_test_name(row.title) and row.project_id not in protected_project_ids)
        )
        and row.id not in protected_incident_ids
    }
    incident_rows = [row for row in incidents if row.id in selected_incidents]
    incident_numbers = {row.incident_number for row in incident_rows}

    waiver_ids = {row.waiver_id for row in waivers if row.project_id in project_ids}
    waiver_token_rows = [row for row in _model_rows(session, WaiverToken) if row.waiver_id in waiver_ids]
    waiver_document_rows = [row for row in _model_rows(session, WaiverSignedDocument) if row.waiver_id in waiver_ids]
    checkout_token_rows = [
        row for row in _model_rows(session, CheckoutToken)
        if row.inspection_id in checkout_numbers or row.record_id in {str(i) for i in checkout_ids}
    ]
    checkout_document_rows = [
        row for row in _model_rows(session, CheckoutSignedDocument)
        if row.inspection_id in checkout_numbers
    ]
    checkin_token_rows = [
        row for row in _model_rows(session, CheckinToken)
        if row.inspection_id in checkin_numbers or row.record_id in {str(i) for i in checkin_ids}
    ]
    checkin_document_rows = [
        row for row in _model_rows(session, CheckinSignedDocument)
        if row.inspection_id in checkin_numbers
    ]
    incident_token_rows = [
        row for row in _model_rows(session, IncidentToken)
        if row.incident_id in selected_incidents
    ]
    incident_document_rows = [
        row for row in _model_rows(session, IncidentSignedDocument)
        if row.incident_id in selected_incidents or row.incident_number in incident_numbers
    ]

    report_rows = [row for row in reports if row.project_id in project_ids]
    kdrive_rows = [row for row in kdrive_objects if row.project_id in project_ids]
    checkpoint_rows = [
        row for row in _model_rows(session, InspectionCheckpoint)
        if row.checkout_id in checkout_ids or row.checkin_id in checkin_ids
    ]

    retained_project_action_ids = {
        row.last_action_by_id for row in projects
        if row.id in retained_project_ids and getattr(row, "last_action_by_id", None) is not None
    }
    referent_table = db.metadata.tables["project_bv_referents"]
    retained_referent_user_ids = {
        row["user_id"] for row in session.execute(
            select(referent_table.c.user_id).where(referent_table.c.project_id.in_(retained_project_ids))
        ).mappings().all()
        if row["user_id"] is not None
    } if retained_project_ids else set()
    retained_checkout_user_ids = {
        row.controller_id for row in checkouts
        if row.id not in checkout_ids and getattr(row, "controller_id", None) is not None
    }
    retained_checkin_user_ids = {
        row.controller_id for row in checkins
        if row.id not in checkin_ids and getattr(row, "controller_id", None) is not None
    }
    retained_incident_user_ids = {
        row.reported_by_id for row in incidents
        if (row.id not in selected_incidents) and getattr(row, "reported_by_id", None) is not None
    }
    retained_report_user_ids = {
        row.user_id for row in reports
        if row.project_id in retained_project_ids and getattr(row, "user_id", None) is not None
    }
    retained_user_ids = (
        retained_project_action_ids
        | retained_referent_user_ids
        | retained_checkout_user_ids
        | retained_checkin_user_ids
        | retained_incident_user_ids
        | retained_report_user_ids
    )

    candidate_user_ids = {
        row.id for row in test_users if row.id not in protected_user_ids
    }
    shared_test_users = sorted(candidate_user_ids & retained_user_ids)
    candidate_user_ids.difference_update(retained_user_ids)
    if shared_test_users:
        warnings.append({
            "type": "shared_user",
            "message": "Utilisateurs TEST conservés car ils sont utilisés par des projets, inspections ou incidents conservés.",
            "user_ids": shared_test_users,
        })

    candidate_token_ids = {
        row.id for row in mcp_tokens
        if row.user_id in candidate_user_ids or is_test_name(row.name)
    }
    candidate_log_ids = {
        row.id for row in mcp_logs
        if row.user_id in candidate_user_ids
    }
    candidate_cal_ids = {
        row.id for row in calendar_subscriptions
        if row.user_id in candidate_user_ids
    }

    model_rows_by_table = {
        "inspection_checkpoints": (InspectionCheckpoint, checkpoint_rows),
        "waiver_tokens": (WaiverToken, waiver_token_rows),
        "waiver_signed_documents": (WaiverSignedDocument, waiver_document_rows),
        "checkout_tokens": (CheckoutToken, checkout_token_rows),
        "checkout_signed_documents": (CheckoutSignedDocument, checkout_document_rows),
        "checkin_tokens": (CheckinToken, checkin_token_rows),
        "checkin_signed_documents": (CheckinSignedDocument, checkin_document_rows),
        "incident_tokens": (IncidentToken, incident_token_rows),
        "incident_signed_documents": (IncidentSignedDocument, incident_document_rows),
        "project_reports": (ProjectReport, report_rows),
        "kdrive_objects": (KDriveObject, kdrive_rows),
        "incidents": (Incident, incident_rows),
        "waivers": (Waiver, [row for row in waivers if row.waiver_id in waiver_ids]),
        "checkout_vehicles": (CheckoutVehicle, [row for row in checkouts if row.id in checkout_ids]),
        "checkin_vehicles": (CheckinVehicle, [row for row in checkins if row.id in checkin_ids]),
        "projects": (Project, [row for row in projects if row.id in project_ids]),
        "mcp_audit_logs": (McpAuditLog, [row for row in mcp_logs if row.id in candidate_log_ids]),
        "mcp_api_tokens": (McpApiToken, [row for row in mcp_tokens if row.id in candidate_token_ids]),
        "calendar_subscriptions": (CalendarSubscription, [row for row in calendar_subscriptions if row.id in candidate_cal_ids]),
        "users": (User, [row for row in users if row.id in candidate_user_ids]),
        "contacts": (Contact, [row for row in contacts if row.id in contact_ids]),
        "productions": (Production, [row for row in productions if row.id in production_ids]),
    }
    delete_keys = {
        table_name: _primary_key_records(model, rows)
        for table_name, (model, rows) in model_rows_by_table.items()
    }

    referent_conditions = []
    if project_ids:
        referent_conditions.append(referent_table.c.project_id.in_(project_ids))
    if candidate_user_ids:
        referent_conditions.append(referent_table.c.user_id.in_(candidate_user_ids))
    referent_rows = session.execute(
        select(referent_table).where(or_(*referent_conditions))
    ).mappings().all() if referent_conditions else []
    delete_keys["project_bv_referents"] = _table_key_records(referent_table, referent_rows)

    for table_name, rows in test_catalog.items():
        model = next(model for model in CATALOG_MODELS if model.__tablename__ == table_name)
        delete_keys[table_name] = _primary_key_records(model, [row for row in rows if (table_name, row.id) not in protected_catalog_keys])

    for table_name in DELETE_ORDER:
        delete_keys.setdefault(table_name, [])

    selected_roots = []
    selected_roots.extend(_root_entry("productions", row.id, row.name) for row in productions if row.id in production_ids)
    selected_roots.extend(_root_entry("projects", row.id, row.name) for row in projects if row.id in project_ids)
    selected_roots.extend(_root_entry("contacts", row.id, _contact_name(row)) for row in contacts if row.id in contact_ids)
    selected_roots.extend(_root_entry("users", row.id, _user_name(row)) for row in users if row.id in candidate_user_ids)
    selected_roots.extend(_root_entry("mcp_api_tokens", row.id, row.name) for row in mcp_tokens if row.id in candidate_token_ids)
    selected_roots.extend(_root_entry("incidents", row.id, row.title) for row in incident_rows if is_test_name(row.title))
    for table_name, rows in test_catalog.items():
        selected_roots.extend(
            _root_entry(table_name, row.id, _catalog_name(row))
            for row in rows if (table_name, row.id) not in protected_catalog_keys
        )
    selected_roots = _sort_records(selected_roots)

    protected_entities = []
    protected_entities.extend(_root_entry("productions", row.id, row.name) for row in productions if row.id in protected_production_ids)
    protected_entities.extend(_root_entry("projects", row.id, row.name) for row in projects if row.id in protected_project_ids)
    protected_entities.extend(_root_entry("contacts", row.id, _contact_name(row)) for row in contacts if row.id in protected_contact_ids)
    protected_entities.extend(_root_entry("users", row.id, _user_name(row)) for row in users if row.id in protected_user_ids)
    protected_entities.extend(_root_entry("incidents", row.id, row.title) for row in incidents if row.id in protected_incident_ids)
    for table_name, rows in test10_catalog.items():
        protected_entities.extend(_root_entry(table_name, row.id, _catalog_name(row)) for row in rows)
    protected_entities = _sort_records(protected_entities)

    signature_document_ids = (
        waiver_ids | checkout_numbers | checkin_numbers | incident_numbers
    )
    signature_event_count = 0
    if signature_document_ids:
        signature_event_count = len(session.execute(
            select(SignatureEvent.id).where(SignatureEvent.document_id.in_(signature_document_ids))
        ).all())

    target_host = database_host if os.getenv("FLASK_ENV") == "production" else "127.0.0.1"
    target_port = database_port if os.getenv("FLASK_ENV") == "production" else None
    selection = {
        "database": database_name,
        "database_host": target_host,
        "database_port": target_port,
        "roots": selected_roots,
        "protected_test_10_group": protected_entities,
        "delete_keys": delete_keys,
    }
    selection_sha256 = hashlib.sha256(
        json.dumps(selection, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    counts = {table: len(delete_keys[table]) for table in DELETE_ORDER}
    return {
        "format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": database_name,
        "database_target": {"host": database_host, "port": database_port},
        "selection": selection,
        "selection_sha256": selection_sha256,
        "counts": counts,
        "warnings": warnings,
        "signature_events_preserved": signature_event_count,
        "notes": [
            "Aucun fichier local ou objet kDrive ne sera supprimé.",
            "Les éléments de catalogue supprimés de MySQL peuvent revenir au prochain sync Airtable.",
            "La table signature_events est immuable et sera conservée.",
        ],
    }


def _write_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _read_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Impossible de lire le manifeste {path}: {exc}") from exc
    if manifest.get("format_version") != 1:
        raise RuntimeError("Version de manifeste inconnue.")
    return manifest


def _mysql_option(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def create_verified_backup(engine, backup_dir: Path) -> tuple[Path, str]:
    """Create and verify a fresh compressed SQL dump without retention cleanup."""
    if engine.dialect.name != "mysql":
        raise RuntimeError("La sauvegarde d’application exige une base MySQL.")
    if not shutil_which("mysqldump"):
        raise RuntimeError("mysqldump est introuvable ; aucune donnée n’a été modifiée.")

    url = engine.url
    database_name = url.database
    backup_dir.mkdir(parents=True, exist_ok=True)
    safe_db_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", database_name or "database")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"cleanup_test_records_{safe_db_name}_{timestamp}.sql.gz"

    credential_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=backup_dir, prefix=".cleanup-mysql-", suffix=".cnf", delete=False) as credentials:
            credential_path = Path(credentials.name)
            credentials.write("[client]\n")
            if url.username:
                credentials.write(f"user={_mysql_option(url.username)}\n")
            if url.password:
                credentials.write(f"password={_mysql_option(url.password)}\n")
            if url.host:
                credentials.write(f"host={_mysql_option(url.host)}\n")
            if url.port:
                credentials.write(f"port={int(url.port)}\n")
            credentials.write("default-character-set=utf8mb4\n")
        os.chmod(credential_path, 0o600)

        command = [
            "mysqldump",
            f"--defaults-extra-file={credential_path}",
            "--single-transaction",
            "--quick",
            "--routines",
            "--triggers",
            "--events",
            "--hex-blob",
            "--set-gtid-purged=OFF",
            "--databases",
            database_name,
        ]
        with tempfile.TemporaryFile() as stderr_file:
            with gzip.open(backup_path, "wb", compresslevel=6) as compressed:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file)
                assert process.stdout is not None
                for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
                    compressed.write(chunk)
                return_code = process.wait()
            stderr_file.seek(0)
            stderr_text = stderr_file.read().decode("utf-8", errors="replace").strip()
        if return_code != 0:
            backup_path.unlink(missing_ok=True)
            raise RuntimeError(f"mysqldump a échoué ({return_code}): {stderr_text}")

        has_sql_header = False
        with gzip.open(backup_path, "rb") as compressed:
            while True:
                chunk = compressed.read(1024 * 1024)
                if not chunk:
                    break
                if b"-- MySQL dump" in chunk or b"-- MariaDB dump" in chunk:
                    has_sql_header = True
        if not has_sql_header or backup_path.stat().st_size == 0:
            backup_path.unlink(missing_ok=True)
            raise RuntimeError("La sauvegarde n’a pas passé la vérification gzip/SQL.")

        hasher = hashlib.sha256()
        with backup_path.open("rb") as backup_file:
            for chunk in iter(lambda: backup_file.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        return backup_path, digest
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
    finally:
        if credential_path:
            credential_path.unlink(missing_ok=True)


def shutil_which(executable: str) -> str | None:
    from shutil import which
    return which(executable)


def _delete_records(connection, manifest: dict) -> dict[str, int]:
    metadata = db.metadata
    deleted = {}
    for table_name in DELETE_ORDER:
        rows = manifest["selection"]["delete_keys"].get(table_name, [])
        table = metadata.tables[table_name]
        if not rows:
            deleted[table_name] = 0
            continue

        key_columns = tuple(table.primary_key.columns)
        deleted_count = 0
        for start in range(0, len(rows), 400):
            batch = rows[start:start + 400]
            condition = _keys_condition(table, key_columns, batch)
            result = connection.execute(delete(table).where(condition))
            deleted_count += max(result.rowcount or 0, 0)
        deleted[table_name] = deleted_count
    return deleted


def _keys_condition(table, key_columns, rows):
    if len(key_columns) == 1:
        column = key_columns[0]
        return column.in_([row[column.name] for row in rows])
    return or_(*[
        and_(*(table.c[name] == value for name, value in row.items()))
        for row in rows
    ])


def _selection_hash(manifest: dict) -> str:
    selection = manifest.get("selection")
    return hashlib.sha256(
        json.dumps(selection, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _apply_manifest(
    app: Flask,
    manifest_path: Path,
    confirmed_database: str,
    confirmed_hash: str,
    allow_dev: bool = False,
    no_backup: bool = False,
) -> dict:
    env = os.getenv("FLASK_ENV", "development").lower()
    if env != "production" and not allow_dev:
        raise RuntimeError("--apply est autorisé uniquement avec FLASK_ENV=production (ou --allow-dev).")
    if no_backup and not allow_dev:
        raise RuntimeError("--no-backup est strictement interdit en production.")

    manifest = _read_manifest(manifest_path)
    if _selection_hash(manifest) != manifest.get("selection_sha256"):
        raise RuntimeError("Le manifeste a été modifié depuis sa création.")
    if confirmed_hash != manifest.get("selection_sha256"):
        raise RuntimeError("--confirm-selection ne correspond pas au hash du manifeste.")

    with app.app_context():
        engine = db.engine
        database_name = engine.url.database or ""
        if database_name != confirmed_database or manifest.get("database") != database_name:
            raise RuntimeError(
                f"Base inattendue (connectée={database_name!r}, confirmation={confirmed_database!r})."
            )
        if engine.dialect.name != "mysql":
            raise RuntimeError("--apply refuse toute base autre que MySQL.")

        # Recompute before the backup. Any new/deleted dependency invalidates
        # the approval and prevents deletion.
        with Session(engine) as session:
            current = discover_cleanup(session, database_name, engine.url.host, engine.url.port)
        if current["selection_sha256"] != manifest["selection_sha256"]:
            raise RuntimeError("La base a changé depuis l’aperçu ; relance une prévisualisation.")

        if no_backup:
            backup_path = "SKIPPED_DEV"
            backup_sha256 = "SKIPPED_DEV"
        else:
            backup_dir = Path(app.config.get("BACKUPS_FOLDER") or ROOT / "backups")
            backup_path, backup_sha256 = create_verified_backup(engine, backup_dir)

        # Recheck in the mutation transaction to close the preview/backup race.
        with engine.begin() as connection:
            with Session(bind=connection) as session:
                current = discover_cleanup(session, database_name, engine.url.host, engine.url.port)
            if current["selection_sha256"] != manifest["selection_sha256"]:
                raise RuntimeError("La base a changé pendant la sauvegarde ; aucune ligne n’a été supprimée.")
            deleted = _delete_records(connection, manifest)
            for table_name, rows in manifest["selection"]["delete_keys"].items():
                table = db.metadata.tables[table_name]
                if not rows:
                    continue
                key_columns = tuple(table.primary_key.columns)
                remaining = connection.execute(
                    select(table).where(_keys_condition(table, key_columns, rows))
                ).all()
                if remaining:
                    raise RuntimeError(f"Vérification post-suppression échouée pour {table_name}.")

        return {
            "database": database_name,
            "backup": str(backup_path),
            "backup_sha256": backup_sha256,
            "deleted": deleted,
            "signature_events_preserved": manifest.get("signature_events_preserved", 0),
        }


def _build_app() -> tuple[Flask, object | None]:
    env = os.getenv("FLASK_ENV", "development").lower()
    app = Flask("test_record_cleanup")
    app.config.from_object(config.get(env, config["default"]))
    tunnel = None
    if env != "production" and os.getenv("USE_SSH_TUNNEL", "true").lower() == "true":
        from utils.ssh_helper import get_ssh_tunnel
        tunnel, local_port = get_ssh_tunnel()
        if tunnel:
            mysql_user = os.getenv("MYSQL_USER", "Maxcongi")
            mysql_pass = os.getenv("MYSQL_PASSWORD", "")
            mysql_db = os.getenv("MYSQL_DATABASE", "BelleVitesse")
            app.config["SQLALCHEMY_DATABASE_URI"] = (
                f"mysql+mysqldb://{mysql_user}:{mysql_pass}@127.0.0.1:{local_port}/{mysql_db}?charset=utf8mb4"
            )
    db.init_app(app)
    return app, tunnel


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inventorie puis nettoie les données nommées TEST dans MySQL.")
    parser.add_argument("--apply", action="store_true", help="Appliquer un manifeste après confirmation explicite.")
    parser.add_argument("--manifest", type=Path, help="Manifeste approuvé à appliquer.")
    parser.add_argument("--manifest-out", type=Path, help="Chemin de sortie du manifeste de prévisualisation.")
    parser.add_argument("--confirm-database", help="Nom exact de base requis avec --apply.")
    parser.add_argument("--confirm-selection", help="SHA-256 affiché par l’aperçu, requis avec --apply.")
    parser.add_argument("--allow-dev", action="store_true", help="Autoriser l'exécution en environnement de développement local.")
    parser.add_argument("--no-backup", action="store_true", help="Désactive la sauvegarde SQL (autorisé UNIQUEMENT avec --allow-dev en local).")
    args = parser.parse_args(argv)

    app, tunnel = _build_app()
    try:
        if args.apply:
            if not all((args.manifest, args.confirm_database, args.confirm_selection)):
                parser.error("--apply exige --manifest, --confirm-database et --confirm-selection.")
            result = _apply_manifest(
                app,
                args.manifest,
                args.confirm_database,
                args.confirm_selection,
                allow_dev=args.allow_dev,
                no_backup=args.no_backup,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0

        with app.app_context():
            if os.getenv("FLASK_ENV", "development").lower() != "production" and not args.allow_dev:
                raise RuntimeError("L’aperçu doit être lancé dans le conteneur VPS avec FLASK_ENV=production (ou utiliser --allow-dev).")
            database_name = db.engine.url.database or ""
            if db.engine.dialect.name != "mysql":
                raise RuntimeError("La prévisualisation exige MySQL afin de cibler la base VPS prévue.")
            with Session(db.engine) as session:
                manifest = discover_cleanup(session, database_name, db.engine.url.host, db.engine.url.port)
            manifest_path = args.manifest_out or Path(tempfile.gettempdir()) / f"test-cleanup-{database_name or 'db'}.json"
            _write_manifest(manifest, manifest_path)
        print(json.dumps({
            "database": manifest["database"],
            "database_target": manifest["database_target"],
            "manifest": str(manifest_path),
            "selection_sha256": manifest["selection_sha256"],
            "roots": manifest["selection"]["roots"],
            "counts_by_table": manifest["counts"],
            "warnings": manifest["warnings"],
            "protected_test_10_group": manifest["selection"]["protected_test_10_group"],
            "signature_events_preserved": manifest["signature_events_preserved"],
            "notes": manifest["notes"],
        }, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    finally:
        if tunnel and getattr(tunnel, "is_active", False):
            tunnel.stop()


if __name__ == "__main__":
    raise SystemExit(main())
