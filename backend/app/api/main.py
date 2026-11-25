"""Adaptateur HTTP (FastAPI). Ne contient aucune règle métier."""
from __future__ import annotations

import re
from dataclasses import asdict

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ..adapters.db.sqlalchemy_repo import profile_from_dict
from ..application.services import AccountRequired, NotFound, ProfileIncomplete, QuotaExceeded
from ..config import Settings
from ..container import build
from ..domain import ats
from ..domain.errors import UserFacingError
from ..domain.questions import Answer
from ..domain.swipe import Raison, TypeReaction
from ..domain.tracking import Statut
from ..domain.models import ContractType, DocumentKind, OfferQuery, Profile

settings = Settings()
container = build(settings)

app = FastAPI(title="Candidature API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "PUT", "POST", "PATCH", "DELETE"],  # upload multipart inclus
    allow_headers=["Content-Type", "X-Client-Id"],
)

_CLIENT_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_profile_adapter = TypeAdapter(Profile)


def client_id(x_client_id: str = Header(default="")) -> str:
    """POC : identifiant anonyme généré par le navigateur. Remplacé par l'auth (Supabase) en V1."""
    if not _CLIENT_RE.match(x_client_id):
        raise HTTPException(400, "En-tête X-Client-Id manquant ou invalide")
    return x_client_id


@app.get("/api/health")
def health():
    return {"ok": True, "offres": settings.offers_provider, "redaction": settings.writer_provider}


@app.get("/api/offers")
def search_offers(q: str = "", lieu: str = "", contrat: str = "alternance", page: int = 0):
    try:
        c = None if contrat in ("", "tous") else ContractType(contrat)
    except ValueError:
        raise HTTPException(400, "Type de contrat inconnu")
    if lieu and not re.fullmatch(r"\d{2}|2[AB]|97\d", lieu):
        raise HTTPException(400, "Le lieu doit être un numéro de département (ex. 44)")
    res = container.offers.search(OfferQuery(mots_cles=q[:100], lieu=lieu, contrat=c, page=max(0, page)))
    return [asdict(o) for o in res]


class ImportIn(BaseModel):
    url: str = Field(default="", max_length=2000)
    texte: str = Field(default="", max_length=30000)


@app.post("/api/offers/import")
def import_offer(body: ImportIn, request: Request, owner: str = Depends(client_id)):
    """V1 : on colle le lien (ou le texte) d'une offre."""
    if not container.generation.limiter.check_and_consume("import:" + _quota_subject(request), 30):
        raise HTTPException(429, "Trop d'imports aujourd'hui")
    try:
        offer = container.imports.import_offer(owner, body.url, body.texte)
    except UserFacingError as e:
        raise HTTPException(422, str(e))
    return {"id": offer.id, "intitule": offer.intitule, "entreprise": offer.entreprise}


@app.post("/api/onboarding/cv")
async def upload_cv(file: UploadFile = File(...), owner: str = Depends(client_id)):
    data = await file.read(5_000_001)
    try:
        p = container.onboarding.import_cv(owner, file.filename or "", data)
    except UserFacingError as e:
        raise HTTPException(422, str(e))
    return {"experiences": len(p.experiences), "formations": len(p.formations),
            "nom": p.nom_complet, "onboarded": p.is_onboarded()}


@app.get("/api/offers/{offer_id}")
def get_offer(offer_id: str, owner: str = Depends(client_id)):
    try:
        offer = container.offers.get(offer_id)
    except NotFound:
        raise HTTPException(404, "Offre introuvable")
    profile = container.profiles.get(owner)
    a = ats.analyse(profile, offer)
    return {**asdict(offer), "analyse": asdict(a), "profil_connu": profile.is_onboarded(),
            "matching": {"score": round(a.score_adequation * 10), "atouts": a.points_forts, "manques": a.ecarts}}


@app.get("/api/offers/{offer_id}/company")
def company(offer_id: str):
    try:
        offer = container.offers.get(offer_id)
    except NotFound:
        raise HTTPException(404, "Offre introuvable")
    info = container.companies.fiche(offer)
    if not info:
        raise HTTPException(404, "Entreprise introuvable dans l'annuaire")
    return asdict(info)


@app.get("/api/profile")
def get_profile(owner: str = Depends(client_id)):
    profile = container.profiles.get(owner)
    p = asdict(profile)
    p.pop("owner_id")
    p["a_un_cv"] = bool(p.pop("cv_base"))
    p["onboarded"] = profile.is_onboarded()
    return p


@app.put("/api/profile")
async def put_profile(request: Request, owner: str = Depends(client_id)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(422, "Profil invalide")
    body["owner_id"] = owner
    existing = container.profiles.get(owner)
    for k in ("a_un_cv", "onboarded"):
        body.pop(k, None)
    body["cv_base"] = existing.cv_base          # jamais modifiable par ce point d'entrée
    try:
        _profile_adapter.validate_python(body)
        profile = profile_from_dict(body)
    except (ValidationError, TypeError) as e:
        raise HTTPException(422, f"Profil invalide : {e}")
    container.profiles.save(profile)
    p = asdict(profile)
    p.pop("owner_id")
    p["a_un_cv"] = bool(p.pop("cv_base"))
    p["onboarded"] = profile.is_onboarded()
    return p


class AnswerIn(BaseModel):
    question: str = Field(max_length=300)
    reponse: str = Field(default="", max_length=600)


class GenerateIn(BaseModel):
    kinds: list[DocumentKind] = Field(min_length=1, max_length=2)
    instructions: str = Field(default="", max_length=1500)   # champ libre facultatif
    reponses: list[AnswerIn] = Field(default_factory=list, max_length=10)


@app.get("/api/offers/{offer_id}/questions")
def offer_questions(offer_id: str, n: int = 10, owner: str = Depends(client_id)):
    """Les 10 questions à poser pour cette offre (sans IA). Le swipe n'en demande que 3 (n=3)."""
    try:
        return [asdict(q) for q in container.generation.questions(owner, offer_id)][:max(1, min(n, 10))]
    except NotFound:
        raise HTTPException(404, "Offre introuvable")


class AnalyseIn(BaseModel):
    reponses: list[AnswerIn] = Field(default_factory=list, max_length=10)


@app.post("/api/offers/{offer_id}/analyse")
def analyse_offer(offer_id: str, body: AnalyseIn, owner: str = Depends(client_id)):
    """Adéquation recalculée avec les réponses aux questions (sans IA, sans quota)."""
    try:
        a = container.generation.analyse(owner, offer_id, [Answer(r.question, r.reponse) for r in body.reponses])
    except NotFound:
        raise HTTPException(404, "Offre introuvable")
    return asdict(a)


@app.get("/api/quota")
def quota(request: Request, owner: str = Depends(client_id)):
    return {"restant": container.generation.remaining(_quota_subject(request)),
            "limite": settings.daily_generation_limit}


@app.post("/api/offers/{offer_id}/generate")
def generate(offer_id: str, body: GenerateIn, request: Request, owner: str = Depends(client_id)):
    try:
        res = container.generation.generate(owner, _quota_subject(request), offer_id,
                                            list(dict.fromkeys(body.kinds)), body.instructions,
                                            [Answer(a.question, a.reponse) for a in body.reponses])
    except ProfileIncomplete:
        raise HTTPException(409, "Complète ton profil (nom, email, au moins une expérience ou formation)")
    except NotFound:
        raise HTTPException(404, "Offre introuvable")
    except QuotaExceeded:
        raise HTTPException(429, "Limite quotidienne atteinte, reviens demain")
    out = asdict(res)
    out["urls"] = {k: f"/api/files/{res.id}/{name}" for k, name in res.files.items()}
    return out


@app.get("/api/files/{gen_id}/{name}")
def download(gen_id: str, name: str):
    if not re.fullmatch(r"[a-f0-9]{12}", gen_id) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,140}\.pdf", name):
        raise HTTPException(400, "Fichier invalide")
    data = container.storage.get(f"{gen_id}/{name}")
    if data is None:
        raise HTTPException(404, "Fichier introuvable")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


# ---------------- CRM (onglet Suivi) ----------------

class CandidatureIn(BaseModel):
    intitule: str = Field(max_length=200)
    entreprise: str = Field(max_length=200)
    lieu: str = Field(default="", max_length=120)
    url: str = Field(default="", max_length=2000)
    statut: Statut = Statut.A_ENVOYER


class CandidaturePatch(BaseModel):
    statut: Statut | None = None
    notes: str | None = Field(default=None, max_length=3000)
    contact: str | None = Field(default=None, max_length=300)
    relance_prevue: str | None = Field(default=None, max_length=10)


def _cand_out(c) -> dict:
    d = asdict(c)
    d.pop("owner_id")
    d["relance_due"] = c.relance_due(container.tracking.today())
    return d


@app.get("/api/candidatures")
def list_candidatures(owner: str = Depends(client_id)):
    return [_cand_out(c) for c in container.tracking.list(owner)]


@app.get("/api/candidatures/stats")
def candidatures_stats(owner: str = Depends(client_id)):
    return asdict(container.tracking.stats(owner))


@app.post("/api/candidatures")
def add_candidature(body: CandidatureIn, owner: str = Depends(client_id)):
    try:
        return _cand_out(container.tracking.add(owner, body.intitule, body.entreprise, body.lieu, body.url, body.statut))
    except UserFacingError as e:
        raise HTTPException(422, str(e))


@app.patch("/api/candidatures/{cand_id}")
def update_candidature(cand_id: str, body: CandidaturePatch, owner: str = Depends(client_id)):
    try:
        c = container.tracking.update(owner, cand_id, body.statut, body.notes, body.contact, body.relance_prevue)
    except NotFound:
        raise HTTPException(404, "Candidature introuvable")
    except ValueError:
        raise HTTPException(422, "Date de relance invalide (AAAA-MM-JJ)")
    return _cand_out(c)


@app.delete("/api/candidatures/{cand_id}")
def delete_candidature(cand_id: str, owner: str = Depends(client_id)):
    try:
        container.tracking.delete(owner, cand_id)
    except NotFound:
        raise HTTPException(404, "Candidature introuvable")
    return {"ok": True}


# ---------------- Swipe d'offres (mobile) ----------------

class PreferencesIn(BaseModel):
    contrats: list[str] = Field(default_factory=list, max_length=5)
    departements: list[str] = Field(default_factory=list, max_length=5)
    mots_cles: str = Field(default="", max_length=100)


class ReactionIn(BaseModel):
    offer_id: str = Field(min_length=1, max_length=64)
    type: TypeReaction


class RaisonIn(BaseModel):
    raison: Raison | None = None


class RappelIn(BaseModel):
    actif: bool


class BrouillonIn(BaseModel):
    reponses: list[AnswerIn] = Field(default_factory=list, max_length=10)


def _reaction_out(r) -> dict:
    d = asdict(r)
    d.pop("owner_id")
    d["rappel_du"] = r.rappel_du(container.swipe.today())
    return d


@app.get("/api/preferences")
def get_preferences(owner: str = Depends(client_id)):
    return asdict(container.swipe.preferences(owner))


@app.put("/api/preferences")
def put_preferences(body: PreferencesIn, owner: str = Depends(client_id)):
    try:
        return asdict(container.swipe.save_preferences(owner, body.contrats, body.departements, body.mots_cles))
    except ValueError as e:
        raise HTTPException(422, f"Préférences invalides : {e}")


@app.get("/api/swipe/pile")
def swipe_pile(taille: int = 20, owner: str = Depends(client_id)):
    """Les prochaines offres à swiper : préférences appliquées, offres déjà swipées retirées."""
    return [asdict(o) for o in container.swipe.pile(owner, max(1, min(taille, 50)))]


@app.post("/api/swipe/reactions")
def swipe_react(body: ReactionIn, owner: str = Depends(client_id)):
    try:
        return _reaction_out(container.swipe.reagir(owner, body.offer_id, body.type))
    except AccountRequired:
        raise HTTPException(401, "Crée ton compte pour postuler ou garder des favoris")
    except NotFound:
        raise HTTPException(404, "Offre introuvable")


@app.patch("/api/swipe/reactions/{offer_id}/raison")
def swipe_raison(offer_id: str, body: RaisonIn, owner: str = Depends(client_id)):
    try:
        return _reaction_out(container.swipe.donner_raison(owner, offer_id, body.raison))
    except NotFound:
        raise HTTPException(404, "Réaction introuvable")
    except UserFacingError as e:
        raise HTTPException(422, str(e))


@app.patch("/api/swipe/reactions/{offer_id}/rappel")
def swipe_rappel(offer_id: str, body: RappelIn, owner: str = Depends(client_id)):
    try:
        return _reaction_out(container.swipe.rappel(owner, offer_id, body.actif))
    except NotFound:
        raise HTTPException(404, "Favori introuvable")
    except UserFacingError as e:
        raise HTTPException(422, str(e))


@app.delete("/api/swipe/reactions/{offer_id}")
def swipe_undo(offer_id: str, owner: str = Depends(client_id)):
    """Annuler (gratuit) : l'offre revient dans la pile."""
    try:
        container.swipe.annuler(owner, offer_id)
    except NotFound:
        raise HTTPException(404, "Réaction introuvable")
    return {"ok": True}


@app.post("/api/swipe/reactions/{offer_id}/brouillon")
def swipe_brouillon(offer_id: str, body: BrouillonIn, owner: str = Depends(client_id)):
    try:
        c = container.swipe.brouillon(owner, offer_id, [Answer(a.question, a.reponse) for a in body.reponses])
    except NotFound:
        raise HTTPException(404, "Offre introuvable")
    except UserFacingError as e:
        raise HTTPException(422, str(e))
    return _cand_out(c)


@app.get("/api/swipe/passees")
def swipe_passees(owner: str = Depends(client_id)):
    """Offres passées des 30 derniers jours (masquées pour toujours, mais on peut les remettre)."""
    return [_reaction_out(r) for r in container.swipe.passees(owner)]


@app.get("/api/swipe/favoris")
def swipe_favoris(owner: str = Depends(client_id)):
    return [_reaction_out(r) for r in container.swipe.favoris(owner)]


def _quota_subject(request: Request) -> str:
    # Derrière un proxy (Cloudflare), utiliser l'en-tête CF-Connecting-IP en prod.
    return "ip:" + (request.client.host if request.client else "inconnu")
