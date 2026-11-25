"""Les 10 questions suggérées à la création du compte. Réponses courtes acceptées, toutes facultatives."""

QUESTIONS: list[dict[str, str]] = [
    {"id": "poste", "question": "Quel poste ou type de missions vises-tu ?",
     "exemple": "Business developer, chef de projet IT..."},
    {"id": "secteurs", "question": "Dans quels secteurs ou types d'entreprises aimerais-tu travailler ?",
     "exemple": "ESN, banque, start-up, grand groupe..."},
    {"id": "lieu", "question": "Où peux-tu travailler ?", "exemple": "Nantes, mobile en Bretagne, télétravail partiel"},
    {"id": "dispo", "question": "Quand es-tu disponible, et à quel rythme ?",
     "exemple": "Septembre, 1 semaine école / 3 semaines entreprise"},
    {"id": "fierte", "question": "De quelle réalisation es-tu le plus fier ou la plus fière ? Un chiffre si possible.",
     "exemple": "J'ai contacté 50 prospects et obtenu 10 rendez-vous"},
    {"id": "forces", "question": "Quelles sont tes 3 compétences les plus solides ?", "exemple": "Prospection, Excel, animation de réunions"},
    {"id": "outils", "question": "Quels outils ou logiciels utilises-tu à l'aise ?", "exemple": "HubSpot, Excel (TCD), Canva, Python"},
    {"id": "entourage", "question": "Que disent de toi tes managers, profs ou collègues ?", "exemple": "Fiable, bon relationnel, apprend vite"},
    {"id": "motivation", "question": "Qu'est-ce qui te motive dans ce métier ?", "exemple": "Le contact client, résoudre des problèmes concrets"},
    {"id": "a_expliquer", "question": "Y a-t-il un point de ton parcours à expliquer ou à éviter ?",
     "exemple": "Réorientation après un BTS, année de césure..."},
]

QUESTION_IDS = {q["id"] for q in QUESTIONS}
