"""
Couleurs d'identification fixes du matériel (véhicules et têtes).

Chaque véhicule / tête porte une couleur choisie dans une palette fermée, stockée dans la colonne
locale `color` (non écrasée par la synchro Airtable). Elle sert partout où le matériel doit être
reconnu d'un coup d'œil (pointage des jours de tournage, fiches, statistiques).

- À la création de la colonne, la migration attribue une couleur à tout le parc (ordre du catalogue).
- Un matériel arrivé ensuite par la synchro reçoit automatiquement la couleur la moins utilisée.
- La couleur se modifie depuis la page Flotte.
"""
import logging

from models import Head, Vehicle, db

logger = logging.getLogger(__name__)

# Palette fermée : coloris du gaffer 25 mm x 50 m vendu par Cinéboutique, gamme standard + gamme fluo
# (marquage physique du matériel),
# noir, blanc et gris (gris, argent) exclus.
# Codes hexadécimaux repris des pastilles de la fiche produit (le rouge, affiché en texture, est approché).
# (clé, libellé, hexadécimal). L'ordre sert à l'attribution automatique (couleurs les plus distinctes d'abord).
# Les classes CSS correspondantes sont .eq-color-<clé> (css/admin/admin-components.css).
# Une couleur enregistrée hors palette (ancienne palette) est réattribuée automatiquement.
EQUIPMENT_COLORS = [
    ("red", "Rouge", "#D7261E"),
    ("blue", "Bleu", "#0CB8FF"),
    ("yellow", "Jaune", "#FFDD34"),
    ("green", "Vert", "#008006"),
    ("orange", "Orange", "#EF6500"),
    ("purple", "Violet", "#760083"),
    ("pink", "Rose", "#FF6CC6"),
    ("neon_yellow", "Jaune fluo", "#FFFD40"),
    ("neon_green", "Vert fluo", "#2DDB00"),
    ("neon_pink", "Rose fluo", "#FF309B"),
    ("neon_orange", "Orange fluo", "#F35800"),
    ("neon_blue", "Bleu fluo", "#007CCB"),
    ("brown", "Marron", "#7C4400"),
    ("dark_blue", "Bleu foncé", "#0021A3"),
    ("dark_green", "Vert foncé", "#013220"),
    ("cream", "Crème", "#FFB87C"),
]
COLOR_KEYS = [key for key, _, _ in EQUIPMENT_COLORS]
COLOR_LABELS = {key: label for key, label, _ in EQUIPMENT_COLORS}
COLOR_HEX = {key: hexa for key, _, hexa in EQUIPMENT_COLORS}
# Couleur unique par matériel. Clé "none" = sans couleur (pastille neutre) :
# - choisie volontairement depuis la page Flotte pour libérer une couleur (enregistrée telle quelle,
#   jamais réattribuée automatiquement) ;
# - ou faute de couleur libre (palette épuisée : colonne laissée vide, réattribuée dès qu'une couleur se libère).
DEFAULT_COLOR = "none"
COLOR_LABELS[DEFAULT_COLOR] = "Sans couleur"

_MODELS = {"vehicle": Vehicle, "head": Head}


class EquipmentColorError(ValueError):
    """Matériel ou couleur invalide."""


def palette():
    """Palette pour les sélecteurs : [{key, label, hex}, ...]."""
    return [{"key": k, "label": label, "hex": h} for k, label, h in EQUIPMENT_COLORS]


def _all_records():
    rows = []
    for eq_type, model in _MODELS.items():
        for rec in model.query.order_by(model.display_order, model.id).all():
            rows.append((eq_type, rec))
    return rows


def _record_name(rec):
    fields = rec.fields if isinstance(getattr(rec, "fields", None), dict) else {}
    return fields.get("name") or fields.get("Nom") or str(rec.id)


def ensure_equipment_colors():
    """
    Garantit qu'une couleur n'est portée que par un seul matériel (véhicule ou tête).

    - Doublons : le premier matériel dans l'ordre du catalogue (véhicules puis têtes) garde la couleur,
      les suivants en reçoivent une libre.
    - Matériel sans couleur (nouveau véhicule / nouvelle tête synchronisé depuis Airtable, ou ancienne
      couleur hors palette) : reçoit la première couleur libre de la palette.
    - « Sans couleur » choisi volontairement (DEFAULT_COLOR enregistré) : respecté, rien n'est attribué.
    - Palette épuisée : le matériel reste sans couleur (DEFAULT_COLOR).
    Retourne la table {(type, id): clé de couleur}.
    """
    rows = _all_records()
    taken = set()
    pending = []
    for _, rec in rows:
        if rec.color == DEFAULT_COLOR:
            continue
        if rec.color in COLOR_HEX and rec.color not in taken:
            taken.add(rec.color)
        else:
            pending.append(rec)

    changed = False
    for rec in pending:
        free = next((k for k in COLOR_KEYS if k not in taken), None)
        if free:
            taken.add(free)
        if rec.color != free:
            rec.color = free
            changed = True
        if free is None:
            logger.warning(f"Palette de couleurs épuisée : « {_record_name(rec)} » reste sans couleur.")
    if changed:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Attribution automatique des couleurs du matériel impossible : {e}")
    return {(eq_type, str(rec.id)): rec.color or DEFAULT_COLOR for eq_type, rec in rows}


def get_color_owners():
    """{clé de couleur: {"type", "id", "name"}} : matériel qui porte chaque couleur."""
    owners = {}
    for eq_type, rec in _all_records():
        if rec.color in COLOR_HEX:
            owners.setdefault(rec.color, {"type": eq_type, "id": str(rec.id), "name": _record_name(rec)})
    return owners


def get_color_map():
    """{(type, id): clé de couleur} pour tout le parc (attribue les couleurs manquantes au passage)."""
    try:
        return ensure_equipment_colors()
    except Exception as e:
        logger.warning(f"Lecture des couleurs du matériel impossible : {e}")
        return {}


def set_equipment_color(equipment_type, equipment_id, color):
    """
    Change la couleur d'un véhicule ou d'une tête. Retourne la clé enregistrée.
    Refuse une couleur déjà portée par un autre matériel (une couleur = un seul matériel).
    DEFAULT_COLOR (« Sans couleur ») retire la couleur du matériel et la rend disponible.
    """
    eq_type = str(equipment_type or "").strip()
    model = _MODELS.get(eq_type)
    if model is None:
        raise EquipmentColorError("Type de matériel inconnu.")
    color = str(color or "").strip().lower()
    if color not in COLOR_HEX and color != DEFAULT_COLOR:
        raise EquipmentColorError("Couleur inconnue.")
    record = db.session.get(model, str(equipment_id or "").strip())
    if record is None:
        raise LookupError("Matériel introuvable.")
    if color == DEFAULT_COLOR:
        record.color = DEFAULT_COLOR
        db.session.commit()
        return color
    for other_type, other_model in _MODELS.items():
        holder = other_model.query.filter(other_model.color == color).first()
        if holder is not None and not (other_type == eq_type and str(holder.id) == str(record.id)):
            raise EquipmentColorError(
                f"La couleur {COLOR_LABELS[color]} est déjà utilisée par « {_record_name(holder)} »."
            )
    record.color = color
    db.session.commit()
    return color
