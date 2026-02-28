import logging
from collections import defaultdict


from models import CheckoutVehicle

logger = logging.getLogger(__name__)


# ── Stats (Chart.js) ─────────────────────────────────────────────


def get_checkout_stats():
    """
    Compute checkout statistics for Chart.js charts.

    Returns a dict with nested structure matching the frontend expectations:
        {
            'monthly_activity': { 'labels': [...], 'data': [...] },
            'status_distribution': { 'labels': [...], 'data': [...] },
        }
    """
    records = CheckoutVehicle.query.all()

    # ── Status counts ─────────────────────────────────────────────
    status_counts = defaultdict(int)
    for r in records:
        status = r.etat_controle or "Inconnu"
        status_counts[status] += 1

    # ── Monthly activity ──────────────────────────────────────────
    monthly = defaultdict(int)
    for r in records:
        if r.created_at:
            month_key = r.created_at.strftime("%Y-%m")
            monthly[month_key] += 1

    sorted_months = sorted(monthly.items())

    # ── Status labels in display order ────────────────────────────
    ordered_statuses = ["Signé", "Terminé", "À signer", "Inconnu"]
    status_labels = [
        s for s in ordered_statuses if status_counts.get(s, 0) > 0]
    # Add any extra statuses not in our ordered list
    for s in status_counts:
        if s not in status_labels:
            status_labels.append(s)

    return {
        "monthly_activity": {
            "labels": [m[0] for m in sorted_months],
            "data": [m[1] for m in sorted_months],
        },
        "status_distribution": {
            "labels": status_labels,
            "data": [status_counts[s] for s in status_labels],
        },
    }
