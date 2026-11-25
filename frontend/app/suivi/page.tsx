"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, API_URL, STATUT_LABEL, type Candidature, type CrmStats, type Statut } from "../../lib/api";

const STATUTS = Object.keys(STATUT_LABEL) as Statut[];
const FILTRES: { key: string; label: string; match: (c: Candidature) => boolean }[] = [
  { key: "tout", label: "Tout", match: () => true },
  { key: "relancer", label: "À relancer", match: (c) => c.relance_due },
  { key: "a_envoyer", label: "À envoyer", match: (c) => c.statut === "a_envoyer" },
  { key: "attente", label: "En attente", match: (c) => c.statut === "envoyee" || c.statut === "relancee" },
  { key: "entretien", label: "Entretiens", match: (c) => c.statut === "entretien" || c.statut === "offre" },
  { key: "fini", label: "Terminées", match: (c) => c.statut === "refus" || c.statut === "abandon" },
];
const fr = (iso: string) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString("fr-FR") : "");

export default function Suivi() {
  const [items, setItems] = useState<Candidature[] | null>(null);
  const [st, setSt] = useState<CrmStats | null>(null);
  const [filtre, setFiltre] = useState("tout");
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    try {
      const [l, s] = await Promise.all([api.candidatures(), api.crmStats()]);
      setItems(l); setSt(s);
    } catch (e) { setError((e as Error).message); setItems([]); }
  }
  useEffect(() => { refresh(); }, []);

  async function patch(id: string, p: Parameters<typeof api.updateCandidature>[1]) {
    setError("");
    try {
      const c = await api.updateCandidature(id, p);
      setItems((xs) => xs?.map((x) => (x.id === id ? c : x)) ?? null);
      api.crmStats().then(setSt).catch(() => {});
    } catch (e) { setError((e as Error).message); }
  }

  async function remove(id: string) {
    if (!window.confirm("Supprimer définitivement cette candidature ?")) return;
    await api.deleteCandidature(id).catch((e) => setError(e.message));
    refresh();
  }

  const visibles = items?.filter(FILTRES.find((f) => f.key === filtre)!.match) ?? [];

  return (
    <>
      {st && (
        <section className="card">
          <h2>Mon suivi</h2>
          <div className="summary four">
            <div><b>{st.total}</b><span>candidatures</span></div>
            <div><b>{st.envoyees}</b><span>envoyées</span></div>
            <div><b>{st.taux_reponse} %</b><span>réponses</span></div>
            <div><b>{st.taux_entretien} %</b><span>entretiens</span></div>
          </div>
          {st.relances_a_faire > 0 && (
            <button className="alert" onClick={() => setFiltre("relancer")}>
              🔔 {st.relances_a_faire} relance{st.relances_a_faire > 1 ? "s" : ""} à faire
            </button>
          )}
          <p className="small muted">{st.cette_semaine} candidature(s) ajoutée(s) ces 7 derniers jours.</p>
        </section>
      )}

      <div className="chips">
        {FILTRES.map((f) => (
          <button key={f.key} className={`chip ${filtre === f.key ? "on" : ""}`} onClick={() => setFiltre(f.key)}>
            {f.label}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {items === null && <p className="muted">Chargement…</p>}
      {items?.length === 0 && (
        <section className="card">
          <p className="muted">Aucune candidature pour l&apos;instant. Elles arrivent ici dès que tu génères un CV ou une
            lettre, ou ajoute-en une à la main.</p>
          <Link href="/" className="btn primary block">Coller un lien d&apos;offre</Link>
        </section>
      )}

      <ul className="list">
        {visibles.map((c) => (
          <li key={c.id} className="card cand">
            <div className="cand-head" onClick={() => setOpen(open === c.id ? null : c.id)}>
              <div>
                <div className="offer-title">{c.intitule}</div>
                <div className="muted small">{[c.entreprise, c.lieu].filter(Boolean).join(" · ")}</div>
              </div>
              <span className={`pill st-${c.statut}`}>{STATUT_LABEL[c.statut]}</span>
            </div>
            <div className="meta">
              <span>Ajoutée le {fr(c.date_creation)}</span>
              {c.date_envoi && <span>Envoyée le {fr(c.date_envoi)}</span>}
              {c.score_ats !== null && <span>ATS {c.score_ats}/100</span>}
              {c.relance_due && <span className="due">Relance à faire</span>}
              {!c.relance_due && c.relance_prevue && <span>Relance le {fr(c.relance_prevue)}</span>}
            </div>

            <div className="actions">
              {c.statut === "a_envoyer" && (
                <button className="btn primary" onClick={() => patch(c.id, { statut: "envoyee" })}>J&apos;ai postulé</button>
              )}
              {c.relance_due && (
                <button className="btn primary" onClick={() => patch(c.id, { statut: "relancee" })}>J&apos;ai relancé</button>
              )}
              {c.fichiers.cv && <a className="btn" href={API_URL + c.fichiers.cv} target="_blank">CV</a>}
              {c.fichiers.lettre && <a className="btn" href={API_URL + c.fichiers.lettre} target="_blank">Lettre</a>}
              {c.offer_id && <Link className="btn" href={`/offres/${encodeURIComponent(c.offer_id)}`}>Offre</Link>}
            </div>

            {open === c.id && (
              <div className="cand-detail">
                <label>Statut
                  <select value={c.statut} onChange={(e) => patch(c.id, { statut: e.target.value as Statut })}>
                    {STATUTS.map((s) => <option key={s} value={s}>{STATUT_LABEL[s]}</option>)}
                  </select>
                </label>
                <label>Contact (recruteur, manager…)
                  <input defaultValue={c.contact} maxLength={300} onBlur={(e) => e.target.value !== c.contact && patch(c.id, { contact: e.target.value })} />
                </label>
                <label>Date de relance
                  <input type="date" defaultValue={c.relance_prevue} onChange={(e) => patch(c.id, { relance_prevue: e.target.value })} />
                </label>
                <label>Notes
                  <textarea defaultValue={c.notes} maxLength={3000} placeholder="Questions d'entretien, ressenti, prochaine étape…"
                            onBlur={(e) => e.target.value !== c.notes && patch(c.id, { notes: e.target.value })} />
                </label>
                <div className="small muted">
                  Historique : {c.historique.map((h) => `${STATUT_LABEL[h.statut]} (${fr(h.date)})`).join(" → ")}
                </div>
                {c.url && <p className="small"><a href={c.url} target="_blank" rel="noopener noreferrer">Annonce d&apos;origine</a></p>}
                <button className="btn ghost small danger" onClick={() => remove(c.id)}>Supprimer cette candidature</button>
              </div>
            )}
            {open !== c.id && (
              <button className="btn ghost small" onClick={() => setOpen(c.id)}>Détails, notes et statut</button>
            )}
          </li>
        ))}
      </ul>

      {adding ? <AddForm onDone={() => { setAdding(false); refresh(); }} /> : (
        <button className="btn block" onClick={() => setAdding(true)}>+ Ajouter une candidature à la main</button>
      )}
    </>
  );
}

function AddForm({ onDone }: { onDone: () => void }) {
  const [f, setF] = useState({ intitule: "", entreprise: "", lieu: "", url: "", statut: "envoyee" as Statut });
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try { await api.addCandidature(f); onDone(); } catch (err) { setError((err as Error).message); }
  }
  return (
    <form className="card" onSubmit={submit}>
      <h2>Nouvelle candidature</h2>
      <input placeholder="Intitulé du poste" required value={f.intitule} onChange={(e) => setF({ ...f, intitule: e.target.value })} />
      <input placeholder="Entreprise" required value={f.entreprise} onChange={(e) => setF({ ...f, entreprise: e.target.value })} />
      <div className="row">
        <input placeholder="Ville" value={f.lieu} onChange={(e) => setF({ ...f, lieu: e.target.value })} />
        <select value={f.statut} onChange={(e) => setF({ ...f, statut: e.target.value as Statut })}>
          {STATUTS.map((s) => <option key={s} value={s}>{STATUT_LABEL[s]}</option>)}
        </select>
      </div>
      <input type="url" placeholder="Lien de l'annonce (facultatif)" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} />
      <div className="actions">
        <button className="btn primary">Ajouter</button>
        <button type="button" className="btn ghost" onClick={onDone}>Annuler</button>
      </div>
      {error && <p className="error small">{error}</p>}
    </form>
  );
}
