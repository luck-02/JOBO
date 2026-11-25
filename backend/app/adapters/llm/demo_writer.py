"""Rédacteur de démonstration, sans IA ni coût : réordonne le profil selon les mots-clés de l'offre.
Sert aussi de solution de secours si l'API IA est indisponible."""
from __future__ import annotations

from ...domain import ats
from ...domain.models import CompanyInfo, CvContent, LetterContent, Offer, Profile
from .common import build_cv_from_tool


def _relevance(text: str, keywords: list[str]) -> int:
    t = ats.normalize(text)
    return sum(1 for k in keywords if ats.normalize(k) in t)


class DemoWriter:
    supports_feedback = False  # déterministe : une seule version

    def write_cv(self, profile: Profile, offer: Offer, instructions: str = "", answers=None,
                 feedback: str = "") -> CvContent:
        kws = ats.extract_keywords(offer)
        ranked = sorted(range(len(profile.experiences)),
                        key=lambda i: -_relevance(" ".join(profile.experiences[i].missions), kws))
        exps = []
        for i in ranked:
            e = profile.experiences[i]
            missions = sorted(e.missions, key=lambda m: -_relevance(m, kws))[:4]
            exps.append({"index": i, "missions": missions, "outils": e.outils})
        comps = sorted(profile.competences, key=lambda c: -_relevance(c, kws))
        qualites = ", ".join(profile.qualites[:2]) or "sérieux"
        profil = (f"{profile.recherche or 'Candidat'} visant le poste "
                  f"{offer.intitule}. {qualites.capitalize()}.").strip()
        return build_cv_from_tool(profile, offer, {
            "titre": offer.intitule,
            "profil": profil,
            "experiences": exps,
            "competences": [{"groupe": "Compétences", "items": comps}],
            "savoir_etre": profile.qualites,
        })

    def write_letter(self, profile: Profile, offer: Offer, company: CompanyInfo | None,
                     instructions: str = "", answers=None) -> LetterContent:
        e = profile.experiences[0] if profile.experiences else None
        exemple = f"Chez {e.entreprise}, en tant que {e.poste}, j'ai notamment pu {e.missions[0][0].lower() + e.missions[0][1:]}." \
            if e and e.missions else ""
        return LetterContent(
            objet=f"Candidature au poste de {offer.intitule}",
            paragraphes=[
                f"Votre offre de {offer.intitule} chez {offer.entreprise} a retenu mon attention.",
                f"{exemple} Ces expériences m'ont préparé aux missions décrites dans votre annonce.",
                f"Je suis disponible {profile.disponibilite or 'rapidement'} et serais ravi d'échanger avec vous.",
            ],
        )
