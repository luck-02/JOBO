"""Garde-fous communs : postes, entreprises et dates viennent TOUJOURS du profil, jamais de l'IA."""
from __future__ import annotations

from ...domain.models import CvContent, CvSection, Experience, Offer, Profile


def dates(e: Experience) -> str:
    if not e.debut:
        return e.fin
    return f"{e.debut} – {e.fin or 'en cours'}"


def poste_label(e: Experience) -> str:
    if e.type and e.type.lower() not in e.poste.lower():
        return f"{e.poste} ({e.type})"
    return e.poste


def build_cv_from_tool(profile: Profile, offer: Offer, data: dict) -> CvContent:
    sections: list[CvSection] = []
    used: set[int] = set()
    for item in data.get("experiences", []):
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(profile.experiences)) or idx in used:
            continue  # index inventé ou doublon : ignoré
        used.add(idx)
        e = profile.experiences[idx]
        missions = [m.strip() for m in item.get("missions", []) if m.strip()][:5] or e.missions[:4]
        outils = [o for o in item.get("outils", []) if o] or e.outils
        sections.append(CvSection(poste_label(e), e.entreprise, e.ville, dates(e), missions, outils))
    if not sections:  # sécurité : on garde le profil d'origine
        sections = [CvSection(poste_label(e), e.entreprise, e.ville, dates(e), e.missions[:4], e.outils)
                    for e in profile.experiences]

    competences: dict[str, list[str]] = {}
    for g in data.get("competences", []):
        items = [i for i in g.get("items", []) if i]
        if g.get("groupe") and items:
            competences[g["groupe"]] = items
    if not competences and profile.competences:
        competences = {"Compétences": profile.competences}

    return CvContent(
        titre=data.get("titre") or offer.intitule,
        profil=data.get("profil", "").strip(),
        experiences=sections,
        competences=competences,
        savoir_etre=[s for s in data.get("savoir_etre", []) if s] or profile.qualites,
    )
