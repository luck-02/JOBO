"""Rédaction via l'API Anthropic. Sortie structurée (tool use) : l'IA écrit le contenu,
la mise en page reste maîtrisée par le code (CV toujours compatible ATS)."""
from __future__ import annotations

import json
from dataclasses import asdict

import anthropic

from ...domain.models import CompanyInfo, CvContent, LetterContent, Offer, Profile
from ...domain.questions import Answer
from . import prompts
from .common import build_cv_from_tool


class AnthropicWriter:
    def __init__(self, api_key: str, model: str, max_tokens: int = 2000):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def _call(self, tool: dict, user: str) -> dict:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=prompts.SYSTEM,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user}],
        )
        for block in msg.content:
            if block.type == "tool_use":
                return block.input  # type: ignore[return-value]
        raise RuntimeError("Réponse IA sans contenu structuré")

    @staticmethod
    def _context(profile: Profile, offer: Offer, instructions: str, extra: str = "",
                 answers: list[Answer] | None = None) -> str:
        p = asdict(profile)
        for k in ("owner_id", "cv_base"):
            p.pop(k, None)
        for i, e in enumerate(p["experiences"]):
            e["index"] = i
        reponses = "\n".join(f"- {a.question} -> {a.reponse}" for a in (answers or []))
        parts = [
            "<offre>",
            f"Intitulé : {offer.intitule}\nEntreprise : {offer.entreprise}\nLieu : {offer.lieu}",
            f"Compétences listées : {', '.join(offer.competences)}",
            offer.description,
            "</offre>",
            "<profil>",
            json.dumps(p, ensure_ascii=False),
            "</profil>",
        ]
        if reponses:
            parts.append(f"<reponses_candidat>\n{reponses}\n</reponses_candidat>")
        if not profile.experiences and profile.cv_base:
            parts.append(f"<cv_de_base>\n{profile.cv_base[:6000]}\n</cv_de_base>")
        if extra:
            parts.append(extra)
        if instructions.strip():
            parts.append(f"<notes_candidat>\n{instructions.strip()[:1500]}\n</notes_candidat>")
        return "\n".join(parts)

    supports_feedback = True

    def write_cv(self, profile: Profile, offer: Offer, instructions: str = "",
                 answers: list[Answer] | None = None, feedback: str = "") -> CvContent:
        extra = f"<corrections_version_precedente>\n{feedback}\n</corrections_version_precedente>" if feedback else ""
        data = self._call(prompts.CV_TOOL, prompts.CV_TASK + "\n\n"
                          + self._context(profile, offer, instructions, extra, answers))
        return build_cv_from_tool(profile, offer, data)

    def write_letter(self, profile: Profile, offer: Offer, company: CompanyInfo | None,
                     instructions: str = "", answers: list[Answer] | None = None) -> LetterContent:
        extra = ""
        if company:
            extra = "<fiche_entreprise>\n" + json.dumps(asdict(company), ensure_ascii=False) + "\n</fiche_entreprise>"
        data = self._call(prompts.LETTER_TOOL,
                          prompts.LETTER_TASK + "\n\n" + self._context(profile, offer, instructions, extra, answers))
        return LetterContent(objet=data.get("objet", f"Candidature au poste de {offer.intitule}"),
                             paragraphes=[p for p in data.get("paragraphes", []) if p.strip()])
