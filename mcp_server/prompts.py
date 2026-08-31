"""Prompts MCP : Modèles de requêtes et instructions guidées pour agents IA."""
from typing import Optional
from mcp_server.core import mcp


@mcp.prompt("nouveau_tournage")
def prompt_nouveau_tournage(
    nom_projet: str = "Nom du Tournage",
    nom_production: Optional[str] = None,
) -> str:
    """Modèle guidé pour préparer et enregistrer un nouveau tournage complet sur Belle Vitesse."""
    return (
        f"Tu es l'assistant de production Belle Vitesse. Aide-moi à enregistrer le tournage '{nom_projet}'.\n"
        f"Production : {nom_production or 'À spécifier'}\n\n"
        "Étapes à suivre :\n"
        "1. Recherche ou crée la société de production via `list_productions` / `create_production`.\n"
        "2. Identifie les contacts clés (pilote, chargé de production, chef opérateur/DOP) avec `list_contacts` / `create_contact`.\n"
        "3. Vérifie la disponibilité du véhicule et de la tête motorisée demandés avec `check_vehicle_availability`.\n"
        "4. Enregistre le projet via `create_project` avec les dates de départ, tournage et retour.\n"
        "5. Présente un récapitulatif clair incluant les statuts des décharges pilote et production générées."
    )


@mcp.prompt("chiffrer_devis")
def prompt_chiffrer_devis(
    nom_projet: str,
    nb_jours_tournage: int = 1,
    nom_vehicule: Optional[str] = None,
) -> str:
    """Guide pour structurer un pré-devis conforme à la grille tarifaire Belle Vitesse."""
    return (
        f"Tu dois établir une proposition de devis pour le projet '{nom_projet}' ({nb_jours_tournage} jour(s) de tournage).\n"
        f"Véhicule pressenti : {nom_vehicule or 'Mercedes Travelling / Autre'}\n\n"
        "Instructions :\n"
        "1. Consulte la grille tarifaire via la ressource `bv://pricing/rates` ou l'outil `get_pre_quote_form_context`.\n"
        "2. Inclus les lignes d'équipements nécessaires (véhicule travelling, tête gyro-stabilisée, monitoring).\n"
        "3. Ajoute les lignes de salaires réglementaires (Pilote de précision, Opérateur tête, Assistant caméra).\n"
        "4. Inclus les frais de logistique et kilomètres applicables.\n"
        "5. Utilise `create_pre_quote` pour enregistrer le pré-devis dans le système Belle Vitesse."
    )


@mcp.prompt("audit_tournage")
def prompt_audit_tournage(project_id: int) -> str:
    """Procédure d'audit avant départ d'un tournage (décharges signées, checkpoints véhicule)."""
    return (
        f"Réalise un audit complet avant tournage pour le projet #{project_id} :\n\n"
        "1. Récupère tous les détails du projet avec `get_project({project_id})`.\n"
        "2. Vérifie le statut de la décharge pilote (permis de conduire, attestation) et de la décharge production.\n"
        "3. Vérifie que les contacts d'urgence et le chef opérateur sont correctement renseignés.\n"
        "4. Liste les points de contrôle requis pour chaque véhicule via `get_checkpoints_for_vehicle`.\n"
        "5. Fournis un rapport de conformité : statut vert (prêt au départ) ou rouge (actions requises)."
    )
