"""
Project service layer — business logic for project management.
"""

from utils.checkout import TABLE_PROJECTS, TABLE_CHECKOUT, TABLE_PRODUCTIONS, format_date_fr
from utils.airtable import get_vehicles
from utils.checkin import TABLE_CHECKIN


def list_projects():
    """
    Fetch all project records and format for listing.
    Cross-references checkout and checkin records to determine each vehicle's control status.
    """
    records = TABLE_PROJECTS.all(sort=["-Nom"])

    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}

    productions = TABLE_PRODUCTIONS.all()
    prod_names = {p["id"]: p.get("fields", {}).get("Nom", "—")
                  for p in productions}

    checkouts = TABLE_CHECKOUT.all()
    checkout_info = {}
    for c in checkouts:
        cf = c.get("fields", {})
        veh_ids = cf.get("Véhicule contrôlé", [])
        status = cf.get("État du contrôle", "")
        ready = cf.get("Véhicule prêt au départ", "—")
        vid = veh_ids[0] if isinstance(veh_ids, list) and veh_ids else None
        checkout_info[c["id"]] = {"vehicle_id": vid,
                                  "status": status, "ready": ready}

    checkins = TABLE_CHECKIN.all()
    checkin_info = {}
    for c in checkins:
        cf = c.get("fields", {})
        veh_ids = cf.get("Véhicule contrôlé", [])
        status = cf.get("État du contrôle", "")
        ready = cf.get("Véhicule prêt au retour", "—")
        vid = veh_ids[0] if isinstance(veh_ids, list) and veh_ids else None
        checkin_info[c["id"]] = {"vehicle_id": vid,
                                 "status": status, "ready": ready}

    projects = []
    for r in records:
        fields = r.get("fields", {})
        veh_ids = fields.get("Véhicules à contrôler", [])

        checkout_ids = fields.get("checkout_vehicles", [])
        proj_vehicle_status = {}
        if isinstance(checkout_ids, list):
            for cid in checkout_ids:
                ci = checkout_info.get(cid, {})
                if ci.get("vehicle_id"):
                    proj_vehicle_status[ci["vehicle_id"]] = {
                        "status": ci["status"],
                        "checkout_id": cid,
                        "ready": ci.get("ready", "—")
                    }

        checkin_ids = fields.get("checkin_vehicles", [])
        proj_vehicle_checkin_status = {}
        if isinstance(checkin_ids, list):
            for cid in checkin_ids:
                ci = checkin_info.get(cid, {})
                if ci.get("vehicle_id"):
                    proj_vehicle_checkin_status[ci["vehicle_id"]] = {
                        "status": ci["status"],
                        "checkin_id": cid,
                        "ready": ci.get("ready", "—")
                    }

        veh_list = []
        if isinstance(veh_ids, list):
            for vid in veh_ids:
                v_info = proj_vehicle_status.get(vid, {})
                ci_info = proj_vehicle_checkin_status.get(vid, {})
                veh_list.append({
                    "id": vid,
                    "name": vehicle_names.get(vid, "—"),
                    "checkout_status": v_info.get("status", ""),
                    "checkout_id": v_info.get("checkout_id", ""),
                    "checkout_ready": v_info.get("ready", "—"),
                    "checkin_status": ci_info.get("status", ""),
                    "checkin_id": ci_info.get("checkin_id", ""),
                    "checkin_ready": ci_info.get("ready", "—"),
                })

        prod_ids = fields.get("Production", [])
        prod_name = prod_names.get(prod_ids[0], "—") if isinstance(
            prod_ids, list) and prod_ids else "—"

        projects.append({
            "id": r["id"],
            "name": fields.get("Nom", "—"),
            "production": prod_name,
            "departure_date": format_date_fr(fields.get("Date de départ", "—")),
            "raw_departure_date": fields.get("Date de départ", ""),
            "shoot_start": format_date_fr(fields.get("Date de début de tournage", "—")),
            "shoot_end": format_date_fr(fields.get("Date de fin de tournage", "—")),
            "return_date": format_date_fr(fields.get("Date de retour", "—")),
            "raw_return_date": fields.get("Date de retour", "—"),
            "raw_checkin_date": fields.get("Date de retour", ""),
            "vehicles": veh_list,
        })
    return projects


def get_project_form_context():
    return {
        "productions": TABLE_PRODUCTIONS.all(sort=["Nom"]),
        "vehicles": get_vehicles(),
    }


def build_project_fields(form):
    fields = {
        "Nom": form.get("name"),
        "Date de départ": form.get("departure_date"),
        "Date de retour": form.get("return_date"),
        "Date de début de tournage": form.get("shoot_start"),
        "Date de fin de tournage": form.get("shoot_end"),
    }
    if form.get("production_id"):
        fields["Production"] = [form.get("production_id")]

    vehicle_ids = form.getlist("vehicle_ids") if hasattr(
        form, 'getlist') else []
    fields["Véhicules à contrôler"] = vehicle_ids if vehicle_ids else []
    return fields


def create_project(form):
    fields = build_project_fields(form)
    TABLE_PROJECTS.create(fields)
    return True


def update_project(record_id, form):
    fields = build_project_fields(form)
    TABLE_PROJECTS.update(record_id, fields)
    return True


def get_project_for_edit(record_id):
    record = TABLE_PROJECTS.get(record_id)
    if not record:
        return None

    fields = record.get("fields", {})
    prod_ids = fields.get("Production", [])
    production_id = prod_ids[0] if isinstance(
        prod_ids, list) and prod_ids else ""

    veh_ids = fields.get("Véhicules à contrôler", [])
    vehicle_ids = veh_ids if isinstance(veh_ids, list) else []

    return {
        "name": fields.get("Nom", ""),
        "departure_date_raw": fields.get("Date de départ", ""),
        "shoot_start_raw": fields.get("Date de début de tournage", ""),
        "shoot_end_raw": fields.get("Date de fin de tournage", ""),
        "return_date_raw": fields.get("Date de retour", ""),
        "production_id": production_id,
        "vehicle_ids": vehicle_ids,
    }


def delete_project(record_id):
    TABLE_PROJECTS.delete(record_id)
