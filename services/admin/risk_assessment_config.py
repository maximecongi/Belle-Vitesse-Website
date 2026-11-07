# services/admin/risk_assessment_config.py
"""
Gestion du catalogue d'Analyse des Risques (Risk Assessment - BVRS)
Fournit les risques par défaut (Travelling et véhicules spécifiques) et les fonctions CRUD
pour l'administration de la Flotte et la génération des documents BVRS.
"""

import json
import logging
from models import AppSetting
from utils.image_utils import extract_vehicle_image

logger = logging.getLogger(__name__)

# ── 1. Risques Généraux : Véhicules Travelling (Défaut FR / EN) ──
DEFAULT_GENERAL_RISK_ASSESSMENT = [
    {
        "id": "intrusion_dans_la_zone_de_roulage",
        "category_fr": "ZONE DE TOURNAGE",
        "category_en": "SHOOTING AREA",
        "title_fr": "Intrusion dans la zone de roulage",
        "title_en": "Intrusion into the Driving Area",
        "level": "major",
        "description_fr": "Une personne du public, un membre de l’équipe ou un véhicule extérieur peut entrer dans la trajectoire pendant une prise, y compris en forçant un blocage.",
        "description_en": "Une personne du public, un membre de l’équipe ou un véhicule extérieur peut entrer dans la trajectoire pendant une prise, y compris en forçant un blocage.",
        "recommendations_fr": [
            "Faire définir et sécuriser la zone de roulage par la production avant chaque plan (périmètre, circulation, public).",
            "Pendant les prises, rouler uniquement dans une zone fermée à toute circulation extérieure (voie fermée par arrêté de l’autorité compétente, terrain privé ou piste), délimitée et sécurisée par la production.",
            "Vérifier que le blocage est en place avant chaque départ.",
            "Éloigner de la trajectoire toute personne non indispensable au plan.",
            "Placer des véhicules tampons devant et derrière pour protéger la scène.",
            "Relier chaque point de blocage au pilote par radio, pour pouvoir interrompre la prise immédiatement."
        ],
        "recommendations_en": [
            "Faire définir et sécuriser la zone de roulage par la production avant chaque plan (périmètre, circulation, public).",
            "Pendant les prises, rouler uniquement dans une zone fermée à toute circulation extérieure (voie fermée par arrêté de l’autorité compétente, terrain privé ou piste), délimitée et sécurisée par la production.",
            "Vérifier que le blocage est en place avant chaque départ.",
            "Éloigner de la trajectoire toute personne non indispensable au plan.",
            "Placer des véhicules tampons devant et derrière pour protéger la scène.",
            "Relier chaque point de blocage au pilote par radio, pour pouvoir interrompre la prise immédiatement."
        ]
    },
    {
        "id": "mauvais_état_du_sol",
        "category_fr": "ZONE DE TOURNAGE",
        "category_en": "SHOOTING AREA",
        "title_fr": "Mauvais état du sol",
        "title_en": "Poor Ground Conditions",
        "level": "standard",
        "description_fr": "Des graviers, des nids de poule, de la boue, de l’huile ou un sol mouillé réduisent l’adhérence et peuvent faire perdre le contrôle du véhicule.",
        "description_en": "Des graviers, des nids de poule, de la boue, de l’huile ou un sol mouillé réduisent l’adhérence et peuvent faire perdre le contrôle du véhicule.",
        "recommendations_fr": [
            "Reconnaître la trajectoire à pied ou à basse vitesse avant la première prise.",
            "Adapter la vitesse à l’état du sol.",
            "Suspendre le roulage en cas de doute."
        ],
        "recommendations_en": [
            "Reconnaître la trajectoire à pied ou à basse vitesse avant la première prise.",
            "Adapter la vitesse à l’état du sol.",
            "Suspendre le roulage en cas de doute."
        ]
    },
    {
        "id": "visibilité_réduite",
        "category_fr": "ZONE DE TOURNAGE",
        "category_en": "SHOOTING AREA",
        "title_fr": "Visibilité réduite",
        "title_en": "Reduced Visibility",
        "level": "standard",
        "description_fr": "La nuit, la poussière, la fumée, les effets spéciaux ou un éblouissement peuvent empêcher le pilote de voir la trajectoire ou le sujet filmé.",
        "description_en": "La nuit, la poussière, la fumée, les effets spéciaux ou un éblouissement peuvent empêcher le pilote de voir la trajectoire ou le sujet filmé.",
        "recommendations_fr": [
            "Baliser et éclairer la trajectoire de nuit.",
            "Adapter la vitesse à la visibilité.",
            "S’arrêter immédiatement si la visibilité est perdue."
        ],
        "recommendations_en": [
            "Baliser et éclairer la trajectoire de nuit.",
            "Adapter la vitesse à la visibilité.",
            "S’arrêter immédiatement si la visibilité est perdue."
        ]
    },
    {
        "id": "conditions_météo_difficiles",
        "category_fr": "ZONE DE TOURNAGE",
        "category_en": "SHOOTING AREA",
        "title_fr": "Conditions météo difficiles",
        "title_en": "Adverse Weather Conditions",
        "level": "standard",
        "description_fr": "La pluie, le vent fort ou le froid rendent les planchers glissants, gênent le pilotage et fatiguent les personnes exposées.",
        "description_en": "La pluie, le vent fort ou le froid rendent les planchers glissants, gênent le pilotage et fatiguent les personnes exposées.",
        "recommendations_fr": [
            "Adapter ou suspendre le roulage selon la météo.",
            "Essuyer les planchers mouillés avant chaque prise.",
            "Équiper les personnes exposées selon la météo."
        ],
        "recommendations_en": [
            "Adapter ou suspendre le roulage selon la météo.",
            "Essuyer les planchers mouillés avant chaque prise.",
            "Équiper les personnes exposées selon la météo."
        ]
    },
    {
        "id": "sortie_de_trajectoire_du_véhicule_de_jeu",
        "category_fr": "ZONE DE TOURNAGE",
        "category_en": "SHOOTING AREA",
        "title_fr": "Sortie de trajectoire du véhicule de jeu",
        "title_en": "Picture Vehicle Deviating from Trajectory",
        "level": "standard",
        "description_fr": "Un véhicule de jeu peut déraper ou sortir de sa trajectoire, surtout dans les virages et sur sol mouillé, et heurter l’équipe ou le matériel en bord de trajectoire.",
        "description_en": "Un véhicule de jeu peut déraper ou sortir de sa trajectoire, surtout dans les virages et sur sol mouillé, et heurter l’équipe ou le matériel en bord de trajectoire.",
        "recommendations_fr": [
            "Ne placer aucune personne ni caméra avec opérateur à l’extérieur des virages ou dans les zones de dérapage.",
            "Utiliser des caméras sans opérateur ou des protections à ces endroits.",
            "Choisir une trajectoire avec des zones de dégagement.",
            "Interdire l’accès aux piétons dans les virages et les zones de manœuvres rapides."
        ],
        "recommendations_en": [
            "Ne placer aucune personne ni caméra avec opérateur à l’extérieur des virages ou dans les zones de dérapage.",
            "Utiliser des caméras sans opérateur ou des protections à ces endroits.",
            "Choisir une trajectoire avec des zones de dégagement.",
            "Interdire l’accès aux piétons dans les virages et les zones de manœuvres rapides."
        ]
    },
    {
        "id": "obstacles_en_hauteur_et_lignes_électriqu",
        "category_fr": "ZONE DE TOURNAGE",
        "category_en": "SHOOTING AREA",
        "title_fr": "Obstacles en hauteur et lignes électriques",
        "title_en": "Overhead Obstacles and Power Lines",
        "level": "standard",
        "description_fr": "Une potence, un bras ou une caméra qui dépasse du véhicule peut heurter un obstacle en hauteur ou sur le côté, ou s’approcher d’une ligne électrique.",
        "description_en": "Une potence, un bras ou une caméra qui dépasse du véhicule peut heurter un obstacle en hauteur ou sur le côté, ou s’approcher d’une ligne électrique.",
        "recommendations_fr": [
            "Repérer les obstacles en hauteur et sur les côtés de la trajectoire.",
            "Garder une distance de sécurité adaptée avec les lignes électriques.",
            "Près des arbres, surveiller les branches qui peuvent entrer dans la cabine."
        ],
        "recommendations_en": [
            "Repérer les obstacles en hauteur et sur les côtés de la trajectoire.",
            "Garder une distance de sécurité adaptée avec les lignes électriques.",
            "Près des arbres, surveiller les branches qui peuvent entrer dans la cabine."
        ]
    },
    {
        "id": "mauvaise_communication",
        "category_fr": "COORDINATION",
        "category_en": "COORDINATION",
        "title_fr": "Mauvaise communication",
        "title_en": "Poor Communication",
        "level": "standard",
        "description_fr": "Un ordre de départ ou d’arrêt mal compris entre le pilote, l’opérateur et la mise en scène peut provoquer un mouvement imprévu.",
        "description_en": "Un ordre de départ ou d’arrêt mal compris entre le pilote, l’opérateur et la mise en scène peut provoquer un mouvement imprévu.",
        "recommendations_fr": [
            "Faire un safety meeting avant chaque plan.",
            "Désigner une seule personne pour donner les ordres de départ et d’arrêt.",
            "Garder une liaison radio permanente avec le pilote.",
            "Convenir d’un mot d’arrêt connu de toute l’équipe.",
            "Fixer à l’avance le point d’arrêt de chaque prise et le faire connaître à tous.",
            "Lors d’un dépassement, laisser le pilote qui dépasse décider du moment."
        ],
        "recommendations_en": [
            "Faire un safety meeting avant chaque plan.",
            "Désigner une seule personne pour donner les ordres de départ et d’arrêt.",
            "Garder une liaison radio permanente avec le pilote.",
            "Convenir d’un mot d’arrêt connu de toute l’équipe.",
            "Fixer à l’avance le point d’arrêt de chaque prise et le faire connaître à tous.",
            "Lors d’un dépassement, laisser le pilote qui dépasse décider du moment."
        ]
    },
    {
        "id": "plan_modifié_sans_répétition",
        "category_fr": "COORDINATION",
        "category_en": "COORDINATION",
        "title_fr": "Plan modifié sans répétition",
        "title_en": "Shot Modified Without Rehearsal",
        "level": "standard",
        "description_fr": "Un changement de trajectoire, de vitesse ou de configuration décidé au dernier moment augmente le risque d’erreur.",
        "description_en": "Un changement de trajectoire, de vitesse ou de configuration décidé au dernier moment augmente le risque d’erreur.",
        "recommendations_fr": [
            "Répéter à basse vitesse toute modification de trajectoire, de vitesse ou de configuration.",
            "Laisser au pilote et aux techniciens formés par Belle Vitesse le droit de refuser ou d’interrompre un mouvement.",
            "Refaire un safety meeting dès que la chorégraphie, les véhicules ou les personnes changent.",
            "Réévaluer les risques dès que les conditions changent."
        ],
        "recommendations_en": [
            "Répéter à basse vitesse toute modification de trajectoire, de vitesse ou de configuration.",
            "Laisser au pilote et aux techniciens formés par Belle Vitesse le droit de refuser ou d’interrompre un mouvement.",
            "Refaire un safety meeting dès que la chorégraphie, les véhicules ou les personnes changent.",
            "Réévaluer les risques dès que les conditions changent."
        ]
    },
    {
        "id": "fatigue_et_pression_du_tournage",
        "category_fr": "COORDINATION",
        "category_en": "COORDINATION",
        "title_fr": "Fatigue et pression du tournage",
        "title_en": "Fatigue and Shoot Pressure",
        "level": "standard",
        "description_fr": "L’enchaînement des prises et la pression du planning peuvent réduire la vigilance du pilote et de l’équipe.",
        "description_en": "L’enchaînement des prises et la pression du planning peuvent réduire la vigilance du pilote et de l’équipe.",
        "recommendations_fr": [
            "Prévoir des pauses régulières pour le pilote.",
            "Ne jamais réduire le temps de répétition ou de mise en place pour gagner du temps.",
            "Découper l’action en plans courts."
        ],
        "recommendations_en": [
            "Prévoir des pauses régulières pour le pilote.",
            "Ne jamais réduire le temps de répétition ou de mise en place pour gagner du temps.",
            "Découper l’action en plans courts."
        ]
    },
    {
        "id": "pilote_du_véhicule_de_jeu_inexpérimenté",
        "category_fr": "COORDINATION",
        "category_en": "COORDINATION",
        "title_fr": "Pilote du véhicule de jeu inexpérimenté",
        "title_en": "Inexperienced Picture Vehicle Driver",
        "level": "standard",
        "description_fr": "Un acteur ou un pilote non spécialisé au volant du véhicule de jeu peut perdre le contrôle ou mal réagir.",
        "description_en": "Un acteur ou un pilote non spécialisé au volant du véhicule de jeu peut perdre le contrôle ou mal réagir.",
        "recommendations_fr": [
            "Vérifier que le pilote du véhicule de jeu maîtrise ce qui lui est demandé.",
            "Ne jamais le pousser au‑delà de ses capacités.",
            "Prévoir un temps de répétition suffisant."
        ],
        "recommendations_en": [
            "Vérifier que le pilote du véhicule de jeu maîtrise ce qui lui est demandé.",
            "Ne jamais le pousser au‑delà de ses capacités.",
            "Prévoir un temps de répétition suffisant."
        ]
    },
    {
        "id": "équipe_au_sol_près_d_un_véhicule_silenci",
        "category_fr": "PERSONNES À BORD ET AUTOUR DU VÉHICULE",
        "category_en": "PEOPLE ON BOARD AND AROUND THE VEHICLE",
        "title_fr": "Équipe au sol près d’un véhicule silencieux",
        "title_en": "Ground Crew Near a Silent Vehicle",
        "level": "major",
        "description_fr": "Les membres de l’équipe à pied (assistants, perchman, machinistes), concentrés sur leur travail, peuvent ne pas voir le véhicule arriver. Électriques, les véhicules Belle Vitesse sont presque silencieux : l’équipe peut aussi ne pas les entendre, et être heurtée.",
        "description_en": "Les membres de l’équipe à pied (assistants, perchman, machinistes), concentrés sur leur travail, peuvent ne pas voir le véhicule arriver. Électriques, les véhicules Belle Vitesse sont presque silencieux : l’équipe peut aussi ne pas les entendre, et être heurtée.",
        "recommendations_fr": [
            "Donner deux coups de klaxon avant chaque démarrage et un coup de klaxon à chaque arrêt.",
            "Prévenir l’équipe par radio avant chaque départ.",
            "Définir des positions fixes pour l’équipe au sol, hors trajectoire.",
            "Rouler au pas dans les zones où circule l’équipe.",
            "Respecter une distance de sécurité adaptée."
        ],
        "recommendations_en": [
            "Donner deux coups de klaxon avant chaque démarrage et un coup de klaxon à chaque arrêt.",
            "Prévenir l’équipe par radio avant chaque départ.",
            "Définir des positions fixes pour l’équipe au sol, hors trajectoire.",
            "Rouler au pas dans les zones où circule l’équipe.",
            "Respecter une distance de sécurité adaptée."
        ]
    },
    {
        "id": "montée_ou_descente_en_mouvement",
        "category_fr": "PERSONNES À BORD ET AUTOUR DU VÉHICULE",
        "category_en": "PEOPLE ON BOARD AND AROUND THE VEHICLE",
        "title_fr": "Montée ou descente en mouvement",
        "title_en": "Mounting or Dismounting While in Motion",
        "level": "standard",
        "description_fr": "Monter ou descendre d’un véhicule en mouvement peut provoquer une chute ou un écrasement.",
        "description_en": "Monter ou descendre d’un véhicule en mouvement peut provoquer une chute ou un écrasement.",
        "recommendations_fr": [
            "Ne jamais monter ni descendre tant que le véhicule n’est pas à l’arrêt complet.",
            "À l’arrêt, monter ou descendre seulement sur instruction du pilote."
        ],
        "recommendations_en": [
            "Ne jamais monter ni descendre tant que le véhicule n’est pas à l’arrêt complet.",
            "À l’arrêt, monter ou descendre seulement sur instruction du pilote."
        ]
    },
    {
        "id": "passagers_non_informés",
        "category_fr": "PERSONNES À BORD ET AUTOUR DU VÉHICULE",
        "category_en": "PEOPLE ON BOARD AND AROUND THE VEHICLE",
        "title_fr": "Passagers non informés",
        "title_en": "Uninformed Passengers",
        "level": "standard",
        "description_fr": "Une personne qui monte à bord sans connaître les consignes peut se mettre en danger ou mettre les autres en danger.",
        "description_en": "Une personne qui monte à bord sans connaître les consignes peut se mettre en danger ou mettre les autres en danger.",
        "recommendations_fr": [
            "Faire un safety meeting avant la première montée de toute nouvelle personne.",
            "Réserver l’accès à bord aux personnes concernées et habilitées.",
            "Ne faire monter que les personnes indispensables au plan.",
            "Consulter le manuel officiel du véhicule, disponible à bord et via un QR code (eCar, eRider, eRover, eTrike et Segway)."
        ],
        "recommendations_en": [
            "Faire un safety meeting avant la première montée de toute nouvelle personne.",
            "Réserver l’accès à bord aux personnes concernées et habilitées.",
            "Ne faire monter que les personnes indispensables au plan.",
            "Consulter le manuel officiel du véhicule, disponible à bord et via un QR code (eCar, eRider, eRover, eTrike et Segway)."
        ]
    },
    {
        "id": "opérateur_debout_ou_penché_hors_du_véhic",
        "category_fr": "PERSONNES À BORD ET AUTOUR DU VÉHICULE",
        "category_en": "PEOPLE ON BOARD AND AROUND THE VEHICLE",
        "title_fr": "Opérateur debout ou penché hors du véhicule",
        "title_en": "Operator Standing or Leaning Out of Vehicle",
        "level": "standard",
        "description_fr": "Un opérateur qui se lève ou se penche pour cadrer peut être éjecté ou heurter un obstacle.",
        "description_en": "Un opérateur qui se lève ou se penche pour cadrer peut être éjecté ou heurter un obstacle.",
        "recommendations_fr": [
            "Rester assis et attaché pendant le roulage.",
            "Garder les pieds sur le plancher ou le cale‑pied.",
            "Ne jamais sortir du gabarit du véhicule.",
            "Ne jamais s’asseoir sur les rambardes de sécurité.",
            "Utiliser une caméra télécommandée quand la position est trop exposée pour un opérateur."
        ],
        "recommendations_en": [
            "Rester assis et attaché pendant le roulage.",
            "Garder les pieds sur le plancher ou le cale‑pied.",
            "Ne jamais sortir du gabarit du véhicule.",
            "Ne jamais s’asseoir sur les rambardes de sécurité.",
            "Utiliser une caméra télécommandée quand la position est trop exposée pour un opérateur."
        ]
    },
    {
        "id": "pilote_gêné_ou_distrait",
        "category_fr": "PERSONNES À BORD ET AUTOUR DU VÉHICULE",
        "category_en": "PEOPLE ON BOARD AND AROUND THE VEHICLE",
        "title_fr": "Pilote gêné ou distrait",
        "title_en": "Driver Obstructed or Distracted",
        "level": "standard",
        "description_fr": "Un opérateur ou du matériel placé dans le champ de vision du pilote, ou les gestes et les demandes d’une personne à bord, peuvent gêner le pilote ou détourner son attention.",
        "description_en": "Un opérateur ou du matériel placé dans le champ de vision du pilote, ou les gestes et les demandes d’une personne à bord, peuvent gêner le pilote ou détourner son attention.",
        "recommendations_fr": [
            "Ne placer aucun matériel ni opérateur dans le champ de vision du pilote.",
            "Ne jamais gêner le pilote par des gestes ou des demandes pendant le roulage."
        ],
        "recommendations_en": [
            "Ne placer aucun matériel ni opérateur dans le champ de vision du pilote.",
            "Ne jamais gêner le pilote par des gestes ou des demandes pendant le roulage."
        ]
    },
    {
        "id": "matériel_mal_fixé_ou_mal_rangé",
        "category_fr": "MATÉRIEL",
        "category_en": "EQUIPMENT",
        "title_fr": "Matériel mal fixé ou mal rangé",
        "title_en": "Improperly Secured or Stored Equipment",
        "level": "standard",
        "description_fr": "Une caméra ou un accessoire mal fixé peut se détacher sous l’effet des vibrations et des freinages, et un câble ou une sangle mal rangé peut se prendre dans les roues ou faire trébucher l’équipe.",
        "description_en": "Une caméra ou un accessoire mal fixé peut se détacher sous l’effet des vibrations et des freinages, et un câble ou une sangle mal rangé peut se prendre dans les roues ou faire trébucher l’équipe.",
        "recommendations_fr": [
            "Élinguer et sécuriser tout élément technique.",
            "Faire valider chaque installation par un technicien formé par Belle Vitesse.",
            "Vérifier les serrages avant chaque roulage.",
            "Placer le matériel pour qu’il ne puisse pas heurter un occupant en cas d’arrêt brusque.",
            "Attacher tous les câbles et sangles le long de la structure, et ne rien laisser traîner au sol ni près des roues.",
            "Faire vérifier le véhicule par le pilote après chaque changement de machinerie.",
            "Ranger dans le véhicule suiveur le matériel inutile au plan."
        ],
        "recommendations_en": [
            "Élinguer et sécuriser tout élément technique.",
            "Faire valider chaque installation par un technicien formé par Belle Vitesse.",
            "Vérifier les serrages avant chaque roulage.",
            "Placer le matériel pour qu’il ne puisse pas heurter un occupant en cas d’arrêt brusque.",
            "Attacher tous les câbles et sangles le long de la structure, et ne rien laisser traîner au sol ni près des roues.",
            "Faire vérifier le véhicule par le pilote après chaque changement de machinerie.",
            "Ranger dans le véhicule suiveur le matériel inutile au plan."
        ]
    }
]

# ── 2. Risques Spécifiques par Famille de Véhicules (Défaut FR / EN) ──
DEFAULT_VEHICLE_RISK_ASSESSMENT = {
    "erover": {
        "label": "eRover (Polaris Kinetic)",
        "keywords": ["erover", "polaris", "kinetic", "rover", "buggy"],
        "risks": [
        {
                "id": "circulation_sur_voie_ouverte",
                "category_fr": "CIRCULATION SUR VOIE OUVERTE",
                "category_en": "DRIVING ON PUBLIC OPEN ROADS",
                "title_fr": "Circulation sur voie ouverte",
                "title_en": "Driving on Public Open Roads",
                "level": "major",
                "description_fr": "Modifié pour la prise de vue, l’eRover n’est pas homologué pour circuler sur une voie ouverte au public. Un accident sur la route peut provoquer des blessures graves et ne pas être couvert par l’assurance.",
                "description_en": "Modifié pour la prise de vue, l’eRover n’est pas homologué pour circuler sur une voie ouverte au public. Un accident sur la route peut provoquer des blessures graves et ne pas être couvert par l’assurance.",
                "recommendations_fr": [
                        "Ne jamais faire circuler l’eRover sur une voie ouverte au public, y compris pour se déplacer entre deux décors. Tout manquement engage la seule responsabilité de la production.",
                        "Déplacer l’eRover entre deux décors sur une voie fermée à la circulation, ou par transport sur plateau ou remorque."
                ],
                "recommendations_en": [
                        "Ne jamais faire circuler l’eRover sur une voie ouverte au public, y compris pour se déplacer entre deux décors. Tout manquement engage la seule responsabilité de la production.",
                        "Déplacer l’eRover entre deux décors sur une voie fermée à la circulation, ou par transport sur plateau ou remorque."
                ]
        },
        {
                "id": "collision_avec_le_sujet_filmé",
                "category_fr": "COLLISIONS ET CHUTES",
                "category_en": "COLLISIONS AND FALLS",
                "title_fr": "Collision avec le sujet filmé",
                "title_en": "Collision with Filmed Subject",
                "level": "major",
                "description_fr": "Quand l’eRover suit le sujet filmé (acteur, cycliste, véhicule de jeu), une chute ou un freinage inattendu du sujet peut provoquer une collision. Quand le sujet suit l’eRover, c’est un freinage inattendu ou une mauvaise gestion de la vitesse de l’eRover qui peut la provoquer. Dans les deux cas, la collision peut causer des blessures graves.",
                "description_en": "Quand l’eRover suit le sujet filmé (acteur, cycliste, véhicule de jeu), une chute ou un freinage inattendu du sujet peut provoquer une collision. Quand le sujet suit l’eRover, c’est un freinage inattendu ou une mauvaise gestion de la vitesse de l’eRover qui peut la provoquer. Dans les deux cas, la collision peut causer des blessures graves.",
                "recommendations_fr": [
                        "Rouler à une vitesse régulière et éviter tout freinage brusque hors urgence.",
                        "Respecter une distance de sécurité adaptée à la vitesse et à la distance de freinage.",
                        "Répéter le plan à basse vitesse avant de tourner.",
                        "Schématiser les trajectoires complexes.",
                        "Garder une communication constante avec la mise en scène, le coordinateur cascade et le responsable du blocage."
                ],
                "recommendations_en": [
                        "Rouler à une vitesse régulière et éviter tout freinage brusque hors urgence.",
                        "Respecter une distance de sécurité adaptée à la vitesse et à la distance de freinage.",
                        "Répéter le plan à basse vitesse avant de tourner.",
                        "Schématiser les trajectoires complexes.",
                        "Garder une communication constante avec la mise en scène, le coordinateur cascade et le responsable du blocage."
                ]
        },
        {
                "id": "choc_contre_la_structure_du_véhicule",
                "category_fr": "COLLISIONS ET CHUTES",
                "category_en": "COLLISIONS AND FALLS",
                "title_fr": "Choc contre la structure du véhicule",
                "title_en": "Impact Against Vehicle Structure",
                "level": "standard",
                "description_fr": "L’eRover est équipé de plaques en aluminium sur un châssis renforcé en acier, de planchers d’extension et de cale‑pieds. Cette structure ne se déforme pas à l’impact, et la machinerie installée augmente le gabarit du véhicule : même à basse vitesse, un choc peut provoquer des blessures graves.",
                "description_en": "L’eRover est équipé de plaques en aluminium sur un châssis renforcé en acier, de planchers d’extension et de cale‑pieds. Cette structure ne se déforme pas à l’impact, et la machinerie installée augmente le gabarit du véhicule : même à basse vitesse, un choc peut provoquer des blessures graves.",
                "recommendations_fr": [
                        "Toujours installer les pare‑chocs en caoutchouc fournis sur les planchers d’extension et les cale‑pieds.",
                        "Faire valider chaque nouvelle installation par un technicien formé par Belle Vitesse.",
                        "Prendre en compte le gabarit réel dans le schéma des trajectoires et pendant la répétition.",
                        "Faire définir et sécuriser la zone de roulage par la production avant chaque plan.",
                        "Respecter une distance de sécurité adaptée avec toute personne."
                ],
                "recommendations_en": [
                        "Toujours installer les pare‑chocs en caoutchouc fournis sur les planchers d’extension et les cale‑pieds.",
                        "Faire valider chaque nouvelle installation par un technicien formé par Belle Vitesse.",
                        "Prendre en compte le gabarit réel dans le schéma des trajectoires et pendant la répétition.",
                        "Faire définir et sécuriser la zone de roulage par la production avant chaque plan.",
                        "Respecter une distance de sécurité adaptée avec toute personne."
                ]
        },
        {
                "id": "choc_lors_des_freinages_d_urgence",
                "category_fr": "COLLISIONS ET CHUTES",
                "category_en": "COLLISIONS AND FALLS",
                "title_fr": "Choc lors des freinages d’urgence",
                "title_en": "Impact During Emergency Braking",
                "level": "major",
                "description_fr": "Lors d’un freinage d’urgence, les passagers peuvent être violemment projetés contre le véhicule ou contre la machinerie installée pour le plan.",
                "description_en": "Lors d’un freinage d’urgence, les passagers peuvent être violemment projetés contre le véhicule ou contre la machinerie installée pour le plan.",
                "recommendations_fr": [
                        "Imposer la ceinture à toute personne à bord, et le casque et la double ceinture à toute personne à l’extérieur de l’habitacle.",
                        "Dans l’habitacle, garder le dos contre le siège et les pieds à plat.",
                        "Utiliser les filets ou les portes de la cabine, et vérifier ceintures, filets et attaches avant chaque utilisation.",
                        "Ne jamais se tenir à l’arceau ni s’appuyer sur les portes ou les filets.",
                        "Placer le matériel pour qu’il ne puisse pas heurter un occupant.",
                        "Répéter le plan à basse vitesse pour limiter les freinages imprévus.",
                        "Respecter les seuils de vitesse fixés dans les règles de sécurité pour les personnes à l’extérieur de l’habitacle."
                ],
                "recommendations_en": [
                        "Imposer la ceinture à toute personne à bord, et le casque et la double ceinture à toute personne à l’extérieur de l’habitacle.",
                        "Dans l’habitacle, garder le dos contre le siège et les pieds à plat.",
                        "Utiliser les filets ou les portes de la cabine, et vérifier ceintures, filets et attaches avant chaque utilisation.",
                        "Ne jamais se tenir à l’arceau ni s’appuyer sur les portes ou les filets.",
                        "Placer le matériel pour qu’il ne puisse pas heurter un occupant.",
                        "Répéter le plan à basse vitesse pour limiter les freinages imprévus.",
                        "Respecter les seuils de vitesse fixés dans les règles de sécurité pour les personnes à l’extérieur de l’habitacle."
                ]
        },
        {
                "id": "pied_coincé_dans_une_roue_avant",
                "category_fr": "ROUES",
                "category_en": "WHEELS",
                "title_fr": "Pied coincé dans une roue avant",
                "title_en": "Foot Trapped in Front Wheel",
                "level": "major",
                "description_fr": "Les roues avant sont exposées pour laisser la direction libre. Un passager installé trop près peut, par inattention, coincer son pied entre la roue et le châssis et se blesser gravement.",
                "description_en": "Les roues avant sont exposées pour laisser la direction libre. Un passager installé trop près peut, par inattention, coincer son pied entre la roue et le châssis et se blesser gravement.",
                "recommendations_fr": [
                        "Ne jamais installer quelqu’un trop près des roues avant.",
                        "Sécuriser au maximum toute personne installée à l’avant, pour qu’aucun membre ne puisse atteindre une roue.",
                        "Imposer la ceinture à toute personne à bord."
                ],
                "recommendations_en": [
                        "Ne jamais installer quelqu’un trop près des roues avant.",
                        "Sécuriser au maximum toute personne installée à l’avant, pour qu’aucun membre ne puisse atteindre une roue.",
                        "Imposer la ceinture à toute personne à bord."
                ]
        },
        {
                "id": "vêtement_entraîné_dans_les_roues",
                "category_fr": "ROUES",
                "category_en": "WHEELS",
                "title_fr": "Vêtement entraîné dans les roues",
                "title_en": "Clothing or Object Caught in Wheels",
                "level": "standard",
                "description_fr": "Une écharpe ou un vêtement ample peut être entraîné dans les roues et entraîner la personne qui le porte.",
                "description_en": "Une écharpe ou un vêtement ample peut être entraîné dans les roues et entraîner la personne qui le porte.",
                "recommendations_fr": [
                        "Retirer ou attacher les écharpes et vêtements amples avant tout roulage."
                ],
                "recommendations_en": [
                        "Retirer ou attacher les écharpes et vêtements amples avant tout roulage."
                ]
        },
        {
                "id": "chute_du_véhicule_lors_d_un_levage",
                "category_fr": "ROUES",
                "category_en": "WHEELS",
                "title_fr": "Chute du véhicule lors d’un levage",
                "title_en": "Vehicle Drop During Hoisting",
                "level": "standard",
                "description_fr": "Pendant un changement de roue, un véhicule mal calé ou mal soutenu peut tomber ou basculer.",
                "description_en": "Pendant un changement de roue, un véhicule mal calé ou mal soutenu peut tomber ou basculer.",
                "recommendations_fr": [
                        "Réserver le levage du véhicule aux techniciens formés par Belle Vitesse.",
                        "Lever le véhicule uniquement sur un sol plat et dur, en position P, roues calées.",
                        "Utiliser un cric adapté et ne jamais passer sous le véhicule sans chandelles."
                ],
                "recommendations_en": [
                        "Réserver le levage du véhicule aux techniciens formés par Belle Vitesse.",
                        "Lever le véhicule uniquement sur un sol plat et dur, en position P, roues calées.",
                        "Utiliser un cric adapté et ne jamais passer sous le véhicule sans chandelles."
                ]
        },
        {
                "id": "retournement",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Retournement",
                "title_en": "Vehicle Rollover",
                "level": "major",
                "description_fr": "L’eRover peut se retourner dans un virage pris trop vite ou trop serré, même sur terrain plat. Sur goudron, la forte adhérence augmente ce risque.",
                "description_en": "L’eRover peut se retourner dans un virage pris trop vite ou trop serré, même sur terrain plat. Sur goudron, la forte adhérence augmente ce risque.",
                "recommendations_fr": [
                        "Réduire la vitesse avant chaque virage, en particulier sur goudron, et éviter les manœuvres brusques, les glissades, les dérapages et les fortes accélérations en virage, même au départ arrêté.",
                        "Anticiper les pentes, les ornières et les changements d’adhérence. En pente, rouler droit, en transmission intégrale (AWD), jamais au point mort ni en travers.",
                        "Ne jamais sauter de bosse.",
                        "Respecter le nombre maximum de personnes à bord (1 pilote et 3 passagers) et répartir le poids de façon cohérente.",
                        "Régler le limiteur de vitesse (SPD LIM) selon le plan à chaque démarrage, car il se désactive à l’arrêt du contact (le véhicule reste bridé à 60 km/h en France).",
                        "Si le véhicule bascule, se tenir fermement aux poignées et ne sortir aucune partie du corps du véhicule.",
                        "Après un retournement ou un choc, ne pas reprendre le roulage avant une inspection complète (ceintures, arceau, freins, direction, système électrique)."
                ],
                "recommendations_en": [
                        "Réduire la vitesse avant chaque virage, en particulier sur goudron, et éviter les manœuvres brusques, les glissades, les dérapages et les fortes accélérations en virage, même au départ arrêté.",
                        "Anticiper les pentes, les ornières et les changements d’adhérence. En pente, rouler droit, en transmission intégrale (AWD), jamais au point mort ni en travers.",
                        "Ne jamais sauter de bosse.",
                        "Respecter le nombre maximum de personnes à bord (1 pilote et 3 passagers) et répartir le poids de façon cohérente.",
                        "Régler le limiteur de vitesse (SPD LIM) selon le plan à chaque démarrage, car il se désactive à l’arrêt du contact (le véhicule reste bridé à 60 km/h en France).",
                        "Si le véhicule bascule, se tenir fermement aux poignées et ne sortir aucune partie du corps du véhicule.",
                        "Après un retournement ou un choc, ne pas reprendre le roulage avant une inspection complète (ceintures, arceau, freins, direction, système électrique)."
                ]
        },
        {
                "id": "accélérations_et_pédales",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Accélérations et pédales",
                "title_en": "Throttle and Pedal Response",
                "level": "standard",
                "description_fr": "Le jeu entre la pédale de frein et l’accélérateur peut provoquer des à‑coups, et l’eRover peut continuer à accélérer légèrement après le relâchement de l’accélérateur. Le mode Sport rend les accélérations très vives et le véhicule difficile à contrôler.",
                "description_en": "Le jeu entre la pédale de frein et l’accélérateur peut provoquer des à‑coups, et l’eRover peut continuer à accélérer légèrement après le relâchement de l’accélérateur. Le mode Sport rend les accélérations très vives et le véhicule difficile à contrôler.",
                "recommendations_fr": [
                        "Confier la conduite uniquement à un pilote validé par Belle Vitesse ou mandaté par le coordinateur cascade.",
                        "Ne jamais appuyer sur les deux pédales en même temps, ce qui peut couper la puissance moteur.",
                        "Anticiper les freinages et tenir compte des distances de freinage.",
                        "Ne pas utiliser le mode Sport, sauf validation par un technicien formé par Belle Vitesse.",
                        "Répéter le plan à basse vitesse."
                ],
                "recommendations_en": [
                        "Confier la conduite uniquement à un pilote validé par Belle Vitesse ou mandaté par le coordinateur cascade.",
                        "Ne jamais appuyer sur les deux pédales en même temps, ce qui peut couper la puissance moteur.",
                        "Anticiper les freinages et tenir compte des distances de freinage.",
                        "Ne pas utiliser le mode Sport, sauf validation par un technicien formé par Belle Vitesse.",
                        "Répéter le plan à basse vitesse."
                ]
        },
        {
                "id": "mouvement_imprévu_du_véhicule",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Mouvement imprévu du véhicule",
                "title_en": "Unexpected Vehicle Movement",
                "level": "standard",
                "description_fr": "Un mauvais choix de sens de marche (F/R) peut faire partir le véhicule dans la direction opposée à celle prévue. À l’arrêt, la légère souplesse du frein à main peut le laisser avancer ou reculer d’environ 20 cm.",
                "description_en": "Un mauvais choix de sens de marche (F/R) peut faire partir le véhicule dans la direction opposée à celle prévue. À l’arrêt, la légère souplesse du frein à main peut le laisser avancer ou reculer d’environ 20 cm.",
                "recommendations_fr": [
                        "Vérifier la position du sélecteur F/R avant chaque départ.",
                        "Ne jamais changer de sens en roulant.",
                        "En marche arrière, vérifier que la zone est dégagée, accélérer doucement et rouler lentement.",
                        "Toujours passer en position P à l’arrêt.",
                        "Sur une pente, caler les roues arrière côté descente.",
                        "Retirer la clé quand le véhicule est laissé seul.",
                        "Ne jamais se placer juste devant ou derrière le véhicule à l’arrêt."
                ],
                "recommendations_en": [
                        "Vérifier la position du sélecteur F/R avant chaque départ.",
                        "Ne jamais changer de sens en roulant.",
                        "En marche arrière, vérifier que la zone est dégagée, accélérer doucement et rouler lentement.",
                        "Toujours passer en position P à l’arrêt.",
                        "Sur une pente, caler les roues arrière côté descente.",
                        "Retirer la clé quand le véhicule est laissé seul.",
                        "Ne jamais se placer juste devant ou derrière le véhicule à l’arrêt."
                ]
        },
        {
                "id": "passage_dans_l_eau",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Passage dans l’eau",
                "title_en": "Water Fording",
                "level": "standard",
                "description_fr": "Une eau trop profonde ou un courant peut faire perdre l’adhérence et le contrôle du véhicule. Après un passage dans l’eau, les freins mouillés sont moins efficaces.",
                "description_en": "Une eau trop profonde ou un courant peut faire perdre l’adhérence et le contrôle du véhicule. Après un passage dans l’eau, les freins mouillés sont moins efficaces.",
                "recommendations_fr": [
                        "Ne jamais rouler dans une eau qui dépasse le plancher ou dans un courant.",
                        "Après un passage dans l’eau, tester les freins en roulant lentement."
                ],
                "recommendations_en": [
                        "Ne jamais rouler dans une eau qui dépasse le plancher ou dans un courant.",
                        "Après un passage dans l’eau, tester les freins en roulant lentement."
                ]
        },
        {
                "id": "perte_de_puissance",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Perte de puissance",
                "title_en": "Loss of Power",
                "level": "standard",
                "description_fr": "Une batterie faible, une surchauffe du moteur ou de la batterie, des températures extrêmes ou de l’eau dans les composants électriques peuvent réduire la puissance ou arrêter le véhicule en pleine prise.",
                "description_en": "Une batterie faible, une surchauffe du moteur ou de la batterie, des températures extrêmes ou de l’eau dans les composants électriques peuvent réduire la puissance ou arrêter le véhicule en pleine prise.",
                "recommendations_fr": [
                        "Commencer chaque plan avec une batterie suffisamment chargée, et recharger pendant les pauses.",
                        "Arrêter les prises et ramener le véhicule dès l’alerte LOW CHARGE ou le voyant de surchauffe.",
                        "Par grand froid, laisser chauffer la batterie quelques minutes avant de rouler.",
                        "Garder une distance de sécurité adaptée avec les véhicules qui suivent, pour absorber un arrêt imprévu."
                ],
                "recommendations_en": [
                        "Commencer chaque plan avec une batterie suffisamment chargée, et recharger pendant les pauses.",
                        "Arrêter les prises et ramener le véhicule dès l’alerte LOW CHARGE ou le voyant de surchauffe.",
                        "Par grand froid, laisser chauffer la batterie quelques minutes avant de rouler.",
                        "Garder une distance de sécurité adaptée avec les véhicules qui suivent, pour absorber un arrêt imprévu."
                ]
        },
        {
                "id": "défaut_non_détecté_avant_roulage",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Défaut non détecté avant roulage",
                "title_en": "Undetected Defect Before Driving",
                "level": "standard",
                "description_fr": "Un défaut non repéré avant le roulage (pneus, freins, direction, ceintures) augmente le risque d’accident.",
                "description_en": "Un défaut non repéré avant le roulage (pneus, freins, direction, ceintures) augmente le risque d’accident.",
                "recommendations_fr": [
                        "Faire avant chaque journée l’inspection préconisée par Polaris : charge, liquide de frein, direction, suspension, feux et ceintures.",
                        "Vérifier la pression des pneus (83 kPa à l’avant, 97 kPa à l’arrière) et les remplacer sous 3 mm de sculpture.",
                        "Vérifier le serrage des roues et retirer les débris inflammables (herbe, feuilles).",
                        "Inspecter aussi le véhicule après chaque journée.",
                        "Faire réparer tout élément défectueux par un technicien qualifié avant de rouler, et retirer du service tout matériel cassé."
                ],
                "recommendations_en": [
                        "Faire avant chaque journée l’inspection préconisée par Polaris : charge, liquide de frein, direction, suspension, feux et ceintures.",
                        "Vérifier la pression des pneus (83 kPa à l’avant, 97 kPa à l’arrière) et les remplacer sous 3 mm de sculpture.",
                        "Vérifier le serrage des roues et retirer les débris inflammables (herbe, feuilles).",
                        "Inspecter aussi le véhicule après chaque journée.",
                        "Faire réparer tout élément défectueux par un technicien qualifié avant de rouler, et retirer du service tout matériel cassé."
                ]
        },
        {
                "id": "surcharge",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Surcharge",
                "title_en": "Overloading",
                "level": "standard",
                "description_fr": "Le poids de la machinerie, du matériel et des personnes à bord allonge les distances de freinage et augmente le risque de perte de contrôle.",
                "description_en": "Le poids de la machinerie, du matériel et des personnes à bord allonge les distances de freinage et augmente le risque de perte de contrôle.",
                "recommendations_fr": [
                        "Ne jamais dépasser 680 kg de charge totale (pilote, passagers, chargement et accessoires compris).",
                        "Au‑delà de 227 kg de charge totale, rouler en gamme basse (LOW).",
                        "Au‑delà de 249 kg de charge totale, ne pas dépasser 48 km/h.",
                        "Réduire la vitesse et anticiper les freinages quand le véhicule est chargé."
                ],
                "recommendations_en": [
                        "Ne jamais dépasser 680 kg de charge totale (pilote, passagers, chargement et accessoires compris).",
                        "Au‑delà de 227 kg de charge totale, rouler en gamme basse (LOW).",
                        "Au‑delà de 249 kg de charge totale, ne pas dépasser 48 km/h.",
                        "Réduire la vitesse et anticiper les freinages quand le véhicule est chargé."
                ]
        },
        {
                "id": "conduite_imprudente",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Conduite imprudente",
                "title_en": "Reckless Driving",
                "level": "standard",
                "description_fr": "Une conduite imprudente, ou sous l’emprise de l’alcool, de médicaments ou de drogues, peut provoquer un accident grave.",
                "description_en": "Une conduite imprudente, ou sous l’emprise de l’alcool, de médicaments ou de drogues, peut provoquer un accident grave.",
                "recommendations_fr": [
                        "Interdire toute conduite imprudente.",
                        "Interdire le pilotage sous l’emprise de l’alcool, de médicaments ou de drogues.",
                        "Ne pas manipuler l’écran ni régler le volant en roulant."
                ],
                "recommendations_en": [
                        "Interdire toute conduite imprudente.",
                        "Interdire le pilotage sous l’emprise de l’alcool, de médicaments ou de drogues.",
                        "Ne pas manipuler l’écran ni régler le volant en roulant."
                ]
        },
        {
                "id": "défaillance_des_installations_de_machine",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Défaillance des installations de machinerie",
                "title_en": "Grip Rigging Failure",
                "level": "standard",
                "description_fr": "Une installation de machinerie qui cède (tubes, colliers, potence) peut faire chuter le matériel ou les personnes et provoquer des blessures graves.",
                "description_en": "Une installation de machinerie qui cède (tubes, colliers, potence) peut faire chuter le matériel ou les personnes et provoquer des blessures graves.",
                "recommendations_fr": [
                        "Réserver l’installation de la machinerie aux personnes habilitées par Belle Vitesse.",
                        "Faire valider chaque nouvelle installation par un technicien formé par Belle Vitesse.",
                        "Vérifier les serrages avant chaque roulage.",
                        "Imposer le casque à toute personne à l’extérieur de l’habitacle."
                ],
                "recommendations_en": [
                        "Réserver l’installation de la machinerie aux personnes habilitées par Belle Vitesse.",
                        "Faire valider chaque nouvelle installation par un technicien formé par Belle Vitesse.",
                        "Vérifier les serrages avant chaque roulage.",
                        "Imposer le casque à toute personne à l’extérieur de l’habitacle."
                ]
        },
        {
                "id": "glissade_ou_chute_pendant_l_installation",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Glissade ou chute pendant l’installation",
                "title_en": "Slip or Fall During Rigging Setup",
                "level": "standard",
                "description_fr": "Pendant l’installation de la machinerie, une glissade ou une chute depuis le véhicule peut provoquer une blessure grave. L’humidité et l’eau rendent les planchers glissants.",
                "description_en": "Pendant l’installation de la machinerie, une glissade ou une chute depuis le véhicule peut provoquer une blessure grave. L’humidité et l’eau rendent les planchers glissants.",
                "recommendations_fr": [
                        "Préparer le véhicule hors circulation.",
                        "Essuyer les planchers mouillés avant toute installation.",
                        "Réserver l’installation aux personnes habilitées par Belle Vitesse."
                ],
                "recommendations_en": [
                        "Préparer le véhicule hors circulation.",
                        "Essuyer les planchers mouillés avant toute installation.",
                        "Réserver l’installation aux personnes habilitées par Belle Vitesse."
                ]
        },
        {
                "id": "chute_d_objets",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Chute d’objets",
                "title_en": "Falling Objects",
                "level": "standard",
                "description_fr": "Des outils ou du matériel mal sécurisés peuvent tomber pendant le roulage et faire chuter ou heurter le sujet filmé s’il suit l’eRover.",
                "description_en": "Des outils ou du matériel mal sécurisés peuvent tomber pendant le roulage et faire chuter ou heurter le sujet filmé s’il suit l’eRover.",
                "recommendations_fr": [
                        "Élinguer et sécuriser tout élément technique.",
                        "Sécuriser tout matériel supplémentaire (sac batterie, caméra, commande de point).",
                        "Ne laisser aucun outil libre sur le véhicule avant le roulage."
                ],
                "recommendations_en": [
                        "Élinguer et sécuriser tout élément technique.",
                        "Sécuriser tout matériel supplémentaire (sac batterie, caméra, commande de point).",
                        "Ne laisser aucun outil libre sur le véhicule avant le roulage."
                ]
        },
        {
                "id": "électrocution",
                "category_fr": "ÉLECTRICITÉ ET BATTERIE",
                "category_en": "ELECTRICAL SYSTEM & BATTERY",
                "title_fr": "Électrocution",
                "title_en": "Electrocution",
                "level": "standard",
                "description_fr": "Un contact avec la batterie, le chargeur ou les câbles haute tension (orange) peut provoquer une électrocution.",
                "description_en": "Un contact avec la batterie, le chargeur ou les câbles haute tension (orange) peut provoquer une électrocution.",
                "recommendations_fr": [
                        "Réserver toute intervention sur la batterie aux techniciens formés par Belle Vitesse.",
                        "Ne jamais toucher les câbles haute tension, ni ouvrir la batterie ou le chargeur.",
                        "Après un choc ou un retournement, couper la haute tension (boucle de sécurité sous le bac du siège) et faire inspecter le véhicule avant de rouler.",
                        "N’apporter aucune modification interne au véhicule."
                ],
                "recommendations_en": [
                        "Réserver toute intervention sur la batterie aux techniciens formés par Belle Vitesse.",
                        "Ne jamais toucher les câbles haute tension, ni ouvrir la batterie ou le chargeur.",
                        "Après un choc ou un retournement, couper la haute tension (boucle de sécurité sous le bac du siège) et faire inspecter le véhicule avant de rouler.",
                        "N’apporter aucune modification interne au véhicule."
                ]
        },
        {
                "id": "branchement_électrique",
                "category_fr": "ÉLECTRICITÉ ET BATTERIE",
                "category_en": "ELECTRICAL SYSTEM & BATTERY",
                "title_fr": "Branchement électrique",
                "title_en": "Electrical Hookup",
                "level": "standard",
                "description_fr": "Une caméra, un moniteur ou un éclairage branché sur le véhicule, un objet au contact de la batterie 12 V ou une source extérieure peut faire sauter un fusible, couper l’éclairage ou la puissance moteur, ou provoquer un court‑circuit et un départ de feu.",
                "description_en": "Une caméra, un moniteur ou un éclairage branché sur le véhicule, un objet au contact de la batterie 12 V ou une source extérieure peut faire sauter un fusible, couper l’éclairage ou la puissance moteur, ou provoquer un court‑circuit et un départ de feu.",
                "recommendations_fr": [
                        "Respecter la capacité des prises 12 V : 10 A au tableau de bord, 15 A à l’arrière.",
                        "Ne raccorder aucun accessoire au circuit électrique du véhicule sans validation par un technicien formé par Belle Vitesse.",
                        "Ne rien ranger sous le bac du siège, au contact de la batterie 12 V.",
                        "Ne jamais brancher une source extérieure sur la batterie 12 V (pas de démarrage par câbles)."
                ],
                "recommendations_en": [
                        "Respecter la capacité des prises 12 V : 10 A au tableau de bord, 15 A à l’arrière.",
                        "Ne raccorder aucun accessoire au circuit électrique du véhicule sans validation par un technicien formé par Belle Vitesse.",
                        "Ne rien ranger sous le bac du siège, au contact de la batterie 12 V.",
                        "Ne jamais brancher une source extérieure sur la batterie 12 V (pas de démarrage par câbles)."
                ]
        },
        {
                "id": "écrasement_de_la_personne_qui_guide",
                "category_fr": "CHARGEMENT ET TRANSPORT",
                "category_en": "LOADING AND TRANSPORT",
                "title_fr": "Écrasement de la personne qui guide",
                "title_en": "Crushing of Guiding Spotter",
                "level": "major",
                "description_fr": "Pendant le chargement ou le déchargement, la personne qui guide le pilote peut être écrasée si elle se trouve dans l’axe de roulage ou si les rampes glissent.",
                "description_en": "Pendant le chargement ou le déchargement, la personne qui guide le pilote peut être écrasée si elle se trouve dans l’axe de roulage ou si les rampes glissent.",
                "recommendations_fr": [
                        "Charger et décharger à deux : le pilote et une personne qui le guide.",
                        "Ne jamais se trouver dans l’axe de roulage du véhicule.",
                        "Toujours se trouver à plus de 2 m du véhicule.",
                        "Réserver le chargement et le déchargement aux personnes habilitées par Belle Vitesse."
                ],
                "recommendations_en": [
                        "Charger et décharger à deux : le pilote et une personne qui le guide.",
                        "Ne jamais se trouver dans l’axe de roulage du véhicule.",
                        "Toujours se trouver à plus de 2 m du véhicule.",
                        "Réserver le chargement et le déchargement aux personnes habilitées par Belle Vitesse."
                ]
        },
        {
                "id": "glissade_des_rampes",
                "category_fr": "CHARGEMENT ET TRANSPORT",
                "category_en": "LOADING AND TRANSPORT",
                "title_fr": "Glissade des rampes",
                "title_en": "Ramp Slippage",
                "level": "standard",
                "description_fr": "Une rampe non adaptée ou mal fixée peut glisser pendant le chargement ou le déchargement et faire chuter le véhicule.",
                "description_en": "Une rampe non adaptée ou mal fixée peut glisser pendant le chargement ou le déchargement et faire chuter le véhicule.",
                "recommendations_fr": [
                        "Utiliser uniquement les rampes fournies et homologuées.",
                        "Sécuriser les rampes avec des sangles (et des goupilles si disponibles)."
                ],
                "recommendations_en": [
                        "Utiliser uniquement les rampes fournies et homologuées.",
                        "Sécuriser les rampes avec des sangles (et des goupilles si disponibles)."
                ]
        },
        {
                "id": "mouvement_du_véhicule_pendant_le_transpo",
                "category_fr": "CHARGEMENT ET TRANSPORT",
                "category_en": "LOADING AND TRANSPORT",
                "title_fr": "Mouvement du véhicule pendant le transport",
                "title_en": "Vehicle Movement During Transport",
                "level": "standard",
                "description_fr": "Un véhicule mal sanglé peut bouger ou tomber pendant le transport.",
                "description_en": "Un véhicule mal sanglé peut bouger ou tomber pendant le transport.",
                "recommendations_fr": [
                        "Sangler le véhicule en 4 points, 2 à l’avant et 2 à l’arrière, sur les points d’arrimage prévus par Polaris.",
                        "Avant le transport, passer en position P, retirer la clé, et retirer ou sécuriser la machinerie et toute pièce libre.",
                        "Sur une remorque ouverte, charger le véhicule face à la route, ou retirer le toit."
                ],
                "recommendations_en": [
                        "Sangler le véhicule en 4 points, 2 à l’avant et 2 à l’arrière, sur les points d’arrimage prévus par Polaris.",
                        "Avant le transport, passer en position P, retirer la clé, et retirer ou sécuriser la machinerie et toute pièce libre.",
                        "Sur une remorque ouverte, charger le véhicule face à la route, ou retirer le toit."
                ]
        },
        {
                "id": "incendie_pendant_la_recharge",
                "category_fr": "INCENDIE",
                "category_en": "FIRE HAZARDS",
                "title_fr": "Incendie pendant la recharge",
                "title_en": "Fire During Battery Charging",
                "level": "standard",
                "description_fr": "Une recharge sans surveillance, avec un chargeur non adapté, un câble abîmé ou une installation électrique inadaptée peut provoquer un départ de feu.",
                "description_en": "Une recharge sans surveillance, avec un chargeur non adapté, un câble abîmé ou une installation électrique inadaptée peut provoquer un départ de feu.",
                "recommendations_fr": [
                        "Ne jamais laisser le véhicule en charge sans surveillance.",
                        "Recharger uniquement avec le chargeur fourni, branché directement sur une prise protégée par un différentiel, d’au moins 15 A et sans autre appareil.",
                        "Ne jamais utiliser de rallonge, de multiprise ni d’adaptateur.",
                        "Vérifier l’état du câble, des prises et du port de charge avant chaque recharge.",
                        "Sous la pluie, recharger uniquement sur une prise extérieure étanche.",
                        "Recharger loin des matières inflammables, câble placé là où il ne peut pas être écrasé."
                ],
                "recommendations_en": [
                        "Ne jamais laisser le véhicule en charge sans surveillance.",
                        "Recharger uniquement avec le chargeur fourni, branché directement sur une prise protégée par un différentiel, d’au moins 15 A et sans autre appareil.",
                        "Ne jamais utiliser de rallonge, de multiprise ni d’adaptateur.",
                        "Vérifier l’état du câble, des prises et du port de charge avant chaque recharge.",
                        "Sous la pluie, recharger uniquement sur une prise extérieure étanche.",
                        "Recharger loin des matières inflammables, câble placé là où il ne peut pas être écrasé."
                ]
        },
        {
                "id": "incendie_après_un_choc",
                "category_fr": "INCENDIE",
                "category_en": "FIRE HAZARDS",
                "title_fr": "Incendie après un choc",
                "title_en": "Fire Following Impact",
                "level": "standard",
                "description_fr": "Un choc, un retournement ou une infiltration d’eau peut endommager la batterie sans que ce soit visible, et provoquer un feu plusieurs heures après.",
                "description_en": "Un choc, un retournement ou une infiltration d’eau peut endommager la batterie sans que ce soit visible, et provoquer un feu plusieurs heures après.",
                "recommendations_fr": [
                        "Après tout choc, retournement ou passage dans l’eau profonde, faire contrôler la batterie par un technicien formé par Belle Vitesse avant de rouler.",
                        "En cas de doute, garer le véhicule à l’extérieur, loin de tout ce qui peut brûler."
                ],
                "recommendations_en": [
                        "Après tout choc, retournement ou passage dans l’eau profonde, faire contrôler la batterie par un technicien formé par Belle Vitesse avant de rouler.",
                        "En cas de doute, garer le véhicule à l’extérieur, loin de tout ce qui peut brûler."
                ]
        },
        {
                "id": "emballement_thermique",
                "category_fr": "INCENDIE",
                "category_en": "FIRE HAZARDS",
                "title_fr": "Emballement thermique",
                "title_en": "Thermal Runaway",
                "level": "major",
                "description_fr": "Une défaillance de la batterie peut faire monter sa température très vite et provoquer un feu ou une explosion. Un feu de batterie est difficile à éteindre et peut reprendre après avoir été éteint.",
                "description_en": "Une défaillance de la batterie peut faire monter sa température très vite et provoquer un feu ou une explosion. Un feu de batterie est difficile à éteindre et peut reprendre après avoir été éteint.",
                "recommendations_fr": [
                        "En cas de fumée, d’odeur anormale ou d’alerte « DANGER EXIT NOW FIRE » au tableau de bord, arrêter le véhicule et faire descendre tout le monde immédiatement.",
                        "S’éloigner du véhicule et appeler les pompiers (18 ou 112) en précisant qu’il s’agit d’un véhicule électrique.",
                        "Ne jamais tenter d’éteindre soi‑même un feu de batterie déclaré.",
                        "Prévoir à proximité du véhicule un extincteur adapté pour un départ de feu sur les accessoires."
                ],
                "recommendations_en": [
                        "En cas de fumée, d’odeur anormale ou d’alerte « DANGER EXIT NOW FIRE » au tableau de bord, arrêter le véhicule et faire descendre tout le monde immédiatement.",
                        "S’éloigner du véhicule et appeler les pompiers (18 ou 112) en précisant qu’il s’agit d’un véhicule électrique.",
                        "Ne jamais tenter d’éteindre soi‑même un feu de batterie déclaré.",
                        "Prévoir à proximité du véhicule un extincteur adapté pour un départ de feu sur les accessoires."
                ]
        }
]
    },
    "erider": {
        "label": "eRider (Stark Varg)",
        "keywords": ["erider", "stark", "varg", "rider", "moto", "ebike"],
        "risks": [
        {
                "id": "circulation_sur_voie_ouverte",
                "category_fr": "CIRCULATION SUR VOIE OUVERTE",
                "category_en": "DRIVING ON PUBLIC OPEN ROADS",
                "title_fr": "Circulation sur voie ouverte",
                "title_en": "Driving on Public Open Roads",
                "level": "major",
                "description_fr": "Conçu pour les terrains de motocross, le Stark Varg MX 1.2 n’est pas homologué pour circuler sur une voie ouverte au public. Un accident sur la route peut provoquer des blessures graves et ne pas être couvert par l’assurance.",
                "description_en": "Conçu pour les terrains de motocross, le Stark Varg MX 1.2 n’est pas homologué pour circuler sur une voie ouverte au public. Un accident sur la route peut provoquer des blessures graves et ne pas être couvert par l’assurance.",
                "recommendations_fr": [
                        "Ne jamais faire circuler l’eRider sur une voie ouverte au public, y compris pour se déplacer entre deux décors. Tout manquement engage la seule responsabilité de la production.",
                        "Déplacer l’eRider entre deux décors sur une voie fermée à la circulation, ou par transport sur remorque."
                ],
                "recommendations_en": [
                        "Ne jamais faire circuler l’eRider sur une voie ouverte au public, y compris pour se déplacer entre deux décors. Tout manquement engage la seule responsabilité de la production.",
                        "Déplacer l’eRider entre deux décors sur une voie fermée à la circulation, ou par transport sur remorque."
                ]
        },
        {
                "id": "collision_avec_le_sujet_filmé",
                "category_fr": "COLLISIONS ET CHUTES",
                "category_en": "COLLISIONS AND FALLS",
                "title_fr": "Collision avec le sujet filmé",
                "title_en": "Collision with Filmed Subject",
                "level": "major",
                "description_fr": "En travelling rapproché, une erreur de trajectoire ou un arrêt imprévu du sujet filmé (acteur, cycliste, véhicule de jeu) peut provoquer une collision et des blessures graves.",
                "description_en": "En travelling rapproché, une erreur de trajectoire ou un arrêt imprévu du sujet filmé (acteur, cycliste, véhicule de jeu) peut provoquer une collision et des blessures graves.",
                "recommendations_fr": [
                        "Respecter une distance de sécurité adaptée à la vitesse et à la distance de freinage.",
                        "Répéter le plan à basse vitesse avant de tourner.",
                        "Schématiser les trajectoires complexes.",
                        "Garder une communication constante avec la mise en scène, le coordinateur cascade et le responsable du blocage."
                ],
                "recommendations_en": [
                        "Respecter une distance de sécurité adaptée à la vitesse et à la distance de freinage.",
                        "Répéter le plan à basse vitesse avant de tourner.",
                        "Schématiser les trajectoires complexes.",
                        "Garder une communication constante avec la mise en scène, le coordinateur cascade et le responsable du blocage."
                ]
        },
        {
                "id": "obstacle_ou_cascade_dans_la_trajectoire",
                "category_fr": "COLLISIONS ET CHUTES",
                "category_en": "COLLISIONS AND FALLS",
                "title_fr": "Obstacle ou cascade dans la trajectoire",
                "title_en": "Obstacle or Stunt in Path",
                "level": "major",
                "description_fr": "À moto, le pilote n’a aucune protection. Une cascade, un véhicule de jeu, une personne ou un objet qui entre dans sa trajectoire peut provoquer une chute ou une collision très graves.",
                "description_en": "À moto, le pilote n’a aucune protection. Une cascade, un véhicule de jeu, une personne ou un objet qui entre dans sa trajectoire peut provoquer une chute ou une collision très graves.",
                "recommendations_fr": [
                        "Garder la trajectoire de la moto entièrement dégagée pendant chaque prise.",
                        "Préparer chaque cascade avec le coordinateur cascade et le pilote, et la répéter à basse vitesse.",
                        "Garder une distance de sécurité adaptée avec toute cascade ou tout effet spécial.",
                        "Ne jamais introduire un objet ou un effet dans la trajectoire sans l’accord du pilote."
                ],
                "recommendations_en": [
                        "Garder la trajectoire de la moto entièrement dégagée pendant chaque prise.",
                        "Préparer chaque cascade avec le coordinateur cascade et le pilote, et la répéter à basse vitesse.",
                        "Garder une distance de sécurité adaptée avec toute cascade ou tout effet spécial.",
                        "Ne jamais introduire un objet ou un effet dans la trajectoire sans l’accord du pilote."
                ]
        },
        {
                "id": "chute_du_pilote",
                "category_fr": "COLLISIONS ET CHUTES",
                "category_en": "COLLISIONS AND FALLS",
                "title_fr": "Chute du pilote",
                "title_en": "Rider Fall",
                "level": "major",
                "description_fr": "Une perte d’adhérence, un freinage brusque ou un obstacle peut faire chuter le pilote. Un freinage avec le seul frein avant peut le faire passer par‑dessus le guidon.",
                "description_en": "Une perte d’adhérence, un freinage brusque ou un obstacle peut faire chuter le pilote. Un freinage avec le seul frein avant peut le faire passer par‑dessus le guidon.",
                "recommendations_fr": [
                        "Confier la conduite uniquement à un pilote expérimenté, validé par Belle Vitesse ou mandaté par le coordinateur cascade.",
                        "Imposer au pilote un casque, des bottes, des gants, un pantalon et une veste de protection, en parfait état.",
                        "Utiliser les freins avant et arrière ensemble.",
                        "Adapter la vitesse au terrain et à la visibilité, en tenant compte des distances de freinage plus longues sur sol mouillé.",
                        "Ne pas rouler de nuit ou par faible luminosité sans éclairage ni réflecteurs.",
                        "Répéter le plan à basse vitesse.",
                        "En cas d’accident, éteindre la moto et porter secours à la victime."
                ],
                "recommendations_en": [
                        "Confier la conduite uniquement à un pilote expérimenté, validé par Belle Vitesse ou mandaté par le coordinateur cascade.",
                        "Imposer au pilote un casque, des bottes, des gants, un pantalon et une veste de protection, en parfait état.",
                        "Utiliser les freins avant et arrière ensemble.",
                        "Adapter la vitesse au terrain et à la visibilité, en tenant compte des distances de freinage plus longues sur sol mouillé.",
                        "Ne pas rouler de nuit ou par faible luminosité sans éclairage ni réflecteurs.",
                        "Répéter le plan à basse vitesse.",
                        "En cas d’accident, éteindre la moto et porter secours à la victime."
                ]
        },
        {
                "id": "pièces_en_mouvement",
                "category_fr": "ROUES",
                "category_en": "WHEELS",
                "title_fr": "Pièces en mouvement",
                "title_en": "Moving Parts",
                "level": "standard",
                "description_fr": "Quand la moto est allumée, la chaîne et les roues peuvent tourner et happer une main, un vêtement ou une sangle.",
                "description_en": "Quand la moto est allumée, la chaîne et les roues peuvent tourner et happer une main, un vêtement ou une sangle.",
                "recommendations_fr": [
                        "Ne jamais approcher la chaîne ni les roues quand la moto est allumée.",
                        "Retirer ou attacher les écharpes et vêtements amples avant tout roulage.",
                        "Éteindre complètement la moto avant toute intervention, tout nettoyage ou toute installation."
                ],
                "recommendations_en": [
                        "Ne jamais approcher la chaîne ni les roues quand la moto est allumée.",
                        "Retirer ou attacher les écharpes et vêtements amples avant tout roulage.",
                        "Éteindre complètement la moto avant toute intervention, tout nettoyage ou toute installation."
                ]
        },
        {
                "id": "accélérations_et_modes_de_puissance",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Accélérations et modes de puissance",
                "title_en": "Power Modes and Rapid Acceleration",
                "level": "standard",
                "description_fr": "Le moteur électrique délivre tout son couple instantanément. Un coup d’accélérateur trop fort peut provoquer une perte de contrôle, un lever de roue avant ou une chute.",
                "description_en": "Le moteur électrique délivre tout son couple instantanément. Un coup d’accélérateur trop fort peut provoquer une perte de contrôle, un lever de roue avant ou une chute.",
                "recommendations_fr": [
                        "Choisir le mode de puissance adapté au plan et le faire valider par un technicien formé par Belle Vitesse.",
                        "Changer de mode uniquement à l’arrêt ou avec précaution, en prévenant l’équipe."
                ],
                "recommendations_en": [
                        "Choisir le mode de puissance adapté au plan et le faire valider par un technicien formé par Belle Vitesse.",
                        "Changer de mode uniquement à l’arrêt ou avec précaution, en prévenant l’équipe."
                ]
        },
        {
                "id": "démarrage_involontaire",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Démarrage involontaire",
                "title_en": "Unintended Start-Up",
                "level": "standard",
                "description_fr": "Si la moto est allumée, un coup d’accélérateur en montant ou en descendant peut la faire partir.",
                "description_en": "Si la moto est allumée, un coup d’accélérateur en montant ou en descendant peut la faire partir.",
                "recommendations_fr": [
                        "Éteindre la moto avec le bouton On/Off dès qu’elle ne roule pas.",
                        "Ne jamais monter ni descendre en tenant la poignée d’accélérateur.",
                        "Ne pas maintenir appuyés les boutons de mode, qui activent le mode Crawl en marche avant ou arrière."
                ],
                "recommendations_en": [
                        "Éteindre la moto avec le bouton On/Off dès qu’elle ne roule pas.",
                        "Ne jamais monter ni descendre en tenant la poignée d’accélérateur.",
                        "Ne pas maintenir appuyés les boutons de mode, qui activent le mode Crawl en marche avant ou arrière."
                ]
        },
        {
                "id": "perte_de_puissance",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Perte de puissance",
                "title_en": "Loss of Power",
                "level": "standard",
                "description_fr": "Une batterie faible, une température hors plage ou une surcharge peut réduire la puissance et l’autonomie, parfois en pleine prise.",
                "description_en": "Une batterie faible, une température hors plage ou une surcharge peut réduire la puissance et l’autonomie, parfois en pleine prise.",
                "recommendations_fr": [
                        "Commencer chaque plan avec une batterie suffisamment chargée, et recharger pendant les pauses.",
                        "Arrêter les prises dès que le voyant de puissance limitée s’allume.",
                        "Utiliser la moto de préférence entre 0 et 25 °C."
                ],
                "recommendations_en": [
                        "Commencer chaque plan avec une batterie suffisamment chargée, et recharger pendant les pauses.",
                        "Arrêter les prises dès que le voyant de puissance limitée s’allume.",
                        "Utiliser la moto de préférence entre 0 et 25 °C."
                ]
        },
        {
                "id": "défaut_non_détecté_avant_roulage",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Défaut non détecté avant roulage",
                "title_en": "Undetected Defect Before Driving",
                "level": "standard",
                "description_fr": "Un défaut non repéré avant le roulage (serrages, pneus, jantes, freins, poignées) augmente le risque de chute.",
                "description_en": "Un défaut non repéré avant le roulage (serrages, pneus, jantes, freins, poignées) augmente le risque de chute.",
                "recommendations_fr": [
                        "Vérifier avant chaque journée le serrage des écrous et boulons, l’état des pneus et des jantes, les poignées et les freins à l’arrêt.",
                        "Avec des mousses, ne pas dépasser 130 km/h et les regraisser au plus tard toutes les 5 heures d’utilisation.",
                        "Inspecter aussi le véhicule après chaque journée.",
                        "Faire réparer tout élément défectueux par un technicien qualifié avant de rouler, et retirer du service tout matériel cassé."
                ],
                "recommendations_en": [
                        "Vérifier avant chaque journée le serrage des écrous et boulons, l’état des pneus et des jantes, les poignées et les freins à l’arrêt.",
                        "Avec des mousses, ne pas dépasser 130 km/h et les regraisser au plus tard toutes les 5 heures d’utilisation.",
                        "Inspecter aussi le véhicule après chaque journée.",
                        "Faire réparer tout élément défectueux par un technicien qualifié avant de rouler, et retirer du service tout matériel cassé."
                ]
        },
        {
                "id": "surcharge",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Surcharge",
                "title_en": "Overloading",
                "level": "standard",
                "description_fr": "Au‑delà de la charge maximale prévue par la suspension, pilote et matériel compris, la moto devient instable et le pilote peut perdre le contrôle.",
                "description_en": "Au‑delà de la charge maximale prévue par la suspension, pilote et matériel compris, la moto devient instable et le pilote peut perdre le contrôle.",
                "recommendations_fr": [
                        "Ne jamais dépasser la charge maximale prévue par la suspension installée, pilote et matériel compris.",
                        "Réduire la vitesse et anticiper les freinages quand la moto est chargée."
                ],
                "recommendations_en": [
                        "Ne jamais dépasser la charge maximale prévue par la suspension installée, pilote et matériel compris.",
                        "Réduire la vitesse et anticiper les freinages quand la moto est chargée."
                ]
        },
        {
                "id": "conduite_imprudente",
                "category_fr": "PILOTAGE",
                "category_en": "DRIVING & HANDLING",
                "title_fr": "Conduite imprudente",
                "title_en": "Reckless Driving",
                "level": "standard",
                "description_fr": "Une conduite imprudente, ou sous l’emprise de l’alcool, de médicaments ou de drogues, peut provoquer une chute grave.",
                "description_en": "Une conduite imprudente, ou sous l’emprise de l’alcool, de médicaments ou de drogues, peut provoquer une chute grave.",
                "recommendations_fr": [
                        "Interdire toute conduite imprudente.",
                        "Interdire le pilotage sous l’emprise de l’alcool, de médicaments ou de drogues."
                ],
                "recommendations_en": [
                        "Interdire toute conduite imprudente.",
                        "Interdire le pilotage sous l’emprise de l’alcool, de médicaments ou de drogues."
                ]
        },
        {
                "id": "chute_de_la_moto_pendant_l_installation",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Chute de la moto pendant l’installation",
                "title_en": "Motorcycle Fall During Rigging Setup",
                "level": "standard",
                "description_fr": "Pendant l’installation ou la manipulation du matériel, une moto mal maintenue peut basculer et blesser une personne ou endommager le matériel.",
                "description_en": "Pendant l’installation ou la manipulation du matériel, une moto mal maintenue peut basculer et blesser une personne ou endommager le matériel.",
                "recommendations_fr": [
                        "Maintenir la moto sur le système de docking prévu pendant toute installation ou manipulation de matériel.",
                        "Éteindre complètement la moto avant toute installation."
                ],
                "recommendations_en": [
                        "Maintenir la moto sur le système de docking prévu pendant toute installation ou manipulation de matériel.",
                        "Éteindre complètement la moto avant toute installation."
                ]
        },
        {
                "id": "défaillance_du_support_caméra",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Défaillance du support caméra",
                "title_en": "Camera Mount Failure",
                "level": "standard",
                "description_fr": "Une caméra ou un support mal fixé peut se détacher, déséquilibrer la moto ou gêner le pilote.",
                "description_en": "Une caméra ou un support mal fixé peut se détacher, déséquilibrer la moto ou gêner le pilote.",
                "recommendations_fr": [
                        "Réserver l’installation du support caméra aux personnes habilitées par Belle Vitesse.",
                        "Faire valider chaque installation par un technicien formé par Belle Vitesse.",
                        "Élinguer et sécuriser tout élément technique.",
                        "Vérifier que le matériel ne gêne ni le guidon, ni les commandes, ni la vue du pilote."
                ],
                "recommendations_en": [
                        "Réserver l’installation du support caméra aux personnes habilitées par Belle Vitesse.",
                        "Faire valider chaque installation par un technicien formé par Belle Vitesse.",
                        "Élinguer et sécuriser tout élément technique.",
                        "Vérifier que le matériel ne gêne ni le guidon, ni les commandes, ni la vue du pilote."
                ]
        },
        {
                "id": "déséquilibre_de_la_moto",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Déséquilibre de la moto",
                "title_en": "Motorcycle Imbalance",
                "level": "standard",
                "description_fr": "Une caméra ou un bras anti‑vibration installé en déport déséquilibre la moto. Trop à l’arrière, sans contrepoids suffisant à l’avant, il allège la roue avant : elle perd de l’appui, la direction devient floue et le pilote peut perdre le contrôle.",
                "description_en": "Une caméra ou un bras anti‑vibration installé en déport déséquilibre la moto. Trop à l’arrière, sans contrepoids suffisant à l’avant, il allège la roue avant : elle perd de l’appui, la direction devient floue et le pilote peut perdre le contrôle.",
                "recommendations_fr": [
                        "Toujours équilibrer la moto avec des contrepoids cohérents à l’avant ou à l’arrière, selon la position du matériel.",
                        "Limiter le déport du bras anti‑vibration au strict nécessaire.",
                        "Avant chaque plan, vérifier à basse vitesse que la direction reste précise et que la roue avant garde son appui.",
                        "Faire valider la configuration par un technicien formé par Belle Vitesse, sans dépasser la charge maximale prévue par la suspension installée."
                ],
                "recommendations_en": [
                        "Toujours équilibrer la moto avec des contrepoids cohérents à l’avant ou à l’arrière, selon la position du matériel.",
                        "Limiter le déport du bras anti‑vibration au strict nécessaire.",
                        "Avant chaque plan, vérifier à basse vitesse que la direction reste précise et que la roue avant garde son appui.",
                        "Faire valider la configuration par un technicien formé par Belle Vitesse, sans dépasser la charge maximale prévue par la suspension installée."
                ]
        },
        {
                "id": "électrocution",
                "category_fr": "ÉLECTRICITÉ ET BATTERIE",
                "category_en": "ELECTRICAL SYSTEM & BATTERY",
                "title_fr": "Électrocution",
                "title_en": "Electrocution",
                "level": "standard",
                "description_fr": "Un contact avec la batterie, le moteur ou les câbles haute tension peut provoquer une électrocution.",
                "description_en": "Un contact avec la batterie, le moteur ou les câbles haute tension peut provoquer une électrocution.",
                "recommendations_fr": [
                        "Réserver toute intervention sur la batterie et le moteur aux techniciens formés par Belle Vitesse.",
                        "Ne jamais ouvrir la batterie ni le moteur, ni toucher les câbles haute tension.",
                        "Éteindre complètement la moto avant toute intervention.",
                        "N’apporter aucune modification à la moto."
                ],
                "recommendations_en": [
                        "Réserver toute intervention sur la batterie et le moteur aux techniciens formés par Belle Vitesse.",
                        "Ne jamais ouvrir la batterie ni le moteur, ni toucher les câbles haute tension.",
                        "Éteindre complètement la moto avant toute intervention.",
                        "N’apporter aucune modification à la moto."
                ]
        },
        {
                "id": "mouvement_de_la_moto_pendant_le_transpor",
                "category_fr": "CHARGEMENT ET TRANSPORT",
                "category_en": "LOADING AND TRANSPORT",
                "title_fr": "Mouvement de la moto pendant le transport",
                "title_en": "Motorcycle Shifting During Transport",
                "level": "standard",
                "description_fr": "Une moto mal sanglée ou mal manipulée peut bouger ou tomber pendant le transport.",
                "description_en": "Une moto mal sanglée ou mal manipulée peut bouger ou tomber pendant le transport.",
                "recommendations_fr": [
                        "Transporter la moto éteinte, sur ses deux roues, sur une remorque horizontale de capacité suffisante.",
                        "Ne jamais soulever la moto avec un engin de levage.",
                        "Utiliser le système de docking prévu pour garder la moto stable pendant les manipulations.",
                        "Sangler la moto autour de la fourche et du té inférieur."
                ],
                "recommendations_en": [
                        "Transporter la moto éteinte, sur ses deux roues, sur une remorque horizontale de capacité suffisante.",
                        "Ne jamais soulever la moto avec un engin de levage.",
                        "Utiliser le système de docking prévu pour garder la moto stable pendant les manipulations.",
                        "Sangler la moto autour de la fourche et du té inférieur."
                ]
        },
        {
                "id": "incendie_pendant_la_recharge",
                "category_fr": "INCENDIE",
                "category_en": "FIRE HAZARDS",
                "title_fr": "Incendie pendant la recharge",
                "title_en": "Fire During Battery Charging",
                "level": "standard",
                "description_fr": "Une recharge sans surveillance, sur une prise inadaptée, près de matières inflammables ou avec une batterie humide peut provoquer un départ de feu.",
                "description_en": "Une recharge sans surveillance, sur une prise inadaptée, près de matières inflammables ou avec une batterie humide peut provoquer un départ de feu.",
                "recommendations_fr": [
                        "Ne jamais laisser la moto en charge sans surveillance, ni la couvrir pendant la charge.",
                        "Recharger dans un endroit sec et ventilé, loin des matières inflammables.",
                        "Utiliser une prise reliée à la terre et protégée par un différentiel, et débrancher dès la fin de la charge.",
                        "Ne pas recharger en dessous de 4 °C, ni une batterie humide ou exposée à l’eau de mer."
                ],
                "recommendations_en": [
                        "Ne jamais laisser la moto en charge sans surveillance, ni la couvrir pendant la charge.",
                        "Recharger dans un endroit sec et ventilé, loin des matières inflammables.",
                        "Utiliser une prise reliée à la terre et protégée par un différentiel, et débrancher dès la fin de la charge.",
                        "Ne pas recharger en dessous de 4 °C, ni une batterie humide ou exposée à l’eau de mer."
                ]
        },
        {
                "id": "incendie_après_une_chute",
                "category_fr": "INCENDIE",
                "category_en": "FIRE HAZARDS",
                "title_fr": "Incendie après une chute",
                "title_en": "Fire Following a Crash",
                "level": "standard",
                "description_fr": "Une chute ou un choc peut endommager la batterie sans que ce soit visible. Une batterie déformée, bruyante ou anormalement chaude peut prendre feu ou exploser.",
                "description_en": "Une chute ou un choc peut endommager la batterie sans que ce soit visible. Une batterie déformée, bruyante ou anormalement chaude peut prendre feu ou exploser.",
                "recommendations_fr": [
                        "Après toute chute, faire contrôler la batterie par un technicien formé par Belle Vitesse avant de rouler ou de recharger.",
                        "Ne jamais utiliser ni recharger une batterie déformée, bruyante ou anormalement chaude.",
                        "Ne jamais ranger en intérieur une moto dont la batterie ou un composant électrique est endommagé."
                ],
                "recommendations_en": [
                        "Après toute chute, faire contrôler la batterie par un technicien formé par Belle Vitesse avant de rouler ou de recharger.",
                        "Ne jamais utiliser ni recharger une batterie déformée, bruyante ou anormalement chaude.",
                        "Ne jamais ranger en intérieur une moto dont la batterie ou un composant électrique est endommagé."
                ]
        },
        {
                "id": "emballement_thermique",
                "category_fr": "INCENDIE",
                "category_en": "FIRE HAZARDS",
                "title_fr": "Emballement thermique",
                "title_en": "Thermal Runaway",
                "level": "major",
                "description_fr": "Une défaillance de la batterie peut faire monter sa température très vite et provoquer un feu ou une explosion. Un feu de batterie est difficile à éteindre et peut reprendre après avoir été éteint.",
                "description_en": "Une défaillance de la batterie peut faire monter sa température très vite et provoquer un feu ou une explosion. Un feu de batterie est difficile à éteindre et peut reprendre après avoir été éteint.",
                "recommendations_fr": [
                        "En cas de fumée, d’odeur anormale ou de chaleur excessive, éteindre la moto et s’en éloigner immédiatement.",
                        "S’éloigner du véhicule et appeler les pompiers (18 ou 112) en précisant qu’il s’agit d’un véhicule électrique.",
                        "Ne jamais tenter d’éteindre soi‑même un feu de batterie déclaré."
                ],
                "recommendations_en": [
                        "En cas de fumée, d’odeur anormale ou de chaleur excessive, éteindre la moto et s’en éloigner immédiatement.",
                        "S’éloigner du véhicule et appeler les pompiers (18 ou 112) en précisant qu’il s’agit d’un véhicule électrique.",
                        "Ne jamais tenter d’éteindre soi‑même un feu de batterie déclaré."
                ]
        }
]
    },
    "ecar": {
        "label": "eCar (Twizy)",
        "keywords": ["ecar", "twizy", "car"],
        "risks": [
            {
                "id": "circulation_voie_ouverte_ecar",
                "category_fr": "CIRCULATION SUR VOIE OUVERTE",
                "category_en": "DRIVING ON PUBLIC OPEN ROADS",
                "title_fr": "Circulation sur voie ouverte",
                "title_en": "Driving on Public Open Roads",
                "level": "major",
                "description_fr": "L'eCar configuré pour la prise de vue n'est pas autorisé sur voie ouverte sans encadrement légal strict.",
                "description_en": "The camera-rigged eCar is not authorized on open roads without strict legal road closure.",
                "recommendations_fr": [
                    "Roulage exclusivement sur voie fermée sécurisée ou circuit privé.",
                    "Blocage certifié par la production avant chaque départ."
                ],
                "recommendations_en": [
                    "Driving strictly restricted to closed secured roads or private tracks.",
                    "Certified road closure in place by production before any take."
                ]
            },
            {
                "id": "surcharge_arceau_ecar",
                "category_fr": "RIGGING",
                "category_en": "RIGGING",
                "title_fr": "Respect de la charge utile de l'arceau",
                "title_en": "Roll-bar Payload Compliance",
                "level": "standard",
                "description_fr": "Une surcharge ou une mauvaise répartition du matériel caméra peut déstabiliser le véhicule.",
                "description_en": "Overloading or improper weight distribution of camera gear may destabilize the vehicle.",
                "recommendations_fr": [
                    "Respecter la limite de 110 kg sur les plateformes et l'arceau.",
                    "Élingage de sécurité systématique de chaque élément."
                ],
                "recommendations_en": [
                    "Strictly adhere to the 110 kg payload limit on platforms and roll bar.",
                    "Systematic safety tethering for every piece of technical gear."
                ]
            }
        ]
    }
}


def get_general_risk_assessment():
    """
    Retourne la liste des risques généraux (Travelling).
    Lit AppSetting('general_risk_assessment') ou utilise la dotation initiale.
    """
    try:
        raw = AppSetting.get('general_risk_assessment', None)
        if raw is not None and str(raw).strip() != '':
            if isinstance(raw, str):
                parsed = json.loads(raw)
            elif isinstance(raw, list):
                parsed = raw
            else:
                parsed = None
            if isinstance(parsed, list):
                return parsed
    except Exception as e:
        logger.warning(f"Erreur lecture general_risk_assessment : {e}")

    return list(DEFAULT_GENERAL_RISK_ASSESSMENT)


def _strip_internal_keys(risks):
    """Retire les clés calculées pour l'affichage (préfixe '_', ex. _translation_status)."""
    return [
        {k: v for k, v in r.items() if not str(k).startswith('_')} if isinstance(r, dict) else r
        for r in (risks or [])
    ]


def annotate_translation_status(risks):
    """
    Retourne des COPIES des risques enrichies de '_translation_status'.
    Ne jamais muter les dicts sources : ils peuvent être les constantes DEFAULT_*.
    """
    annotated = []
    for r in risks or []:
        copy = dict(r)
        copy['_translation_status'] = check_risk_translation_status(copy)
        annotated.append(copy)
    return annotated


def save_general_risk_assessment(risks):
    """
    Enregistre les risques généraux (Travelling) dans AppSetting.
    """
    try:
        if not isinstance(risks, list):
            return False, "Format de risques invalide (liste requise)."
        AppSetting.set('general_risk_assessment', json.dumps(_strip_internal_keys(risks), ensure_ascii=False))
        return True, "Risques généraux enregistrés avec succès."
    except Exception as e:
        logger.error(f"Erreur sauvegarde general_risk_assessment : {e}")
        return False, f"Erreur lors de la sauvegarde : {e}"


def get_all_vehicle_risk_assessment_catalog():
    """
    Retourne le catalogue complet des risques par véhicule de la flotte.
    Fusionne les règles par défaut, les personnalisations AppSetting,
    et les véhicules réels de la flotte (avec images et noms).
    """
    custom_dict = {}
    try:
        raw = AppSetting.get('vehicle_risk_assessment_catalog', None)
        if raw is not None and str(raw).strip() != '':
            custom_dict = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(custom_dict, dict):
                custom_dict = {}
    except Exception as e:
        logger.warning(f"Erreur lecture vehicle_risk_assessment_catalog : {e}")

    # Récupération des véhicules réels de la flotte avec réconciliation SQL locale
    fleet_vehicles = []
    seen_ids = set()
    try:
        from utils.database import get_vehicles
        for v in (get_vehicles() or []):
            fleet_vehicles.append(v)
            if v.get("id"):
                seen_ids.add(str(v["id"]))
    except Exception as e:
        logger.warning(f"Impossible de charger les véhicules via get_vehicles : {e}")

    try:
        from models.catalog import Vehicle
        db_vehs = Vehicle.query.all()
        for v in db_vehs:
            if str(v.id) not in seen_ids:
                fleet_vehicles.append({
                    "id": v.id,
                    "fields": v.fields or {}
                })
                seen_ids.add(str(v.id))
    except Exception as e:
        logger.warning(f"Erreur réconciliation véhicules analyse des risques : {e}")

    catalog = {}

    if fleet_vehicles:
        for veh in fleet_vehicles:
            vid = str(veh.get("id") or "").strip()
            fields = veh.get("fields") or {}
            vname = fields.get("Nom") or fields.get("name") or f"Véhicule {vid}"
            vslug = (fields.get("slug") or veh.get("slug") or vname).strip().lower()
            vimg = extract_vehicle_image(fields)

            # Recherche d'une correspondance par défaut
            matched_def = None
            vname_lower = vname.lower()
            def_key = None
            for d_k, d_v in DEFAULT_VEHICLE_RISK_ASSESSMENT.items():
                kws = d_v.get('keywords', [])
                if any(kw in vname_lower or kw in vid.lower() or kw in vslug for kw in kws):
                    matched_def = d_v
                    def_key = d_k
                    break

            def_label = matched_def['label'] if matched_def else vname
            def_risks = list(matched_def.get('risks', [])) if matched_def else []
            def_kws = list(matched_def.get('keywords', [])) if matched_def else [vname_lower]

            # Recherche d'une personnalisation (par id, par slug, ou par clé par défaut)
            custom_entry = custom_dict.get(vid) or custom_dict.get(vslug) or (custom_dict.get(def_key) if def_key else None)
            if not custom_entry:
                for ckey, cval in custom_dict.items():
                    if ckey.lower() == vname_lower or ckey.lower() in vname_lower or (matched_def and ckey.lower() in def_kws):
                        custom_entry = cval
                        break

            label = (custom_entry.get("label") if custom_entry else None) or def_label
            # Une liste personnalisée vide est volontaire (tous les risques supprimés) :
            # ne pas retomber sur la dotation par défaut.
            if custom_entry and custom_entry.get("risks") is not None:
                risks = custom_entry.get("risks")
            else:
                risks = def_risks

            entry_dict = {
                "id": vid,
                "name": vname,
                "label": label,
                "image": vimg or "/static/imgs/placeholders/vehicle.svg",
                "thumbnail": vimg or "/static/imgs/placeholders/vehicle.svg",
                "keywords": def_kws,
                "risks": risks if isinstance(risks, list) else []
            }
            catalog[vid] = entry_dict
            if def_key and def_key not in catalog:
                catalog[def_key] = entry_dict

        # S'assurer que les clés de test/défaut non couvertes sont présentes
        for def_key, def_data in DEFAULT_VEHICLE_RISK_ASSESSMENT.items():
            if def_key not in catalog:
                custom_entry = custom_dict.get(def_key, {})
                catalog[def_key] = {
                    "id": def_key,
                    "name": def_data.get('label', def_key.capitalize()),
                    "label": custom_entry.get("label") or def_data.get('label', def_key.capitalize()),
                    "image": "/static/imgs/placeholders/vehicle.svg",
                    "thumbnail": "/static/imgs/placeholders/vehicle.svg",
                    "keywords": list(def_data.get('keywords', [])),
                    "risks": custom_entry.get("risks") if custom_entry.get("risks") is not None else list(def_data.get('risks', []))
                }
    else:
        # Fallback si pas de BDD flotte (tests unitaires ou mode standalone)
        for k, v in DEFAULT_VEHICLE_RISK_ASSESSMENT.items():
            custom_entry = custom_dict.get(k, {})
            label = custom_entry.get('label') or v.get('label', k.capitalize())
            risks = custom_entry.get('risks') if custom_entry.get('risks') is not None else list(v.get('risks', []))
            catalog[k] = {
                'id': k,
                'name': v.get('label', k.capitalize()),
                'label': label,
                'image': '/static/imgs/placeholders/vehicle.svg',
                'thumbnail': '/static/imgs/placeholders/vehicle.svg',
                'keywords': list(v.get('keywords', [])),
                'risks': risks
            }

    return catalog


def save_vehicle_risk_assessment(vehicle_key, data):
    """
    Enregistre ou met à jour les risques d'une famille de véhicules.
    """
    try:
        if not vehicle_key:
            return False, "Identifiant de véhicule manquant."
        raw = AppSetting.get('vehicle_risk_assessment_catalog', None)
        custom_dict = {}
        if raw is not None and str(raw).strip() != '':
            custom_dict = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(custom_dict, dict):
                custom_dict = {}

        if isinstance(data, dict) and isinstance(data.get('risks'), list):
            data = dict(data, risks=_strip_internal_keys(data['risks']))

        if vehicle_key in custom_dict:
            custom_dict[vehicle_key].update(data)
        else:
            custom_dict[vehicle_key] = data

        AppSetting.set('vehicle_risk_assessment_catalog', json.dumps(custom_dict, ensure_ascii=False))
        return True, "Configuration véhicule enregistrée avec succès."
    except Exception as e:
        logger.error(f"Erreur sauvegarde vehicle_risk_assessment : {e}")
        return False, f"Erreur lors de la sauvegarde : {e}"


def check_risk_translation_status(risk):
    """
    Vérifie la complétude des traductions anglaises pour un risque.
    Retourne { 'is_complete': bool, 'missing_count': int, 'missing_fields': list }.
    """
    missing_count = 0
    missing_fields = []

    # 1. Titre EN
    title_en = (risk.get('title_en') or '').strip()
    if not title_en or title_en.lower() in ('traduction manquante', 'traduction anglaise manquante'):
        missing_count += 1
        missing_fields.append('title_en')

    # 2. Description EN
    desc_en = (risk.get('description_en') or '').strip()
    if not desc_en or desc_en.lower() in ('traduction manquante', 'traduction anglaise manquante'):
        missing_count += 1
        missing_fields.append('description_en')

    # 3. Recommandations EN
    recs_fr = risk.get('recommendations_fr') or risk.get('recommendations') or []
    recs_en = risk.get('recommendations_en') or []
    for idx in range(len(recs_fr)):
        rec_en_val = (recs_en[idx] if idx < len(recs_en) else '').strip()
        if not rec_en_val or rec_en_val.lower() in ('traduction manquante', 'traduction anglaise manquante'):
            missing_count += 1
            missing_fields.append(f'rec_en_{idx}')

    return {
        'is_complete': (missing_count == 0),
        'missing_count': missing_count,
        'missing_fields': missing_fields
    }


def get_risks_stats(risks):
    """Calcule les statistiques globales d'une liste de risques."""
    if not risks:
        return {'total': 0, 'major': 0, 'standard': 0, 'incomplete_en': 0}
    total = len(risks)
    major = sum(1 for r in risks if r.get('level') == 'major')
    standard = total - major
    incomplete = sum(1 for r in risks if not check_risk_translation_status(r)['is_complete'])
    return {
        'total': total,
        'major': major,
        'standard': standard,
        'incomplete_en': incomplete
    }


_RISK_TEXT_FIELDS = ('category_fr', 'category_en', 'title_fr', 'title_en', 'description_fr', 'description_en')


def _normalize_risk_payload(risk_data):
    """Valide et normalise un risque reçu du client (liste blanche des champs)."""
    import re
    import time

    def clean_list(values):
        if not isinstance(values, list):
            return []
        return [str(v or '').strip() for v in values]

    risk = {k: str(risk_data.get(k) or '').strip() for k in _RISK_TEXT_FIELDS}
    risk['title_fr'] = risk['title_fr'] or str(risk_data.get('title') or '').strip()
    risk['level'] = 'major' if risk_data.get('level') == 'major' else 'standard'
    risk['category_fr'] = risk['category_fr'] or 'GÉNÉRAL'
    risk['category_en'] = risk['category_en'] or risk['category_fr']

    recs_fr = clean_list(risk_data.get('recommendations_fr'))
    recs_en = clean_list(risk_data.get('recommendations_en'))
    # Aligner EN sur FR (une entrée EN par recommandation FR) et ignorer les lignes vides
    pairs = [(fr, recs_en[i] if i < len(recs_en) else '') for i, fr in enumerate(recs_fr)]
    pairs = [(fr, en) for fr, en in pairs if fr or en]
    risk['recommendations_fr'] = [fr for fr, _ in pairs]
    risk['recommendations_en'] = [en for _, en in pairs]

    risk_id = str(risk_data.get('id') or '').strip()
    if not risk_id:
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', risk['title_fr'].lower()).strip('_')
        risk_id = slug or f"risk_{int(time.time())}"
    risk['id'] = risk_id
    return risk


def _load_scope_risks(scope, vehicle_key):
    """Retourne (risks, erreur) pour le scope demandé."""
    if scope == 'general':
        return list(get_general_risk_assessment()), None
    if scope == 'vehicle':
        if not vehicle_key:
            return None, "Identifiant de véhicule manquant."
        v_entry = get_all_vehicle_risk_assessment_catalog().get(vehicle_key)
        if not v_entry:
            return None, "Véhicule introuvable."
        return list(v_entry.get('risks', [])), None
    return None, "Scope inconnu."


def _save_scope_risks(scope, vehicle_key, risks):
    """Persiste la liste de risques du scope (seule la clé 'risks' est écrite pour un véhicule)."""
    if scope == 'general':
        return save_general_risk_assessment(risks)
    return save_vehicle_risk_assessment(vehicle_key, {'risks': risks})


def save_single_risk(scope, risk_data, vehicle_key=None):
    """
    Ajoute ou met à jour un risque individuel dans le scope 'general' ou 'vehicle'.
    Retourne (success: bool, message: str, saved_risk: dict, stats: dict).
    """
    if not risk_data or not isinstance(risk_data, dict):
        return False, "Données de risque invalides.", None, None

    risk = _normalize_risk_payload(risk_data)
    if not risk['title_fr']:
        return False, "Le titre du risque en français est obligatoire.", None, None

    risks, err = _load_scope_risks(scope, vehicle_key)
    if err:
        return False, err, None, None

    found_idx = next((i for i, r in enumerate(risks) if str(r.get('id')) == risk['id']), -1)
    if found_idx >= 0:
        # Conserver d'éventuels champs non gérés par l'éditeur
        merged = {k: v for k, v in risks[found_idx].items()
                  if k not in ('title', 'description', 'recommendations', 'category')}
        merged.update(risk)
        risks[found_idx] = merged
        risk = merged
    else:
        risks.append(risk)

    ok, msg = _save_scope_risks(scope, vehicle_key, risks)
    return ok, msg, dict(risk), get_risks_stats(risks)


def delete_single_risk(scope, risk_id, vehicle_key=None):
    """Supprime un risque par son identifiant."""
    if not risk_id:
        return False, "Identifiant de risque manquant.", None

    risks, err = _load_scope_risks(scope, vehicle_key)
    if err:
        return False, err, None

    remaining = [r for r in risks if str(r.get('id')) != str(risk_id)]
    if len(remaining) == len(risks):
        return False, "Risque introuvable.", None

    ok, msg = _save_scope_risks(scope, vehicle_key, remaining)
    return ok, msg, get_risks_stats(remaining)


def reorder_risks_list(scope, risk_ids, vehicle_key=None):
    """Réordonne la liste des risques selon les IDs fournis (IDs inconnus ignorés)."""
    if not risk_ids or not isinstance(risk_ids, list):
        return False, "Liste d'IDs invalide."

    risks, err = _load_scope_risks(scope, vehicle_key)
    if err:
        return False, err

    wanted = [str(rid) for rid in risk_ids]
    risk_map = {str(r.get('id')): r for r in risks}
    reordered = [risk_map[rid] for rid in wanted if rid in risk_map]
    reordered += [r for r in risks if str(r.get('id')) not in wanted]
    return _save_scope_risks(scope, vehicle_key, reordered)


def get_shared_risk_categories(catalog=None):
    """
    Catégories communes à toute l'Analyse des Risques (risques généraux + tous les véhicules),
    pour pouvoir les réutiliser d'un écran d'édition à l'autre.
    Retourne [{"fr": "ZONE DE TOURNAGE", "en": "SHOOTING AREA"}, ...] sans doublon (clé FR
    insensible à la casse), dans l'ordre d'apparition (généraux d'abord).
    """
    if catalog is None:
        catalog = get_all_vehicle_risk_assessment_catalog()

    all_risks = list(get_general_risk_assessment())
    for v_data in catalog.values():
        all_risks.extend(v_data.get('risks') or [])

    categories = {}
    for r in all_risks:
        fr = (r.get('category_fr') or r.get('category') or '').strip()
        if not fr:
            continue
        key = fr.upper()
        en = (r.get('category_en') or '').strip()
        if key not in categories:
            categories[key] = {'fr': key, 'en': en}
        elif not categories[key]['en'] and en:
            categories[key]['en'] = en
    return list(categories.values())


def group_risks_by_category(risks):
    """
    Regroupe une liste de risques par catégorie (en préservant l'ordre d'apparition).
    Retourne une liste de dicts :
    [
        {
            "name": "ZONE DE TOURNAGE",
            "display_name": "Zone de tournage",
            "risks": [...],
            "count": 6,
            "major_count": 1,
            "standard_count": 5,
        },
        ...
    ]
    """
    groups = []
    groups_map = {}
    for r in risks:
        cat = (r.get("category_fr") or r.get("category") or "GÉNÉRAL").strip()
        cat_key = cat.upper()
        if cat_key not in groups_map:
            group = {
                "name": cat_key,
                "display_name": cat,
                "risks": [],
                "count": 0,
                "major_count": 0,
                "standard_count": 0,
            }
            groups.append(group)
            groups_map[cat_key] = group
        groups_map[cat_key]["risks"].append(r)
        groups_map[cat_key]["count"] += 1
        if r.get("level") == "major":
            groups_map[cat_key]["major_count"] += 1
        else:
            groups_map[cat_key]["standard_count"] += 1
    return groups


def get_risk_assessment_for_vehicles(vehicles_details, catalog=None):
    """
    Retourne la liste des risques spécifiques pour les véhicules d'un tournage.
    Dédupliqué par famille de véhicules.
    """
    if catalog is None:
        catalog = get_all_vehicle_risk_assessment_catalog()

    matched_categories = {}

    if isinstance(vehicles_details, str):
        vehicle_items = [v.strip() for v in vehicles_details.split(',') if v.strip()]
    elif isinstance(vehicles_details, list):
        vehicle_items = vehicles_details
    else:
        vehicle_items = []

    for item in vehicle_items:
        vid = ''
        vname = ''
        vslug = ''
        vuid = ''
        if isinstance(item, dict):
            vid = str(item.get('id') or '').strip()
            vname = str(item.get('name') or '').strip()
            vslug = str(item.get('slug') or '').strip().lower()
            vuid = str(item.get('unique_id') or '').strip().lower()
        elif isinstance(item, str):
            vid = item.strip()
            vname = item.strip()
            vslug = item.strip().lower()

        entry = (catalog.get(vid) if vid else None) or (catalog.get(vslug) if vslug else None)

        if not entry:
            vname_lower = vname.lower()
            for c_id, c_data in catalog.items():
                if (c_id.lower() == vname_lower) or (vslug and c_id.lower() == vslug) or (vid and c_id.lower() == vid.lower()):
                    entry = c_data
                    break
                if c_data.get('name', '').lower() == vname_lower or c_data.get('label', '').lower() == vname_lower:
                    entry = c_data
                    break

        if not entry:
            vname_lower = vname.lower()
            for c_id, c_data in catalog.items():
                keywords = [kw.lower() for kw in c_data.get('keywords', [])]
                if any(kw in vname_lower or (vslug and kw in vslug) or (vuid and kw in vuid) for kw in keywords):
                    entry = c_data
                    break

        if entry:
            entry_risks = entry.get('risks', [])
            if entry_risks and len(entry_risks) > 0:
                lbl = entry.get('label') or entry.get('name') or vname or 'Véhicule Spécifique'
                lbl_en = entry.get('label_en') or entry.get('label') or entry.get('name') or vname or 'Specific Vehicle'
                if lbl not in matched_categories:
                    matched_categories[lbl] = {
                        'label': lbl,
                        'label_en': lbl_en,
                        'risks': entry_risks
                    }

    return list(matched_categories.values())


def get_merged_risk_assessment_for_project(project):
    """
    Retourne l'analyse des risques fusionnée complète pour un projet :
    - general : liste des risques généraux de travelling
    - vehicles : liste des sections de risques spécifiques pour chaque véhicule présent
    """
    general_risks = get_general_risk_assessment()
    
    vehicles_details = []
    if project:
        vehicles_details = getattr(project, 'vehicles_details', None)
        if not vehicles_details and getattr(project, 'vehicles_to_check', None):
            vehicles_details = project.vehicles_to_check

    vehicle_sections = get_risk_assessment_for_vehicles(vehicles_details)
    return {
        'general': general_risks,
        'vehicles': vehicle_sections
    }
