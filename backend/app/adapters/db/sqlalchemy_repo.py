"""Stockage des profils via SQLAlchemy : SQLite en local, PostgreSQL (Supabase, Neon...) en prod,
en changeant seulement DATABASE_URL."""
from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy import JSON, Column, DateTime, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base

from ...domain.models import ContractType, Experience, Formation, Offer, Profile
from ...domain.tracking import Candidature, Etape, Statut

Base = declarative_base()


class ProfileRow(Base):
    __tablename__ = "profiles"
    owner_id = Column(String(64), primary_key=True)
    data = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def profile_from_dict(d: dict) -> Profile:
    d = dict(d)
    d["experiences"] = [Experience(**e) for e in d.get("experiences", [])]
    d["formations"] = [Formation(**f) for f in d.get("formations", [])]
    return Profile(**d)


class SqlProfileRepository:
    def __init__(self, url: str):
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self._engine = create_engine(url, **kwargs)
        Base.metadata.create_all(self._engine)

    def get(self, owner_id: str) -> Profile | None:
        with Session(self._engine) as s:
            row = s.get(ProfileRow, owner_id)
            if not row:
                return None
            data = row.data if isinstance(row.data, dict) else json.loads(row.data)
            return profile_from_dict(data)

    def save(self, profile: Profile) -> None:
        with Session(self._engine) as s:
            row = s.get(ProfileRow, profile.owner_id)
            if row:
                row.data = asdict(profile)
            else:
                s.add(ProfileRow(owner_id=profile.owner_id, data=asdict(profile)))
            s.commit()


class ImportedOfferRow(Base):
    __tablename__ = "imported_offers"
    id = Column(String(40), primary_key=True)
    owner_id = Column(String(64), index=True, nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class SqlImportedOfferRepository:
    def __init__(self, url: str):
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self._engine = create_engine(url, **kwargs)
        Base.metadata.create_all(self._engine)

    def save(self, owner_id: str, offer: Offer) -> None:
        with Session(self._engine) as s:
            s.merge(ImportedOfferRow(id=offer.id, owner_id=owner_id, data=asdict(offer)))
            s.commit()

    def get(self, offer_id: str) -> Offer | None:
        with Session(self._engine) as s:
            row = s.get(ImportedOfferRow, offer_id)
            if not row:
                return None
            d = dict(row.data)
            d["contrat"] = ContractType(d["contrat"])
            return Offer(**d)


class CandidatureRow(Base):
    __tablename__ = "candidatures"
    id = Column(String(40), primary_key=True)
    owner_id = Column(String(64), index=True, nullable=False)
    offer_id = Column(String(64), index=True, default="")
    data = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def _cand_from_dict(d: dict) -> Candidature:
    d = dict(d)
    d["statut"] = Statut(d["statut"])
    d["historique"] = [Etape(e["date"], Statut(e["statut"])) for e in d.get("historique", [])]
    return Candidature(**d)


class SqlCandidatureRepository:
    def __init__(self, url: str):
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self._engine = create_engine(url, **kwargs)
        Base.metadata.create_all(self._engine)

    def save(self, c: Candidature) -> None:
        with Session(self._engine) as s:
            s.merge(CandidatureRow(id=c.id, owner_id=c.owner_id, offer_id=c.offer_id, data=asdict(c)))
            s.commit()

    def get(self, cand_id: str) -> Candidature | None:
        with Session(self._engine) as s:
            row = s.get(CandidatureRow, cand_id)
            return _cand_from_dict(row.data) if row else None

    def list(self, owner_id: str) -> list[Candidature]:
        with Session(self._engine) as s:
            rows = s.query(CandidatureRow).filter_by(owner_id=owner_id).all()
            return sorted((_cand_from_dict(r.data) for r in rows), key=lambda c: c.date_creation, reverse=True)

    def find_by_offer(self, owner_id: str, offer_id: str) -> Candidature | None:
        with Session(self._engine) as s:
            row = s.query(CandidatureRow).filter_by(owner_id=owner_id, offer_id=offer_id).first()
            return _cand_from_dict(row.data) if row else None

    def delete(self, cand_id: str) -> None:
        with Session(self._engine) as s:
            row = s.get(CandidatureRow, cand_id)
            if row:
                s.delete(row)
                s.commit()
