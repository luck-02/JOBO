"""Câblage : le SEUL endroit qui choisit les adaptateurs. Changer de techno = changer ici."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .application.services import (
    CompanyService, GenerationService, ImportService, OfferService, OnboardingService, ProfileService,
    TrackingService,
)
from .config import Settings


@dataclass
class Container:
    offers: OfferService
    profiles: ProfileService
    companies: CompanyService
    generation: GenerationService
    imports: ImportService
    onboarding: OnboardingService
    tracking: TrackingService
    storage: object


def build(settings: Settings) -> Container:
    if settings.offers_provider == "france_travail":
        from .adapters.offers.france_travail import FranceTravailOfferSource
        offer_source = FranceTravailOfferSource(settings.france_travail_client_id,
                                                settings.france_travail_client_secret)
    else:
        from .adapters.offers.demo import DemoOfferSource
        offer_source = DemoOfferSource()

    if settings.writer_provider == "anthropic":
        from .adapters.llm.anthropic_extractors import AnthropicCvParser, AnthropicOfferExtractor
        from .adapters.llm.anthropic_writer import AnthropicWriter
        writer = AnthropicWriter(settings.anthropic_api_key, settings.anthropic_model)
        extractor = AnthropicOfferExtractor(settings.anthropic_api_key, settings.anthropic_model)
        cv_parser = AnthropicCvParser(settings.anthropic_api_key, settings.anthropic_model)
    else:
        from .adapters.cv.reader import DemoCvParser
        from .adapters.llm.demo_writer import DemoWriter
        from .adapters.offers.extract import HeuristicOfferExtractor
        writer = DemoWriter()
        extractor = HeuristicOfferExtractor()
        cv_parser = DemoCvParser()

    from .adapters.company.annuaire import AnnuaireEntreprisesSource, DemoCompanySource
    company_source = AnnuaireEntreprisesSource() if settings.company_provider == "annuaire" else DemoCompanySource()

    from .adapters.cv.reader import PdfDocxCvReader
    from .adapters.db.sqlalchemy_repo import SqlCandidatureRepository, SqlImportedOfferRepository, SqlProfileRepository
    from .adapters.web.fetcher import SafePageFetcher, WebOfferLinkReader
    from .adapters.infra import InMemoryDailyLimiter, LocalFileStorage
    from .adapters.pdf.weasyprint_renderer import WeasyPrintRenderer

    if settings.database_url.startswith("sqlite:///./"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    imported = SqlImportedOfferRepository(settings.database_url)
    offers = OfferService(offer_source, imported)
    profiles = ProfileService(SqlProfileRepository(settings.database_url))
    ft = offer_source if settings.offers_provider == "france_travail" else None
    imports = ImportService(WebOfferLinkReader(SafePageFetcher(), ft), extractor, imported)
    onboarding = OnboardingService(profiles, PdfDocxCvReader(), cv_parser)
    companies = CompanyService(company_source)
    storage = LocalFileStorage(settings.storage_dir)
    tracking = TrackingService(SqlCandidatureRepository(settings.database_url))
    generation = GenerationService(
        offers=offers, profiles=profiles, companies=companies, writer=writer,
        renderer=WeasyPrintRenderer(settings.cv_accent_color), storage=storage,
        limiter=InMemoryDailyLimiter(), daily_limit=settings.daily_generation_limit,
        max_iterations=settings.max_cv_iterations, tracking=tracking,
    )
    return Container(offers, profiles, companies, generation, imports, onboarding, tracking, storage)
