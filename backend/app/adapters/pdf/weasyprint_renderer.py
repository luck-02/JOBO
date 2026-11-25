"""Rendu PDF compatible ATS : une colonne, texte sélectionnable, sections standards, A4."""
from __future__ import annotations

import io
from datetime import date

from jinja2 import Environment, select_autoescape
from pypdf import PdfReader
from weasyprint import HTML

from ...domain.models import CvContent, LetterContent, Offer, Profile

_env = Environment(autoescape=select_autoescape(["html"]))

_CSS = """
@page { size: A4; margin: 1.6cm 1.7cm; }
body { font-family: 'Lato', 'Open Sans', Arial, 'Liberation Sans', 'DejaVu Sans', sans-serif; font-size: 10pt; color: #1f2328; line-height: 1.35; }
h1 { font-size: 20pt; margin: 0; }
.titre { font-size: 12.5pt; color: {{ accent }}; font-weight: bold; margin: 2px 0 4px; }
.contact { font-size: 9.5pt; color: #444; }
h2 { font-size: 12pt; color: {{ accent }}; border-bottom: 1.2px solid {{ accent }}; padding-bottom: 2px;
     margin: 12px 0 6px; text-transform: none; }
.exp { margin-bottom: 7px; page-break-inside: avoid; }
.exp-head { display: flex; justify-content: space-between; font-weight: bold; }
.exp-head .d { font-weight: normal; color: #555; white-space: nowrap; padding-left: 8px; }
ul { margin: 2px 0 0 0; padding-left: 14px; }
li { margin: 1px 0; }
.env { font-size: 9pt; color: #555; margin-top: 2px; }
p { margin: 0 0 4px; }
.lettre p { margin: 0 0 10px; text-align: justify; font-size: 10.5pt; }
"""

_CV = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>CV {{ p.nom_complet }} – {{ cv.titre }}</title>
<meta name="author" content="{{ p.nom_complet }}"><style>{{ css }}</style></head><body>
<h1>{{ p.nom_complet }}</h1>
<div class="titre">{{ cv.titre }}</div>
<div class="contact">
{% if p.email %}Email : {{ p.email }}{% endif %}{% if p.telephone %} · Tél : {{ p.telephone }}{% endif %}
{% if p.ville %} · {{ p.ville }}{% endif %}{% if p.linkedin %} · LinkedIn : {{ p.linkedin }}{% endif %}
</div>
{% if p.disponibilite %}<div class="contact">Disponibilité : {{ p.disponibilite }}</div>{% endif %}

<h2>Profil</h2><p>{{ cv.profil }}</p>

{% if cv.experiences %}<h2>Expériences professionnelles</h2>
{% for e in cv.experiences %}<div class="exp">
<div class="exp-head"><span>{{ e.poste }} · {{ e.entreprise }}{% if e.ville %} · {{ e.ville }}{% endif %}</span><span class="d">{{ e.dates }}</span></div>
<ul>{% for m in e.missions %}<li>{{ m }}</li>{% endfor %}</ul>
{% if e.outils %}<div class="env">Env. : {{ e.outils | join(' · ') }}</div>{% endif %}
</div>{% endfor %}{% endif %}

{% if p.formations %}<h2>Formation</h2>
{% for f in p.formations %}<div class="exp"><div class="exp-head"><span>{{ f.diplome }} · {{ f.ecole }}</span>
<span class="d">{{ f.debut }}{% if f.debut %} – {% endif %}{{ f.fin }}</span></div>
{% if f.details %}<div class="env">{{ f.details }}</div>{% endif %}</div>{% endfor %}{% endif %}

<h2>Compétences</h2>
{% for g, items in cv.competences.items() %}<p><b>{{ g }} :</b> {{ items | join(', ') }}</p>{% endfor %}
{% if cv.savoir_etre %}<p><b>Savoir-être :</b> {{ cv.savoir_etre | join(', ') }}</p>{% endif %}

{% if p.langues %}<h2>Langues</h2><p>{{ p.langues | join(' · ') }}</p>{% endif %}
{% if p.interets %}<h2>Centres d'intérêt</h2><p>{{ p.interets | join(', ') }}</p>{% endif %}
</body></html>"""

_LETTRE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Lettre {{ p.nom_complet }} – {{ o.intitule }}</title>
<meta name="author" content="{{ p.nom_complet }}"><style>{{ css }}</style></head><body class="lettre">
<p><b>{{ p.nom_complet }}</b><br>{{ p.ville }}<br>{{ p.email }}{% if p.telephone %} · {{ p.telephone }}{% endif %}</p>
<p style="text-align:right">{{ o.entreprise }}<br>{{ p.ville or '' }}, le {{ today }}</p>
<p><b>Objet : {{ l.objet }}</b></p>
<p>Madame, Monsieur,</p>
{% for par in l.paragraphes %}<p>{{ par }}</p>{% endfor %}
<p>Je vous prie d'agréer, Madame, Monsieur, mes salutations distinguées.</p>
<p>{{ p.nom_complet }}</p>
</body></html>"""

_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
         "octobre", "novembre", "décembre"]


class WeasyPrintRenderer:
    def __init__(self, accent: str = "#1d4ed8"):
        self._css = _env.from_string(_CSS).render(accent=accent)

    def render_cv(self, profile: Profile, cv: CvContent) -> bytes:
        html = _env.from_string(_CV).render(p=profile, cv=cv, css=self._css)
        return HTML(string=html).write_pdf()

    def render_letter(self, profile: Profile, offer: Offer, letter: LetterContent) -> bytes:
        d = date.today()
        html = _env.from_string(_LETTRE).render(p=profile, o=offer, l=letter, css=self._css,
                                                today=f"{d.day} {_MOIS[d.month - 1]} {d.year}")
        return HTML(string=html).write_pdf()

    def extract_text(self, pdf: bytes) -> str:
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)

    def page_count(self, pdf: bytes) -> int:
        return len(PdfReader(io.BytesIO(pdf)).pages)
