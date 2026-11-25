# Candidature (POC)

Appli qui trouve les offres de stage et d'alternance et prépare un CV et une lettre sur mesure pour chacune.

## Ce que fait le POC
- **Un lien, un CV (V1)** : on colle le lien d'une offre (ou son texte si le site bloque) et le CV se génère.
  Lecture sans IA des données schema.org publiées par la plupart des sites d'emploi, IA seulement en secours.
- **Inscription (V1)** : on importe son CV de base (PDF ou Word).
- **10 questions par offre (V1)** : après le lien, 10 questions propres à l'offre (réponses courtes, toutes
  facultatives) + un champ libre. Calculées sans IA : d'abord les mots-clés de l'offre absents du profil,
  puis motivation pour l'entreprise, situation concrète, chiffre, priorité, projet, disponibilité...
  L'IA utilise les réponses pour adapter le CV et la lettre.
- **Déroulé identique à la skill candidature-alternance** :
  1. analyse de l'offre : table des mots-clés en 3 niveaux (obligatoires, importants, bonus), couverture
     par le profil, score d'adéquation /10, points forts et écarts ;
  2. 10 questions, d'abord sur les mots-clés obligatoires non couverts ;
  3. CV puis auto-évaluation ATS /100 avec la grille de la skill (obligatoires /25, importants et bonus /10,
     intitulé /10, parsing /20, chiffres /10, pertinence /10, ton naturel /15), mesurée sur le texte du PDF ;
  4. si score < 90 ou obligatoires < 80 % : correction et nouvelle version, 3 maximum (`MAX_CV_ITERATIONS`),
     on garde la meilleure ; jamais d'invention pour gagner des points ;
  5. résumé : adéquation /10, ATS /100, couverture des obligatoires, points forts.
- **Accueil** : recherche d'offres (mots-clés, département, type de contrat), liste légère.
- **Détail d'une offre** : description, % de correspondance avec le profil, boutons *CV*, *Lettre*, *CV + lettre*,
  *Fiche entreprise*, et instructions libres pour l'IA.
- **Génération** : PDF compatibles ATS (une colonne, texte sélectionnable) et **score ATS calculé sans IA**.
- **Fiche entreprise** : données officielles de l'annuaire des entreprises (data.gouv), sans IA.
- **Profil** : identité, expériences, formations, compétences.
- **Quota** quotidien par IP (prépare les offres gratuit / inscrit / premium).
- **Suivi (CRM gratuit, sans IA)** : chaque offre pour laquelle on génère un CV ou une lettre s'ajoute
  automatiquement (fichiers, score ATS, adéquation) ; ajout manuel possible. Statuts : à envoyer, envoyée,
  relancée, entretien, offre, refus, abandon, avec historique. Relance proposée 7 jours après l'envoi puis
  après chaque relance, relances en retard mises en avant. Stats : total, envoyées, taux de réponse et
  d'entretien, candidatures de la semaine. Notes et contact par candidature.
- Onglet **Tips** : emplacement prévu.

## Lancer en local
```bash
cp .env.example .env
# Backend (première fois : crée l'environnement et installe les dépendances)
cd backend && uv venv --python 3.12 .venv && uv pip install -r requirements.txt
# Backend (à chaque fois)
cd backend && source .venv/bin/activate && uvicorn app.api.main:app --reload --env-file ../.env
# Front (autre terminal)
cd frontend && npm install && npm run dev
```
Ouvrir http://localhost:3000. Ou tout d'un coup : `docker compose up --build`.

Sur Mac, WeasyPrint (PDF) a besoin de `brew install pango` et de
`export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (à mettre dans `~/.zshrc`),
sinon le back plante au démarrage avec `cannot load library 'libgobject-2.0-0'`.

Sans clés, tout marche en **mode démo** (offres fictives, rédaction sans IA).

## Passer en mode réel
1. **France Travail** : créer une application sur francetravail.io, s'abonner à l'API *Offres d'emploi v2*,
   puis `OFFERS_PROVIDER=france_travail` + les deux identifiants.
2. **Anthropic** : créer une clé sur console.anthropic.com, puis `WRITER_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`.
   Modèle par défaut : Haiku (le moins cher), réglable avec `ANTHROPIC_MODEL`.
3. **PostgreSQL** (Supabase, Neon…) : changer seulement `DATABASE_URL`.

## Architecture (hexagonale)
```
backend/app/
  domain/        modèles, ports (interfaces), scoring ATS : aucune dépendance technique
  application/   cas d'usage (rechercher, générer, profil)
  adapters/      France Travail, démo, Anthropic, WeasyPrint, SQLAlchemy, annuaire, stockage, quotas
  api/           FastAPI (HTTP seulement)
  container.py   SEUL endroit qui choisit les adaptateurs
frontend/        Next.js (app router), mobile d'abord ; lib/api.ts = seul point de contact avec l'API
```
Changer une techno = écrire un adaptateur qui respecte le port, puis le brancher dans `container.py`.

## Sécurité déjà en place
- Clés d'API uniquement côté serveur (`.env`, jamais dans le front).
- L'IA ne peut pas inventer d'expérience : postes, entreprises et dates viennent toujours du profil.
- Instructions utilisateur isolées et limitées (1 500 caractères) ; validation des entrées ; anti-traversée de chemin.
- Quota quotidien ; conteneurs non-root ; en-têtes de sécurité côté front.
- Import par lien protégé contre le SSRF : adresses internes refusées, vérifiées à chaque redirection,
  taille et durée limitées. Reste à ajouter en prod : sortie réseau via un proxy dédié (rebinding DNS).
- Le texte d'une annonce ou d'un CV est traité comme une donnée, jamais comme une consigne pour l'IA.

## À faire avant la mise en ligne (V1)
- Comptes (Supabase Auth) à la place de l'identifiant anonyme du navigateur.
- Quotas dans Redis ou la BDD (aujourd'hui en mémoire) et IP réelle derrière Cloudflare.
- Stockage des PDF dans un bucket privé avec liens signés et suppression automatique (RGPD).
- Captcha invisible (Cloudflare Turnstile) pour les invités ; page de confidentialité.
- File d'attente pour les générations IA ; onglet Tips ; e-mails de relance générés par IA (premium).

## Tests
`cd backend && pytest`
