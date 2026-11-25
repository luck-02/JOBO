"""Fiche entreprise factuelle via l'API Recherche d'entreprises (data.gouv, gratuite, sans clé).

Aucune IA ici : que des données officielles, donc pas d'invention possible.
"""
from __future__ import annotations

import httpx

from ...domain.models import CompanyInfo

API = "https://recherche-entreprises.api.gouv.fr/search"

EFFECTIFS = {
    "00": "0 salarié", "01": "1 ou 2 salariés", "02": "3 à 5 salariés", "03": "6 à 9 salariés",
    "11": "10 à 19 salariés", "12": "20 à 49 salariés", "21": "50 à 99 salariés",
    "22": "100 à 199 salariés", "31": "200 à 249 salariés", "32": "250 à 499 salariés",
    "41": "500 à 999 salariés", "42": "1 000 à 1 999 salariés", "51": "2 000 à 4 999 salariés",
    "52": "5 000 à 9 999 salariés", "53": "10 000 salariés et plus",
}


class AnnuaireEntreprisesSource:
    def __init__(self, timeout: float = 8.0):
        self._http = httpx.Client(timeout=timeout)

    def find(self, nom: str, siret: str = "") -> CompanyInfo | None:
        q = siret[:9] if siret else nom
        if not q:
            return None
        try:
            r = self._http.get(API, params={"q": q, "per_page": 1})
            r.raise_for_status()
            results = r.json().get("results", [])
        except httpx.HTTPError:
            return None
        if not results:
            return None
        e = results[0]
        siege = e.get("siege") or {}
        dirigeants = []
        for d in (e.get("dirigeants") or [])[:3]:
            label = d.get("denomination") or " ".join(x for x in [d.get("prenoms"), d.get("nom")] if x)
            if label:
                dirigeants.append(f"{label} ({d.get('qualite', '')})".replace(" ()", ""))
        return CompanyInfo(
            nom=e.get("nom_complet", nom),
            siren=e.get("siren", ""),
            activite=siege.get("libelle_activite_principale") or e.get("activite_principale", ""),
            date_creation=e.get("date_creation", "") or "",
            effectif=EFFECTIFS.get(e.get("tranche_effectif_salarie") or "", "Non communiqué"),
            adresse=siege.get("adresse", ""),
            dirigeants=dirigeants,
            categorie=e.get("categorie_entreprise", "") or "",
            source="annuaire-entreprises.data.gouv.fr",
        )


class DemoCompanySource:
    def find(self, nom: str, siret: str = "") -> CompanyInfo | None:
        return CompanyInfo(
            nom=nom, activite="Entreprise fictive de démonstration", effectif="50 à 99 salariés",
            date_creation="2012-03-01", adresse="Nantes", categorie="PME", source="démo",
        )
