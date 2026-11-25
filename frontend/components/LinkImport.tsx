"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "../lib/api";

// V1 : l'action principale. On colle le lien d'une offre, le CV se génère.
export default function LinkImport() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [texte, setTexte] = useState("");
  const [modeTexte, setModeTexte] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const o = await api.importOffer(modeTexte ? "" : url, modeTexte ? texte : "");
      router.push(`/offres/${o.id}?depuis=lien`);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      if (msg.includes("colle le texte")) setModeTexte(true);
      setBusy(false);
    }
  }

  return (
    <form className="card link-import" onSubmit={submit}>
      <h2>Un lien, un CV</h2>
      {modeTexte ? (
        <textarea placeholder="Colle ici le texte complet de l'offre" value={texte}
                  onChange={(e) => setTexte(e.target.value)} required minLength={100} />
      ) : (
        <input type="url" inputMode="url" placeholder="Colle le lien de l'offre (Indeed, WTTJ, site carrière…)"
               value={url} onChange={(e) => setUrl(e.target.value)} required />
      )}
      <button className="btn primary block" disabled={busy}>{busy ? "Lecture de l'offre…" : "Créer mon CV"}</button>
      <button type="button" className="btn ghost small" onClick={() => { setModeTexte(!modeTexte); setError(""); }}>
        {modeTexte ? "J'ai plutôt un lien" : "Le lien ne marche pas ? Colle le texte"}
      </button>
      {error && <p className="error small">{error}</p>}
    </form>
  );
}
