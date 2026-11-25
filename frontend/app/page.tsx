"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import LinkImport from "../components/LinkImport";
import { api, CONTRAT_LABEL, type OfferSummary } from "../lib/api";

export default function Accueil() {
  const [q, setQ] = useState("");
  const [lieu, setLieu] = useState("");
  const [contrat, setContrat] = useState("alternance");
  const [offers, setOffers] = useState<OfferSummary[] | null>(null);
  const [error, setError] = useState("");
  const [onboarded, setOnboarded] = useState(true);

  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    setError("");
    try {
      setOffers(await api.search(q, lieu, contrat));
    } catch (err) {
      setError((err as Error).message);
      setOffers([]);
    }
  }

  useEffect(() => { api.profile().then((p) => setOnboarded(!!p.onboarded)).catch(() => {}); }, []);
  useEffect(() => { search(); }, [contrat]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {!onboarded && (
        <Link href="/bienvenue" className="card onboarding-cta">
          <b>Crée ton profil en 3 minutes</b>
          <span className="small">Importe ton CV de base : ensuite, un lien d&apos;offre suffit.</span>
        </Link>
      )}
      <LinkImport />
      <h2 className="section-title">Ou cherche parmi les offres</h2>
      <form className="card search" onSubmit={search}>
        <input placeholder="Poste, mot-clé (ex. commercial)" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="row">
          <input placeholder="Département (44)" inputMode="numeric" maxLength={3} value={lieu}
                 onChange={(e) => setLieu(e.target.value)} />
          <select value={contrat} onChange={(e) => setContrat(e.target.value)} aria-label="Type de contrat">
            <option value="alternance">Alternance</option>
            <option value="stage">Stage</option>
            <option value="cdi">CDI</option>
            <option value="cdd">CDD</option>
            <option value="tous">Tous</option>
          </select>
        </div>
        <button className="btn primary">Rechercher</button>
      </form>

      {error && <p className="error">{error}</p>}
      {offers === null && <p className="muted">Chargement…</p>}
      {offers?.length === 0 && !error && <p className="muted">Aucune offre trouvée.</p>}

      <ul className="list">
        {offers?.map((o) => (
          <li key={o.id}>
            <Link href={`/offres/${encodeURIComponent(o.id)}`} className="card offer">
              <div className="offer-title">{o.intitule}</div>
              <div className="muted">{o.entreprise}</div>
              <div className="meta">
                <span className="pill">{CONTRAT_LABEL[o.contrat] ?? o.contrat}</span>
                <span>{o.lieu}</span>
                {o.date_publication && <span>{new Date(o.date_publication).toLocaleDateString("fr-FR")}</span>}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
