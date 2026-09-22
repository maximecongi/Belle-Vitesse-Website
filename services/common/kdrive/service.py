"""
Service d'orchestration kDrive pour la plateforme Belle Vitesse.
Architecture modulaire basée sur des Mixins spécialisés (SRP) :
- ProjectTreeMixin : Gestion des arborescences de projet et cycle de vie (tree.py)
- UploadMixin : Téléversement synchrone et par lot (uploads.py)
- MaintenanceMixin : Purge orphelins, suppressions d'entités et nettoyage récursif (maintenance.py)
"""
import logging
from typing import Optional

from services.common.kdrive.client import KDriveClient
from services.common.kdrive.maintenance import MaintenanceMixin
from services.common.kdrive.tree import ProjectTreeMixin
from services.common.kdrive.uploads import UploadMixin

logger = logging.getLogger("kdrive.service")


class KDriveService(ProjectTreeMixin, UploadMixin, MaintenanceMixin):
    """
    Service métier d'orchestration kDrive pour la plateforme Belle Vitesse.
    Garantit l'idempotence, l'accès direct aux fichiers du disque local,
    l'envoi concurrent des pièces jointes et la suppression par ID.

    Cette classe de façade hérite de toutes les fonctionnalités réparties
    dans les mixins modulaires sans aucune rupture d'API pour les appelants.
    """

    def __init__(self, client: Optional[KDriveClient] = None):
        self.client = client or KDriveClient()
