"""Offres de démonstration (entreprises fictives) pour tester sans clé France Travail."""
from __future__ import annotations

from ...domain.ats import normalize
from ...domain.models import ContractType, Offer, OfferQuery, OfferSummary

_OFFERS = [
    Offer(
        id="demo-1", intitule="Alternance Business Developer IT", entreprise="Atlantique Numérique (démo)",
        lieu="44 - Nantes", contrat=ContractType.ALTERNANCE, date_publication="2026-10-28",
        description=(
            "Rattaché(e) au directeur commercial, vous participez au développement commercial de notre ESN.\n"
            "Missions : prospection B2B (téléphone, emailing, LinkedIn Sales Navigator), qualification des "
            "besoins clients, préparation des propositions commerciales et des réponses aux appels d'offres, "
            "suivi du pipeline dans le CRM HubSpot, participation aux rendez-vous clients.\n"
            "Profil : école de commerce ou d'ingénieur, rythme alternance, bon relationnel, anglais apprécié. "
            "Une première expérience en prospection est un plus."
        ),
        competences=["Prospection commerciale", "CRM", "Négociation"], source="démo",
    ),
    Offer(
        id="demo-2", intitule="Alternance Chef de Projet IT", entreprise="Loire Assurances (démo)",
        lieu="44 - Nantes", contrat=ContractType.ALTERNANCE, date_publication="2026-10-30",
        description=(
            "Au sein de la DSI, vous accompagnez les chefs de projet sur le pilotage de projets applicatifs.\n"
            "Missions : suivi du planning et du budget, animation des comités, rédaction des cahiers des charges, "
            "coordination de la recette avec les équipes métiers, reporting KPI, conduite du changement.\n"
            "Environnement : Agile Scrum, Jira, Confluence, Excel. Profil : Bac+4/5, rigueur, aisance à l'oral."
        ),
        competences=["Gestion de projet", "Agile", "Recette"], source="démo",
    ),
    Offer(
        id="demo-3", intitule="Stage Assistant Marketing Digital", entreprise="Studio Erdre (démo)",
        lieu="44 - Nantes", contrat=ContractType.STAGE, date_publication="2026-10-25",
        description=(
            "Stage de 6 mois. Missions : animation des réseaux sociaux, création de contenus sur Canva, "
            "suivi des KPI des campagnes, SEO, newsletters, organisation d'événementiel.\n"
            "Profil : créatif, à l'aise avec les outils digitaux, Google Workspace."
        ),
        competences=["Marketing digital", "Réseaux sociaux"], source="démo",
    ),
    Offer(
        id="demo-4", intitule="Alternance Analyste Data", entreprise="Vilaine Data (démo)",
        lieu="35 - Rennes", contrat=ContractType.ALTERNANCE, date_publication="2026-10-29",
        description=(
            "Vous rejoignez l'équipe data pour construire des tableaux de bord Power BI, écrire des requêtes SQL, "
            "automatiser des traitements en Python et présenter les analyses aux équipes métiers. "
            "Connaissances en Excel avancé (TCD, VBA) appréciées."
        ),
        competences=["SQL", "Python", "Power BI"], source="démo",
    ),
    Offer(
        id="demo-5", intitule="Alternance Chargé de Recrutement", entreprise="Talents de l'Ouest (démo)",
        lieu="75 - Paris", contrat=ContractType.ALTERNANCE, date_publication="2026-10-27",
        description=(
            "Missions : rédaction et diffusion des annonces, sourcing, préqualification téléphonique, "
            "organisation des entretiens, suivi des candidats dans l'ATS, relation avec les managers. "
            "Profil : école RH ou commerce, excellent relationnel, Pack Office."
        ),
        competences=["Recrutement", "Ressources humaines"], source="démo",
    ),
    Offer(
        id="demo-6", intitule="CDI Ingénieur d'Affaires", entreprise="Atlantique Numérique (démo)",
        lieu="44 - Nantes", contrat=ContractType.CDI, date_publication="2026-10-20",
        description=(
            "Vous développez un portefeuille de grands comptes : prospection, négociation, closing, "
            "account management et suivi du pipeline dans Salesforce. Anglais professionnel."
        ),
        competences=["Négociation", "Account management"], source="démo",
    ),
]

_BY_ID = {o.id: o for o in _OFFERS}


class DemoOfferSource:
    def search(self, query: OfferQuery) -> list[OfferSummary]:
        res = []
        words = [w for w in normalize(query.mots_cles).split() if w]
        for o in _OFFERS:
            if query.contrat and o.contrat != query.contrat:
                continue
            if query.lieu and not o.lieu.startswith(query.lieu):
                continue
            hay = normalize(f"{o.intitule} {o.description} {o.entreprise}")
            if words and not all(w in hay for w in words):
                continue
            res.append(OfferSummary(o.id, o.intitule, o.entreprise, o.lieu, o.contrat, o.date_publication))
        start = query.page * query.taille
        return res[start:start + query.taille]

    def get(self, offer_id: str) -> Offer | None:
        return _BY_ID.get(offer_id)
