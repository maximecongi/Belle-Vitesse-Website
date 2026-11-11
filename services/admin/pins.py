"""
Pages épinglées (favoris) de l'ERP.

Chaque utilisateur peut épingler n'importe quelle page de l'admin (⌘ + ;) ; les épingles
s'affichent en tête de la sidebar. Toutes les opérations sont scopées sur l'utilisateur :
un utilisateur ne peut ni lire ni modifier les épingles d'un autre.
"""

from typing import Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func

from models import UserPin, db
from utils.navigation import RETURN_TO_PARAM, safe_return_to


class PinError(ValueError):
    """Donnée d'épingle invalide (URL hors admin, libellé vide…)."""


def _clean_label(label) -> str:
    label = " ".join(str(label or "").split())
    if not label:
        raise PinError("Le nom du favori est obligatoire.")
    return label[: UserPin.LABEL_MAX]


def _clean_url(url) -> str:
    """URL interne à l'admin, sans fragment ni contexte de retour (`return_to`)."""
    cleaned = safe_return_to(url)
    if not cleaned:
        raise PinError("Seules les pages de l'ERP peuvent être épinglées.")
    parts = urlsplit(cleaned)
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != RETURN_TO_PARAM]
    )
    return urlunsplit(("", "", parts.path, query, ""))


def list_pins(user_id: int) -> List[dict]:
    """Épingles de l'utilisateur, dans l'ordre d'affichage."""
    if not user_id:
        return []
    pins = (
        UserPin.query.filter_by(user_id=user_id)
        .order_by(UserPin.position.asc(), UserPin.id.asc())
        .all()
    )
    return [p.to_dict() for p in pins]


def _get_owned(user_id: int, pin_id: int) -> Optional[UserPin]:
    return UserPin.query.filter_by(id=pin_id, user_id=user_id).first()


def upsert_pin(user_id: int, url, label) -> UserPin:
    """Épingle une page (en fin de liste) ou renomme l'épingle existante pour cette URL."""
    url = _clean_url(url)
    label = _clean_label(label)
    pin = UserPin.query.filter_by(user_id=user_id, url=url).first()
    if pin:
        pin.label = label
    else:
        last = (
            db.session.query(func.max(UserPin.position))
            .filter(UserPin.user_id == user_id)
            .scalar()
        )
        pin = UserPin(user_id=user_id, url=url, label=label, position=(last or 0) + 1)
        db.session.add(pin)
    db.session.commit()
    return pin


def rename_pin(user_id: int, pin_id: int, label) -> Optional[UserPin]:
    pin = _get_owned(user_id, pin_id)
    if not pin:
        return None
    pin.label = _clean_label(label)
    db.session.commit()
    return pin


def delete_pin(user_id: int, pin_id: int) -> bool:
    pin = _get_owned(user_id, pin_id)
    if not pin:
        return False
    db.session.delete(pin)
    db.session.commit()
    return True


def reorder_pins(user_id: int, ids: Iterable) -> None:
    """Applique l'ordre donné ; les identifiants inconnus ou d'un autre utilisateur sont ignorés."""
    try:
        wanted = [int(i) for i in ids]
    except (TypeError, ValueError):
        raise PinError("Ordre invalide.")
    pins = {p.id: p for p in UserPin.query.filter_by(user_id=user_id).all()}
    ordered = [pins[i] for i in dict.fromkeys(wanted) if i in pins]
    # Les épingles absentes de la liste reçue conservent leur ordre relatif, en fin de liste
    rest = sorted(
        (p for p in pins.values() if p not in ordered), key=lambda p: (p.position, p.id)
    )
    for position, pin in enumerate(ordered + rest, start=1):
        pin.position = position
    db.session.commit()
