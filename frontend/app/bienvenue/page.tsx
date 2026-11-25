"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

// Inscription : on importe juste le CV de base. Les 10 questions viennent ensuite, à chaque offre.
export default function Bienvenue() {
  const [cvInfo, setCvInfo] = useState("");
  const [done, setDone] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.profile().then((p) => {
      if (p.a_un_cv) { setCvInfo("CV de base déjà importé ✔ Tu peux en importer un nouveau."); setDone(true); }
    }).catch(() => {});
  }, []);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const r = await api.uploadCv(file);
      setCvInfo(`CV lu ✔ ${r.nom ? r.nom + " · " : ""}${r.experiences} expérience(s), ${r.formations} formation(s).`);
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <>
      <section className="card">
        <h1>Bienvenue 👋</h1>
        <p className="muted">
          Importe ton CV de base. Ensuite, pour chaque offre, tu colles le lien et tu réponds à 10 questions
          rapides : ton CV est adapté à l&apos;offre.
        </p>
      </section>

      <section className="card">
        <h2>Ton CV de base</h2>
        <label className="file">
          <input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                 onChange={onFile} disabled={uploading} />
          {uploading ? "Lecture du CV…" : "Choisir mon CV (PDF ou Word)"}
        </label>
        {cvInfo && <p className="small ok">{cvInfo}</p>}
        {error && <p className="error small">{error}</p>}
      </section>

      {done && (
        <>
          <Link href="/profil" className="btn block">Vérifier mon profil</Link>
          <p />
          <Link href="/" className="btn primary block">Coller mon premier lien d&apos;offre</Link>
        </>
      )}
    </>
  );
}
