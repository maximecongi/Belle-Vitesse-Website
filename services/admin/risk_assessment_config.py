# services/admin/risk_assessment_config.py
"""
Gestion du catalogue d'Analyse des Risques (Risk Assessment - BVRA)
Fournit les risques par défaut (Travelling et véhicules spécifiques) et les fonctions CRUD
pour l'administration de la Flotte et la génération des documents BVRA.
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
        "description_en": "A member of the public, a crew member or an outside vehicle may enter the vehicle’s path during a take, including by forcing their way through a lock-off.",
        "recommendations_fr": [
            "Faire définir et sécuriser la zone de roulage par la production avant chaque plan (périmètre, circulation, public).",
            "Pendant les prises, rouler uniquement dans une zone fermée à toute circulation extérieure (voie fermée par arrêté de l’autorité compétente, terrain privé ou piste), délimitée et sécurisée par la production.",
            "Vérifier que le blocage est en place avant chaque départ.",
            "Éloigner de la trajectoire toute personne non indispensable au plan.",
            "Placer des véhicules tampons devant et derrière pour protéger la scène.",
            "Relier chaque point de blocage au pilote par radio, pour pouvoir interrompre la prise immédiatement."
        ],
        "recommendations_en": [
            "Have the production define and secure the driving area before each shot (perimeter, traffic, public).",
            "During takes, drive only in an area closed to all outside traffic (road closed by order of the competent authority, private land or track), marked out and secured by the production.",
            "Check that the lock-off is in place before each start.",
            "Keep anyone not essential to the shot away from the vehicle’s path.",
            "Position buffer vehicles ahead and behind to protect the scene.",
            "Connect each lock-off point to the driver by radio, so the take can be stopped immediately."
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
        "description_en": "Gravel, potholes, mud, oil or wet ground reduce grip and can cause the driver to lose control of the vehicle.",
        "recommendations_fr": [
            "Reconnaître la trajectoire à pied ou à basse vitesse avant la première prise.",
            "Adapter la vitesse à l’état du sol.",
            "Suspendre le roulage en cas de doute."
        ],
        "recommendations_en": [
            "Survey the path on foot or at low speed before the first take.",
            "Adapt speed to ground conditions.",
            "Suspend driving if in doubt."
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
        "description_en": "Darkness, dust, smoke, special effects or glare can prevent the driver from seeing the path or the filmed subject.",
        "recommendations_fr": [
            "Baliser et éclairer la trajectoire de nuit.",
            "Adapter la vitesse à la visibilité.",
            "S’arrêter immédiatement si la visibilité est perdue."
        ],
        "recommendations_en": [
            "Mark out and light the path at night.",
            "Adapt speed to visibility.",
            "Stop immediately if visibility is lost."
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
        "description_en": "Rain, strong wind or cold make the floors slippery, hamper driving and tire out anyone exposed.",
        "recommendations_fr": [
            "Adapter ou suspendre le roulage selon la météo.",
            "Essuyer les planchers mouillés avant chaque prise.",
            "Équiper les personnes exposées selon la météo."
        ],
        "recommendations_en": [
            "Adapt or suspend driving according to the weather.",
            "Wipe wet floors dry before each take.",
            "Equip anyone exposed according to the weather."
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
        "description_en": "A picture vehicle may skid or leave its path, especially in turns and on wet ground, and strike crew or equipment at the edge of the path.",
        "recommendations_fr": [
            "Ne placer aucune personne ni caméra avec opérateur à l’extérieur des virages ou dans les zones de dérapage.",
            "Utiliser des caméras sans opérateur ou des protections à ces endroits.",
            "Choisir une trajectoire avec des zones de dégagement.",
            "Interdire l’accès aux piétons dans les virages et les zones de manœuvres rapides."
        ],
        "recommendations_en": [
            "Never place anyone, or any manned camera, on the outside of turns or in skid zones.",
            "Use unmanned cameras or protective barriers at these locations.",
            "Choose a path with run-off areas.",
            "Keep pedestrians out of turns and fast-maneuver areas."
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
        "description_en": "A boom, an arm or a camera extending beyond the vehicle can strike an overhead or side obstacle, or come close to a power line.",
        "recommendations_fr": [
            "Repérer les obstacles en hauteur et sur les côtés de la trajectoire.",
            "Garder une distance de sécurité adaptée avec les lignes électriques.",
            "Près des arbres, surveiller les branches qui peuvent entrer dans la cabine."
        ],
        "recommendations_en": [
            "Identify overhead and side obstacles along the path.",
            "Keep an appropriate safe distance from power lines.",
            "Near trees, watch out for branches that may enter the cab."
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
        "description_en": "A start or stop command misunderstood between the driver, the camera operator and the director’s team can cause an unexpected movement.",
        "recommendations_fr": [
            "Faire un safety meeting avant chaque plan.",
            "Désigner une seule personne pour donner les ordres de départ et d’arrêt.",
            "Garder une liaison radio permanente avec le pilote.",
            "Convenir d’un mot d’arrêt connu de toute l’équipe.",
            "Fixer à l’avance le point d’arrêt de chaque prise et le faire connaître à tous.",
            "Lors d’un dépassement, laisser le pilote qui dépasse décider du moment."
        ],
        "recommendations_en": [
            "Hold a safety meeting before each shot.",
            "Appoint a single person to give start and stop commands.",
            "Maintain a permanent radio link with the driver.",
            "Agree on a stop word known to the entire crew.",
            "Set the stopping point of each take in advance and make it known to everyone.",
            "When overtaking, let the overtaking driver decide when to pass."
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
        "description_en": "A last-minute change of path, speed or configuration increases the risk of error.",
        "recommendations_fr": [
            "Répéter à basse vitesse toute modification de trajectoire, de vitesse ou de configuration.",
            "Laisser au pilote et aux techniciens formés par Belle Vitesse le droit de refuser ou d’interrompre un mouvement.",
            "Refaire un safety meeting dès que la chorégraphie, les véhicules ou les personnes changent.",
            "Réévaluer les risques dès que les conditions changent."
        ],
        "recommendations_en": [
            "Rehearse at low speed any change of path, speed or configuration.",
            "Give the driver and Belle Vitesse-trained technicians the right to refuse or stop a move.",
            "Hold a new safety meeting whenever the choreography, vehicles or people change.",
            "Reassess the risks whenever conditions change."
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
        "description_en": "Back-to-back takes and schedule pressure can reduce the alertness of the driver and the crew.",
        "recommendations_fr": [
            "Prévoir des pauses régulières pour le pilote.",
            "Ne jamais réduire le temps de répétition ou de mise en place pour gagner du temps.",
            "Découper l’action en plans courts."
        ],
        "recommendations_en": [
            "Schedule regular breaks for the driver.",
            "Never cut rehearsal or setup time to save time.",
            "Break the action down into short shots."
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
        "description_en": "An actor or a non-specialist driver at the wheel of the picture vehicle may lose control or react poorly.",
        "recommendations_fr": [
            "Vérifier que le pilote du véhicule de jeu maîtrise ce qui lui est demandé.",
            "Ne jamais le pousser au‑delà de ses capacités.",
            "Prévoir un temps de répétition suffisant."
        ],
        "recommendations_en": [
            "Check that the picture vehicle driver can handle what is being asked of them.",
            "Never push them beyond their abilities.",
            "Allow enough rehearsal time."
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
        "description_en": "Crew members on foot (assistants, boom operator, grips), focused on their work, may not see the vehicle coming. Being electric, Belle Vitesse vehicles are almost silent: the crew may not hear them either, and be struck.",
        "recommendations_fr": [
            "Donner deux coups de klaxon avant chaque démarrage et un coup de klaxon à chaque arrêt.",
            "Prévenir l’équipe par radio avant chaque départ.",
            "Définir des positions fixes pour l’équipe au sol, hors trajectoire.",
            "Rouler au pas dans les zones où circule l’équipe.",
            "Respecter une distance de sécurité adaptée."
        ],
        "recommendations_en": [
            "Sound the horn twice before each start and once at each stop.",
            "Warn the crew by radio before each start.",
            "Set fixed positions for the ground crew, outside the vehicle’s path.",
            "Drive at walking pace in areas where crew are moving around.",
            "Keep an appropriate safe distance."
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
        "description_en": "Getting on or off a moving vehicle can result in a fall or crush injury.",
        "recommendations_fr": [
            "Ne jamais monter ni descendre tant que le véhicule n’est pas à l’arrêt complet.",
            "À l’arrêt, monter ou descendre seulement sur instruction du pilote."
        ],
        "recommendations_en": [
            "Never get on or off until the vehicle has come to a complete stop.",
            "When stopped, get on or off only when instructed by the driver."
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
        "description_en": "A person who boards without knowing the safety instructions may put themselves or others in danger.",
        "recommendations_fr": [
            "Faire un safety meeting avant la première montée de toute nouvelle personne.",
            "Réserver l’accès à bord aux personnes concernées et habilitées.",
            "Ne faire monter que les personnes indispensables au plan.",
            "Consulter le manuel officiel du véhicule, disponible à bord et via un QR code (eCar, eRider, eRover, eTrike et Segway)."
        ],
        "recommendations_en": [
            "Hold a safety meeting before any new person boards for the first time.",
            "Restrict access on board to the people concerned and authorized.",
            "Only allow on board the people essential to the shot.",
            "Consult the vehicle’s official manual, available on board and via a QR code (eCar, eRider, eRover, eTrike and Segway)."
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
        "description_en": "A camera operator who stands up or leans out to frame a shot may be thrown from the vehicle or strike an obstacle.",
        "recommendations_fr": [
            "Rester assis et attaché pendant le roulage.",
            "Garder les pieds sur le plancher ou le cale‑pied.",
            "Ne jamais sortir du gabarit du véhicule.",
            "Ne jamais s’asseoir sur les rambardes de sécurité.",
            "Utiliser une caméra télécommandée quand la position est trop exposée pour un opérateur."
        ],
        "recommendations_en": [
            "Remain seated and strapped in while the vehicle is moving.",
            "Keep your feet on the floor or the footrest.",
            "Never extend beyond the vehicle’s outline.",
            "Never sit on the safety rails.",
            "Use a remote-controlled camera when the position is too exposed for an operator."
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
        "description_en": "A camera operator or equipment placed in the driver’s field of vision, or the gestures and requests of someone on board, can obstruct the driver or divert their attention.",
        "recommendations_fr": [
            "Ne placer aucun matériel ni opérateur dans le champ de vision du pilote.",
            "Ne jamais gêner le pilote par des gestes ou des demandes pendant le roulage."
        ],
        "recommendations_en": [
            "Never place any equipment or operator in the driver’s field of vision.",
            "Never distract the driver with gestures or requests while the vehicle is moving."
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
        "description_en": "A poorly secured camera or accessory can come loose under vibration and braking, and a poorly stowed cable or strap can get caught in the wheels or trip the crew.",
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
            "Safety-cable and secure every technical component.",
            "Have every installation approved by a Belle Vitesse-trained technician.",
            "Check all fastenings before each run.",
            "Position equipment so that it cannot strike an occupant in the event of a sudden stop.",
            "Tie all cables and straps along the structure, and leave nothing trailing on the ground or near the wheels.",
            "Have the driver check the vehicle after each rigging change.",
            "Store any equipment not needed for the shot in the follow vehicle."
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
                "description_en": "Modified for filming, the eRover is not approved for use on roads open to the public. An accident on the road can cause serious injury and may not be covered by insurance.",
                "recommendations_fr": [
                        "Ne jamais faire circuler l’eRover sur une voie ouverte au public, y compris pour se déplacer entre deux décors. Tout manquement engage la seule responsabilité de la production.",
                        "Déplacer l’eRover entre deux décors sur une voie fermée à la circulation, ou par transport sur plateau ou remorque."
                ],
                "recommendations_en": [
                    "Never drive the eRover on a road open to the public, including to move between two sets. Any breach is the sole responsibility of the production.",
                    "Move the eRover between sets on a road closed to traffic, or transport it on a flatbed or trailer."
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
                "description_en": "When the eRover follows the filmed subject (actor, cyclist, picture vehicle), a fall or unexpected braking by the subject can cause a collision. When the subject follows the eRover, unexpected braking or poor speed management by the eRover can cause it. In both cases, the collision can cause serious injury.",
                "recommendations_fr": [
                        "Rouler à une vitesse régulière et éviter tout freinage brusque hors urgence.",
                        "Respecter une distance de sécurité adaptée à la vitesse et à la distance de freinage.",
                        "Répéter le plan à basse vitesse avant de tourner.",
                        "Schématiser les trajectoires complexes.",
                        "Garder une communication constante avec la mise en scène, le coordinateur cascade et le responsable du blocage."
                ],
                "recommendations_en": [
                    "Drive at a steady speed and avoid any sudden braking except in an emergency.",
                    "Keep a safe distance appropriate to the speed and braking distance.",
                    "Rehearse the shot at low speed before shooting.",
                    "Draw diagrams of complex paths.",
                    "Maintain constant communication with the director’s team, the stunt coordinator and the lock-off supervisor."
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
                "description_en": "The eRover is fitted with aluminum plates on a reinforced steel chassis, extension platforms and footrests. This structure does not deform on impact, and the installed rigging increases the vehicle’s footprint: even at low speed, an impact can cause serious injury.",
                "recommendations_fr": [
                        "Toujours installer les pare‑chocs en caoutchouc fournis sur les planchers d’extension et les cale‑pieds.",
                        "Faire valider chaque nouvelle installation par un technicien formé par Belle Vitesse.",
                        "Prendre en compte le gabarit réel dans le schéma des trajectoires et pendant la répétition.",
                        "Faire définir et sécuriser la zone de roulage par la production avant chaque plan.",
                        "Respecter une distance de sécurité adaptée avec toute personne."
                ],
                "recommendations_en": [
                    "Always fit the supplied rubber bumpers to the extension platforms and footrests.",
                    "Have every new installation approved by a Belle Vitesse-trained technician.",
                    "Take the actual footprint into account in the path diagram and during rehearsal.",
                    "Have the production define and secure the driving area before each shot.",
                    "Keep an appropriate safe distance from everyone."
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
                "description_en": "During emergency braking, passengers can be thrown violently against the vehicle or against the rigging installed for the shot.",
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
                    "Require a seatbelt for everyone on board, and a helmet and double harness for anyone outside the cab.",
                    "Inside the cab, keep your back against the seat and your feet flat.",
                    "Use the cab nets or doors, and check seatbelts, nets and fastenings before each use.",
                    "Never hold onto the roll cage or lean on the doors or nets.",
                    "Position equipment so that it cannot strike an occupant.",
                    "Rehearse the shot at low speed to limit unplanned braking.",
                    "Respect the speed limits set in the safety rules for people outside the cab."
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
                "description_en": "The front wheels are exposed to allow free steering. A passenger seated too close may inadvertently trap their foot between the wheel and the chassis and be seriously injured.",
                "recommendations_fr": [
                        "Ne jamais installer quelqu’un trop près des roues avant.",
                        "Sécuriser au maximum toute personne installée à l’avant, pour qu’aucun membre ne puisse atteindre une roue.",
                        "Imposer la ceinture à toute personne à bord."
                ],
                "recommendations_en": [
                    "Never seat anyone too close to the front wheels.",
                    "Secure anyone seated at the front as fully as possible, so that no limb can reach a wheel.",
                    "Require a seatbelt for everyone on board."
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
                "description_en": "A scarf or loose clothing can get caught in the wheels and pull in the person wearing it.",
                "recommendations_fr": [
                        "Retirer ou attacher les écharpes et vêtements amples avant tout roulage."
                ],
                "recommendations_en": [
                    "Remove or tie back scarves and loose clothing before any driving."
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
                "description_en": "During a wheel change, a poorly chocked or poorly supported vehicle can fall or tip over.",
                "recommendations_fr": [
                        "Réserver le levage du véhicule aux techniciens formés par Belle Vitesse.",
                        "Lever le véhicule uniquement sur un sol plat et dur, en position P, roues calées.",
                        "Utiliser un cric adapté et ne jamais passer sous le véhicule sans chandelles."
                ],
                "recommendations_en": [
                    "Restrict vehicle lifting to Belle Vitesse-trained technicians.",
                    "Lift the vehicle only on flat, hard ground, in P, with the wheels chocked.",
                    "Use a suitable jack and never go under the vehicle without jack stands."
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
                "description_en": "The eRover can roll over in a turn taken too fast or too tight, even on flat ground. On asphalt, the high grip increases this risk.",
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
                    "Reduce speed before each turn, especially on asphalt, and avoid sudden maneuvers, slides, skids and hard acceleration in turns, even from a standstill.",
                    "Anticipate slopes, ruts and changes in grip. On slopes, drive straight up or down in all-wheel drive (AWD), never in neutral or across the slope.",
                    "Never jump bumps.",
                    "Respect the maximum number of people on board (1 driver and 3 passengers) and distribute the weight evenly.",
                    "Set the speed limiter (SPD LIM) for the shot at each start-up, as it deactivates when the ignition is switched off (the vehicle remains restricted to 60 km/h in France).",
                    "If the vehicle tips over, hold on firmly to the grab handles and keep every part of your body inside the vehicle.",
                    "After a rollover or impact, do not resume driving until a full inspection has been carried out (seatbelts, roll cage, brakes, steering, electrical system)."
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
                "description_en": "The play between the brake pedal and the accelerator can cause jerky movements, and the eRover may continue to accelerate slightly after the accelerator is released. Sport mode makes acceleration very sharp and the vehicle hard to control.",
                "recommendations_fr": [
                        "Confier la conduite uniquement à un pilote validé par Belle Vitesse ou mandaté par le coordinateur cascade.",
                        "Ne jamais appuyer sur les deux pédales en même temps, ce qui peut couper la puissance moteur.",
                        "Anticiper les freinages et tenir compte des distances de freinage.",
                        "Ne pas utiliser le mode Sport, sauf validation par un technicien formé par Belle Vitesse.",
                        "Répéter le plan à basse vitesse."
                ],
                "recommendations_en": [
                    "Entrust driving only to a driver approved by Belle Vitesse or appointed by the stunt coordinator.",
                    "Never press both pedals at the same time, as this can cut motor power.",
                    "Anticipate braking and allow for braking distances.",
                    "Do not use Sport mode unless approved by a Belle Vitesse-trained technician.",
                    "Rehearse the shot at low speed."
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
                "description_en": "Selecting the wrong direction of travel (F/R) can send the vehicle the opposite way from what was planned. When stopped, the slight give in the parking brake can let it roll forward or backward by about 20 cm (8 in).",
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
                    "Check the position of the F/R selector before each start.",
                    "Never change direction while moving.",
                    "When reversing, check that the area is clear, accelerate gently and drive slowly.",
                    "Always shift into P when stopped.",
                    "On a slope, chock the rear wheels on the downhill side.",
                    "Remove the key when the vehicle is left unattended.",
                    "Never stand directly in front of or behind the stationary vehicle."
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
                "description_en": "Water that is too deep or a current can cause loss of grip and loss of control of the vehicle. After driving through water, wet brakes are less effective.",
                "recommendations_fr": [
                        "Ne jamais rouler dans une eau qui dépasse le plancher ou dans un courant.",
                        "Après un passage dans l’eau, tester les freins en roulant lentement."
                ],
                "recommendations_en": [
                    "Never drive through water deeper than the floor or through a current.",
                    "After driving through water, test the brakes while driving slowly."
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
                "description_en": "A low battery, motor or battery overheating, extreme temperatures or water in the electrical components can reduce power or stop the vehicle in the middle of a take.",
                "recommendations_fr": [
                        "Commencer chaque plan avec une batterie suffisamment chargée, et recharger pendant les pauses.",
                        "Arrêter les prises et ramener le véhicule dès l’alerte LOW CHARGE ou le voyant de surchauffe.",
                        "Par grand froid, laisser chauffer la batterie quelques minutes avant de rouler.",
                        "Garder une distance de sécurité adaptée avec les véhicules qui suivent, pour absorber un arrêt imprévu."
                ],
                "recommendations_en": [
                    "Start each shot with a sufficiently charged battery, and recharge during breaks.",
                    "Stop shooting and bring the vehicle back as soon as the LOW CHARGE alert or the overheating warning light appears.",
                    "In very cold weather, let the battery warm up for a few minutes before driving.",
                    "Keep an appropriate safe distance from following vehicles, to absorb an unplanned stop."
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
                "description_en": "A defect not spotted before driving (tires, brakes, steering, seatbelts) increases the risk of an accident.",
                "recommendations_fr": [
                        "Faire avant chaque journée l’inspection préconisée par Polaris : charge, liquide de frein, direction, suspension, feux et ceintures.",
                        "Vérifier la pression des pneus (83 kPa à l’avant, 97 kPa à l’arrière) et les remplacer sous 3 mm de sculpture.",
                        "Vérifier le serrage des roues et retirer les débris inflammables (herbe, feuilles).",
                        "Inspecter aussi le véhicule après chaque journée.",
                        "Faire réparer tout élément défectueux par un technicien qualifié avant de rouler, et retirer du service tout matériel cassé."
                ],
                "recommendations_en": [
                    "Before each day, carry out the inspection recommended by Polaris: charge, brake fluid, steering, suspension, lights and seatbelts.",
                    "Check tire pressure (83 kPa / 12 psi front, 97 kPa / 14 psi rear) and replace tires with less than 3 mm of tread.",
                    "Check wheel nut tightness and remove flammable debris (grass, leaves).",
                    "Also inspect the vehicle at the end of each day.",
                    "Have any defective part repaired by a qualified technician before driving, and take any broken equipment out of service."
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
                "description_en": "The weight of the rigging, equipment and people on board lengthens braking distances and increases the risk of loss of control.",
                "recommendations_fr": [
                        "Ne jamais dépasser 680 kg de charge totale (pilote, passagers, chargement et accessoires compris).",
                        "Au‑delà de 227 kg de charge totale, rouler en gamme basse (LOW).",
                        "Au‑delà de 249 kg de charge totale, ne pas dépasser 48 km/h.",
                        "Réduire la vitesse et anticiper les freinages quand le véhicule est chargé."
                ],
                "recommendations_en": [
                    "Never exceed a total load of 680 kg (1,500 lb), including driver, passengers, cargo and accessories.",
                    "Above a total load of 227 kg (500 lb), drive in low range (LOW).",
                    "Above a total load of 249 kg (550 lb), do not exceed 48 km/h (30 mph).",
                    "Reduce speed and anticipate braking when the vehicle is loaded."
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
                "description_en": "Reckless driving, or driving under the influence of alcohol, medication or drugs, can cause a serious accident.",
                "recommendations_fr": [
                        "Interdire toute conduite imprudente.",
                        "Interdire le pilotage sous l’emprise de l’alcool, de médicaments ou de drogues.",
                        "Ne pas manipuler l’écran ni régler le volant en roulant."
                ],
                "recommendations_en": [
                    "Prohibit any reckless driving.",
                    "Prohibit driving under the influence of alcohol, medication or drugs.",
                    "Do not operate the screen or adjust the steering wheel while driving."
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
                "description_en": "A grip rig that gives way (tubes, clamps, boom) can cause equipment or people to fall and result in serious injury.",
                "recommendations_fr": [
                        "Réserver l’installation de la machinerie aux personnes habilitées par Belle Vitesse.",
                        "Faire valider chaque nouvelle installation par un technicien formé par Belle Vitesse.",
                        "Vérifier les serrages avant chaque roulage.",
                        "Imposer le casque à toute personne à l’extérieur de l’habitacle."
                ],
                "recommendations_en": [
                    "Restrict rigging installation to people authorized by Belle Vitesse.",
                    "Have every new installation approved by a Belle Vitesse-trained technician.",
                    "Check all fastenings before each run.",
                    "Require a helmet for anyone outside the cab."
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
                "description_en": "While rigging is being installed, slipping or falling from the vehicle can cause serious injury. Moisture and water make the floors slippery.",
                "recommendations_fr": [
                        "Préparer le véhicule hors circulation.",
                        "Essuyer les planchers mouillés avant toute installation.",
                        "Réserver l’installation aux personnes habilitées par Belle Vitesse."
                ],
                "recommendations_en": [
                    "Prepare the vehicle away from traffic.",
                    "Wipe wet floors dry before any installation.",
                    "Restrict installation to people authorized by Belle Vitesse."
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
                "description_en": "Poorly secured tools or equipment can fall off while driving and cause the filmed subject to fall or be struck if it is following the eRover.",
                "recommendations_fr": [
                        "Élinguer et sécuriser tout élément technique.",
                        "Sécuriser tout matériel supplémentaire (sac batterie, caméra, commande de point).",
                        "Ne laisser aucun outil libre sur le véhicule avant le roulage."
                ],
                "recommendations_en": [
                    "Safety-cable and secure every technical component.",
                    "Secure any additional equipment (battery bag, camera, focus control).",
                    "Leave no loose tools on the vehicle before driving."
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
                "description_en": "Contact with the battery, the charger or the high-voltage (orange) cables can cause electrocution.",
                "recommendations_fr": [
                        "Réserver toute intervention sur la batterie aux techniciens formés par Belle Vitesse.",
                        "Ne jamais toucher les câbles haute tension, ni ouvrir la batterie ou le chargeur.",
                        "Après un choc ou un retournement, couper la haute tension (boucle de sécurité sous le bac du siège) et faire inspecter le véhicule avant de rouler.",
                        "N’apporter aucune modification interne au véhicule."
                ],
                "recommendations_en": [
                    "Restrict any work on the battery to Belle Vitesse-trained technicians.",
                    "Never touch the high-voltage cables, or open the battery or the charger.",
                    "After an impact or rollover, disconnect the high voltage (safety loop under the seat base) and have the vehicle inspected before driving.",
                    "Make no internal modifications to the vehicle."
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
                "description_en": "A camera, monitor or light connected to the vehicle, an object in contact with the 12 V battery or an external power source can blow a fuse, cut the lights or motor power, or cause a short circuit and a fire.",
                "recommendations_fr": [
                        "Respecter la capacité des prises 12 V : 10 A au tableau de bord, 15 A à l’arrière.",
                        "Ne raccorder aucun accessoire au circuit électrique du véhicule sans validation par un technicien formé par Belle Vitesse.",
                        "Ne rien ranger sous le bac du siège, au contact de la batterie 12 V.",
                        "Ne jamais brancher une source extérieure sur la batterie 12 V (pas de démarrage par câbles)."
                ],
                "recommendations_en": [
                    "Respect the capacity of the 12 V outlets: 10 A on the dashboard, 15 A at the rear.",
                    "Do not connect any accessory to the vehicle’s electrical circuit without approval from a Belle Vitesse-trained technician.",
                    "Do not store anything under the seat base, in contact with the 12 V battery.",
                    "Never connect an external power source to the 12 V battery (no jump-starting)."
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
                "description_en": "During loading or unloading, the person guiding the driver can be crushed if they are in the vehicle’s line of travel or if the ramps slip.",
                "recommendations_fr": [
                        "Charger et décharger à deux : le pilote et une personne qui le guide.",
                        "Ne jamais se trouver dans l’axe de roulage du véhicule.",
                        "Toujours se trouver à plus de 2 m du véhicule.",
                        "Réserver le chargement et le déchargement aux personnes habilitées par Belle Vitesse."
                ],
                "recommendations_en": [
                    "Load and unload with two people: the driver and a spotter guiding them.",
                    "Never stand in the vehicle’s line of travel.",
                    "Always stay more than 2 m (6.5 ft) from the vehicle.",
                    "Restrict loading and unloading to people authorized by Belle Vitesse."
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
                "description_en": "An unsuitable or poorly secured ramp can slip during loading or unloading and cause the vehicle to fall.",
                "recommendations_fr": [
                        "Utiliser uniquement les rampes fournies et homologuées.",
                        "Sécuriser les rampes avec des sangles (et des goupilles si disponibles)."
                ],
                "recommendations_en": [
                    "Use only the supplied, approved ramps.",
                    "Secure the ramps with straps (and locking pins if available)."
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
                "description_en": "A poorly strapped vehicle can shift or fall during transport.",
                "recommendations_fr": [
                        "Sangler le véhicule en 4 points, 2 à l’avant et 2 à l’arrière, sur les points d’arrimage prévus par Polaris.",
                        "Avant le transport, passer en position P, retirer la clé, et retirer ou sécuriser la machinerie et toute pièce libre.",
                        "Sur une remorque ouverte, charger le véhicule face à la route, ou retirer le toit."
                ],
                "recommendations_en": [
                    "Strap the vehicle down at 4 points, 2 at the front and 2 at the rear, using the tie-down points specified by Polaris.",
                    "Before transport, shift into P, remove the key, and remove or secure the rigging and any loose parts.",
                    "On an open trailer, load the vehicle facing forward, or remove the roof."
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
                "description_en": "Unattended charging, an unsuitable charger, a damaged cable or an unsuitable electrical installation can start a fire.",
                "recommendations_fr": [
                        "Ne jamais laisser le véhicule en charge sans surveillance.",
                        "Recharger uniquement avec le chargeur fourni, branché directement sur une prise protégée par un différentiel, d’au moins 15 A et sans autre appareil.",
                        "Ne jamais utiliser de rallonge, de multiprise ni d’adaptateur.",
                        "Vérifier l’état du câble, des prises et du port de charge avant chaque recharge.",
                        "Sous la pluie, recharger uniquement sur une prise extérieure étanche.",
                        "Recharger loin des matières inflammables, câble placé là où il ne peut pas être écrasé."
                ],
                "recommendations_en": [
                    "Never leave the vehicle charging unattended.",
                    "Charge only with the supplied charger, plugged directly into a dedicated outlet of at least 15 A protected by a residual-current device (GFCI), with no other appliance connected.",
                    "Never use an extension cord, power strip or adapter.",
                    "Check the condition of the cable, plugs and charging port before each charge.",
                    "In the rain, charge only from a weatherproof outdoor outlet.",
                    "Charge away from flammable materials, with the cable placed where it cannot be crushed."
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
                "description_en": "An impact, a rollover or water ingress can damage the battery without any visible sign, and cause a fire several hours later.",
                "recommendations_fr": [
                        "Après tout choc, retournement ou passage dans l’eau profonde, faire contrôler la batterie par un technicien formé par Belle Vitesse avant de rouler.",
                        "En cas de doute, garer le véhicule à l’extérieur, loin de tout ce qui peut brûler."
                ],
                "recommendations_en": [
                    "After any impact, rollover or deep-water crossing, have the battery checked by a Belle Vitesse-trained technician before driving.",
                    "If in doubt, park the vehicle outdoors, away from anything that can burn."
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
                "description_en": "A battery failure can cause its temperature to rise very quickly and lead to a fire or explosion. A battery fire is hard to extinguish and can reignite after being put out.",
                "recommendations_fr": [
                        "En cas de fumée, d’odeur anormale ou d’alerte « DANGER EXIT NOW FIRE » au tableau de bord, arrêter le véhicule et faire descendre tout le monde immédiatement.",
                        "S’éloigner du véhicule et appeler les pompiers (18 ou 112) en précisant qu’il s’agit d’un véhicule électrique.",
                        "Ne jamais tenter d’éteindre soi‑même un feu de batterie déclaré.",
                        "Prévoir à proximité du véhicule un extincteur adapté pour un départ de feu sur les accessoires."
                ],
                "recommendations_en": [
                    "In case of smoke, an unusual smell or a “DANGER EXIT NOW FIRE” alert on the dashboard, stop the vehicle and get everyone out immediately.",
                    "Move away from the vehicle and call the fire department (18 or 112 in France), stating that it is an electric vehicle.",
                    "Never attempt to put out a battery fire yourself once it has started.",
                    "Keep a suitable fire extinguisher near the vehicle for any fire starting on the accessories."
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
                "description_en": "Designed for motocross tracks, the Stark Varg MX 1.2 is not approved for use on roads open to the public. An accident on the road can cause serious injury and may not be covered by insurance.",
                "recommendations_fr": [
                        "Ne jamais faire circuler l’eRider sur une voie ouverte au public, y compris pour se déplacer entre deux décors. Tout manquement engage la seule responsabilité de la production.",
                        "Déplacer l’eRider entre deux décors sur une voie fermée à la circulation, ou par transport sur remorque."
                ],
                "recommendations_en": [
                    "Never ride the eRider on a road open to the public, including to move between two sets. Any breach is the sole responsibility of the production.",
                    "Move the eRider between sets on a road closed to traffic, or transport it on a trailer."
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
                "description_en": "In close tracking shots, a path error or an unplanned stop by the filmed subject (actor, cyclist, picture vehicle) can cause a collision and serious injury.",
                "recommendations_fr": [
                        "Respecter une distance de sécurité adaptée à la vitesse et à la distance de freinage.",
                        "Répéter le plan à basse vitesse avant de tourner.",
                        "Schématiser les trajectoires complexes.",
                        "Garder une communication constante avec la mise en scène, le coordinateur cascade et le responsable du blocage."
                ],
                "recommendations_en": [
                    "Keep a safe distance appropriate to the speed and braking distance.",
                    "Rehearse the shot at low speed before shooting.",
                    "Draw diagrams of complex paths.",
                    "Maintain constant communication with the director’s team, the stunt coordinator and the lock-off supervisor."
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
                "description_en": "On a motorcycle, the rider has no protection. A stunt, a picture vehicle, a person or an object entering their path can cause a very serious fall or collision.",
                "recommendations_fr": [
                        "Garder la trajectoire de la moto entièrement dégagée pendant chaque prise.",
                        "Préparer chaque cascade avec le coordinateur cascade et le pilote, et la répéter à basse vitesse.",
                        "Garder une distance de sécurité adaptée avec toute cascade ou tout effet spécial.",
                        "Ne jamais introduire un objet ou un effet dans la trajectoire sans l’accord du pilote."
                ],
                "recommendations_en": [
                    "Keep the motorcycle’s path completely clear during each take.",
                    "Prepare each stunt with the stunt coordinator and the rider, and rehearse it at low speed.",
                    "Keep an appropriate safe distance from any stunt or special effect.",
                    "Never introduce an object or effect into the path without the rider’s agreement."
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
                "description_en": "Loss of grip, sudden braking or an obstacle can cause the rider to fall. Braking with the front brake alone can throw the rider over the handlebars.",
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
                    "Entrust riding only to an experienced rider approved by Belle Vitesse or appointed by the stunt coordinator.",
                    "Require the rider to wear a helmet, boots, gloves, protective trousers and jacket, all in perfect condition.",
                    "Use the front and rear brakes together.",
                    "Adapt speed to the terrain and visibility, allowing for longer braking distances on wet ground.",
                    "Do not ride at night or in low light without lights and reflectors.",
                    "Rehearse the shot at low speed.",
                    "In the event of an accident, switch off the motorcycle and assist the victim."
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
                "description_en": "When the motorcycle is switched on, the chain and wheels can turn and catch a hand, a piece of clothing or a strap.",
                "recommendations_fr": [
                        "Ne jamais approcher la chaîne ni les roues quand la moto est allumée.",
                        "Retirer ou attacher les écharpes et vêtements amples avant tout roulage.",
                        "Éteindre complètement la moto avant toute intervention, tout nettoyage ou toute installation."
                ],
                "recommendations_en": [
                    "Never go near the chain or wheels when the motorcycle is switched on.",
                    "Remove or tie back scarves and loose clothing before any riding.",
                    "Switch the motorcycle off completely before any work, cleaning or installation."
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
                "description_en": "The electric motor delivers all its torque instantly. Too much throttle can cause loss of control, a front-wheel lift or a fall.",
                "recommendations_fr": [
                        "Choisir le mode de puissance adapté au plan et le faire valider par un technicien formé par Belle Vitesse.",
                        "Changer de mode uniquement à l’arrêt ou avec précaution, en prévenant l’équipe."
                ],
                "recommendations_en": [
                    "Choose the power mode suited to the shot and have it approved by a Belle Vitesse-trained technician.",
                    "Change modes only when stopped or with caution, after warning the crew."
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
                "description_en": "If the motorcycle is switched on, a twist of the throttle while getting on or off can set it in motion.",
                "recommendations_fr": [
                        "Éteindre la moto avec le bouton On/Off dès qu’elle ne roule pas.",
                        "Ne jamais monter ni descendre en tenant la poignée d’accélérateur.",
                        "Ne pas maintenir appuyés les boutons de mode, qui activent le mode Crawl en marche avant ou arrière."
                ],
                "recommendations_en": [
                    "Switch the motorcycle off with the On/Off button as soon as it is not moving.",
                    "Never get on or off while holding the throttle grip.",
                    "Do not hold down the mode buttons, which activate Crawl mode forward or in reverse."
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
                "description_en": "A low battery, an out-of-range temperature or an overload can reduce power and range, sometimes in the middle of a take.",
                "recommendations_fr": [
                        "Commencer chaque plan avec une batterie suffisamment chargée, et recharger pendant les pauses.",
                        "Arrêter les prises dès que le voyant de puissance limitée s’allume.",
                        "Utiliser la moto de préférence entre 0 et 25 °C."
                ],
                "recommendations_en": [
                    "Start each shot with a sufficiently charged battery, and recharge during breaks.",
                    "Stop shooting as soon as the limited-power warning light comes on.",
                    "Preferably use the motorcycle between 0 and 25 °C (32 and 77 °F)."
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
                "description_en": "A defect not spotted before riding (fastenings, tires, rims, brakes, grips) increases the risk of a fall.",
                "recommendations_fr": [
                        "Vérifier avant chaque journée le serrage des écrous et boulons, l’état des pneus et des jantes, les poignées et les freins à l’arrêt.",
                        "Avec des mousses, ne pas dépasser 130 km/h et les regraisser au plus tard toutes les 5 heures d’utilisation.",
                        "Inspecter aussi le véhicule après chaque journée.",
                        "Faire réparer tout élément défectueux par un technicien qualifié avant de rouler, et retirer du service tout matériel cassé."
                ],
                "recommendations_en": [
                    "Before each day, check nut and bolt tightness, tire and rim condition, the grips and the brakes while stationary.",
                    "With mousse inserts, do not exceed 130 km/h (80 mph) and re-grease them at least every 5 hours of use.",
                    "Also inspect the motorcycle at the end of each day.",
                    "Have any defective part repaired by a qualified technician before riding, and take any broken equipment out of service."
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
                "description_en": "Beyond the maximum load the suspension is set up for, rider and equipment included, the motorcycle becomes unstable and the rider may lose control.",
                "recommendations_fr": [
                        "Ne jamais dépasser la charge maximale prévue par la suspension installée, pilote et matériel compris.",
                        "Réduire la vitesse et anticiper les freinages quand la moto est chargée."
                ],
                "recommendations_en": [
                    "Never exceed the maximum load the installed suspension is set up for, rider and equipment included.",
                    "Reduce speed and anticipate braking when the motorcycle is loaded."
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
                "description_en": "Reckless riding, or riding under the influence of alcohol, medication or drugs, can cause a serious fall.",
                "recommendations_fr": [
                        "Interdire toute conduite imprudente.",
                        "Interdire le pilotage sous l’emprise de l’alcool, de médicaments ou de drogues."
                ],
                "recommendations_en": [
                    "Prohibit any reckless riding.",
                    "Prohibit riding under the influence of alcohol, medication or drugs."
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
                "description_en": "During installation or equipment handling, a poorly held motorcycle can tip over and injure someone or damage equipment.",
                "recommendations_fr": [
                        "Maintenir la moto sur le système de docking prévu pendant toute installation ou manipulation de matériel.",
                        "Éteindre complètement la moto avant toute installation."
                ],
                "recommendations_en": [
                    "Keep the motorcycle on the dedicated docking stand throughout any installation or equipment handling.",
                    "Switch the motorcycle off completely before any installation."
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
                "description_en": "A poorly secured camera or mount can come loose, unbalance the motorcycle or obstruct the rider.",
                "recommendations_fr": [
                        "Réserver l’installation du support caméra aux personnes habilitées par Belle Vitesse.",
                        "Faire valider chaque installation par un technicien formé par Belle Vitesse.",
                        "Élinguer et sécuriser tout élément technique.",
                        "Vérifier que le matériel ne gêne ni le guidon, ni les commandes, ni la vue du pilote."
                ],
                "recommendations_en": [
                    "Restrict camera mount installation to people authorized by Belle Vitesse.",
                    "Have every installation approved by a Belle Vitesse-trained technician.",
                    "Safety-cable and secure every technical component.",
                    "Check that the equipment does not obstruct the handlebars, the controls or the rider’s view."
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
                "description_en": "A camera or anti-vibration arm mounted off-center unbalances the motorcycle. Too far back, without enough counterweight at the front, it lightens the front wheel: the wheel loses traction, the steering becomes vague and the rider may lose control.",
                "recommendations_fr": [
                        "Toujours équilibrer la moto avec des contrepoids cohérents à l’avant ou à l’arrière, selon la position du matériel.",
                        "Limiter le déport du bras anti‑vibration au strict nécessaire.",
                        "Avant chaque plan, vérifier à basse vitesse que la direction reste précise et que la roue avant garde son appui.",
                        "Faire valider la configuration par un technicien formé par Belle Vitesse, sans dépasser la charge maximale prévue par la suspension installée."
                ],
                "recommendations_en": [
                    "Always balance the motorcycle with appropriate counterweights at the front or rear, depending on where the equipment is mounted.",
                    "Keep the anti-vibration arm’s offset to the strict minimum.",
                    "Before each shot, check at low speed that the steering stays precise and the front wheel keeps its traction.",
                    "Have the configuration approved by a Belle Vitesse-trained technician, without exceeding the maximum load the installed suspension is set up for."
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
                "description_en": "Contact with the battery, the motor or the high-voltage cables can cause electrocution.",
                "recommendations_fr": [
                        "Réserver toute intervention sur la batterie et le moteur aux techniciens formés par Belle Vitesse.",
                        "Ne jamais ouvrir la batterie ni le moteur, ni toucher les câbles haute tension.",
                        "Éteindre complètement la moto avant toute intervention.",
                        "N’apporter aucune modification à la moto."
                ],
                "recommendations_en": [
                    "Restrict any work on the battery and motor to Belle Vitesse-trained technicians.",
                    "Never open the battery or the motor, or touch the high-voltage cables.",
                    "Switch the motorcycle off completely before any work.",
                    "Make no modifications to the motorcycle."
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
                "description_en": "A poorly strapped or poorly handled motorcycle can shift or fall during transport.",
                "recommendations_fr": [
                        "Transporter la moto éteinte, sur ses deux roues, sur une remorque horizontale de capacité suffisante.",
                        "Ne jamais soulever la moto avec un engin de levage.",
                        "Utiliser le système de docking prévu pour garder la moto stable pendant les manipulations.",
                        "Sangler la moto autour de la fourche et du té inférieur."
                ],
                "recommendations_en": [
                    "Transport the motorcycle switched off, on both wheels, on a level trailer of sufficient capacity.",
                    "Never lift the motorcycle with lifting equipment.",
                    "Use the dedicated docking stand to keep the motorcycle stable during handling.",
                    "Strap the motorcycle around the fork and the lower triple clamp."
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
                "description_en": "Unattended charging, an unsuitable outlet, nearby flammable materials or a wet battery can start a fire.",
                "recommendations_fr": [
                        "Ne jamais laisser la moto en charge sans surveillance, ni la couvrir pendant la charge.",
                        "Recharger dans un endroit sec et ventilé, loin des matières inflammables.",
                        "Utiliser une prise reliée à la terre et protégée par un différentiel, et débrancher dès la fin de la charge.",
                        "Ne pas recharger en dessous de 4 °C, ni une batterie humide ou exposée à l’eau de mer."
                ],
                "recommendations_en": [
                    "Never leave the motorcycle charging unattended, or cover it while charging.",
                    "Charge in a dry, ventilated place, away from flammable materials.",
                    "Use a grounded outlet protected by a residual-current device (GFCI), and unplug as soon as charging is complete.",
                    "Do not charge below 4 °C (39 °F), or charge a battery that is wet or has been exposed to seawater."
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
                "description_en": "A fall or impact can damage the battery without any visible sign. A battery that is deformed, noisy or abnormally hot can catch fire or explode.",
                "recommendations_fr": [
                        "Après toute chute, faire contrôler la batterie par un technicien formé par Belle Vitesse avant de rouler ou de recharger.",
                        "Ne jamais utiliser ni recharger une batterie déformée, bruyante ou anormalement chaude.",
                        "Ne jamais ranger en intérieur une moto dont la batterie ou un composant électrique est endommagé."
                ],
                "recommendations_en": [
                    "After any fall, have the battery checked by a Belle Vitesse-trained technician before riding or charging.",
                    "Never use or charge a battery that is deformed, noisy or abnormally hot.",
                    "Never store a motorcycle indoors if its battery or any electrical component is damaged."
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
                "description_en": "A battery failure can cause its temperature to rise very quickly and lead to a fire or explosion. A battery fire is hard to extinguish and can reignite after being put out.",
                "recommendations_fr": [
                        "En cas de fumée, d’odeur anormale ou de chaleur excessive, éteindre la moto et s’en éloigner immédiatement.",
                        "S’éloigner du véhicule et appeler les pompiers (18 ou 112) en précisant qu’il s’agit d’un véhicule électrique.",
                        "Ne jamais tenter d’éteindre soi‑même un feu de batterie déclaré."
                ],
                "recommendations_en": [
                    "In case of smoke, an unusual smell or excessive heat, switch off the motorcycle and move away from it immediately.",
                    "Move away from the vehicle and call the fire department (18 or 112 in France), stating that it is an electric vehicle.",
                    "Never attempt to put out a battery fire yourself once it has started."
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
