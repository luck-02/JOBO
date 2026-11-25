"""Les 10 questions posées pour CHAQUE offre (après avoir collé le lien), calculées sans IA.

Même logique que la skill candidature-alternance : on questionne d'abord sur les mots-clés de l'offre
que le profil ne couvre pas, puis sur la motivation, une situation concrète, un chiffre, etc.
Réponses courtes acceptées, toutes facultatives. Chaque question propose des choix à cliquer (`options`),
la réponse libre (« Autre ») reste toujours possible. Les choix ne contiennent jamais de fait inventé :
soit des réponses génériques, soit des éléments recopiés du profil.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import ats
from .models import ContractType, Offer, OfferAnalysis, Profile

NB_QUESTIONS = 10
MAX_QUESTIONS_MOTS_CLES = 6   # au moins 4 questions générales restent
LANGUES = {"anglais", "espagnol", "allemand", "italien", "chinois", "arabe", "portugais"}


@dataclass
class Question:
    id: str
    question: str
    exemple: str = ""
    options: list[str] = field(default_factory=list)
    multiple: bool = False       # plusieurs choix cochables


@dataclass
class Answer:
    question: str
    reponse: str


OPTIONS_MOT_CLE = ["Oui, en stage ou en alternance", "Oui, en projet d'école", "Oui, en job étudiant",
                   "Un peu, des notions", "Non, jamais"]
OPTIONS_LANGUE = ["Débutant (A1-A2)", "Intermédiaire (B1)", "Courant (B2)", "Bilingue (C1-C2)"]


def _options_profil(profile: Profile) -> list[str]:
    """Choix recopiés du profil (jamais inventés) : expériences puis formations."""
    opts = [f"{e.poste} chez {e.entreprise}" for e in profile.experiences if e.poste and e.entreprise]
    opts += [f"{f.diplome} ({f.ecole})" for f in profile.formations if f.diplome and f.ecole]
    return opts[:4]


def questions_for_offer(profile: Profile, offer: Offer) -> list[Question]:
    # Comme la skill : chaque mot-clé obligatoire non couvert d'abord, puis les importants
    a = ats.analyse(profile, offer)
    manques = [k.terme for k in a.mots_cles if k.couverture != "oui" and k.niveau == "obligatoire"]
    manques += [k.terme for k in a.mots_cles if k.couverture != "oui" and k.niveau == "important"]
    entreprise = offer.entreprise if offer.entreprise and "non précisée" not in offer.entreprise else "cette entreprise"
    qs: list[Question] = []

    for i, mot in enumerate(manques[:MAX_QUESTIONS_MOTS_CLES]):
        if ats.normalize(mot) in LANGUES:
            qs.append(Question(f"mot_{i}", f"L'offre demande « {mot} » : quel est ton niveau, et l'as-tu déjà pratiqué ?",
                               "B2, séjour de 3 mois à Dublin", OPTIONS_LANGUE))
            continue
        qs.append(Question(f"mot_{i}", f"L'offre demande « {mot} » : l'as-tu déjà fait ou utilisé, même en cours, "
                                       f"en projet ou en job étudiant ? Comment ?",
                           "Oui, en projet d'école : ... / Non, jamais", OPTIONS_MOT_CLE))

    generiques = [
        Question("attrait", f"Qu'est-ce qui t'attire chez {entreprise} ou dans ce poste ?",
                 "Le secteur, un produit, les valeurs, le contact client...",
                 ["Le secteur d'activité", "Les missions du poste", "Les valeurs et la culture",
                  "Les produits ou services", "La taille de l'entreprise"], multiple=True),
        Question("situation", "Raconte en une phrase une situation où tu as fait une mission proche de celles de l'offre.",
                 "J'ai préparé 3 propositions commerciales pour des PME",
                 ["Oui, en stage ou en alternance", "Oui, en projet d'école", "Oui, en job étudiant", "Pas encore"]),
        Question("chiffre", "As-tu un chiffre ou un résultat à mettre en avant pour ce poste ?",
                 "50 prospects contactés, 10 rendez-vous obtenus", ["Pas de chiffre à mettre en avant"]),
        Question("priorite", "Quelle expérience ou compétence veux-tu mettre en premier pour cette offre ?",
                 "Mon alternance chez ...", _options_profil(profile)),
        Question("projet", "Un projet d'école, un projet perso ou une formation en lien avec ce poste ?",
                 "Projet de création d'entreprise, certification Google Ads...",
                 ["Un projet d'école", "Un projet perso", "Une formation ou certification", "Rien de spécifique"]),
        Question("qualite", "Une qualité demandée dans l'offre que tu peux prouver par un exemple ?",
                 "Autonomie : j'ai géré seul le suivi de 40 clients",
                 ["Autonomie", "Rigueur", "Sens du relationnel", "Esprit d'équipe", "Organisation"], multiple=True),
        Question("dispo", "Ta date de début, ton rythme et ta mobilité collent-ils à l'offre ?",
                 "Dispo en septembre, 1 semaine école / 3 semaines entreprise",
                 ["Oui, tout colle", "Date de début différente", "Rythme différent", "Mobilité limitée"]),
        Question("eviter", "Un point à éviter ou à expliquer dans cette candidature ?",
                 "Ne pas parler de ma 1re année de licence",
                 ["Rien de particulier", "Un trou dans le parcours", "Un changement d'orientation",
                  "Une expérience courte"]),
        Question("ton", "Un ton ou un style particulier pour cette entreprise ?",
                 "Plutôt start-up et direct / plutôt formel",
                 ["Formel et classique", "Dynamique, style start-up", "Neutre et professionnel"]),
    ]
    if offer.contrat not in (ContractType.ALTERNANCE, ContractType.STAGE):
        generiques = [q for q in generiques if q.id != "dispo"]
    for q in generiques:
        if len(qs) >= NB_QUESTIONS:
            break
        qs.append(q)
    return qs


NEGATIFS = ("non", "pas ", "pas,", "jamais", "aucun", "rien")
PARTIELS = tuple(ats.normalize(o) for o in ("Un peu", "Débutant"))
_MOT = re.compile(r"«\s*(.+?)\s*»")


def _negative(reponse: str) -> bool:
    r = ats.normalize(reponse)
    return not r or r.startswith(NEGATIFS)


def analyse_with_answers(profile: Profile, offer: Offer, answers: list[Answer]) -> OfferAnalysis:
    """Adéquation recalculée avec ce que le candidat a déclaré, sans IA.
    « Oui… » sur un mot-clé = couvert, « Un peu » / « Débutant » = partiel, « Non » = rien."""
    declare: list[str] = []
    forced: dict[str, str] = {}
    for a in clean_answers(answers):
        if _negative(a.reponse):
            continue
        declare.append(a.reponse)
        m = _MOT.search(a.question)
        if m:
            partiel = ats.normalize(a.reponse).startswith(PARTIELS)
            forced[ats.normalize(m.group(1))] = "partiel" if partiel else "oui"
    return ats.analyse(profile, offer, "\n".join(declare), forced)


def clean_answers(answers: list[Answer], max_len: int = 600) -> list[Answer]:
    """Garde au plus 10 réponses non vides, tronquées."""
    out = [Answer(a.question.strip()[:300], a.reponse.strip()[:max_len]) for a in answers]
    return [a for a in out if a.question and a.reponse][:NB_QUESTIONS]
