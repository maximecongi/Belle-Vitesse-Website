"""
services/admin/waivers/reminders.py — Gestion des relances automatiques par e-mail (CGL et BVSR).
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import joinedload

from models import (
    CglWaiver,
    Project,
    SafetyRulesWaiver,
    WaiverToken,
    db,
)
from services.admin.utils import handle_admin_service_error

logger = logging.getLogger(__name__)


@handle_admin_service_error
def auto_remind_pending_waivers(days_before: int = 2, base_url: str = None) -> dict:
    """
    Identifie et relance automatiquement les CGL et engagements BVSR
    non signés rattachés à des projets dont le tournage débute prochainement (J-days_before).
    """
    from utils.mailer import (
        send_cgl_invitation_email,
        send_safety_rules_invitation_email,
    )

    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    target_limit = today + timedelta(days=days_before)

    results = {
        "cgl_reminders_sent": 0,
        "safety_rules_reminders_sent": 0,
        "total_reminders_sent": 0,
        "details": [],
    }

    base_url_str = (base_url or os.getenv("APP_BASE_URL") or os.getenv(
        "BASE_URL") or "https://bellevitesse.com").rstrip("/")

    # 1. Conditions Générales de Location (CGL)
    cgl_waivers = (
        CglWaiver.query.filter(
            CglWaiver.deleted_at.is_(None),
            CglWaiver.status.in_(["to_send", "to_sign"]),
        )
        .options(joinedload(CglWaiver.project).joinedload(Project.production_contact))
        .all()
    )

    for cw in cgl_waivers:
        p = cw.project
        if not p or p.deleted_at is not None:
            continue

        start_dates = [d for d in (p.departure_date, p.shoot_start_date) if d]
        if not start_dates:
            continue
        p_start = min(start_dates)
        end_dates = [d for d in (p.return_date, p.shoot_end_date) if d]
        p_end = max(end_dates) if end_dates else p_start

        if not (p_start <= target_limit and today <= p_end):
            continue

        if cw.last_reminded_at and cw.last_reminded_at.date() == today:
            continue

        contact_prod = p.production_contact
        if not contact_prod or not contact_prod.mail:
            continue

        try:
            new_token = str(uuid.uuid4())
            token_rec = WaiverToken(token=new_token, waiver_id=cw.waiver_id)
            db.session.add(token_rec)

            sig_url = f"{base_url_str}/sign/cgl/{new_token}"

            sent = send_cgl_invitation_email(
                to_email=contact_prod.mail,
                prod_contact_name=f"{contact_prod.first_name} {contact_prod.last_name}",
                project_name=p.name,
                signature_link=sig_url,
                is_reminder=True,
                production_name=(p.production.name if p and p.production else getattr(cw, "production_name", None)),
            )

            if sent:
                cw.last_reminded_at = now_utc.replace(tzinfo=None)
                cw.reminder_count = (cw.reminder_count or 0) + 1
                cw.status = "to_sign"
                cw.sent_at = cw.sent_at or now_utc.replace(tzinfo=None)
                db.session.commit()

                results["cgl_reminders_sent"] += 1
                results["details"].append({
                    "type": "cgl",
                    "waiver_id": cw.waiver_id,
                    "project_name": p.name,
                    "recipient": contact_prod.mail,
                    "departure_date": p_start.isoformat(),
                    "reminder_count": cw.reminder_count,
                })
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erreur relance CGL {cw.waiver_id} : {e}")

    # 2. Règles de Sécurité Universelles (BVSR)
    safety_waivers = (
        SafetyRulesWaiver.query.filter(
            SafetyRulesWaiver.deleted_at.is_(None),
            SafetyRulesWaiver.status.in_(["to_send", "to_sign"]),
        )
        .options(joinedload(SafetyRulesWaiver.project))
        .all()
    )

    for sr in safety_waivers:
        p = sr.project
        if not p or p.deleted_at is not None:
            continue

        start_dates = [d for d in (p.departure_date, p.shoot_start_date) if d]
        if not start_dates:
            continue
        p_start = min(start_dates)
        end_dates = [d for d in (p.return_date, p.shoot_end_date) if d]
        p_end = max(end_dates) if end_dates else p_start

        if not (p_start <= target_limit and today <= p_end):
            continue

        if sr.last_reminded_at and sr.last_reminded_at.date() == today:
            continue

        recipient_mail = sr.signer_email
        recipient_name = sr.signer_name
        if not recipient_mail and sr.signer_role == "pilot" and p and p.pilot_contact:
            recipient_mail = p.pilot_contact.mail
            recipient_name = f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}"

        if not recipient_mail:
            continue

        try:
            new_token = str(uuid.uuid4())
            token_rec = WaiverToken(token=new_token, waiver_id=sr.waiver_id)
            db.session.add(token_rec)

            sig_url = f"{base_url_str}/sign/safety-rules/{new_token}"

            sent = send_safety_rules_invitation_email(
                to_email=recipient_mail,
                recipient_name=recipient_name,
                project_name=p.name,
                signature_link=sig_url,
                is_reminder=True,
                production_name=(p.production.name if p and p.production else getattr(sr, "production_name", None)),
            )

            if sent:
                sr.last_reminded_at = now_utc.replace(tzinfo=None)
                sr.reminder_count = (sr.reminder_count or 0) + 1
                sr.status = "to_sign"
                sr.sent_at = sr.sent_at or now_utc.replace(tzinfo=None)
                db.session.commit()

                results["safety_rules_reminders_sent"] += 1
                results["details"].append({
                    "type": "safety_rules",
                    "waiver_id": sr.waiver_id,
                    "project_name": p.name,
                    "recipient": recipient_mail,
                    "departure_date": p_start.isoformat(),
                    "reminder_count": sr.reminder_count,
                })
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erreur relance BVSR {sr.waiver_id} : {e}")

    results["total_reminders_sent"] = results["cgl_reminders_sent"] + results["safety_rules_reminders_sent"]
    return results
