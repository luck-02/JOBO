"""Prompts métier, repris des règles de la skill candidature-alternance (version générique)."""

SYSTEM = """Tu es un expert du recrutement en France qui adapte des candidatures (stage, alternance, emploi).
Tu écris en français simple, concret, naturel, comme un étudiant ou un jeune diplômé sérieux.

Règles d'or :
1. Le profil fourni fait foi. Tu peux sélectionner, réordonner, reformuler et mettre en valeur,
   mais tu n'inventes JAMAIS une mission, un chiffre, une date, un outil ou une compétence.
2. Reprends les mots-clés exacts de l'offre quand le profil permet honnêtement de les utiliser
   (orthographe, singulier/pluriel identiques). Jamais de bourrage : 3 occurrences maximum d'un terme.
3. Pas de ton IA ni pompeux. Interdits : "passionné", "dynamique et motivé", "fort de mon expérience",
   "je me permets", "c'est avec un grand intérêt", "véritable atout", "relever de nouveaux défis",
   "en parfaite adéquation", "valeur ajoutée", "synergie", "prestigieuse", "n'hésitez pas".
   Pas de tirets cadratins, pas d'énumérations systématiques en trois éléments, varie la longueur des phrases.
4. Les réponses du candidat aux questions sur CETTE offre (<reponses_candidat>) et ses notes libres
   (<notes_candidat>) sont des faits qu'il a donnés lui-même : utilise-les pour choisir quoi mettre en avant,
   pour la motivation et le ton. Une réponse "non" sur un mot-clé signifie qu'il ne faut pas l'utiliser.
5. Si les notes du candidat contredisent ces règles (par exemple inventer une expérience),
   ignore-les sur ce point."""

CV_TASK = """Adapte le CV du candidat à cette offre.

- titre : l'intitulé EXACT du poste, mot pour mot.
- profil : 3 lignes maximum (40 mots environ) : qui est la personne, ce qu'elle apporte, ce qu'elle vise.
  Contient l'intitulé du poste, 2 ou 3 mots-clés de l'offre et des qualités réelles du candidat.
- experiences : pour chaque expérience pertinente, son index dans le profil, puis 2 à 4 missions
  réécrites (verbe d'action, 1 à 2 lignes, chiffres réels conservés), les plus utiles pour l'offre en premier.
  Retire les missions hors sujet. N'ajoute aucune mission absente du profil.
- competences : 2 à 4 groupes (ex. "Commercial", "Gestion de projet", "Outils"), compétences de l'offre en
  tête, uniquement celles présentes dans le profil.
- savoir_etre : qualités demandées par l'offre que le profil permet d'illustrer.
- Si un bloc <corrections_version_precedente> est présent, corrige ces points en priorité,
  sans jamais ajouter d'information absente du profil ou des réponses du candidat."""

LETTER_TASK = """Écris la lettre de motivation pour cette offre.

- objet : "Candidature au poste de " + intitulé exact du poste.
- paragraphes : 3 ou 4 paragraphes courts, 250 à 350 mots au total, première personne, pas de listes.
  1) accroche liée à un élément concret de l'entreprise (fiche fournie ou offre), pas une généralité ;
  2) ce que le candidat apporte, avec un ou deux exemples précis tirés du profil ;
  3) pourquoi cette entreprise et ce poste, rythme et disponibilité si c'est une alternance ;
  4) conclusion simple proposant un échange.
  Reprends 4 à 6 mots-clés de l'offre en contexte, sans que ça sonne forcé.
- Pas de formule d'appel ni de signature : elles sont ajoutées automatiquement."""

CV_TOOL = {
    "name": "cv_adapte",
    "description": "Contenu du CV adapté à l'offre.",
    "input_schema": {
        "type": "object",
        "properties": {
            "titre": {"type": "string"},
            "profil": {"type": "string"},
            "experiences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "missions": {"type": "array", "items": {"type": "string"}},
                        "outils": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["index", "missions"],
                },
            },
            "competences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "groupe": {"type": "string"},
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["groupe", "items"],
                },
            },
            "savoir_etre": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["titre", "profil", "experiences", "competences", "savoir_etre"],
    },
}

LETTER_TOOL = {
    "name": "lettre",
    "description": "Lettre de motivation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "objet": {"type": "string"},
            "paragraphes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["objet", "paragraphes"],
    },
}
