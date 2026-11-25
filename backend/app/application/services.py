"""Cas d'usage. Ils orchestrent les ports, sans savoir quels adaptateurs sont branchés."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from ..domain import ats
from ..domain.models import (
    CompanyInfo,
    DocumentKind,
    GenerationResult,
    Offer,
    OfferQuery,
    OfferSummary,
    Profile,
)
from ..domain.errors import UserFacingError
from ..domain.questions import Answer, Question, analyse_with_answers, clean_answers, questions_for_offer
from ..domain.swipe import (
    Preferences, Raison, Reaction, TypeReaction, composer_pile, nettoyer_preferences, nouvelle_reaction,
    passees_visibles,
)
from ..domain.tracking import Candidature, Etape, Statut, Stats, changer_statut, stats
from ..domain.ports import (
    CandidatureRepository,
    CompanyInfoSource,
    CvParser,
    CvTextReader,
    DocumentWriter,
    FileStorage,
    ImportedOfferRepository,
    OfferExtractor,
    OfferLinkReader,
    OfferSource,
    PdfRenderer,
    PreferencesRepository,
    ProfileRepository,
    ReactionRepository,
    UsageLimiter,
)


class NotFound(Exception):
    pass


class ProfileIncomplete(Exception):
    pass


class QuotaExceeded(Exception):
    pass


class AccountRequired(Exception):
    """Les invités swipent librement ; postuler ou mettre en favori demande un compte."""


@dataclass
class OfferService:
    source: OfferSource
    imported: ImportedOfferRepository | None = None

    def search(self, query: OfferQuery) -> list[OfferSummary]:
        return self.source.search(query)

    def get(self, offer_id: str) -> Offer:
        if offer_id.startswith("imp-") and self.imported is not None:
            offer = self.imported.get(offer_id)
        else:
            offer = self.source.get(offer_id)
        if offer is None:
            raise NotFound(offer_id)
        return offer


@dataclass
class ProfileService:
    repo: ProfileRepository

    def get(self, owner_id: str) -> Profile:
        return self.repo.get(owner_id) or Profile(owner_id=owner_id)

    def save(self, profile: Profile) -> Profile:
        self.repo.save(profile)
        return profile


@dataclass
class ImportService:
    """V1 : l'utilisateur colle juste un lien (ou le texte) d'offre."""
    links: OfferLinkReader
    extractor: OfferExtractor
    repo: ImportedOfferRepository

    def import_offer(self, owner_id: str, url: str = "", texte: str = "") -> Offer:
        url, texte = url.strip(), texte.strip()
        if url:
            offer, raw = self.links.read(url)
            if offer is None:
                offer = self.extractor.extract(raw, url)
        elif len(texte) >= 100:
            offer = self.extractor.extract(texte[:20000])
        else:
            raise UserFacingError("Colle un lien ou le texte complet de l'offre")
        if not offer.intitule or len(offer.description) < 50:
            raise UserFacingError("Annonce incomplète : colle le texte de l'offre")
        offer.id = "imp-" + uuid.uuid4().hex[:12]
        offer.url = offer.url or url
        offer.entreprise = offer.entreprise or "Entreprise non précisée"
        self.repo.save(owner_id, offer)
        return offer


@dataclass
class OnboardingService:
    """Inscription : on importe le CV de base."""
    profiles: ProfileService
    reader: CvTextReader
    parser: CvParser

    def import_cv(self, owner_id: str, filename: str, data: bytes) -> Profile:
        text = self.reader.read(filename, data)
        parsed = self.parser.parse(text)
        p = self.profiles.get(owner_id)
        p.cv_base = text
        # On complète sans écraser ce que l'utilisateur a déjà saisi
        for k in ("prenom", "nom", "email", "telephone", "ville", "linkedin"):
            if not getattr(p, k) and getattr(parsed, k):
                setattr(p, k, getattr(parsed, k))
        for k in ("experiences", "formations", "competences", "qualites", "langues", "interets"):
            if not getattr(p, k) and getattr(parsed, k):
                setattr(p, k, getattr(parsed, k))
        return self.profiles.save(p)



@dataclass
class CompanyService:
    source: CompanyInfoSource

    def fiche(self, offer: Offer) -> CompanyInfo | None:
        if not offer.entreprise and not offer.siret:
            return None
        return self.source.find(offer.entreprise, offer.siret)


@dataclass
class TrackingService:
    """CRM : suivi des candidatures, relances, statistiques. Gratuit (aucune IA)."""
    repo: CandidatureRepository
    today: Callable[[], date] = field(default=date.today)

    def _mine(self, owner_id: str, cand_id: str) -> Candidature:
        c = self.repo.get(cand_id)
        if c is None or c.owner_id != owner_id:   # jamais la candidature de quelqu'un d'autre
            raise NotFound(cand_id)
        return c

    def list(self, owner_id: str) -> list[Candidature]:
        return self.repo.list(owner_id)

    def stats(self, owner_id: str) -> Stats:
        return stats(self.repo.list(owner_id), self.today())

    def add(self, owner_id: str, intitule: str, entreprise: str, lieu: str = "", url: str = "",
            statut: Statut = Statut.A_ENVOYER, offer_id: str = "") -> Candidature:
        if not intitule.strip() or not entreprise.strip():
            raise UserFacingError("Indique au moins l'intitulé et l'entreprise")
        t = self.today()
        depart = Statut.BROUILLON if statut == Statut.BROUILLON else Statut.A_ENVOYER
        c = Candidature(id="cand-" + uuid.uuid4().hex[:12], owner_id=owner_id, intitule=intitule.strip()[:200],
                        entreprise=entreprise.strip()[:200], lieu=lieu.strip()[:120], url=url.strip()[:2000],
                        offer_id=offer_id, statut=depart, date_creation=t.isoformat(),
                        historique=[Etape(t.isoformat(), depart)])
        changer_statut(c, statut, t)
        self.repo.save(c)
        return c

    def update(self, owner_id: str, cand_id: str, statut: Statut | None = None, notes: str | None = None,
               contact: str | None = None, relance_prevue: str | None = None) -> Candidature:
        c = self._mine(owner_id, cand_id)
        if statut is not None:
            changer_statut(c, statut, self.today())
        if notes is not None:
            c.notes = notes[:3000]
        if contact is not None:
            c.contact = contact[:300]
        if relance_prevue is not None:
            if relance_prevue:
                date.fromisoformat(relance_prevue)  # ValueError si invalide
            c.relance_prevue = relance_prevue
        self.repo.save(c)
        return c

    def delete(self, owner_id: str, cand_id: str) -> None:
        self.repo.delete(self._mine(owner_id, cand_id).id)

    def record_generation(self, owner_id: str, offer: Offer, result: GenerationResult) -> Candidature:
        """Après chaque génération : l'offre entre (ou est mise à jour) dans le suivi."""
        c = self.repo.find_by_offer(owner_id, offer.id) or self.add(
            owner_id, offer.intitule, offer.entreprise, offer.lieu, offer.url, offer_id=offer.id)
        if c.statut == Statut.BROUILLON:          # le brouillon du swipe devient une candidature prête à envoyer
            changer_statut(c, Statut.A_ENVOYER, self.today())
        for kind, name in result.files.items():
            c.fichiers[kind] = f"/api/files/{result.id}/{name}"
        if result.ats:
            c.score_ats = result.ats.score
        if result.analyse:
            c.adequation = result.analyse.score_adequation
        self.repo.save(c)
        return c


@dataclass
class GenerationService:
    offers: OfferService
    profiles: ProfileService
    companies: CompanyService
    writer: DocumentWriter
    renderer: PdfRenderer
    storage: FileStorage
    limiter: UsageLimiter
    daily_limit: int
    max_iterations: int = 3          # boucle de correction de la skill : 3 versions maximum
    tracking: TrackingService | None = None

    def analyse(self, owner_id: str, offer_id: str, answers: list[Answer] | None = None):
        """Étape 3 de la skill : table des mots-clés, adéquation /10, points forts, écarts.
        Avec les réponses aux questions, l'adéquation tient compte de ce que le candidat a déclaré."""
        return analyse_with_answers(self.profiles.get(owner_id), self.offers.get(offer_id), answers or [])

    def questions(self, owner_id: str, offer_id: str) -> list[Question]:
        """Les 10 questions propres à CETTE offre, sans IA."""
        return questions_for_offer(self.profiles.get(owner_id), self.offers.get(offer_id))

    def remaining(self, subject: str) -> int:
        return self.limiter.remaining(subject, self.daily_limit)

    def generate(self, owner_id: str, quota_subject: str, offer_id: str,
                 kinds: list[DocumentKind], instructions: str = "",
                 answers: list[Answer] | None = None) -> GenerationResult:
        profile = self.profiles.get(owner_id)
        if not profile.is_complete():
            raise ProfileIncomplete()
        offer = self.offers.get(offer_id)
        if not self.limiter.check_and_consume(quota_subject, self.daily_limit):
            raise QuotaExceeded()

        answers = clean_answers(answers or [])
        gen_id = uuid.uuid4().hex[:12]
        files: dict[str, str] = {}
        report = None
        iterations = 0
        slug = _slug(f"{offer.intitule}_{offer.entreprise}")
        nom = _slug(profile.nom_complet) or "candidat"

        if DocumentKind.CV in kinds:
            # Étapes 5 + 7 de la skill : rédiger, mesurer, corriger (3 versions max), garder la meilleure
            best_pdf, feedback = None, ""
            for iterations in range(1, self.max_iterations + 1):
                cv = self.writer.write_cv(profile, offer, instructions, answers, feedback)
                pdf = self.renderer.render_cv(profile, cv)
                facts = ats.CvFacts(cv.titre, cv.profil, [s.dates for s in cv.experiences],
                                    [s.missions for s in cv.experiences])
                rep = ats.ats_report(offer, self.renderer.extract_text(pdf), self.renderer.page_count(pdf), facts)
                if report is None or rep.score > report.score:
                    report, best_pdf = rep, pdf
                if rep.ok() or not getattr(self.writer, "supports_feedback", True):
                    break
                feedback = ats.feedback_for_rewrite(rep)
            name = f"CV_{nom}_{slug}.pdf"
            self.storage.put(f"{gen_id}/{name}", best_pdf)
            files["cv"] = name

        if DocumentKind.LETTRE in kinds:
            company = self.companies.fiche(offer)
            letter = self.writer.write_letter(profile, offer, company, instructions, answers)
            pdf = self.renderer.render_letter(profile, offer, letter)
            name = f"LM_{nom}_{slug}.pdf"
            self.storage.put(f"{gen_id}/{name}", pdf)
            files["lettre"] = name

        result = GenerationResult(id=gen_id, offer_id=offer.id, files=files, ats=report,
                                  analyse=analyse_with_answers(profile, offer, answers), iterations=iterations,
                                  seuils_atteints=bool(report and report.ok()))
        if self.tracking is not None:
            result.candidature_id = self.tracking.record_generation(owner_id, offer, result).id
        return result


@dataclass
class SwipeService:
    """Swipe d'offres mobile : pile filtrée par les préférences, réactions, annulation, listes."""
    offers: OfferService
    profiles: ProfileService
    tracking: TrackingService
    reactions: ReactionRepository
    prefs: PreferencesRepository
    today: Callable[[], date] = field(default=date.today)
    now: Callable[[], str] = field(default=lambda: __import__("datetime").datetime.now().isoformat())
    max_requetes: int = 6

    def preferences(self, owner_id: str) -> Preferences:
        p = self.prefs.get(owner_id)
        if p is not None:
            return p
        return Preferences()

    def save_preferences(self, owner_id: str, contrats: list[str], departements: list[str],
                         mots_cles: str) -> Preferences:
        p = nettoyer_preferences(contrats, departements, mots_cles)
        self.prefs.save(owner_id, p)
        return p

    def pile(self, owner_id: str, taille: int = 20) -> list[OfferSummary]:
        p = self.preferences(owner_id)
        contrats = list(p.contrats) or [None]
        lieux = list(p.departements) or [""]
        candidates: list[OfferSummary] = []
        for i, (c, l) in enumerate((c, l) for c in contrats for l in lieux):
            if i >= self.max_requetes:
                break
            candidates += self.offers.search(OfferQuery(mots_cles=p.mots_cles, lieu=l, contrat=c, taille=50))
        # Plusieurs contrats : on alterne pour ne pas montrer tous les CDI avant la première alternance
        candidates = _entrelacer(candidates, contrats)
        return composer_pile(candidates, self.reactions.list(owner_id), taille)

    def reagir(self, owner_id: str, offer_id: str, type_: TypeReaction) -> Reaction:
        if type_ in (TypeReaction.POSTULER, TypeReaction.FAVORI) and not self.profiles.get(owner_id).is_onboarded():
            raise AccountRequired()
        offer = self.offers.get(offer_id)
        r = nouvelle_reaction(owner_id, offer, type_, self.today(), self.now())
        self.reactions.save(r)
        return r

    def _mine(self, owner_id: str, offer_id: str) -> Reaction:
        r = self.reactions.get(owner_id, offer_id)
        if r is None:
            raise NotFound(offer_id)
        return r

    def donner_raison(self, owner_id: str, offer_id: str, raison: Raison | None) -> Reaction:
        r = self._mine(owner_id, offer_id)
        if r.type != TypeReaction.PASSER:
            raise UserFacingError("La raison ne concerne que les offres passées")
        r.raison = raison
        self.reactions.save(r)
        return r

    def annuler(self, owner_id: str, offer_id: str) -> None:
        """Annuler un swipe (gratuit) : l'offre revient dans la pile. Un brouillon sans fichier est retiré du suivi."""
        self._mine(owner_id, offer_id)
        self.reactions.delete(owner_id, offer_id)
        c = self.tracking.repo.find_by_offer(owner_id, offer_id)
        if c is not None and c.statut == Statut.BROUILLON and not c.fichiers:
            self.tracking.repo.delete(c.id)

    def brouillon(self, owner_id: str, offer_id: str, answers: list[Answer]) -> Candidature:
        """« Garder en brouillon » après un swipe à droite : entre dans le Suivi avec les réponses."""
        r = self._mine(owner_id, offer_id)
        if r.type != TypeReaction.POSTULER:
            raise UserFacingError("Swipe d'abord l'offre à droite")
        offer = self.offers.get(offer_id)
        c = self.tracking.repo.find_by_offer(owner_id, offer_id) or self.tracking.add(
            owner_id, offer.intitule, offer.entreprise, offer.lieu, offer.url, Statut.BROUILLON, offer.id)
        c.reponses = [{"question": a.question, "reponse": a.reponse} for a in clean_answers(answers)]
        self.tracking.repo.save(c)
        return c

    def passees(self, owner_id: str) -> list[Reaction]:
        return passees_visibles(self.reactions.list(owner_id), self.today())

    def favoris(self, owner_id: str) -> list[Reaction]:
        return [r for r in self.reactions.list(owner_id) if r.type == TypeReaction.FAVORI]

    def rappel(self, owner_id: str, offer_id: str, actif: bool) -> Reaction:
        """Le rappel du favori est unique : vu ou désactivé, il ne revient pas."""
        r = self._mine(owner_id, offer_id)
        if r.type != TypeReaction.FAVORI:
            raise UserFacingError("Seuls les favoris ont un rappel")
        r.rappel_actif = actif and bool(r.rappel_le)
        self.reactions.save(r)
        return r


def _entrelacer(offres: list[OfferSummary], contrats: list) -> list[OfferSummary]:
    if len(contrats) < 2:
        return offres
    groupes: dict[str, list[OfferSummary]] = {}
    for o in offres:
        groupes.setdefault(str(getattr(o.contrat, "value", o.contrat)), []).append(o)
    out: list[OfferSummary] = []
    files = list(groupes.values())
    while any(files):
        for f in files:
            if f:
                out.append(f.pop(0))
    return out


def _slug(text: str) -> str:
    import re

    text = ats.normalize(text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:60]
