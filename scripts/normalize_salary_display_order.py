#!/usr/bin/env python3
"""
Script de normalisation et réindexation des positions de salaire (salary_positions).
Nettoie les valeurs de `display_order` pour leur attribuer une suite séquentielle propre (0, 1, 2, 3...).

Usage :
    python3 scripts/normalize_salary_display_order.py
"""

import os
import sys
from pathlib import Path

# Configuration du chemin pour les imports
_root = Path(__file__).resolve().parent.parent
sys.path.append(str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

from app import create_app
from models import SalaryPosition, db


def run_normalization():
    app = create_app()
    with app.app_context():
        positions = SalaryPosition.query.order_by(
            SalaryPosition.display_order.asc(),
            SalaryPosition.id.asc()
        ).all()

        print("=" * 70)
        print("RÉINDEXATION DES POSITIONS DE SALAIRE (display_order)")
        print("=" * 70)
        print(f"{'ID':<6} {'Groupe':<16} {'Position':<34} {'Ancien':<8} {'Nouveau':<8}")
        print("-" * 70)

        for new_order, pos in enumerate(positions):
            old_order = pos.display_order
            pos.display_order = new_order
            print(f"{pos.id:<6} {pos.group_name or '—':<16} {pos.position:<34} {old_order:<8} {new_order:<8}")

        db.session.commit()
        print("-" * 70)
        print(f"✅ Succès : {len(positions)} positions ont été réindexées de 0 à {len(positions) - 1}.")
        print("=" * 70)


if __name__ == "__main__":
    run_normalization()

