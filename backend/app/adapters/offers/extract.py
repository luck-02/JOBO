"""Lecture d'une annonce : données structurées schema.org (sans IA) puis texte brut."""
from __future__ import annotations

import html as htmllib
import json
import re

from ...domain.models import ContractType, Offer


def html_to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|li|h\d|div|tr)>", "\n", page)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", page))
    lines = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in text.splitlines()]
    return "\n".join(l for l in lines if l)[:20000]


def page_title(page: str) -> str:
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", page) or re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    return htmllib.unescape(re.sub(r"<[^>]+>|\s+", " ", m.group(1))).strip() if m else ""


def guess_contract(text: str) -> ContractType:
    t = text.lower()
    if "alternance" in t or "apprentissage" in t or "apprenti" in t or "professionnalisation" in t:
        return ContractType.ALTERNANCE
    if "stage" in t or "stagiaire" in t or "intern" in t:
        return ContractType.STAGE
    if "cdi" in t or "full_time" in t or "full-time" in t:
        return ContractType.CDI
    if "cdd" in t:
        return ContractType.CDD
    return ContractType.AUTRE


def _iter_jsonld(page: str):
    for raw in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "@graph" in item:
                    stack.extend(item["@graph"])
                yield item


def offer_from_jsonld(page: str, url: str, offer_id: str) -> Offer | None:
    """La plupart des sites d'emploi publient un bloc JobPosting (pour Google Jobs) : on le lit directement."""
    for item in _iter_jsonld(page):
        t = item.get("@type")
        if t != "JobPosting" and not (isinstance(t, list) and "JobPosting" in t):
            continue
        org = item.get("hiringOrganization") or {}
        loc = item.get("jobLocation") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
        lieu = ", ".join(x for x in [addr.get("addressLocality"), addr.get("postalCode")] if x) if isinstance(addr, dict) else ""
        desc = html_to_text(item.get("description", ""))
        emp = item.get("employmentType", "")
        emp = " ".join(emp) if isinstance(emp, list) else str(emp)
        intitule = htmllib.unescape(item.get("title", "")).strip()
        return Offer(
            id=offer_id, intitule=intitule,
            entreprise=org.get("name", "") if isinstance(org, dict) else str(org),
            lieu=lieu, contrat=guess_contract(f"{intitule} {emp} {desc[:500]}"),
            date_publication=str(item.get("datePosted", ""))[:10], description=desc, url=url, source="lien",
        )
    return None


class HeuristicOfferExtractor:
    """Sans IA : 1re ligne = intitulé, le reste = description. Suffisant en démo."""

    def extract(self, text: str, url: str = "") -> Offer:
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        intitule = lines[0][:150] if lines else "Offre importée"
        return Offer(id="", intitule=intitule, entreprise="", lieu="", contrat=guess_contract(text),
                     description="\n".join(lines[1:]) or text, url=url, source="lien" if url else "texte")
