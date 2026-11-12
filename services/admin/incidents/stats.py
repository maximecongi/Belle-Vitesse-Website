"""
Indicateurs du module Incidents sur une période (page Indicateurs) :
- incidents déclarés (dont critiques), coût réel, répartitions par catégorie et par impact
  sur le tournage : incidents dont la date est dans la période ;
- délai moyen de résolution : incidents résolus pendant la période ;
- incidents ouverts (dont critiques) : instantané, indépendant de la période.
"""
from models.incident import Incident
from services.admin.incidents.constants import INCIDENT_CATEGORY_MAP, INCIDENT_IMPACT_MAP

INCIDENT_OPEN_STATUSES = ("signale", "en_expertise", "en_reparation", "assurance")


def _breakdown(incidents, attr, labels):
    """Répartition triée (décroissante) avec pourcentage relatif au maximum, pour les barres."""
    counts = {}
    for inc in incidents:
        key = getattr(inc, attr) or "autre"
        counts[key] = counts.get(key, 0) + 1
    top = max(counts.values(), default=0)
    return [
        {"key": k, "label": labels.get(k, k), "count": n, "pct": round(100 * n / top) if top else 0}
        for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], labels.get(kv[0], kv[0])))
    ]


def incident_stats(start, end):
    base = Incident.query.filter(Incident.deleted_at.is_(None))
    open_q = base.filter(Incident.status.in_(INCIDENT_OPEN_STATUSES))

    declared = base.filter(Incident.incident_date >= start, Incident.incident_date <= end).all()
    resolved = [
        inc for inc in base.filter(Incident.resolved_at.isnot(None)).all()
        if start <= inc.resolved_at.date() <= end and inc.incident_date
        and inc.resolved_at.date() >= inc.incident_date
    ]
    durations = [(inc.resolved_at.date() - inc.incident_date).days for inc in resolved]
    cost = sum((inc.actual_cost for inc in declared if inc.actual_cost is not None), start=0)

    return {
        "open": open_q.count(),
        "open_critical": open_q.filter(Incident.severity == "critique").count(),
        "declared": len(declared),
        "declared_critical": sum(1 for inc in declared if inc.severity == "critique"),
        "avg_days_to_resolve": round(sum(durations) / len(durations)) if durations else None,
        "resolved_sample": len(durations),
        "actual_cost": float(cost),
        "by_category": _breakdown(declared, "category", INCIDENT_CATEGORY_MAP),
        "by_impact": _breakdown(declared, "shooting_impact", INCIDENT_IMPACT_MAP),
    }
