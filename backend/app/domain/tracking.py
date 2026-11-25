"""CRM des candidatures (onglet Suivi, gratuit : aucune IA, juste des règles métier)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

DELAI_RELANCE_JOURS = 7


class Statut(str, Enum):
    BROUILLON = "brouillon"      # swipe à droite gardé pour plus tard (ou quota épuisé)
    A_ENVOYER = "a_envoyer"
    ENVOYEE = "envoyee"
    RELANCEE = "relancee"
    ENTRETIEN = "entretien"
    OFFRE = "offre"
    REFUS = "refus"
    ABANDON = "abandon"


EN_ATTENTE_DE_REPONSE = {Statut.ENVOYEE, Statut.RELANCEE}
REPONDUES = {Statut.ENTRETIEN, Statut.OFFRE, Statut.REFUS}
ENVOYEES = EN_ATTENTE_DE_REPONSE | REPONDUES


@dataclass
class Etape:
    date: str          # AAAA-MM-JJ
    statut: Statut


@dataclass
class Candidature:
    id: str
    owner_id: str
    intitule: str
    entreprise: str
    lieu: str = ""
    url: str = ""
    offer_id: str = ""
    statut: Statut = Statut.A_ENVOYER
    date_creation: str = ""
    date_envoi: str = ""
    relance_prevue: str = ""
    contact: str = ""
    notes: str = ""
    fichiers: dict[str, str] = field(default_factory=dict)   # "cv"/"lettre" -> URL de téléchargement
    score_ats: int | None = None
    adequation: float | None = None
    historique: list[Etape] = field(default_factory=list)
    reponses: list[dict[str, str]] = field(default_factory=list)   # réponses aux questions (brouillon de swipe)

    def relance_due(self, today: date) -> bool:
        return (self.statut in EN_ATTENTE_DE_REPONSE and bool(self.relance_prevue)
                and date.fromisoformat(self.relance_prevue) <= today)


def changer_statut(c: Candidature, statut: Statut, today: date) -> Candidature:
    """Règles : l'envoi date la candidature et prévoit une relance à J+7 ; chaque relance en prévoit une autre ;
    une réponse (entretien, offre, refus) ou un abandon annule la relance."""
    if statut == c.statut:
        return c
    c.statut = statut
    iso = today.isoformat()
    if statut == Statut.ENVOYEE:
        c.date_envoi = c.date_envoi or iso
        c.relance_prevue = (today + timedelta(days=DELAI_RELANCE_JOURS)).isoformat()
    elif statut == Statut.RELANCEE:
        c.date_envoi = c.date_envoi or iso
        c.relance_prevue = (today + timedelta(days=DELAI_RELANCE_JOURS)).isoformat()
    elif statut in REPONDUES or statut == Statut.ABANDON:
        c.relance_prevue = ""
    elif statut in (Statut.A_ENVOYER, Statut.BROUILLON):
        c.relance_prevue = ""
    c.historique.append(Etape(iso, statut))
    return c


@dataclass
class Stats:
    total: int
    par_statut: dict[str, int]
    envoyees: int
    taux_reponse: int          # % des candidatures envoyées qui ont eu une réponse
    taux_entretien: int        # % des candidatures envoyées qui ont mené à un entretien ou une offre
    relances_a_faire: int
    cette_semaine: int         # candidatures créées ces 7 derniers jours


def stats(cands: list[Candidature], today: date) -> Stats:
    par = {s.value: 0 for s in Statut}
    for c in cands:
        par[c.statut.value] += 1
    envoyees = sum(1 for c in cands if c.statut in ENVOYEES)
    repondues = sum(1 for c in cands if c.statut in REPONDUES)
    entretiens = sum(1 for c in cands if c.statut in (Statut.ENTRETIEN, Statut.OFFRE))
    semaine = (today - timedelta(days=7)).isoformat()
    return Stats(
        total=len(cands), par_statut=par, envoyees=envoyees,
        taux_reponse=round(100 * repondues / envoyees) if envoyees else 0,
        taux_entretien=round(100 * entretiens / envoyees) if envoyees else 0,
        relances_a_faire=sum(1 for c in cands if c.relance_due(today)),
        cette_semaine=sum(1 for c in cands if c.date_creation >= semaine),
    )
