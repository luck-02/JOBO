"""Ports = interfaces dont le domaine a besoin.

Le domaine ne connaît que ces contrats. Changer de base de données, de modèle d'IA
ou de source d'offres revient à écrire un nouvel adaptateur, sans toucher au métier.
"""
from __future__ import annotations

from typing import Protocol

from .questions import Answer
from .tracking import Candidature
from .models import (
    CompanyInfo,
    CvContent,
    LetterContent,
    Offer,
    OfferQuery,
    OfferSummary,
    Profile,
)


class OfferSource(Protocol):
    """Fournit les offres (France Travail, démo, demain d'autres jobboards)."""

    def search(self, query: OfferQuery) -> list[OfferSummary]: ...

    def get(self, offer_id: str) -> Offer | None: ...


class CompanyInfoSource(Protocol):
    """Données factuelles sur une entreprise (annuaire officiel, démo...)."""

    def find(self, nom: str, siret: str = "") -> CompanyInfo | None: ...


class DocumentWriter(Protocol):
    """Rédige le contenu (pas la mise en page) : IA ou version démo."""

    def write_cv(self, profile: Profile, offer: Offer, instructions: str = "",
                 answers: list[Answer] | None = None, feedback: str = "") -> CvContent:
        """feedback : consignes de correction issues de l'auto-évaluation ATS (versions 2 et 3)."""
        ...

    def write_letter(
        self, profile: Profile, offer: Offer, company: CompanyInfo | None, instructions: str = "",
        answers: list[Answer] | None = None,
    ) -> LetterContent: ...


class PdfRenderer(Protocol):
    """Transforme le contenu en PDF compatible ATS."""

    def render_cv(self, profile: Profile, cv: CvContent) -> bytes: ...

    def render_letter(self, profile: Profile, offer: Offer, letter: LetterContent) -> bytes: ...

    def extract_text(self, pdf: bytes) -> str: ...

    def page_count(self, pdf: bytes) -> int: ...


class ProfileRepository(Protocol):
    def get(self, owner_id: str) -> Profile | None: ...

    def save(self, profile: Profile) -> None: ...


class FileStorage(Protocol):
    """Stockage des fichiers générés (disque local, S3, Supabase Storage...)."""

    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes | None: ...


class UsageLimiter(Protocol):
    """Quotas : invités, inscrits, premium."""

    def check_and_consume(self, subject: str, limit: int) -> bool: ...

    def remaining(self, subject: str, limit: int) -> int: ...


class ImportedOfferRepository(Protocol):
    """Offres importées par lien ou texte (pour les retrouver lors de la génération)."""

    def save(self, owner_id: str, offer: Offer) -> None: ...

    def get(self, offer_id: str) -> Offer | None: ...


class OfferLinkReader(Protocol):
    """Lit une annonce à partir d'un lien : renvoie l'offre si elle est structurée, sinon le texte brut."""

    def read(self, url: str) -> tuple[Offer | None, str]: ...


class OfferExtractor(Protocol):
    """Transforme le texte brut d'une annonce en offre structurée (IA ou heuristique)."""

    def extract(self, text: str, url: str = "") -> Offer: ...


class CvTextReader(Protocol):
    """Lit le texte d'un CV importé (PDF, DOCX)."""

    def read(self, filename: str, data: bytes) -> str: ...


class CvParser(Protocol):
    """Structure un CV texte en profil (identité, expériences, formations...)."""

    def parse(self, text: str) -> Profile: ...


class CandidatureRepository(Protocol):
    """Stockage du CRM (onglet Suivi)."""

    def save(self, c: "Candidature") -> None: ...

    def get(self, cand_id: str) -> "Candidature | None": ...

    def list(self, owner_id: str) -> "list[Candidature]": ...

    def find_by_offer(self, owner_id: str, offer_id: str) -> "Candidature | None": ...

    def delete(self, cand_id: str) -> None: ...
