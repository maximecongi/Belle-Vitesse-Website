import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from services.common.kdrive.config import (
    KDRIVE_API_BASE,
    KDRIVE_API_TOKEN,
    KDRIVE_DRIVE_ID,
    KDRIVE_MAX_RETRIES,
    KDRIVE_TIMEOUT,
)

logger = logging.getLogger("kdrive.client")


class KDriveError(Exception):
    """Exception levée en cas d'échec d'un appel API kDrive."""

    def __init__(self, status_code: int, payload: Any, error_code: str = None, description: str = None):
        self.status_code = status_code
        self.payload = payload or {}
        if isinstance(payload, dict):
            err_dict = payload.get("error", {})
            self.error_code = error_code or (err_dict.get("code") if isinstance(err_dict, dict) else None)
            self.description = description or (err_dict.get("description") if isinstance(err_dict, dict) else str(payload))
        else:
            self.error_code = error_code
            self.description = description or str(payload)

        msg = f"kDrive HTTP {status_code} [{self.error_code}]: {self.description}"
        super().__init__(msg)


class KDriveClient:
    """
    Client HTTP minimal et robuste pour l'API Infomaniak kDrive v2/v3.
    Prend en charge l'authentification Bearer, les timeouts, et la gestion idempotente des doublons.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        drive_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        import os
        self.token = token or os.getenv("KDRIVE_API_TOKEN") or os.getenv("N8N_API_TOKEN", "") or KDRIVE_API_TOKEN
        self.drive_id = str(drive_id or os.getenv("KDRIVE_DRIVE_ID") or os.getenv("N8N_DRIVE_ID") or KDRIVE_DRIVE_ID)
        self.base_url = (base_url or os.getenv("KDRIVE_API_BASE") or KDRIVE_API_BASE).rstrip("/")
        self.timeout = timeout or int(os.getenv("KDRIVE_TIMEOUT", str(KDRIVE_TIMEOUT)))
        self.session = requests.Session()

    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if additional_headers:
            headers.update(additional_headers)
        return headers

    def _request(self, method: str, path: str, retries: int = KDRIVE_MAX_RETRIES, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        kwargs["headers"] = self._get_headers(kwargs.get("headers"))
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.session.request(method, url, **kwargs)
                try:
                    data = response.json()
                except ValueError:
                    data = {"raw": response.text}

                if not response.ok or (isinstance(data, dict) and data.get("result") == "error"):
                    status = response.status_code
                    # Retry automatique sur les erreurs 5xx ou 429
                    if (status >= 500 or status == 429) and attempt <= retries:
                        backoff = 2 ** attempt
                        logger.warning(f"⚠️ kDrive HTTP {status}, nouvel essai ({attempt}/{retries}) dans {backoff}s...")
                        time.sleep(backoff)
                        continue

                    raise KDriveError(status, data)

                return data

            except requests.RequestException as exc:
                if attempt <= retries:
                    backoff = 2 ** attempt
                    logger.warning(f"⚠️ Erreur réseau kDrive: {exc}, tentative {attempt}/{retries} dans {backoff}s...")
                    time.sleep(backoff)
                    continue
                raise KDriveError(0, {"exception": str(exc)}, error_code="network_error", description=str(exc))

    def get_file(self, file_id: int) -> Dict[str, Any]:
        """Récupère les métadonnées d'un fichier ou dossier (GET /3/drive/{drive_id}/files/{file_id})."""
        res = self._request("GET", f"/3/drive/{self.drive_id}/files/{file_id}")
        return res.get("data", {})

    def list_files(
        self, directory_id: int, cursor: Optional[str] = None, limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """
        Liste les fichiers et dossiers contenus dans un répertoire.
        Retourne (items, cursor, has_more).
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        res = self._request("GET", f"/3/drive/{self.drive_id}/files/{directory_id}/files", params=params)
        items = res.get("data", [])
        has_more = bool(res.get("has_more", False))
        next_cursor = res.get("cursor")
        return items, next_cursor, has_more

    def get_child_by_name(self, parent_id: int, name: str) -> Optional[Dict[str, Any]]:
        """Recherche un enfant direct par son nom exact dans un dossier parent."""
        cursor = None
        target_name = name.strip()
        while True:
            items, cursor, has_more = self.list_files(parent_id, cursor=cursor)
            for item in items:
                if item.get("name") == target_name:
                    return item
            if not has_more or not cursor:
                break
        return None

    def create_directory(
        self, parent_id: int, name: str, relative_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crée un répertoire sous parent_id.
        Supporte relative_path pour créer toute une chaîne intermédiaire en un seul appel !
        Si le dossier existe déjà (HTTP 400 destination_already_exists), retrouve l'ID sans échouer.
        """
        payload = {"name": name}
        if relative_path:
            payload["relative_path"] = relative_path.strip("/")

        try:
            res = self._request("POST", f"/3/drive/{self.drive_id}/files/{parent_id}/directory", json=payload)
            return res.get("data", {})
        except KDriveError as err:
            if err.error_code == "destination_already_exists":
                logger.info(f"ℹ️ Le dossier '{name}' existe déjà sous {parent_id}. Récupération de l'existant...")
                # Si relative_path était renseigné, trouver le parent direct
                curr_parent = parent_id
                if relative_path:
                    segments = [s for s in relative_path.strip("/").split("/") if s]
                    for seg in segments:
                        child = self.get_child_by_name(curr_parent, seg)
                        if not child:
                            raise err
                        curr_parent = child["id"]

                child = self.get_child_by_name(curr_parent, name)
                if child:
                    return child
            raise

    def upload(
        self,
        directory_id: int,
        filename: str,
        content_bytes: bytes,
        conflict: str = "error",
    ) -> Dict[str, Any]:
        """
        Upload binaire direct dans un répertoire kDrive (POST /3/drive/{drive_id}/upload).
        En cas de doublon (conflict='error' -> HTTP 409 file_already_exists_error),
        retrouve l'ID du fichier déjà présent pour garantir l'idempotence.
        """
        params = {
            "total_size": len(content_bytes),
            "directory_id": directory_id,
            "file_name": filename,
            "conflict": conflict,
        }
        headers = {"Content-Type": "application/octet-stream"}

        try:
            res = self._request(
                "POST",
                f"/3/drive/{self.drive_id}/upload",
                params=params,
                data=content_bytes,
                headers=headers,
            )
            return res.get("data", {})
        except KDriveError as err:
            if err.error_code == "file_already_exists_error":
                logger.info(f"ℹ️ Le fichier '{filename}' existe déjà dans {directory_id}. Récupération de l'ID...")
                child = self.get_child_by_name(directory_id, filename)
                if child:
                    return child
            raise

    def move(
        self, file_id: int, destination_directory_id: int, conflict: str = "error"
    ) -> Dict[str, Any]:
        """
        Déplace un fichier ou dossier vers un autre répertoire (POST /3/drive/{drive_id}/files/{file_id}/move/{dest_id}).
        """
        payload = {"conflict": conflict}
        res = self._request(
            "POST",
            f"/3/drive/{self.drive_id}/files/{file_id}/move/{destination_directory_id}",
            json=payload,
        )
        return res.get("data", {})

    def delete(self, file_id: int) -> Dict[str, Any]:
        """
        Supprime un fichier ou dossier vers la corbeille kDrive (DELETE /2/drive/{drive_id}/files/{file_id}).
        Si le fichier est déjà supprimé (HTTP 404), retourne un dictionnaire de complétion sans erreur.
        """
        try:
            res = self._request("DELETE", f"/2/drive/{self.drive_id}/files/{file_id}")
            return res.get("data", {})
        except KDriveError as err:
            if err.status_code == 404 or err.error_code in {"not_found", "file_not_found"}:
                logger.info(f"ℹ️ L'élément {file_id} est déjà supprimé sur kDrive (404).")
                return {"deleted": True, "already_deleted": True}
            raise
