#!/usr/bin/env python3
# scripts/sync_risk_translations.py
"""
Complète les traductions anglaises du catalogue d'Analyse des Risques (BVRA) en base.

Source des traductions : les constantes DEFAULT_GENERAL_RISK_ASSESSMENT et
DEFAULT_VEHICLE_RISK_ASSESSMENT de services/admin/risk_assessment_config.py.

Pour chaque risque stocké dans AppSetting ('general_risk_assessment' et
'vehicle_risk_assessment_catalog'), un champ EN est renseigné uniquement s'il est
vide ou identique au FR (copie non traduite) ET que le texte FR correspond
exactement à un texte FR du catalogue par défaut. Une traduction déjà saisie
n'est jamais écrasée : le script est idempotent.

Usage :
    python scripts/sync_risk_translations.py            # applique
    python scripts/sync_risk_translations.py --dry-run  # affiche sans écrire
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

PAIRS = (('title_fr', 'title_en'), ('category_fr', 'category_en'), ('description_fr', 'description_en'))
MISSING_MARKERS = ('', 'traduction manquante', 'traduction anglaise manquante')


def _build_fr_to_en(default_scopes):
    """Dictionnaire texte FR -> texte EN, construit à partir des risques par défaut traduits."""
    mapping = {}
    for risks in default_scopes:
        for r in risks:
            for fr_key, en_key in PAIRS:
                fr, en = (r.get(fr_key) or '').strip(), (r.get(en_key) or '').strip()
                # Un texte identique en FR et EN (ex. « COORDINATION ») est une traduction valide.
                if fr and en:
                    mapping.setdefault(fr, en)
            for fr, en in zip(r.get('recommendations_fr') or [], r.get('recommendations_en') or []):
                fr, en = (fr or '').strip(), (en or '').strip()
                if fr and en and fr != en:
                    mapping.setdefault(fr, en)
    return mapping


def _needs_translation(fr, en):
    en = (en or '').strip()
    return en.lower() in MISSING_MARKERS or en == (fr or '').strip()


def _translate_risk(risk, fr_to_en):
    """Complète les champs EN d'un risque (mutation en place). Retourne (complétés, manquants)."""
    filled, missing = 0, []
    for fr_key, en_key in PAIRS:
        fr = (risk.get(fr_key) or '').strip()
        if fr and _needs_translation(fr, risk.get(en_key)):
            if fr in fr_to_en:
                filled += risk.get(en_key) != fr_to_en[fr]
                risk[en_key] = fr_to_en[fr]
            else:
                missing.append(en_key)

    recs_fr = risk.get('recommendations_fr') or []
    recs_en = list(risk.get('recommendations_en') or [])
    recs_en += [''] * (len(recs_fr) - len(recs_en))
    for i, fr in enumerate(recs_fr):
        fr = (fr or '').strip()
        if fr and _needs_translation(fr, recs_en[i]):
            if fr in fr_to_en:
                filled += recs_en[i] != fr_to_en[fr]
                recs_en[i] = fr_to_en[fr]
            else:
                missing.append(f'recommendations_en[{i}]')
    risk['recommendations_en'] = recs_en[:len(recs_fr)]
    return filled, missing


def _process(label, risks, fr_to_en):
    total = 0
    for r in risks:
        filled, missing = _translate_risk(r, fr_to_en)
        total += filled
        if missing:
            print(f"  ⚠️  [{label}] {r.get('title_fr') or r.get('id')} : sans traduction de référence -> {', '.join(missing)}")
    print(f"  [{label}] {len(risks)} risques, {total} champs EN complétés")
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help="N'écrit rien en base")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from models import AppSetting
        from services.admin.risk_assessment_config import (
            DEFAULT_GENERAL_RISK_ASSESSMENT,
            DEFAULT_VEHICLE_RISK_ASSESSMENT,
            get_general_risk_assessment,
            save_general_risk_assessment,
            save_vehicle_risk_assessment,
        )

        fr_to_en = _build_fr_to_en(
            [DEFAULT_GENERAL_RISK_ASSESSMENT] + [v.get('risks', []) for v in DEFAULT_VEHICLE_RISK_ASSESSMENT.values()]
        )
        print(f"Référentiel : {len(fr_to_en)} textes FR traduits dans le catalogue par défaut.")

        # 1. Risques généraux
        general = json.loads(json.dumps(get_general_risk_assessment()))
        if _process('général', general, fr_to_en) and not args.dry_run:
            ok, msg = save_general_risk_assessment(general)
            print(f"  -> {msg}")
            if not ok:
                return 1

        # 2. Risques par véhicule (seules les entrées personnalisées sont stockées en base)
        raw = AppSetting.get('vehicle_risk_assessment_catalog', None)
        custom = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw if isinstance(raw, dict) else {})
        for key, entry in custom.items():
            risks = entry.get('risks') if isinstance(entry, dict) else None
            if not isinstance(risks, list):
                continue
            label = entry.get('label') or key
            if _process(f'véhicule {label}', risks, fr_to_en) and not args.dry_run:
                ok, msg = save_vehicle_risk_assessment(key, {'risks': risks})
                print(f"  -> {msg}")
                if not ok:
                    return 1

        if args.dry_run:
            print("Dry-run : aucune écriture.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
