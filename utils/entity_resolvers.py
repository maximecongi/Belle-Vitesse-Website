"""
utils/entity_resolvers.py
Helpers sécurisés pour la résolution d'entités par ID technique (entier) ou code métier (chaîne).
Centralise et fiabilise les résolutions polymorphiques (évite les doublons de `if str(x).isdigit(): ...`).
"""

from typing import Optional, Type, Union
from models import (
    CheckinVehicle,
    CheckoutVehicle,
    Incident,
    PilotWaiver,
    ProductionWaiver,
    Project,
    db,
)


def resolve_project(identifier: Union[int, str, None]) -> Optional[Project]:
    """
    Résout un Project soit par son ID numérique primaire (ex: 14),
    soit par son code métier public (ex: 'BVPR-YGSZ8300NBEC').
    """
    if identifier is None:
        return None

    # Si c'est déjà un entier ou une chaîne numérique
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
        return db.session.get(Project, int(identifier))

    # Sinon, recherche sur la colonne de référence métier
    ident_str = str(identifier).strip()
    return Project.query.filter_by(project_id=ident_str).first()


def resolve_waiver(
    model: Type[Union[PilotWaiver, ProductionWaiver]],
    identifier: Union[int, str, None]
) -> Optional[Union[PilotWaiver, ProductionWaiver]]:
    """
    Résout une décharge (PilotWaiver ou ProductionWaiver) soit par son ID numérique,
    soit par sa référence métier unique (ex: 'BVDW-...', 'BVPW-...').
    """
    if identifier is None:
        return None

    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
        rec = db.session.get(model, int(identifier))
        if rec:
            return rec

    ident_str = str(identifier).strip()
    return model.query.filter_by(waiver_id=ident_str).first()


def resolve_pilot_waiver(identifier: Union[int, str, None]) -> Optional[PilotWaiver]:
    """Résout une décharge pilote par son ID ou code BVDW-*."""
    return resolve_waiver(PilotWaiver, identifier)


def resolve_production_waiver(identifier: Union[int, str, None]) -> Optional[ProductionWaiver]:
    """Résout une décharge production par son ID ou code BVPW-*."""
    return resolve_waiver(ProductionWaiver, identifier)


def resolve_incident(identifier: Union[int, str, None]) -> Optional[Incident]:
    """
    Résout un Incident soit par son ID numérique primaire (ex: 7),
    soit par son numéro d'incident métier (ex: 'BVIC-123456').
    """
    if identifier is None:
        return None

    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
        inc = db.session.get(Incident, int(identifier))
        if inc:
            return inc

    ident_str = str(identifier).strip()
    return Incident.query.filter_by(incident_number=ident_str).first()


def resolve_inspection(
    mode: str,
    identifier: Union[int, str, None]
) -> Optional[Union[CheckoutVehicle, CheckinVehicle]]:
    """
    Résout une inspection (CheckoutVehicle si mode='checkout', CheckinVehicle si mode='checkin')
    soit par son ID numérique primaire, soit par son numéro d'inspection (ex: 'BVCO-...', 'BVCI-...').
    """
    if identifier is None:
        return None

    model = CheckoutVehicle if mode == "checkout" else CheckinVehicle
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
        rec = db.session.get(model, int(identifier))
        if rec:
            return rec

    ident_str = str(identifier).strip()
    return model.query.filter_by(inspection_number=ident_str).first()
