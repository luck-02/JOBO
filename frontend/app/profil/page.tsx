"use client";
import { useEffect, useState } from "react";
import { api, type Experience, type Formation, type Profile } from "../../lib/api";

const EMPTY_EXP: Experience = { poste: "", entreprise: "", ville: "", debut: "", fin: "", type: "", missions: [], outils: [] };
const EMPTY_FORM: Formation = { diplome: "", ecole: "", debut: "", fin: "", details: "" };

// Listes saisies "une par ligne" ou "séparées par des virgules"
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const commas = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function ProfilPage() {
  const [p, setP] = useState<Profile | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => { api.profile().then(setP).catch((e) => setMsg(e.message)); }, []);
  if (!p) return <p className="muted">{msg || "Chargement…"}</p>;

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });
  const setExp = (i: number, patch: Partial<Experience>) =>
    set("experiences", p.experiences.map((e, j) => (j === i ? { ...e, ...patch } : e)));
  const setForm = (i: number, patch: Partial<Formation>) =>
    set("formations", p.formations.map((f, j) => (j === i ? { ...f, ...patch } : f)));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try { setP(await api.saveProfile(p!)); setMsg("Profil enregistré ✔"); }
    catch (err) { setMsg((err as Error).message); }
  }

  return (
    <form onSubmit={save}>
      <a href="/bienvenue" className="card onboarding-cta">
        <b>{p.a_un_cv ? "CV de base importé ✔" : "Importer mon CV de base"}</b>
        <span className="small">Importer un nouveau CV de base</span>
      </a>
      <section className="card">
        <h2>Moi</h2>
        <div className="row">
          <input placeholder="Prénom" value={p.prenom} onChange={(e) => set("prenom", e.target.value)} />
          <input placeholder="Nom" value={p.nom} onChange={(e) => set("nom", e.target.value)} />
        </div>
        <input type="email" placeholder="Email" value={p.email} onChange={(e) => set("email", e.target.value)} />
        <div className="row">
          <input placeholder="Téléphone" value={p.telephone} onChange={(e) => set("telephone", e.target.value)} />
          <input placeholder="Ville" value={p.ville} onChange={(e) => set("ville", e.target.value)} />
        </div>
        <input placeholder="LinkedIn (facultatif)" value={p.linkedin} onChange={(e) => set("linkedin", e.target.value)} />
        <input placeholder="Ce que je cherche (ex. alternance en business development)" value={p.recherche}
               onChange={(e) => set("recherche", e.target.value)} />
        <input placeholder="Disponibilité / rythme (ex. septembre, 1 sem. école / 3 sem. entreprise)"
               value={p.disponibilite} onChange={(e) => set("disponibilite", e.target.value)} />
      </section>

      <section className="card">
        <h2>Expériences</h2>
        {p.experiences.map((x, i) => (
          <fieldset key={i}>
            <div className="row">
              <input placeholder="Poste" value={x.poste} onChange={(e) => setExp(i, { poste: e.target.value })} />
              <input placeholder="Entreprise" value={x.entreprise} onChange={(e) => setExp(i, { entreprise: e.target.value })} />
            </div>
            <div className="row">
              <input placeholder="Type (Alternance, Stage…)" value={x.type} onChange={(e) => setExp(i, { type: e.target.value })} />
              <input placeholder="Ville" value={x.ville} onChange={(e) => setExp(i, { ville: e.target.value })} />
            </div>
            <div className="row">
              <input placeholder="Début (MM/AAAA)" value={x.debut} onChange={(e) => setExp(i, { debut: e.target.value })} />
              <input placeholder="Fin (vide = en cours)" value={x.fin} onChange={(e) => setExp(i, { fin: e.target.value })} />
            </div>
            <textarea placeholder="Missions et résultats, une par ligne (avec des chiffres si possible)"
                      defaultValue={x.missions.join("\n")} onBlur={(e) => setExp(i, { missions: lines(e.target.value) })} />
            <input placeholder="Outils, séparés par des virgules" defaultValue={x.outils.join(", ")}
                   onBlur={(e) => setExp(i, { outils: commas(e.target.value) })} />
            <button type="button" className="btn ghost"
                    onClick={() => set("experiences", p.experiences.filter((_, j) => j !== i))}>Supprimer</button>
          </fieldset>
        ))}
        <button type="button" className="btn" onClick={() => set("experiences", [...p.experiences, { ...EMPTY_EXP }])}>
          + Ajouter une expérience
        </button>
      </section>

      <section className="card">
        <h2>Formations</h2>
        {p.formations.map((f, i) => (
          <fieldset key={i}>
            <div className="row">
              <input placeholder="Diplôme" value={f.diplome} onChange={(e) => setForm(i, { diplome: e.target.value })} />
              <input placeholder="École" value={f.ecole} onChange={(e) => setForm(i, { ecole: e.target.value })} />
            </div>
            <div className="row">
              <input placeholder="Début" value={f.debut} onChange={(e) => setForm(i, { debut: e.target.value })} />
              <input placeholder="Fin" value={f.fin} onChange={(e) => setForm(i, { fin: e.target.value })} />
            </div>
            <input placeholder="Détails (facultatif)" value={f.details} onChange={(e) => setForm(i, { details: e.target.value })} />
            <button type="button" className="btn ghost"
                    onClick={() => set("formations", p.formations.filter((_, j) => j !== i))}>Supprimer</button>
          </fieldset>
        ))}
        <button type="button" className="btn" onClick={() => set("formations", [...p.formations, { ...EMPTY_FORM }])}>
          + Ajouter une formation
        </button>
      </section>

      <section className="card">
        <h2>Compétences et plus</h2>
        <label>Compétences<input defaultValue={p.competences.join(", ")} placeholder="Prospection, Excel, SQL…"
                                 onBlur={(e) => set("competences", commas(e.target.value))} /></label>
        <label>Qualités<input defaultValue={p.qualites.join(", ")} placeholder="bon relationnel, curieux…"
                              onBlur={(e) => set("qualites", commas(e.target.value))} /></label>
        <label>Langues<input defaultValue={p.langues.join(", ")} placeholder="Anglais B2, Espagnol A2"
                             onBlur={(e) => set("langues", commas(e.target.value))} /></label>
        <label>Centres d&apos;intérêt<input defaultValue={p.interets.join(", ")}
                                       onBlur={(e) => set("interets", commas(e.target.value))} /></label>
      </section>

      <button className="btn primary block">Enregistrer</button>
      {msg && <p className="muted center">{msg}</p>}
    </form>
  );
}
