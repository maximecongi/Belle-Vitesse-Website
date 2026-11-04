from services.admin.status_mapping import (
    format_inspection_status,
    format_waiver_status,
    get_inspection_key,
)
from services.admin.projects.intervals import get_project_shoot_status
from utils.formatting import format_date_fr, get_today_paris
from utils.image_utils import extract_head_image, extract_vehicle_image

_extract_vehicle_image = extract_vehicle_image
_extract_head_image = extract_head_image


def _get_secured_document_url(path, doc_type):
    """
    Génère une URL sécurisée et tokenisée pour un document PDF.
    Délègue au helper centralisé des décharges.
    """
    from services.admin.waivers.common import get_secured_waiver_pdf_url
    return get_secured_waiver_pdf_url(path, doc_type)


def _format_vehicle_state(project, vehicle_id, vehicle_map):
    """
    Formate l'état des contrôles (départ/retour) pour un véhicule spécifique au sein d'un projet.
    """
    # Recherche des enregistrements correspondants non supprimés dans les collections pré-chargées du projet
    active_c_outs = [
        c for c in (project.checkout_vehicles or [])
        if str(c.vehicle_id) == str(vehicle_id) and getattr(c, "deleted_at", None) is None
    ]
    c_out = max(active_c_outs, key=lambda x: x.id) if active_c_outs else None

    active_c_ins = [
        c for c in (project.checkin_vehicles or [])
        if str(c.vehicle_id) == str(vehicle_id) and getattr(c, "deleted_at", None) is None
    ]
    c_in = max(active_c_ins, key=lambda x: x.id) if active_c_ins else None

    v_data = vehicle_map.get(vehicle_id, {})
    brand = v_data.get("brand") or ""
    model = v_data.get("model") or ""
    brand_model = f"{brand} {model}".strip()

    raw_type = v_data.get("type") or ""
    type_map = {
        "car": "Véhicule",
        "precision": "Véhicule de précision",
        "bike": "Deux-roues",
        "tracking": "Véhicule de travelling",
        "van": "Fourgon technique",
        "rickshaw": "Rickshaw de travelling",
        "segway": "Gyropode / Segway",
        "trike": "Trike électrique",
    }
    type_fr = type_map.get(raw_type.lower(), brand_model or "Véhicule de tournage")

    return {
        "id": vehicle_id,
        "fields": vehicle_map.get(vehicle_id, {}),
        "image": _extract_vehicle_image(v_data),
        "type_fr": type_fr,
        "checkout_status": format_inspection_status(c_out.status) if c_out else "À contrôler",
        "checkout_status_id": get_inspection_key(c_out.status) if c_out else "to_check",
        "checkout_id": c_out.id if c_out else "",
        "checkout_pdf": _get_secured_document_url(c_out.signed_pdf_path, "checkout") if c_out else None,
        "checkout_conform": "true" if (c_out and c_out.vehicle_ready) else "false",
        "checkout_ready": "true" if (c_out and c_out.vehicle_ready) else ("false" if c_out else "—"),
        "checkin_status": format_inspection_status(c_in.status) if c_in else "À contrôler",
        "checkin_status_id": get_inspection_key(c_in.status) if c_in else "to_check",
        "checkin_id": c_in.id if c_in else "",
        "checkin_pdf": _get_secured_document_url(c_in.signed_pdf_path, "checkin") if c_in else None,
        "checkin_conform": "true" if (c_in and c_in.vehicle_ready) else "false",
        "checkin_ready": "true" if (c_in and c_in.vehicle_ready) else ("false" if c_in else "—"),
    }


def _format_project_admin(p, vehicle_map, heads_map):
    """
    Formate un enregistrement de projet pour l'affichage dans la liste d'administration.
    """
    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(",") if v.strip()]
    head_ids = [h.strip() for h in (p.heads_to_check or "").split(",") if h.strip()]

    today_date = get_today_paris()
    status_info = get_project_shoot_status(p, today_date)
    shoot_status = status_info["status"]
    shoot_status_label = status_info["label"]
    shoot_status_id = status_info["id"]
    shoot_status_color = status_info["color"]
    shoot_dates_label = status_info["dates_label"]

    return {
        "id": p.id,
        "project_id": p.project_id,
        "name": p.name,
        "shoot_status": shoot_status,
        "shoot_status_label": shoot_status_label,
        "shoot_status_id": shoot_status_id,
        "shoot_status_color": shoot_status_color,
        "production": p.production.name if p.production else "—",
        "departure_date": format_date_fr(str(p.departure_date)) if p.departure_date else "—",
        "raw_departure_date": str(p.departure_date) if p.departure_date else "",
        "shoot_start": format_date_fr(str(p.shoot_start_date)) if p.shoot_start_date else "—",
        "raw_shoot_start": str(p.shoot_start_date) if p.shoot_start_date else "",
        "shoot_end": format_date_fr(str(p.shoot_end_date)) if p.shoot_end_date else "—",
        "raw_shoot_end": str(p.shoot_end_date) if p.shoot_end_date else "",
        "return_date": format_date_fr(str(p.return_date)) if p.return_date else "—",
        "raw_return_date": str(p.return_date) if p.return_date else "",
        "raw_checkin_date": str(p.return_date) if p.return_date else "",
        "date_mode": getattr(p, "date_mode", "continuous") or "continuous",
        "is_immobilized_between": bool(getattr(p, "is_immobilized_between", True)),
        "shoot_dates": getattr(p, "shoot_dates", None) or [],
        "shoot_dates_count": len(getattr(p, "shoot_dates", None) or []),
        "shoot_dates_label": shoot_dates_label,
        "notes": p.notes or "",
        "pilot_contact_name": f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}" if p.pilot_contact else "—",
        "production_contact_name": f"{p.production_contact.first_name} {p.production_contact.last_name}" if p.production_contact else "—",
        "dop_contact_name": f"{p.dop_contact.first_name} {p.dop_contact.last_name}" if p.dop_contact else "—",
        "first_ac_contact_name": f"{p.first_ac_contact.first_name} {p.first_ac_contact.last_name}" if p.first_ac_contact else "—",
        "key_grip_contact_name": f"{p.key_grip_contact.first_name} {p.key_grip_contact.last_name}" if p.key_grip_contact else "—",
        "vehicles": [_format_vehicle_state(p, vid, vehicle_map) for vid in veh_ids],
        "heads": [{
            "id": hid,
            "name": heads_map.get(hid, {}).get("name", "Sans nom"),
            "brand": heads_map.get(hid, {}).get("brand", ""),
            "model": heads_map.get(hid, {}).get("model", ""),
            "image": _extract_head_image(heads_map.get(hid, {})),
        } for hid in head_ids],
        "cgl": {
            "id": p.active_cgl.id if p.active_cgl else None,
            "waiver_num": p.active_cgl.waiver_id if p.active_cgl else "",
            "production_name": p.active_cgl.production_name if (p.active_cgl and p.active_cgl.production_name) else (p.production.name if p.production else ""),
            "status": format_waiver_status(p.active_cgl.status) if p.active_cgl else "",
            "raw_status": p.active_cgl.status if p.active_cgl else "",
            "pdf_path": _get_secured_document_url(p.active_cgl.signed_pdf_path, "cgl") if p.active_cgl else None,
        },
        "safety_rules": {
            "count": len(p.active_safety_rules),
            "signed_count": sum(1 for sr in p.active_safety_rules if sr.status == "signed"),
            "has_pending": any(sr.status in ("to_send", "to_sign") for sr in p.active_safety_rules),
            "single_pdf_path": _get_secured_document_url(p.active_safety_rules[0].signed_pdf_path, "safety-rules") if (len(p.active_safety_rules) == 1 and p.active_safety_rules[0].status == "signed") else None,
            "rules_list": [
                {
                    "id": sr.id,
                    "waiver_num": sr.waiver_id,
                    "signer_name": sr.signer_name or "—",
                    "signer_role": sr.signer_role or "pilot",
                    "signer_role_label": getattr(sr, "signer_role_label", sr.signer_role),
                    "status": format_waiver_status(sr.status),
                    "raw_status": sr.status,
                    "pdf_path": _get_secured_document_url(sr.signed_pdf_path, "safety-rules"),
                }
                for sr in p.active_safety_rules
            ],
        },
        "pilot_waivers": {
            "count": len(p.active_pilot_waivers),
            "signed_count": sum(1 for pw in p.active_pilot_waivers if pw.status == "signed"),
            "has_pending": any(pw.status in ("to_send", "to_sign") for pw in p.active_pilot_waivers),
            "single_pdf_path": _get_secured_document_url(
                p.active_pilot_waivers[0].signed_pdf_path, "pilot-attestation"
            ) if (len(p.active_pilot_waivers) == 1 and p.active_pilot_waivers[0].status == "signed") else None,
            "waivers_list": [
                {
                    "id": pw.id,
                    "waiver_num": pw.waiver_id,
                    "signer_name": pw.signer_name or "—",
                    "signer_role": pw.signer_role or "pilot",
                    "signer_role_label": getattr(pw, "signer_role_label", pw.signer_role),
                    "status": format_waiver_status(pw.status),
                    "raw_status": pw.status,
                    "pdf_path": _get_secured_document_url(pw.signed_pdf_path, "pilot-attestation"),
                }
                for pw in p.active_pilot_waivers
            ],
        },
        "reports_count": len(p.reports) if hasattr(p, 'reports') and p.reports else 0,
        "incidents": [
            {
                "id": inc.id,
                "incident_number": inc.incident_number,
                "title": inc.title,
                "severity": inc.severity,
                "severity_label": inc.severity_label,
                "status": inc.status,
                "status_label": inc.status_label,
                "signature_status": inc.signature_status,
                "is_fully_signed": inc.is_fully_signed,
                "signature_status_label": inc.signature_status_label,
            }
            for inc in (getattr(p, "incidents", []) or [])
            if not getattr(inc, "deleted_at", None)
        ],
        "incidents_count": len([inc for inc in (getattr(p, "incidents", []) or []) if not getattr(inc, "deleted_at", None)]),
    }

