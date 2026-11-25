"""Adaptateur API Offres d'emploi v2 de France Travail (gratuite, clés sur francetravail.io)."""
from __future__ import annotations

import time

import httpx

from ...domain.models import ContractType, Offer, OfferQuery, OfferSummary

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
API_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres"
SCOPE = "api_offresdemploiv2 o2dsoffre"

# natureContrat : E2 = apprentissage, FS = professionnalisation
_NATURE_ALTERNANCE = {"E2", "FS"}


class FranceTravailOfferSource:
    def __init__(self, client_id: str, client_secret: str, timeout: float = 10.0):
        self._id = client_id
        self._secret = client_secret
        self._http = httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._token_exp = 0.0

    # --- auth OAuth2 client_credentials, token mis en cache ---
    def _auth(self) -> dict[str, str]:
        if not self._token or time.time() > self._token_exp - 30:
            r = self._http.post(TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": self._id,
                "client_secret": self._secret,
                "scope": SCOPE,
            })
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._token_exp = time.time() + int(data.get("expires_in", 1499))
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    def search(self, query: OfferQuery) -> list[OfferSummary]:
        start = query.page * query.taille
        params: dict[str, str] = {"range": f"{start}-{start + query.taille - 1}", "sort": "1"}
        if query.mots_cles:
            params["motsCles"] = query.mots_cles
        if query.lieu:
            params["departement"] = query.lieu
        if query.contrat == ContractType.ALTERNANCE:
            params["natureContrat"] = "E2,FS"
        elif query.contrat == ContractType.CDI:
            params["typeContrat"] = "CDI"
        elif query.contrat == ContractType.CDD:
            params["typeContrat"] = "CDD"
        elif query.contrat == ContractType.STAGE:
            params["motsCles"] = (params.get("motsCles", "") + " stage").strip()

        r = self._http.get(f"{API_URL}/search", params=params, headers=self._auth())
        if r.status_code == 204:
            return []
        r.raise_for_status()
        return [self._summary(o) for o in r.json().get("resultats", [])]

    def get(self, offer_id: str) -> Offer | None:
        r = self._http.get(f"{API_URL}/{offer_id}", headers=self._auth())
        if r.status_code in (204, 404):
            return None
        r.raise_for_status()
        o = r.json()
        s = self._summary(o)
        return Offer(
            **s.__dict__,
            description=o.get("description", ""),
            competences=[c.get("libelle", "") for c in o.get("competences", []) if c.get("libelle")],
            url=(o.get("origineOffre") or {}).get("urlOrigine", ""),
            siret=(o.get("entreprise") or {}).get("siret", "") or "",
            source="France Travail",
        )

    @staticmethod
    def _summary(o: dict) -> OfferSummary:
        nature = o.get("natureContrat", "") or ""
        type_c = (o.get("typeContrat") or "").upper()
        if o.get("alternance") or any(n in nature for n in ("apprentissage", "professionnalisation")):
            contrat = ContractType.ALTERNANCE
        elif type_c == "CDI":
            contrat = ContractType.CDI
        elif type_c == "CDD":
            contrat = ContractType.CDD
        elif "stage" in (o.get("intitule", "").lower()):
            contrat = ContractType.STAGE
        else:
            contrat = ContractType.AUTRE
        return OfferSummary(
            id=o["id"],
            intitule=o.get("intitule", ""),
            entreprise=(o.get("entreprise") or {}).get("nom", "") or "Entreprise non communiquée",
            lieu=(o.get("lieuTravail") or {}).get("libelle", ""),
            contrat=contrat,
            date_publication=(o.get("dateCreation") or "")[:10],
        )
