"""Analyse d'offre et scoring ATS, calculés sans IA (donc quasi gratuits). Reprend la skill candidature-alternance.

Le score est une estimation : il n'existe pas un seul ATS standard.
Chaque point est expliqué pour que l'utilisateur sache quoi améliorer.
"""
from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass, field

from .models import AtsCheck, AtsReport, Keyword, Offer, OfferAnalysis, Profile

# Compétences et termes fréquents dans les offres de stage / alternance.
LEXIQUE = [
    # commercial
    "prospection", "business development", "développement commercial", "négociation", "CRM",
    "salesforce", "hubspot", "relation client", "avant-vente", "B2B", "B2C", "appels d'offres",
    "account management", "fidélisation", "closing", "pipeline", "sales navigator",
    "marketing", "marketing digital", "SEO", "réseaux sociaux", "communication", "événementiel",
    # projet
    "gestion de projet", "chef de projet", "pilotage", "planning", "reporting", "KPI", "agile",
    "scrum", "jira", "confluence", "cahier des charges", "recette", "AMOA", "MOA", "PMO",
    "conduite du changement", "coordination", "budget", "lean",
    # data / tech
    "excel", "VBA", "power bi", "tableau", "SQL", "python", "java", "javascript", "typescript",
    "react", "node.js", "docker", "cloud", "AWS", "azure", "API", "data", "intelligence artificielle",
    "machine learning", "ERP", "SAP", "git", "devops", "cybersécurité", "linux",
    # finance / RH / admin
    "comptabilité", "contrôle de gestion", "finance", "audit", "paie", "recrutement",
    "ressources humaines", "achats", "supply chain", "logistique", "juridique",
    # outils bureautiques
    "suite office", "pack office", "powerpoint", "word", "google workspace", "canva", "notion",
    # langues
    "anglais", "espagnol", "allemand",
]

STOPWORDS = {"CDI", "CDD", "H/F", "F/H", "HF", "FH", "SAS", "SA", "SARL", "LE", "LA", "LES", "DE", "DU",
             "ET", "EN", "UN", "UNE", "DES", "AU", "AUX", "ETC", "IDF", "BAC", "IT"}

SECTIONS = ["profil", "experiences professionnelles", "formation", "competences"]

MARQUEURS_PROFIL = ["profil", "competences", "vous etes", "requis", "prerequis", "qualifications",
                    "nous recherchons", "vous avez", "vous disposez", "formation", "savoir-etre"]
MARQUEURS_BONUS = ["apprecie", "un plus", "idealement", "serait un plus", "souhaite", "bonus", "atout"]
POIDS = {"obligatoire": 3, "important": 2, "bonus": 1}

A_EVITER = [
    "passionne", "dynamique et motive", "fort de mon experience", "je me permets",
    "c'est avec un grand interet", "veritable atout", "relever de nouveaux defis",
    "en parfaite adequation", "valeur ajoutee", "synergie", "prestigieuse", "n'hesitez pas",
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _contains(haystack_norm: str, term: str) -> bool:
    term_n = normalize(term)
    if not term_n:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(term_n) + r"(?![a-z0-9])", haystack_norm) is not None


def extract_keywords(offer: Offer, limit: int = 25) -> list[str]:
    """Mots-clés de l'offre : compétences listées + lexique + sigles."""
    text = f"{offer.intitule}\n{offer.description}"
    text_n = normalize(text)
    found: list[str] = []

    def add(term: str) -> None:
        if normalize(term) not in {normalize(f) for f in found}:
            found.append(term)

    for c in offer.competences:
        if 2 <= len(c) <= 60:
            add(c.strip())
    for term in LEXIQUE:
        if _contains(text_n, term):
            # on garde l'écriture de l'offre (ex. "HubSpot" plutôt que "hubspot") : c'est le terme exact visé
            m = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)
            add(m.group(0) if m else term)
    for sigle in re.findall(r"\b[A-Z][A-Z0-9]{1,5}\b", text):
        if sigle not in STOPWORDS:
            add(sigle)
    return found[:limit]


def profile_text(profile: Profile) -> str:
    parts = [profile.recherche, *profile.competences, *profile.qualites, *profile.langues]
    for e in profile.experiences:
        parts += [e.poste, e.entreprise, *e.missions, *e.outils]
    for f in profile.formations:
        parts += [f.diplome, f.ecole, f.details]
    return "\n".join(p for p in parts if p)


def _count(haystack_norm: str, term: str) -> int:
    term_n = normalize(term)
    if not term_n:
        return 0
    return len(re.findall(r"(?<![a-z0-9])" + re.escape(term_n) + r"(?![a-z0-9])", haystack_norm))


def _sentences(text: str) -> list[str]:
    return [normalize(x) for x in re.split(r"[\n.;!?•]+", text) if x.strip()]


def keyword_table(offer: Offer) -> list[Keyword]:
    """Mots-clés en 3 niveaux, comme l'étape 3 de la skill.
    Obligatoires : intitulé, compétences listées, section "profil recherché".
    Importants : termes des missions (surtout s'ils sont répétés). Bonus : "apprécié", "un plus"..."""
    full_n = normalize(f"{offer.intitule}\n{offer.description}")
    titre_n = normalize(offer.intitule)
    comps_n = {normalize(c) for c in offer.competences}
    phrases = _sentences(offer.description)
    debut_profil = next((i for i, ph in enumerate(phrases) if any(m in ph for m in MARQUEURS_PROFIL)), len(phrases))
    table: list[Keyword] = []
    for term in extract_keywords(offer, limit=30):
        t = normalize(term)
        occ = max(1, _count(full_n, term))
        idx = [i for i, ph in enumerate(phrases) if _contains(ph, term)]
        if t in comps_n or _contains(titre_n, term):
            niveau = "obligatoire"
        elif idx and all(any(m in phrases[i] for m in MARQUEURS_BONUS) for i in idx):
            niveau = "bonus"
        elif any(i >= debut_profil for i in idx):
            niveau = "obligatoire"
        else:
            niveau = "important"
        table.append(Keyword(term, niveau, occ))
    if table and not any(k.niveau == "obligatoire" for k in table):
        for k in sorted(table, key=lambda k: -k.occurrences)[:3]:
            k.niveau = "obligatoire"
    ordre = {"obligatoire": 0, "important": 1, "bonus": 2}
    return sorted(table, key=lambda k: (ordre[k.niveau], -k.occurrences))


def _coverage(term: str, text_n: str) -> str:
    if _contains(text_n, term):
        return "oui"
    mots = [m for m in re.split(r"[\s'-]+", normalize(term)) if len(m) > 3]
    if len(mots) > 1 and any(_contains(text_n, m) for m in mots):
        return "partiel"
    return "non"


def analyse(profile: Profile, offer: Offer, declare: str = "",
            forced: dict[str, str] | None = None) -> OfferAnalysis:
    """`declare` : texte déclaré par le candidat (réponses aux questions), compté comme le profil.
    `forced` : couverture minimale par mot-clé (normalisé), issue d'une réponse explicite."""
    text_n = normalize(f"{profile_text(profile)}\n{declare}")
    table = keyword_table(offer)
    rang = {"non": 0, "partiel": 1, "oui": 2}
    for k in table:
        k.couverture = _coverage(k.terme, text_n)
        f = (forced or {}).get(normalize(k.terme))
        if f and rang[f] > rang[k.couverture]:
            k.couverture = f
    total = sum(POIDS[k.niveau] for k in table) or 1
    gagne = sum(POIDS[k.niveau] * {"oui": 1, "partiel": .5, "non": 0}[k.couverture] for k in table)
    forts = [k.terme for k in table if k.couverture == "oui" and k.niveau != "bonus"][:5]
    ecarts = [k.terme for k in table if k.couverture != "oui" and k.niveau == "obligatoire"]
    return OfferAnalysis(round(10 * gagne / total, 1), table, forts, ecarts)


def matching_score(profile: Profile, offer: Offer) -> tuple[int, list[str], list[str]]:
    """Compatibilité : % pondéré, termes couverts, termes manquants (obligatoires d'abord)."""
    a = analyse(profile, offer)
    ok = [k.terme for k in a.mots_cles if k.couverture == "oui"]
    ko = [k.terme for k in a.mots_cles if k.couverture != "oui"]
    return round(a.score_adequation * 10), ok, ko


@dataclass
class CvFacts:
    """Ce que le scoring doit savoir du CV généré (en plus du texte extrait du PDF)."""
    titre: str
    profil: str
    dates: list[str]
    missions_par_experience: list[list[str]] = field(default_factory=list)


def ats_report(offer: Offer, cv_text: str, page_count: int, facts: CvFacts) -> AtsReport:
    """Grille de l'étape 7 de la skill, mesurée sur le texte réellement extrait du PDF."""
    text_n = normalize(cv_text)
    table = keyword_table(offer)
    for k in table:
        k.couverture = "oui" if _contains(text_n, k.terme) else "non"
    obl = [k for k in table if k.niveau == "obligatoire"]
    autres = [k for k in table if k.niveau != "obligatoire"]
    cov_obl = round(100 * sum(k.couverture == "oui" for k in obl) / len(obl)) if obl else 100
    cov_autres = round(100 * sum(k.couverture == "oui" for k in autres) / len(autres)) if autres else 100
    cov_all = round(100 * sum(k.couverture == "oui" for k in table) / len(table)) if table else 100
    checks: list[AtsCheck] = []

    manq_obl = [k.terme for k in obl if k.couverture == "non"]
    checks.append(AtsCheck("Mots-clés obligatoires", round(25 * cov_obl / 100), 25,
                           f"{cov_obl} % couverts" + (f" · absents : {', '.join(manq_obl)}" if manq_obl else "")))
    checks.append(AtsCheck("Mots-clés importants et bonus", round(10 * cov_autres / 100), 10, f"{cov_autres} % couverts"))

    titre_ok = normalize(offer.intitule) in normalize(facts.titre)
    profil_ok = normalize(offer.intitule) in normalize(facts.profil)
    checks.append(AtsCheck("Intitulé exact (titre et profil)", 5 * titre_ok + 5 * profil_ok, 10,
                           ("titre ok" if titre_ok else "titre à corriger") + ", "
                           + ("profil ok" if profil_ok else "intitulé absent du profil")))

    has_mail = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", cv_text) is not None
    has_tel = re.search(r"(\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}", cv_text) is not None
    sections_ok = [x for x in SECTIONS if x in text_n]
    dates_ok = all(re.fullmatch(r"\d{2}/\d{4} – (\d{2}/\d{4}|en cours)", d) for d in facts.dates if d)
    parsing = 3 * has_mail + 3 * has_tel + round(6 * len(sections_ok) / len(SECTIONS)) + 4 * dates_ok + 4 * (page_count == 1)
    detail = []
    if not (has_mail and has_tel):
        detail.append("coordonnées incomplètes")
    if len(sections_ok) < len(SECTIONS):
        detail.append("sections manquantes : " + ", ".join(x for x in SECTIONS if x not in sections_ok))
    if not dates_ok:
        detail.append("dates à mettre au format MM/AAAA – MM/AAAA")
    if page_count != 1:
        detail.append(f"{page_count} pages au lieu d'une")
    checks.append(AtsCheck("Lecture par les ATS (parsing)", parsing, 20, " · ".join(detail) or "texte propre, 1 page"))

    missions = [m for ms in facts.missions_par_experience for m in ms]
    chiffrees = [m for m in missions if re.search(r"\d", m)]
    ratio = len(chiffrees) / len(missions) if missions else 0
    checks.append(AtsCheck("Expériences chiffrées", min(10, round(10 * ratio / 0.5)), 10,
                           f"{len(chiffrees)}/{len(missions)} missions avec un chiffre réel"))

    terms = [k.terme for k in table]
    def rel(txt: str) -> int:
        tn = normalize(txt)
        return sum(1 for t in terms if _contains(tn, t))
    exps = [e for e in facts.missions_par_experience if e]
    pert = 10
    if len(exps) > 1 and rel(" ".join(exps[0])) < max(rel(" ".join(e)) for e in exps):
        pert -= 5
    mal_ordonnees = sum(1 for e in exps if len(e) > 1 and rel(e[0]) < max(rel(m) for m in e))
    pert -= min(5, 2 * mal_ordonnees)
    checks.append(AtsCheck("Pertinence de l'ordre", max(0, pert), 10,
                           "expériences et missions les plus utiles en premier" if pert == 10
                           else "remonter les expériences ou missions les plus proches de l'offre"))

    bad = [e for e in A_EVITER if e in text_n]
    bourrage = [k.terme for k in table if _count(text_n, k.terme) > 3]
    ton = max(0, 15 - 4 * len(bad) - 3 * len(bourrage))
    det = []
    if bad:
        det.append("formules à reformuler : " + ", ".join(bad))
    if bourrage:
        det.append("bourrage (plus de 3 fois) : " + ", ".join(bourrage))
    checks.append(AtsCheck("Ton naturel", ton, 15, " · ".join(det) or "aucune formule toute faite ni bourrage"))

    return AtsReport(
        score=sum(c.points for c in checks), couverture_obligatoires=cov_obl, couverture_mots_cles=cov_all,
        mots_cles=table, mots_cles_trouves=[k.terme for k in table if k.couverture == "oui"],
        mots_cles_manquants=[k.terme for k in table if k.couverture == "non"], checks=checks,
        expressions_a_eviter=bad, bourrage=bourrage,
    )


def feedback_for_rewrite(report: AtsReport) -> str:
    """Consignes de correction pour la version suivante du CV (jamais d'invention)."""
    lines = []
    manquants = [k.terme for k in report.mots_cles if k.couverture == "non" and k.niveau == "obligatoire"]
    if manquants:
        lines.append("Mots-clés obligatoires absents du CV : " + ", ".join(manquants)
                     + ". Ajoute-les avec le terme exact UNIQUEMENT si le profil ou les réponses du candidat"
                       " le justifient ; sinon laisse-les de côté.")
    for c in report.checks:
        if c.points < c.max_points and c.label != "Mots-clés obligatoires":
            lines.append(f"{c.label} ({c.points}/{c.max_points}) : {c.detail}")
    return "\n".join(lines)
