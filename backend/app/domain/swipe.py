"""Swipe d'offres (mobile) : réactions, préférences et composition de la pile. Sans IA, sans dépendance technique.

Gestes : droite = postuler, gauche = pas pour moi (masquée pour toujours), haut = favori.
Une raison facultative sur « pas pour moi » affine la pile par des règles simples (jamais d'IA).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from . import ats
from .models import ContractType, OfferSummary

DELAI_RAPPEL_FAVORI_JOURS = 7
DUREE_LISTE_PASSEES_JOURS = 30
MAX_ANNULATIONS = 10
TAILLE_PILE = 20


class TypeReaction(str, Enum):
    POSTULER = "postuler"
    PASSER = "passer"
    FAVORI = "favori"


class Raison(str, Enum):
    """Pourquoi « pas pour moi » (facultatif)."""
    METIER = "metier"
    LIEU = "lieu"
    CONTRAT = "contrat"
    ENTREPRISE = "entreprise"


@dataclass
class Reaction:
    owner_id: str
    offer_id: str
    type: TypeReaction
    date: str                         # AAAA-MM-JJ
    horodatage: str = ""              # ISO complet, pour l'ordre des annulations
    # Copie légère de l'offre : les listes (passées, favoris) s'affichent sans rappeler la source
    intitule: str = ""
    entreprise: str = ""
    lieu: str = ""
    contrat: str = ""
    raison: Raison | None = None      # seulement pour PASSER
    rappel_le: str = ""               # seulement pour FAVORI : un rappel unique à J+7
    rappel_actif: bool = False

    def rappel_du(self, today: date) -> bool:
        return (self.type == TypeReaction.FAVORI and self.rappel_actif and bool(self.rappel_le)
                and date.fromisoformat(self.rappel_le) <= today)


def nouvelle_reaction(owner_id: str, offer: OfferSummary, type_: TypeReaction, today: date,
                      horodatage: str = "") -> Reaction:
    r = Reaction(owner_id=owner_id, offer_id=offer.id, type=type_, date=today.isoformat(),
                 horodatage=horodatage or today.isoformat(), intitule=offer.intitule,
                 entreprise=offer.entreprise, lieu=offer.lieu, contrat=_val(offer.contrat))
    if type_ == TypeReaction.FAVORI:
        r.rappel_le = (today + timedelta(days=DELAI_RAPPEL_FAVORI_JOURS)).isoformat()
        r.rappel_actif = True
    return r


def passees_visibles(reactions: list[Reaction], today: date) -> list[Reaction]:
    """Liste « Offres passées » : les 30 derniers jours. Au-delà, l'offre reste masquée mais n'est plus listée."""
    limite = (today - timedelta(days=DUREE_LISTE_PASSEES_JOURS)).isoformat()
    out = [r for r in reactions if r.type == TypeReaction.PASSER and r.date >= limite]
    return sorted(out, key=lambda r: r.horodatage, reverse=True)


# ---------- Préférences ----------

@dataclass
class Preferences:
    """Ce que la personne cherche, en champs structurés (plusieurs contrats possibles)."""
    contrats: list[ContractType] = field(default_factory=list)   # vide = tous
    departements: list[str] = field(default_factory=list)        # codes ("44") ; vide = toute la France
    mots_cles: str = ""


_DEPT = re.compile(r"^(\d{2}|2[AB]|97\d)$")


def nettoyer_preferences(contrats: list[str], departements: list[str], mots_cles: str) -> Preferences:
    cs: list[ContractType] = []
    for c in contrats:
        ct = ContractType(c)              # ValueError si inconnu
        if ct not in cs:
            cs.append(ct)
    ds: list[str] = []
    for d in departements:
        d = d.strip().upper()
        if not _DEPT.match(d):
            raise ValueError(f"Département invalide : {d}")
        if d not in ds:
            ds.append(d)
    return Preferences(cs[:5], ds[:5], mots_cles.strip()[:100])


# ---------- Pile ----------

_MOTS_VIDES = {"alternance", "stage", "stagiaire", "cdi", "cdd", "apprenti", "apprentissage", "h", "f", "hf",
               "de", "du", "des", "en", "et", "la", "le", "les", "l", "d", "a", "au", "un", "une", "contrat"}


def mots_metier(intitule: str) -> set[str]:
    """Les mots qui disent le métier dans un intitulé (« Alternance Business Developer IT » -> business, developer, it)."""
    return {m for m in re.split(r"[^a-z0-9]+", ats.normalize(intitule)) if m and m not in _MOTS_VIDES}


def _val(x) -> str:
    return x.value if isinstance(x, Enum) else str(x or "")


def _dept(lieu: str) -> str:
    m = re.match(r"\s*(\d{2}|2[AB]|97\d)\b", lieu or "")
    return m.group(1) if m else ats.normalize(lieu or "")


def composer_pile(candidates: list[OfferSummary], reactions: list[Reaction], taille: int = TAILLE_PILE
                  ) -> list[OfferSummary]:
    """Retire toute offre déjà swipée, puis affine avec les raisons données sur « pas pour moi » :
    entreprise -> ses offres disparaissent ; métier, lieu, contrat -> les offres proches passent en fin de pile.
    L'ordre de la source est gardé à pénalité égale."""
    vues = {r.offer_id for r in reactions}
    passees = [r for r in reactions if r.type == TypeReaction.PASSER and r.raison]
    ent_exclues = {ats.normalize(r.entreprise) for r in passees if r.raison == Raison.ENTREPRISE and r.entreprise}
    lieux = {_dept(r.lieu) for r in passees if r.raison == Raison.LIEU and r.lieu}
    contrats = {r.contrat for r in passees if r.raison == Raison.CONTRAT and r.contrat}
    metiers = [mots_metier(r.intitule) for r in passees if r.raison == Raison.METIER]

    def penalite(o: OfferSummary) -> int:
        p = 0
        if _dept(o.lieu) in lieux:
            p += 1
        if _val(o.contrat) in contrats:
            p += 1
        mo = mots_metier(o.intitule)
        if any(m and len(mo & m) * 2 >= len(m) for m in metiers):   # au moins la moitié des mots du métier refusé
            p += 2
        return p

    seen: set[str] = set()
    gardees: list[OfferSummary] = []
    for o in candidates:
        if o.id in vues or o.id in seen or ats.normalize(o.entreprise) in ent_exclues:
            continue
        seen.add(o.id)
        gardees.append(o)
    gardees = sorted(gardees, key=penalite)   # tri stable
    return gardees[:taille]
