"""Lecture du CV de base importé à l'inscription, et version démo du structurage (sans IA)."""
from __future__ import annotations

import io
import re

from ...domain.errors import UserFacingError
from ...domain.models import Profile

MAX_CV_BYTES = 5_000_000


class CvReadError(UserFacingError):
    pass


class PdfDocxCvReader:
    def read(self, filename: str, data: bytes) -> str:
        if len(data) > MAX_CV_BYTES:
            raise CvReadError("Fichier trop lourd (5 Mo maximum)")
        name = filename.lower()
        try:
            if name.endswith(".pdf") and data[:4] == b"%PDF":
                from pypdf import PdfReader
                text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages[:5])
            elif name.endswith(".docx") and data[:2] == b"PK":
                from docx import Document
                text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
            else:
                raise CvReadError("Format accepté : PDF ou Word (.docx)")
        except CvReadError:
            raise
        except Exception:
            raise CvReadError("Impossible de lire ce fichier")
        text = text.strip()
        if len(text) < 80:
            raise CvReadError("CV illisible (scanné ou image ?) : exporte-le en PDF texte")
        return text[:15000]


class DemoCvParser:
    """Sans IA : récupère seulement email, téléphone et nom. L'IA (AnthropicCvParser) fait le reste."""

    def parse(self, text: str) -> Profile:
        p = Profile(owner_id="")
        if m := re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            p.email = m.group(0)
        if m := re.search(r"(\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}", text):
            p.telephone = m.group(0)
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")
        parts = first.split()
        if 1 < len(parts) <= 4 and not re.search(r"\d|@", first):
            p.prenom, p.nom = parts[0], " ".join(parts[1:])
        return p
