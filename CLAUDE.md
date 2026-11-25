# CLAUDE.md – Candidature

Appli (stage / alternance d'abord) : recherche d'offres, CV + lettre sur mesure, score ATS, fiche entreprise.
Produit freemium : invité (quota bas, pas d'image ni de questions IA), inscrit, premium. Cibles ensuite : écoles (B2B).

## Règles d'architecture (hexagonale, à respecter)
- `backend/app/domain` ne dépend de RIEN de technique (pas de FastAPI, SQLAlchemy, httpx, anthropic).
- Toute dépendance externe passe par un port (`domain/ports.py`) et un adaptateur (`adapters/`).
- Le choix des adaptateurs se fait uniquement dans `backend/app/container.py`, piloté par `.env`.
- L'API (`api/main.py`) ne contient pas de règle métier.
- Le front n'appelle l'API que via `frontend/lib/api.ts`.

## Parcours V1
- Inscription : CV de base uniquement (`/api/onboarding/cv`).
- Pour chaque offre : lien (`/api/offers/import`) -> 10 questions propres à l'offre (`domain/questions.py`,
  sans IA, `/api/offers/{id}/questions`) + champ libre -> génération (réponses envoyées dans `/generate`).

- Analyse (`domain/ats.py` : `keyword_table`, `analyse`) et grille ATS (`ats_report`) reprennent les étapes 3 et 7
  de la skill ; la boucle de correction (3 versions max) est dans `GenerationService.generate`.

- CRM : règles dans `domain/tracking.py` (statuts, relance J+7, stats), `TrackingService`, routes `/api/candidatures`.
  Toute lecture ou écriture vérifie que la candidature appartient bien au demandeur.

- Swipe mobile (Accueil sur mobile) : règles dans `domain/swipe.py` (réactions postuler / passer / favori, raison
  facultative qui affine la pile sans IA, offres passées listées 30 jours, rappel favori unique à J+7),
  `SwipeService`, routes `/api/swipe/*` et `/api/preferences`. Postuler ou favori exige un profil importé
  (`is_onboarded`, en attendant les vrais comptes). Statut `brouillon` dans le Suivi.

## Règles produit non négociables
- L'IA n'invente jamais une expérience, un chiffre, une date ou un outil. Postes, entreprises et dates
  sont recopiés depuis le profil par `adapters/llm/common.py`, jamais pris dans la réponse de l'IA.
- PDF compatibles ATS : une colonne, texte sélectionnable, sections standards, A4, une page pour le CV.
- Tout ce qui peut se calculer sans IA (mots-clés, scores, fiche entreprise) se calcule sans IA : coût minimal.
- Clés d'API uniquement côté serveur. Données personnelles minimales (RGPD).

## Commandes
- Tests backend : `cd backend && pytest -q`
- API : `cd backend && uvicorn app.api.main:app --reload --env-file ../.env`
- Front : `cd frontend && npm run dev` ; build : `npm run build`
- Tout : `docker compose up --build`

## Conventions
- Python 3.12, dataclasses dans le domaine, typage partout.
- Textes de l'interface en français, tutoiement.
- Chaque nouvel adaptateur arrive avec un test (voir `tests/test_app.py`, ex. `httpx.MockTransport`).
