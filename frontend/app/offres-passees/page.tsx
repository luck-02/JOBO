"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, CONTRAT_LABEL, RAISON_LABEL, type Reaction } from "../../lib/api";

// Offres passées (swipe à gauche) : masquées pour toujours, listées ici 30 jours. On peut les remettre dans la pile.
export default function OffresPassees() {
  const [items, setItems] = useState<Reaction[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.passees().then(setItems).catch((e) => { setError(e.message); setItems([]); }); }, []);

  async function remettre(id: string) {
    try { await api.undo(id); setItems((xs) => xs?.filter((x) => x.offer_id !== id) ?? null); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <>
      <Link href="/" className="btn ghost small">← Retour aux offres</Link>
      <h1>Offres passées</h1>
      <p className="small muted">Les offres que tu as passées ces 30 derniers jours. Elles ne reviennent plus dans ta pile,
        sauf si tu les remets.</p>
      {error && <p className="error">{error}</p>}
      {items === null && <p className="muted">Chargement…</p>}
      {items?.length === 0 && !error && <p className="muted">Aucune offre passée.</p>}
      <ul className="list">
        {items?.map((r) => (
          <li key={r.offer_id} className="card">
            <Link href={`/offres/${encodeURIComponent(r.offer_id)}`} className="offer-title">{r.intitule}</Link>
            <div className="muted small">{r.entreprise}</div>
            <div className="meta">
              <span className="pill">{CONTRAT_LABEL[r.contrat] ?? r.contrat}</span>
              <span>{r.lieu}</span>
              {r.raison && <span>Raison : {RAISON_LABEL[r.raison].toLowerCase()}</span>}
            </div>
            <button className="btn small" style={{ marginTop: 8 }} onClick={() => remettre(r.offer_id)}>Remettre dans la pile</button>
          </li>
        ))}
      </ul>
    </>
  );
}
