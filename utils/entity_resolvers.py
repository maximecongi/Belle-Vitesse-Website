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
    Waiver,
    CglWaiver,
    SafetyRulesWaiver,
    PilotWaiver,
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
    model_or_identifier: Union[Type[Waiver], int, str, None],
    identifier: Union[int, str, None] = None
) -> Optional[Union[Waiver, CglWaiver, SafetyRulesWaiver]]:
    """
    Résout une décharge (Waiver, CglWaiver ou SafetyRulesWaiver) soit par son ID numérique,
    soit par sa référence métier unique (ex: 'BVRA-...', 'BVSR-...').
    Peut être appelée sous la forme resolve_waiver(identifier) ou resolve_waiver(model, identifier).
    """
    if identifier is None and not (isinstance(model_or_identifier, type) and issubclass(model_or_identifier, db.Model)):
        model = Waiver
        ident = model_or_identifier
    else:
        model = model_or_identifier
        ident = identifier

    if ident is None:
        return None

    if isinstance(ident, int) or (isinstance(ident, str) and str(ident).strip().isdigit()):
        rec = db.session.get(model, int(ident))
        if rec:
            return rec

    ident_str = str(ident).strip()
    return model.query.filter_by(waiver_id=ident_str).first()


def resolve_cgl(identifier: Union[int, str, None]) -> Optional[CglWaiver]:
    """Résout des CGL (BVRA) par leur ID ou code BVRA-*."""
    return resolve_waiver(CglWaiver, identifier)


def resolve_safety_rules_waiver(identifier: Union[int, str, None]) -> Optional[SafetyRulesWaiver]:
    """Résout des Règles de Sécurité Universelles (BVSR) par leur ID ou code BVSR-*."""
    return resolve_waiver(SafetyRulesWaiver, identifier)


def resolve_pilot_waiver(identifier: Union[int, str, None]) -> Optional[PilotWaiver]:
    """Résout une Attestation Pilote Annexe 3 (BVPA) par son ID ou code BVPA-*."""
    return resolve_waiver(PilotWaiver, identifier)



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
