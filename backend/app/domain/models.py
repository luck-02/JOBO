"""Modèles du domaine. Aucune dépendance vers un framework, une BDD ou une API."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContractType(str, Enum):
    ALTERNANCE = "alternance"
    STAGE = "stage"
    CDI = "cdi"
    CDD = "cdd"
    AUTRE = "autre"


class DocumentKind(str, Enum):
    CV = "cv"
    LETTRE = "lettre"


# ---------- Profil candidat ----------

@dataclass
class Experience:
    poste: str
    entreprise: str
    ville: str = ""
    debut: str = ""          # "MM/AAAA"
    fin: str = ""            # "MM/AAAA" ou "" = en cours
    type: str = ""           # "Alternance", "Stage", "CDI", "Job étudiant"...
    missions: list[str] = field(default_factory=list)
    outils: list[str] = field(default_factory=list)


@dataclass
class Formation:
    diplome: str
    ecole: str
    debut: str = ""
    fin: str = ""
    details: str = ""


@dataclass
class Profile:
    owner_id: str
    prenom: str = ""
    nom: str = ""
    email: str = ""
    telephone: str = ""
    ville: str = ""
    linkedin: str = ""
    recherche: str = ""          # ce que la personne cherche (poste, secteur)
    disponibilite: str = ""      # date / rythme
    experiences: list[Experience] = field(default_factory=list)
    formations: list[Formation] = field(default_factory=list)
    competences: list[str] = field(default_factory=list)
    qualites: list[str] = field(default_factory=list)
    langues: list[str] = field(default_factory=list)
    interets: list[str] = field(default_factory=list)
    # Texte du CV de base importé à l'inscription
    cv_base: str = ""

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}".strip()

    def is_complete(self) -> bool:
        return bool(self.prenom and self.nom and self.email and (self.experiences or self.formations))

    def is_onboarded(self) -> bool:
        return bool(self.cv_base or self.experiences)


# ---------- Offres ----------

@dataclass
class OfferSummary:
    """Ce qui s'affiche dans la liste : léger, sans le détail."""
    id: str
    intitule: str
    entreprise: str
    lieu: str
    contrat: ContractType
    date_publication: str = ""


@dataclass
class Offer(OfferSummary):
    description: str = ""
    competences: list[str] = field(default_factory=list)
    url: str = ""
    siret: str = ""
    source: str = ""


@dataclass
class OfferQuery:
    mots_cles: str = ""
    lieu: str = ""                 # code département (ex. "44") ou vide
    contrat: ContractType | None = ContractType.ALTERNANCE
    page: int = 0
    taille: int = 20


@dataclass
class CompanyInfo:
    nom: str
    siren: str = ""
    activite: str = ""
    date_creation: str = ""
    effectif: str = ""
    adresse: str = ""
    dirigeants: list[str] = field(default_factory=list)
    categorie: str = ""
    source: str = ""


# ---------- Documents générés ----------

@dataclass
class CvSection:
    """Expérience telle que réécrite pour une offre donnée."""
    poste: str
    entreprise: str
    ville: str
    dates: str
    missions: list[str]
    outils: list[str] = field(default_factory=list)


@dataclass
class CvContent:
    titre: str                         # intitulé exact du poste
    profil: str                        # 3 lignes max
    experiences: list[CvSection]
    competences: dict[str, list[str]]  # groupe -> compétences
    savoir_etre: list[str]


@dataclass
class LetterContent:
    objet: str
    paragraphes: list[str]


@dataclass
class Keyword:
    terme: str
    niveau: str              # "obligatoire" | "important" | "bonus"
    occurrences: int
    couverture: str = "non"  # "oui" | "partiel" | "non"


@dataclass
class OfferAnalysis:
    """Étape 3 de la skill : table des mots-clés, adéquation /10, points forts et écarts."""
    score_adequation: float          # /10
    mots_cles: list[Keyword]
    points_forts: list[str]
    ecarts: list[str]


@dataclass
class AtsCheck:
    label: str
    points: int
    max_points: int
    detail: str


@dataclass
class AtsReport:
    score: int                          # /100
    couverture_obligatoires: int        # % des mots-clés obligatoires présents (terme exact)
    couverture_mots_cles: int           # % de tous les mots-clés présents
    mots_cles: list[Keyword]            # couverture mesurée dans le CV
    mots_cles_trouves: list[str]
    mots_cles_manquants: list[str]
    checks: list[AtsCheck]
    expressions_a_eviter: list[str]
    bourrage: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return self.score >= 90 and self.couverture_obligatoires >= 80


@dataclass
class GenerationResult:
    id: str
    offer_id: str
    files: dict[str, str]               # kind -> nom de fichier
    ats: AtsReport | None = None
    analyse: OfferAnalysis | None = None
    iterations: int = 0                 # nombre de versions du CV produites
    seuils_atteints: bool = False
    candidature_id: str = ""            # entrée créée ou mise à jour dans le suivi (CRM)
