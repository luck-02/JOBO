"""Téléchargement sécurisé d'une page d'offre collée par l'utilisateur.

Protection SSRF : un utilisateur ne doit pas pouvoir faire appeler au serveur une adresse interne
(127.0.0.1, réseau privé, métadonnées cloud 169.254.169.254...). On vérifie chaque saut de redirection.
"""
from __future__ import annotations

from ...domain.errors import UserFacingError

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
UA = "Mozilla/5.0 (compatible; CandidatureBot/0.1; +https://example.invalid/bot)"


class FetchError(UserFacingError):
    """Message affichable à l'utilisateur."""


def _check_url(url: str, resolver=socket.getaddrinfo) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise FetchError("Lien invalide : il doit commencer par http:// ou https://")
    if u.port not in (None, 80, 443):
        raise FetchError("Lien refusé")
    try:
        infos = resolver(u.hostname, None)
    except socket.gaierror:
        raise FetchError("Site introuvable")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise FetchError("Lien refusé")


class SafePageFetcher:
    def __init__(self, timeout: float = 10.0, transport: httpx.BaseTransport | None = None, resolver=None):
        self._http = httpx.Client(timeout=timeout, follow_redirects=False, transport=transport,
                                  headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
        self._resolver = resolver or socket.getaddrinfo

    def fetch(self, url: str) -> str:
        for _ in range(MAX_REDIRECTS + 1):
            _check_url(url, self._resolver)
            try:
                with self._http.stream("GET", url) as r:
                    if r.is_redirect:
                        url = urljoin(url, r.headers.get("location", ""))
                        continue
                    if r.status_code in (401, 403, 429):
                        raise FetchError("Ce site bloque la lecture automatique : colle le texte de l'offre")
                    if r.status_code >= 400:
                        raise FetchError(f"Page inaccessible (erreur {r.status_code})")
                    ctype = r.headers.get("content-type", "")
                    if "html" not in ctype and "text" not in ctype:
                        raise FetchError("Ce lien n'est pas une page web")
                    body = b""
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise FetchError("Page trop lourde")
                    return body.decode(r.encoding or "utf-8", errors="replace")
            except httpx.HTTPError:
                raise FetchError("Impossible de lire ce lien : colle le texte de l'offre")
        raise FetchError("Trop de redirections")


class WebOfferLinkReader:
    """Lien -> offre. France Travail via l'API officielle, sinon page web (schema.org puis texte)."""

    FT_ID = __import__("re").compile(r"francetravail\.fr/offres/recherche/detail/([A-Za-z0-9]+)")

    def __init__(self, fetcher: "SafePageFetcher", france_travail=None):
        self._fetcher = fetcher
        self._ft = france_travail

    def read(self, url: str):
        from ..offers.extract import html_to_text, offer_from_jsonld

        url = url.strip()
        m = self.FT_ID.search(url)
        if m and self._ft is not None:
            offer = self._ft.get(m.group(1))
            if offer:
                return offer, ""
        page = self._fetcher.fetch(url)
        offer = offer_from_jsonld(page, url, "")
        if offer and offer.intitule and len(offer.description) > 100:
            return offer, ""
        text = html_to_text(page)
        if len(text) < 200:
            raise FetchError("Impossible de lire l'annonce sur ce lien : colle le texte de l'offre")
        return None, text
