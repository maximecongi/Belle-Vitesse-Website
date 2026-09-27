"""
Module de pagination serveur réutilisable pour l'administration et les APIs.

Fournit une structure Pagination standardisée compatible Jinja/Flask,
avec calcul des index, navigation, gestion des ellipses et génération d'URLs
préservant les paramètres de filtrage actifs dans la requête courante.
"""

import math
from typing import Any, Callable, Dict, Generator, List, Optional
from flask import request, url_for


class Pagination:
    """
    Conteneur de données paginées pour les listes serveur.
    """

    def __init__(
        self,
        items: List[Any],
        page: int = 1,
        per_page: int = 10,
        total: int = 0,
    ):
        self.items = items
        self.page = max(1, int(page))
        self.per_page = max(1, int(per_page))
        self.total = max(0, int(total))

    @property
    def pages(self) -> int:
        """Nombre total de pages."""
        if self.per_page <= 0 or self.total == 0:
            return 1
        return max(1, math.ceil(self.total / self.per_page))

    @property
    def has_prev(self) -> bool:
        """Indique s'il existe une page précédente."""
        return self.page > 1

    @property
    def has_next(self) -> bool:
        """Indique s'il existe une page suivante."""
        return self.page < self.pages

    @property
    def prev_num(self) -> Optional[int]:
        """Numéro de la page précédente ou None."""
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self) -> Optional[int]:
        """Numéro de la page suivante ou None."""
        return self.page + 1 if self.has_next else None

    @property
    def start_index(self) -> int:
        """Index du premier élément affiché (1-indexé, 0 si vide)."""
        if self.total == 0:
            return 0
        return (self.page - 1) * self.per_page + 1

    @property
    def end_index(self) -> int:
        """Index du dernier élément affiché (1-indexé, 0 si vide)."""
        if self.total == 0:
            return 0
        return min(self.page * self.per_page, self.total)

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 2,
        right_edge: int = 2,
    ) -> Generator[Optional[int], None, None]:
        """
        Génère les numéros de page à afficher avec None pour insérer des ellipses.
        Exemple : [1, 2, None, 4, 5, 6, None, 19, 20]
        """
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (self.page - left_current <= num <= self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num

    def url_for_page(self, page_num: int, endpoint: Optional[str] = None) -> str:
        """
        Génère l'URL pour la page demandée en préservant l'ensemble des
        paramètres de requête (GET args) et les view_args actifs.
        """
        target_endpoint = endpoint or request.endpoint
        # Fusionner les paramètres d'URL (view_args) et query string (args)
        args: Dict[str, Any] = {}
        if request.view_args:
            args.update(request.view_args)
        if request.args:
            args.update(request.args.to_dict(flat=True))
        args["page"] = page_num
        return url_for(target_endpoint, **args)

    @classmethod
    def from_query(
        cls,
        query: Any,
        page: int = 1,
        per_page: int = 10,
        formatter: Optional[Callable[[Any], Any]] = None,
    ) -> "Pagination":
        """
        Exécute la pagination directement sur une requête SQLAlchemy.
        Calcule le total sans order_by pour une performance maximale.
        """
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 10), 200))

        try:
            total = query.order_by(None).count()
        except Exception:
            total = query.count()

        offset = (page - 1) * per_page
        records = query.limit(per_page).offset(offset).all()

        if formatter:
            items = [formatter(r) for r in records]
        else:
            items = records

        return cls(items=items, page=page, per_page=per_page, total=total)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __repr__(self) -> str:
        return (
            f"<Pagination page={self.page}/{self.pages} per_page={self.per_page} "
            f"total={self.total} items={len(self.items)}>"
        )
