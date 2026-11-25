// Client HTTP du front. Seul fichier qui connaît l'URL et le format de l'API.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Contrat = "alternance" | "stage" | "cdi" | "cdd" | "autre";

export interface OfferSummary {
  id: string; intitule: string; entreprise: string; lieu: string; contrat: Contrat; date_publication: string;
}
export interface Keyword { terme: string; niveau: "obligatoire" | "important" | "bonus"; occurrences: number; couverture: "oui" | "partiel" | "non" }
export interface Analysis { score_adequation: number; mots_cles: Keyword[]; points_forts: string[]; ecarts: string[] }
export interface Offer extends OfferSummary {
  description: string; competences: string[]; url: string; source: string;
  analyse: Analysis;
  profil_connu: boolean;   // profil déjà rempli : l'adéquation peut s'afficher avant les questions
  matching: { score: number; atouts: string[]; manques: string[] };
}
export interface Experience {
  poste: string; entreprise: string; ville: string; debut: string; fin: string; type: string;
  missions: string[]; outils: string[];
}
export interface Formation { diplome: string; ecole: string; debut: string; fin: string; details: string }
export interface Profile {
  prenom: string; nom: string; email: string; telephone: string; ville: string; linkedin: string;
  recherche: string; disponibilite: string; experiences: Experience[]; formations: Formation[];
  competences: string[]; qualites: string[]; langues: string[]; interets: string[];
  a_un_cv?: boolean; onboarded?: boolean;
}
export interface Question { id: string; question: string; exemple: string; options: string[]; multiple: boolean }
export interface AtsCheck { label: string; points: number; max_points: number; detail: string }
export interface Generation {
  id: string; files: Record<string, string>; urls: Record<string, string>;
  analyse: Analysis | null; iterations: number; seuils_atteints: boolean; candidature_id: string;
  ats: null | {
    score: number; couverture_obligatoires: number; couverture_mots_cles: number; mots_cles: Keyword[];
    mots_cles_trouves: string[]; mots_cles_manquants: string[];
    checks: AtsCheck[]; expressions_a_eviter: string[]; bourrage: string[];
  };
}
export type Statut = "brouillon" | "a_envoyer" | "envoyee" | "relancee" | "entretien" | "offre" | "refus" | "abandon";
export interface Candidature {
  id: string; intitule: string; entreprise: string; lieu: string; url: string; offer_id: string; statut: Statut;
  date_creation: string; date_envoi: string; relance_prevue: string; relance_due: boolean; contact: string; notes: string;
  fichiers: Record<string, string>; score_ats: number | null; adequation: number | null;
  historique: { date: string; statut: Statut }[];
  reponses: { question: string; reponse: string }[];
}
export interface CrmStats {
  total: number; par_statut: Record<Statut, number>; envoyees: number; taux_reponse: number; taux_entretien: number;
  relances_a_faire: number; cette_semaine: number;
}
export const STATUT_LABEL: Record<Statut, string> = {
  brouillon: "Brouillon", a_envoyer: "À envoyer", envoyee: "Envoyée", relancee: "Relancée", entretien: "Entretien",
  offre: "Offre reçue", refus: "Refus", abandon: "Abandon",
};

export interface Company {
  nom: string; siren: string; activite: string; date_creation: string; effectif: string; adresse: string;
  dirigeants: string[]; categorie: string; source: string;
}

export type TypeReaction = "postuler" | "passer" | "favori";
export type Raison = "metier" | "lieu" | "contrat" | "entreprise";
export const RAISON_LABEL: Record<Raison, string> = {
  metier: "Le métier", lieu: "Le lieu", contrat: "Le contrat", entreprise: "L'entreprise",
};
export interface Reaction {
  offer_id: string; type: TypeReaction; date: string; horodatage: string;
  intitule: string; entreprise: string; lieu: string; contrat: Contrat;
  raison: Raison | null; rappel_le: string; rappel_actif: boolean; rappel_du: boolean;
}
export interface Preferences { contrats: Contrat[]; departements: string[]; mots_cles: string }

/** Erreur HTTP avec son code (ex. 401 = compte requis). */
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

let memoryId: string | null = null;

// Identifiant anonyme du navigateur (POC). Remplacé par un vrai compte en V1.
export function clientId(): string {
  try {
    let id = localStorage.getItem("client_id");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("client_id", id);
    }
    return id;
  } catch {
    memoryId ??= crypto.randomUUID();
    return memoryId;
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), "X-Client-Id": clientId(), ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = `Erreur ${res.status}`;
    try { msg = (await res.json()).detail ?? msg; } catch {}
    throw new ApiError(typeof msg === "string" ? msg : "Requête invalide", res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  search: (q: string, lieu: string, contrat: string) =>
    call<OfferSummary[]>(`/api/offers?${new URLSearchParams({ q, lieu, contrat })}`),
  offer: (id: string) => call<Offer>(`/api/offers/${encodeURIComponent(id)}`),
  company: (id: string) => call<Company>(`/api/offers/${encodeURIComponent(id)}/company`),
  profile: () => call<Profile>("/api/profile"),
  saveProfile: (p: Profile) => call<Profile>("/api/profile", { method: "PUT", body: JSON.stringify(p) }),
  importOffer: (url: string, texte: string) =>
    call<{ id: string; intitule: string; entreprise: string }>("/api/offers/import", {
      method: "POST", body: JSON.stringify({ url, texte }),
    }),
  questions: (id: string, n = 10) => call<Question[]>(`/api/offers/${encodeURIComponent(id)}/questions?n=${n}`),
  analyse: (id: string, reponses: { question: string; reponse: string }[]) =>
    call<Analysis>(`/api/offers/${encodeURIComponent(id)}/analyse`, {
      method: "POST", body: JSON.stringify({ reponses }),
    }),
  uploadCv: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return call<{ experiences: number; formations: number; nom: string }>("/api/onboarding/cv", { method: "POST", body: fd });
  },
  candidatures: () => call<Candidature[]>("/api/candidatures"),
  crmStats: () => call<CrmStats>("/api/candidatures/stats"),
  addCandidature: (c: { intitule: string; entreprise: string; lieu?: string; url?: string; statut?: Statut }) =>
    call<Candidature>("/api/candidatures", { method: "POST", body: JSON.stringify(c) }),
  updateCandidature: (id: string, patch: Partial<Pick<Candidature, "statut" | "notes" | "contact" | "relance_prevue">>) =>
    call<Candidature>(`/api/candidatures/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteCandidature: (id: string) =>
    call<{ ok: boolean }>(`/api/candidatures/${encodeURIComponent(id)}`, { method: "DELETE" }),
  preferences: () => call<Preferences>("/api/preferences"),
  savePreferences: (p: Preferences) => call<Preferences>("/api/preferences", { method: "PUT", body: JSON.stringify(p) }),
  pile: () => call<OfferSummary[]>("/api/swipe/pile"),
  react: (offer_id: string, type: TypeReaction) =>
    call<Reaction>("/api/swipe/reactions", { method: "POST", body: JSON.stringify({ offer_id, type }) }),
  raison: (offer_id: string, raison: Raison | null) =>
    call<Reaction>(`/api/swipe/reactions/${encodeURIComponent(offer_id)}/raison`, { method: "PATCH", body: JSON.stringify({ raison }) }),
  rappel: (offer_id: string, actif: boolean) =>
    call<Reaction>(`/api/swipe/reactions/${encodeURIComponent(offer_id)}/rappel`, { method: "PATCH", body: JSON.stringify({ actif }) }),
  undo: (offer_id: string) =>
    call<{ ok: boolean }>(`/api/swipe/reactions/${encodeURIComponent(offer_id)}`, { method: "DELETE" }),
  brouillon: (offer_id: string, reponses: { question: string; reponse: string }[]) =>
    call<Candidature>(`/api/swipe/reactions/${encodeURIComponent(offer_id)}/brouillon`, { method: "POST", body: JSON.stringify({ reponses }) }),
  passees: () => call<Reaction[]>("/api/swipe/passees"),
  favoris: () => call<Reaction[]>("/api/swipe/favoris"),
  quota: () => call<{ restant: number; limite: number }>("/api/quota"),
  generate: (id: string, kinds: string[], instructions: string, reponses: { question: string; reponse: string }[]) =>
    call<Generation>(`/api/offers/${encodeURIComponent(id)}/generate`, {
      method: "POST", body: JSON.stringify({ kinds, instructions, reponses }),
    }),
};

export const CONTRAT_LABEL: Record<string, string> = {
  alternance: "Alternance", stage: "Stage", cdi: "CDI", cdd: "CDD", autre: "Autre",
};
