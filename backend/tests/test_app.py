import os
import tempfile

import httpx
import pytest

tmp = tempfile.mkdtemp()
os.environ.update({
    "OFFERS_PROVIDER": "demo", "WRITER_PROVIDER": "demo", "COMPANY_PROVIDER": "demo",
    "DATABASE_URL": f"sqlite:///{tmp}/t.db", "STORAGE_DIR": f"{tmp}/files", "DAILY_GENERATION_LIMIT": "3",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.adapters.llm.common import build_cv_from_tool  # noqa: E402
from app.adapters.offers.france_travail import FranceTravailOfferSource  # noqa: E402
from app.api.main import app  # noqa: E402
from app.domain import ats  # noqa: E402
from app.domain.models import ContractType, Experience, Offer, OfferQuery, Profile  # noqa: E402

H = {"X-Client-Id": "test-client-123"}
H2 = {"X-Client-Id": "test-client-v1-456"}
PROFILE = {
    "prenom": "Camille", "nom": "Martin", "email": "camille@example.com", "telephone": "06 12 34 56 78",
    "ville": "Nantes", "recherche": "Étudiante en école de commerce", "disponibilite": "septembre, rythme 1/3",
    "experiences": [{
        "poste": "Assistante commerciale", "entreprise": "Exemple SAS", "ville": "Nantes", "debut": "09/2025",
        "fin": "", "type": "Alternance",
        "missions": ["Prospection B2B de 50 entreprises par téléphone et LinkedIn",
                     "Suivi du pipeline dans HubSpot", "Préparation de propositions commerciales"],
        "outils": ["HubSpot", "Sales Navigator"],
    }],
    "formations": [{"diplome": "Bachelor Commerce", "ecole": "École Exemple", "debut": "2023", "fin": "2026"}],
    "competences": ["Prospection", "CRM", "Négociation", "Excel"], "qualites": ["bon relationnel", "curieuse"],
    "langues": ["Anglais B2"], "interets": ["Tennis"],
}

client = TestClient(app)


def test_search_filters_contract():
    r = client.get("/api/offers", params={"contrat": "alternance"})
    assert r.status_code == 200
    assert r.json() and all(o["contrat"] == "alternance" for o in r.json())
    assert client.get("/api/offers", params={"lieu": "Paris!"}).status_code == 400


def test_profile_roundtrip_and_isolation():
    assert client.put("/api/profile", json=PROFILE, headers=H).status_code == 200
    assert client.get("/api/profile", headers=H).json()["prenom"] == "Camille"
    other = client.get("/api/profile", headers={"X-Client-Id": "someone-else-1"}).json()
    assert other["prenom"] == ""
    assert client.get("/api/profile").status_code == 400  # sans identifiant


def test_offer_detail_has_matching():
    client.put("/api/profile", json=PROFILE, headers=H)
    d = client.get("/api/offers/demo-1", headers=H).json()
    assert d["description"] and 0 <= d["matching"]["score"] <= 100
    assert "CRM" in d["matching"]["atouts"]


def test_generate_cv_and_letter_pdf():
    client.put("/api/profile", json=PROFILE, headers=H)
    r = client.post("/api/offers/demo-1/generate", json={"kinds": ["cv", "lettre"]}, headers=H)
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out["urls"]) == {"cv", "lettre"}
    pdf = client.get(out["urls"]["cv"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert 0 < out["ats"]["score"] <= 100
    parsing = next(c for c in out["ats"]["checks"] if c["label"] == "Lecture par les ATS (parsing)")
    assert "pages au lieu" not in parsing["detail"]
    assert sum(c["max_points"] for c in out["ats"]["checks"]) == 100


def test_incomplete_profile_refused():
    r = client.post("/api/offers/demo-1/generate", json={"kinds": ["cv"]}, headers={"X-Client-Id": "empty-profile-1"})
    assert r.status_code == 409


def test_path_traversal_blocked():
    assert client.get("/api/files/abcdef123456/..%2F..%2Fsecret.pdf").status_code in (400, 404)


def test_ai_cannot_invent_experience():
    p = Profile(owner_id="x", experiences=[Experience("Vendeur", "Boutique", missions=["Conseil client"])])
    offer = Offer(id="1", intitule="Commercial", entreprise="E", lieu="", contrat=ContractType.CDI)
    cv = build_cv_from_tool(p, offer, {"titre": "Commercial", "profil": "x",
                                       "experiences": [{"index": 7, "missions": ["Directeur chez Google"]}],
                                       "competences": [], "savoir_etre": []})
    assert [e.entreprise for e in cv.experiences] == ["Boutique"]
    assert "Google" not in str(cv)


def test_keywords_and_forbidden_phrases():
    offer = Offer(id="1", intitule="Alternance Business Developer", entreprise="E", lieu="",
                  contrat=ContractType.ALTERNANCE, description="Prospection B2B, CRM HubSpot, négociation.")
    kws = [k.lower() for k in ats.extract_keywords(offer)]
    assert {"prospection", "crm", "hubspot", "négociation"} <= set(kws)
    facts = ats.CvFacts("Alternance Business Developer", "", [], [])
    rep = ats.ats_report(offer, "Profil passionné. Email : a@b.fr CRM CRM CRM CRM", 1, facts)
    assert "passionne" in rep.expressions_a_eviter and "CRM" in rep.bourrage
    assert next(c for c in rep.checks if c.label == "Ton naturel").points == 15 - 4 - 3


def test_france_travail_adapter_parsing():
    def handler(req: httpx.Request) -> httpx.Response:
        if "access_token" in str(req.url):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 1499})
        assert req.headers["Authorization"] == "Bearer tok"
        if req.url.path.endswith("/search"):
            assert req.url.params["natureContrat"] == "E2,FS"
            return httpx.Response(200, json={"resultats": [{
                "id": "123ABC", "intitule": "Alternance commercial", "alternance": True,
                "entreprise": {"nom": "ACME"}, "lieuTravail": {"libelle": "44 - Nantes"},
                "dateCreation": "2026-10-30T10:00:00Z"}]})
        return httpx.Response(200, json={"id": "123ABC", "intitule": "Alternance commercial", "alternance": True,
                                         "description": "Prospection", "competences": [{"libelle": "CRM"}]})

    src = FranceTravailOfferSource("id", "secret")
    src._http = httpx.Client(transport=httpx.MockTransport(handler))
    res = src.search(OfferQuery(mots_cles="commercial", lieu="44"))
    assert res[0].contrat == ContractType.ALTERNANCE and res[0].entreprise == "ACME"
    assert src.get("123ABC").competences == ["CRM"]


def test_quota():
    client.put("/api/profile", json=PROFILE, headers=H)
    codes = [client.post("/api/offers/demo-2/generate", json={"kinds": ["cv"]}, headers=H).status_code
             for _ in range(4)]
    assert codes[-1] == 429


def test_anthropic_writer_uses_structured_output():
    from types import SimpleNamespace

    from app.adapters.llm.anthropic_writer import AnthropicWriter
    from app.adapters.db.sqlalchemy_repo import profile_from_dict

    calls = {}

    def fake_create(**kw):
        calls.update(kw)
        data = {"titre": "Alternance Business Developer IT", "profil": "Étudiante en commerce.",
                "experiences": [{"index": 0, "missions": ["Prospection B2B de 50 entreprises"]}],
                "competences": [{"groupe": "Commercial", "items": ["Prospection", "CRM"]}],
                "savoir_etre": ["bon relationnel"]}
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=data)])

    w = AnthropicWriter("sk-test", "claude-haiku-5-5")
    w._client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))
    from app.adapters.offers.demo import DemoOfferSource
    offer = DemoOfferSource().get("demo-1")
    cv = w.write_cv(profile_from_dict({**PROFILE, "owner_id": "x"}), offer, "Insiste sur la prospection")
    assert calls["tool_choice"] == {"type": "tool", "name": "cv_adapte"}
    assert "<notes_candidat>" in calls["messages"][0]["content"]
    assert cv.experiences[0].entreprise == "Exemple SAS" and cv.experiences[0].dates == "09/2025 – en cours"


# ---------------- V1 : lien d'offre + onboarding ----------------

JOB_PAGE = """<html><head><title>Offre</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting",
"title":"Alternance Business Developer","hiringOrganization":{"@type":"Organization","name":"ACME Conseil"},
"jobLocation":{"@type":"Place","address":{"addressLocality":"Nantes","postalCode":"44000"}},
"employmentType":"INTERN","datePosted":"2026-10-30",
"description":"<p>Missions : prospection B2B, suivi du pipeline dans le CRM HubSpot, négociation avec les clients, préparation des propositions commerciales.</p>"}
</script></head><body>...</body></html>"""

PUBLIC = lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))]  # noqa: E731


def _fetcher(handler, resolver=PUBLIC):
    from app.adapters.web.fetcher import SafePageFetcher
    return SafePageFetcher(transport=httpx.MockTransport(handler), resolver=resolver)


def test_link_reader_uses_jsonld_without_ai():
    from app.adapters.web.fetcher import WebOfferLinkReader
    f = _fetcher(lambda r: httpx.Response(200, text=JOB_PAGE, headers={"content-type": "text/html"}))
    offer, raw = WebOfferLinkReader(f).read("https://jobs.example.com/offre/1")
    assert offer.intitule == "Alternance Business Developer" and offer.entreprise == "ACME Conseil"
    assert offer.contrat == ContractType.ALTERNANCE and "HubSpot" in offer.description and raw == ""


@pytest.mark.parametrize("url,ip", [
    ("http://localhost/admin", "127.0.0.1"), ("http://metadata/", "169.254.169.254"),
    ("http://intra/", "10.0.0.5"), ("file:///etc/passwd", "93.184.216.34"), ("https://x.com:8443/", "93.184.216.34"),
])
def test_ssrf_blocked(url, ip):
    from app.adapters.web.fetcher import FetchError
    f = _fetcher(lambda r: httpx.Response(200, text="x"), resolver=lambda h, p: [(2, 1, 6, "", (ip, 0))])
    with pytest.raises(FetchError):
        f.fetch(url)


def test_ssrf_blocked_after_redirect():
    from app.adapters.web.fetcher import FetchError

    def resolver(host, port):
        return [(2, 1, 6, "", ("127.0.0.1" if host == "evil.local" else "93.184.216.34", 0))]

    f = _fetcher(lambda r: httpx.Response(302, headers={"location": "http://evil.local/"}), resolver)
    with pytest.raises(FetchError):
        f.fetch("https://jobs.example.com/x")


def test_blocked_site_asks_for_text():
    from app.adapters.web.fetcher import FetchError
    f = _fetcher(lambda r: httpx.Response(403, text="no"))
    with pytest.raises(FetchError, match="colle le texte"):
        f.fetch("https://www.example.com/job")


def test_import_text_then_generate():
    client.put("/api/profile", json=PROFILE, headers=H2)
    texte = ("Alternance Assistant Commercial\nNous recherchons un alternant pour la prospection B2B, "
             "le suivi des clients dans le CRM et la préparation des devis. Anglais apprécié.")
    r = client.post("/api/offers/import", json={"texte": texte}, headers=H2)
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    assert oid.startswith("imp-") and r.json()["intitule"] == "Alternance Assistant Commercial"
    d = client.get(f"/api/offers/{oid}", headers=H2).json()
    assert d["contrat"] == "alternance"
    from app.api.main import container
    container.generation.limiter._counts.clear()  # quota consommé par les tests précédents
    g = client.post(f"/api/offers/{oid}/generate", json={"kinds": ["cv"]}, headers=H2)
    assert g.status_code == 200 and g.json()["ats"]["score"] > 0
    assert client.post("/api/offers/import", json={"texte": "trop court"}, headers=H2).status_code == 422


def test_import_bad_link_is_clean_error():
    r = client.post("/api/offers/import", json={"url": "http://127.0.0.1:8000/api/health"}, headers=H2)
    assert r.status_code == 422 and "refusé" in r.json()["detail"]


def test_signup_cv_upload_only():
    from weasyprint import HTML
    hdr = {"X-Client-Id": "onboarding-user-1"}
    pdf = HTML(string="<p>Jeanne Durand</p><p>jeanne@example.com · 06 11 22 33 44</p>"
                      "<p>Expériences : vendeuse chez Boutique Exemple, conseil client et encaissement.</p>").write_pdf()
    r = client.post("/api/onboarding/cv", files={"file": ("cv.pdf", pdf, "application/pdf")}, headers=hdr)
    assert r.status_code == 200, r.text
    p = client.get("/api/profile", headers=hdr).json()
    assert p["prenom"] == "Jeanne" and p["email"] == "jeanne@example.com" and p["a_un_cv"] and p["onboarded"]
    assert "cv_base" not in p
    bad = client.post("/api/onboarding/cv", files={"file": ("cv.exe", b"MZ....", "application/octet-stream")}, headers=hdr)
    assert bad.status_code == 422
    # le PUT du profil ne peut pas effacer le CV de base
    p["prenom"] = "Jeanne-Marie"
    client.put("/api/profile", json=p, headers=hdr)
    assert client.get("/api/profile", headers=hdr).json()["a_un_cv"]


def test_ten_questions_per_offer_target_missing_keywords():
    client.put("/api/profile", json=PROFILE, headers=H)
    qs = client.get("/api/offers/demo-1/questions", headers=H).json()
    assert len(qs) == 10 and len({q["id"] for q in qs}) == 10
    textes = " ".join(q["question"] for q in qs)
    assert "appels d'offres" in textes          # mot-clé de l'offre absent du profil
    assert "Atlantique Numérique" in textes     # question de motivation propre à l'entreprise
    assert "« CRM »" not in textes              # déjà couvert par le profil : pas de question
    assert all(q["options"] for q in qs)        # des choix à cliquer partout, « Autre » géré par le front
    priorite = next(q for q in qs if q["id"] == "priorite")
    assert priorite["options"] == ["Assistante commerciale chez Exemple SAS", "Bachelor Commerce (École Exemple)"]
    client.put("/api/profile", json={**PROFILE, "langues": []}, headers=H)
    qs = client.get("/api/offers/demo-6/questions", headers=H).json()
    assert any("« anglais » : quel est ton niveau" in q["question"].lower() for q in qs)
    client.put("/api/profile", json=PROFILE, headers=H)
    cdi = client.get("/api/offers/demo-6/questions", headers=H).json()
    assert len(cdi) == 10 and all(q["id"] != "dispo" for q in cdi)


def test_answers_update_adequation_without_ai():
    client.put("/api/profile", json=PROFILE, headers=H)
    offer = client.get("/api/offers/demo-1", headers=H).json()
    assert offer["profil_connu"] is True
    base = offer["analyse"]["score_adequation"]
    q = next(x for x in client.get("/api/offers/demo-1/questions", headers=H).json() if x["id"].startswith("mot_"))
    terme = q["question"].split("« ")[1].split(" »")[0]

    def cov(reponse: str) -> tuple[float, str]:
        a = client.post("/api/offers/demo-1/analyse", headers=H,
                        json={"reponses": [{"question": q["question"], "reponse": reponse}]}).json()
        return a["score_adequation"], next(k["couverture"] for k in a["mots_cles"] if k["terme"] == terme)

    assert cov("Non, jamais") == (base, next(k["couverture"] for k in offer["analyse"]["mots_cles"]
                                              if k["terme"] == terme))
    assert cov("Un peu, des notions")[1] == "partiel"
    score_oui, c = cov("Oui, en projet d'école : 2 mois")
    assert c == "oui" and score_oui > base


def test_answers_reach_the_writer():
    from app.api.main import container
    seen = {}
    real = container.generation.writer

    class Spy:
        def write_cv(self, profile, offer, instructions="", answers=None, feedback=""):
            seen["answers"], seen["notes"] = answers, instructions
            return real.write_cv(profile, offer, instructions, answers)

        def write_letter(self, *a, **k):
            return real.write_letter(*a, **k)

    container.generation.writer = Spy()
    container.generation.limiter._counts.clear()
    try:
        client.put("/api/profile", json=PROFILE, headers=H)
        body = {"kinds": ["cv"], "instructions": "Je vise les PME",
                "reponses": [{"question": "Qu'est-ce qui t'attire ?", "reponse": "Le contact client"},
                             {"question": "Un chiffre ?", "reponse": "   "}]}
        assert client.post("/api/offers/demo-1/generate", json=body, headers=H).status_code == 200
    finally:
        container.generation.writer = real
    assert [a.reponse for a in seen["answers"]] == ["Le contact client"]   # réponses vides ignorées
    assert seen["notes"] == "Je vise les PME"
    too_many = {"kinds": ["cv"], "reponses": [{"question": f"q{i}", "reponse": "x"} for i in range(11)]}
    assert client.post("/api/offers/demo-1/generate", json=too_many, headers=H).status_code == 422


def test_docx_cv_reader():
    import io

    from docx import Document

    from app.adapters.cv.reader import PdfDocxCvReader
    doc = Document()
    doc.add_paragraph("Paul Leroy")
    doc.add_paragraph("Stage commercial chez Exemple SAS : prospection de 30 clients et suivi des devis dans Excel.")
    buf = io.BytesIO(); doc.save(buf)
    assert "Paul Leroy" in PdfDocxCvReader().read("cv.docx", buf.getvalue())


def test_ai_context_includes_answers():
    from app.adapters.db.sqlalchemy_repo import profile_from_dict
    from app.adapters.llm.anthropic_writer import AnthropicWriter
    from app.adapters.offers.demo import DemoOfferSource
    from app.domain.questions import Answer
    prof = profile_from_dict({**PROFILE, "owner_id": "x", "cv_base": "texte long"})
    ctx = AnthropicWriter._context(prof, DemoOfferSource().get("demo-1"), "Je vise les PME",
                                   answers=[Answer("Qu'est-ce qui t'attire ?", "le contact client")])
    assert "le contact client" in ctx and "Je vise les PME" in ctx and "texte long" not in ctx


def test_keyword_table_levels_like_skill():
    from app.adapters.offers.demo import DemoOfferSource
    table = {k.terme.lower(): k.niveau for k in ats.keyword_table(DemoOfferSource().get("demo-1"))}
    assert table["crm"] == "obligatoire" and table["négociation"] == "obligatoire"   # compétences listées
    assert table["anglais"] == "bonus"                                             # "anglais apprécié"
    assert table["hubspot"] == "important"                                         # cité dans les missions


def test_offer_analysis_score_and_gaps():
    client.put("/api/profile", json=PROFILE, headers=H)
    a = client.get("/api/offers/demo-1", headers=H).json()["analyse"]
    assert 0 <= a["score_adequation"] <= 10
    assert "CRM" in a["points_forts"] and "appels d'offres" in " ".join(a["ecarts"] + [k["terme"] for k in a["mots_cles"]])
    assert {k["niveau"] for k in a["mots_cles"]} <= {"obligatoire", "important", "bonus"}


def test_correction_loop_keeps_best_and_stops_at_3():
    from app.api.main import container
    from app.domain.models import CvContent, CvSection
    calls = []

    class Writer:
        supports_feedback = True

        def write_cv(self, profile, offer, instructions="", answers=None, feedback=""):
            calls.append(feedback)
            bon = len(calls) >= 2
            comps = {"Commercial": ["Prospection commerciale", "CRM", "Négociation", "prospection", "B2B", "pipeline",
                                    "HubSpot", "Sales Navigator", "appels d'offres", "développement commercial", "anglais",
                                    "ESN"]} if bon else {"Divers": ["Excel"]}
            return CvContent(offer.intitule, f"Étudiante visant le poste {offer.intitule}.",
                             [CvSection("Assistante (Alternance)", "Exemple SAS", "Nantes", "09/2025 – en cours",
                                        ["Prospection B2B de 50 entreprises", "Suivi de 20 clients"])],
                             comps, ["bon relationnel"])

        def write_letter(self, *a, **k):
            raise AssertionError

    real = container.generation.writer
    container.generation.writer = Writer()
    container.generation.limiter._counts.clear()
    try:
        client.put("/api/profile", json=PROFILE, headers=H)
        out = client.post("/api/offers/demo-1/generate", json={"kinds": ["cv"]}, headers=H).json()
    finally:
        container.generation.writer = real
    assert calls[0] == "" and "Mots-clés obligatoires absents" in calls[1]
    assert 2 <= out["iterations"] <= 3 and len(calls) == out["iterations"]
    assert out["ats"]["couverture_obligatoires"] == 100


# ---------------- CRM (onglet Suivi) ----------------

def test_tracking_rules_relance_and_stats():
    from datetime import date

    from app.domain.tracking import Candidature, Statut, changer_statut, stats
    d0 = date(2026, 11, 3)
    c = Candidature(id="c1", owner_id="o", intitule="Alt", entreprise="E", date_creation=d0.isoformat())
    changer_statut(c, Statut.ENVOYEE, d0)
    assert c.date_envoi == "2026-11-03" and c.relance_prevue == "2026-11-10"
    assert not c.relance_due(date(2026, 11, 9)) and c.relance_due(date(2026, 11, 10))
    changer_statut(c, Statut.RELANCEE, date(2026, 11, 10))
    assert c.relance_prevue == "2026-11-17" and c.date_envoi == "2026-11-03"
    changer_statut(c, Statut.ENTRETIEN, date(2026, 11, 12))
    assert c.relance_prevue == "" and [e.statut for e in c.historique][-1] == Statut.ENTRETIEN
    c2 = Candidature(id="c2", owner_id="o", intitule="B", entreprise="F", date_creation="2026-10-01")
    changer_statut(c2, Statut.ENVOYEE, date(2026, 10, 1))
    s = stats([c, c2], date(2026, 11, 12))
    assert s.envoyees == 2 and s.taux_reponse == 50 and s.taux_entretien == 50 and s.relances_a_faire == 1
    assert s.cette_semaine == 0


def test_generation_adds_offer_to_crm_once():
    from app.api.main import container
    container.generation.limiter._counts.clear()
    hdr = {"X-Client-Id": "crm-user-0001"}
    client.put("/api/profile", json=PROFILE, headers=hdr)
    r1 = client.post("/api/offers/demo-2/generate", json={"kinds": ["cv"]}, headers=hdr).json()
    r2 = client.post("/api/offers/demo-2/generate", json={"kinds": ["lettre"]}, headers=hdr).json()
    assert r1["candidature_id"] == r2["candidature_id"]
    lst = client.get("/api/candidatures", headers=hdr).json()
    assert len(lst) == 1 and set(lst[0]["fichiers"]) == {"cv", "lettre"}
    assert lst[0]["statut"] == "a_envoyer" and lst[0]["score_ats"] is not None and "owner_id" not in lst[0]


def test_crm_crud_and_isolation():
    hdr = {"X-Client-Id": "crm-user-0002"}
    other = {"X-Client-Id": "crm-intrus-001"}
    c = client.post("/api/candidatures", json={"intitule": "Alternance Business Developer", "entreprise": "ACME",
                                               "statut": "envoyee"}, headers=hdr).json()
    assert c["statut"] == "envoyee" and c["relance_prevue"] and not c["relance_due"]
    assert client.post("/api/candidatures", json={"intitule": " ", "entreprise": "x"}, headers=hdr).status_code == 422
    u = client.patch(f"/api/candidatures/{c['id']}", json={"statut": "entretien", "notes": "RDV mardi",
                                                           "contact": "Marie, RH"}, headers=hdr).json()
    assert u["statut"] == "entretien" and u["notes"] == "RDV mardi" and u["relance_prevue"] == ""
    assert client.patch(f"/api/candidatures/{c['id']}", json={"relance_prevue": "demain"}, headers=hdr).status_code == 422
    # un autre utilisateur ne voit ni ne modifie rien
    assert client.get("/api/candidatures", headers=other).json() == []
    assert client.patch(f"/api/candidatures/{c['id']}", json={"statut": "refus"}, headers=other).status_code == 404
    assert client.delete(f"/api/candidatures/{c['id']}", headers=other).status_code == 404
    st = client.get("/api/candidatures/stats", headers=hdr).json()
    assert st["total"] == 1 and st["taux_entretien"] == 100
    assert client.delete(f"/api/candidatures/{c['id']}", headers=hdr).json()["ok"]
    assert client.get("/api/candidatures", headers=hdr).json() == []


# ---------------- Swipe d'offres (mobile) ----------------

from datetime import date as _date  # noqa: E402

from app.domain.models import OfferSummary  # noqa: E402
from app.domain.swipe import (  # noqa: E402
    Raison, TypeReaction, composer_pile, nettoyer_preferences, nouvelle_reaction, passees_visibles,
)


def _o(id, intitule="Alternance Business Developer", ent="A", lieu="44 - Nantes", contrat=ContractType.ALTERNANCE):
    return OfferSummary(id, intitule, ent, lieu, contrat)


def test_pile_hides_swiped_and_refines_with_reasons():
    today = _date(2026, 11, 25)
    offres = [_o("1"), _o("2", ent="B"), _o("3", "Stage Business Developer", ent="C"),
              _o("4", "Alternance Data Analyst", ent="D", lieu="35 - Rennes"), _o("5", "Alternance Comptable", ent="E", lieu="35 - Rennes")]
    passe_metier = nouvelle_reaction("u", offres[0], TypeReaction.PASSER, today)
    passe_metier.raison = Raison.METIER
    passe_ent = nouvelle_reaction("u", _o("x", ent="D"), TypeReaction.PASSER, today)
    passe_ent.raison = Raison.ENTREPRISE
    pile = [o.id for o in composer_pile(offres, [passe_metier, passe_ent])]
    assert "1" not in pile                       # déjà swipée : masquée pour toujours
    assert "4" not in pile                       # entreprise refusée : toutes ses offres disparaissent
    assert pile == ["5", "2", "3"]               # même métier refusé -> fin de pile, ordre gardé sinon


def test_passees_listed_30_days_and_favori_reminder_once():
    today = _date(2026, 11, 25)
    vieille = nouvelle_reaction("u", _o("1"), TypeReaction.PASSER, _date(2026, 10, 1))
    recente = nouvelle_reaction("u", _o("2"), TypeReaction.PASSER, _date(2026, 11, 20))
    assert [r.offer_id for r in passees_visibles([vieille, recente], today)] == ["2"]
    fav = nouvelle_reaction("u", _o("3"), TypeReaction.FAVORI, today)
    assert fav.rappel_le == "2026-12-02" and not fav.rappel_du(today) and fav.rappel_du(_date(2026, 12, 2))
    fav.rappel_actif = False
    assert not fav.rappel_du(_date(2026, 12, 3))


def test_preferences_multi_contrats_validated():
    p = nettoyer_preferences(["alternance", "cdi", "cdi"], ["44", "35"], " commercial ")
    assert [c.value for c in p.contrats] == ["alternance", "cdi"] and p.mots_cles == "commercial"
    with pytest.raises(ValueError):
        nettoyer_preferences(["freelance"], [], "")
    with pytest.raises(ValueError):
        nettoyer_preferences([], ["Paris"], "")


def test_swipe_api_flow():
    h = {"X-Client-Id": "swipe-client-001"}
    assert client.put("/api/preferences", json={"contrats": ["alternance", "stage"], "departements": ["44"]},
                      headers=h).status_code == 200
    assert client.put("/api/preferences", json={"contrats": ["xx"]}, headers=h).status_code == 422
    pile = client.get("/api/swipe/pile", headers=h).json()
    assert pile and all(o["contrat"] in ("alternance", "stage") and o["lieu"].startswith("44") for o in pile)
    assert {o["contrat"] for o in pile[:2]} == {"alternance", "stage"}   # contrats entrelacés

    # Invité : peut passer, mais postuler ou favori demande un compte
    first = pile[0]["id"]
    assert client.post("/api/swipe/reactions", json={"offer_id": first, "type": "postuler"}, headers=h).status_code == 401
    assert client.post("/api/swipe/reactions", json={"offer_id": first, "type": "passer"}, headers=h).status_code == 200
    assert client.patch(f"/api/swipe/reactions/{first}/raison", json={"raison": "lieu"}, headers=h).json()["raison"] == "lieu"
    assert first not in [o["id"] for o in client.get("/api/swipe/pile", headers=h).json()]
    assert [r["offer_id"] for r in client.get("/api/swipe/passees", headers=h).json()] == [first]
    # Annuler : l'offre revient
    assert client.delete(f"/api/swipe/reactions/{first}", headers=h).status_code == 200
    assert first in [o["id"] for o in client.get("/api/swipe/pile", headers=h).json()]

    # Avec un compte : postuler -> brouillon dans le suivi, favori avec rappel
    client.put("/api/profile", json=PROFILE, headers=h)
    assert client.post("/api/swipe/reactions", json={"offer_id": first, "type": "postuler"}, headers=h).status_code == 200
    qs = client.get(f"/api/offers/{first}/questions", params={"n": 3}, headers=h).json()
    assert len(qs) == 3
    c = client.post(f"/api/swipe/reactions/{first}/brouillon",
                    json={"reponses": [{"question": qs[0]["question"], "reponse": "Oui, en projet d'école"}]},
                    headers=h).json()
    assert c["statut"] == "brouillon" and c["reponses"][0]["reponse"] == "Oui, en projet d'école"
    assert [x["statut"] for x in client.get("/api/candidatures", headers=h).json()] == ["brouillon"]
    # Annuler un postuler retire le brouillon sans fichier
    client.delete(f"/api/swipe/reactions/{first}", headers=h)
    assert client.get("/api/candidatures", headers=h).json() == []

    second = pile[1]["id"]
    fav = client.post("/api/swipe/reactions", json={"offer_id": second, "type": "favori"}, headers=h).json()
    assert fav["rappel_actif"] and fav["rappel_le"] and not fav["rappel_du"]
    assert client.patch(f"/api/swipe/reactions/{second}/rappel", json={"actif": False}, headers=h).json()["rappel_actif"] is False
    assert [r["offer_id"] for r in client.get("/api/swipe/favoris", headers=h).json()] == [second]
    # Isolation : un autre navigateur ne voit rien
    assert client.get("/api/swipe/favoris", headers={"X-Client-Id": "swipe-client-002"}).json() == []
    assert client.delete(f"/api/swipe/reactions/{second}", headers={"X-Client-Id": "swipe-client-002"}).status_code == 404


def test_generation_turns_brouillon_into_a_envoyer():
    h = {"X-Client-Id": "swipe-client-003"}
    client.put("/api/profile", json=PROFILE, headers=h)
    client.post("/api/swipe/reactions", json={"offer_id": "demo-2", "type": "postuler"}, headers=h)
    client.post("/api/swipe/reactions/demo-2/brouillon", json={"reponses": []}, headers=h)
    r = client.post("/api/offers/demo-2/generate", json={"kinds": ["cv"]}, headers=h)
    assert r.status_code == 200, r.text
    cands = client.get("/api/candidatures", headers=h).json()
    assert len(cands) == 1 and cands[0]["statut"] == "a_envoyer" and cands[0]["fichiers"]["cv"]
