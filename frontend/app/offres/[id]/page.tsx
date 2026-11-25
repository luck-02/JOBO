"use client";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import {
  api, API_URL, CONTRAT_LABEL, type Analysis, type Company, type Generation, type Keyword, type Offer, type Question,
} from "../../../lib/api";
import QuestionBox, { toText, VIDE, type Choice } from "../../../components/QuestionBox";

const ACTIONS: { label: string; kinds: string[] }[] = [
  { label: "Créer mon CV", kinds: ["cv"] },
  { label: "Ma lettre", kinds: ["lettre"] },
  { label: "CV + lettre", kinds: ["cv", "lettre"] },
];

// Brouillon des réponses par offre (pratique si on quitte la page). Stockage local, best effort.
function loadDraft(id: string): { choix: Record<string, Choice>; libre: string } {
  try {
    const d = JSON.parse(localStorage.getItem(`draft:${id}`) ?? "");
    // anciens brouillons : réponses en texte brut
    const old: Record<string, string> = d.reponses ?? {};
    const choix = d.choix ?? Object.fromEntries(
      Object.entries(old).map(([k, v]) => [k, { sel: [], autre: true, texte: v }]));
    return { choix, libre: d.libre ?? "" };
  } catch { return { choix: {}, libre: "" }; }
}
function saveDraft(id: string, choix: Record<string, Choice>, libre: string) {
  try { localStorage.setItem(`draft:${id}`, JSON.stringify({ choix, libre })); } catch {}
}

export default function Page() {
  return <Suspense fallback={<p className="muted">Chargement…</p>}><OffreDetail /></Suspense>;
}

function OffreDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const depuisLien = useSearchParams().get("depuis") === "lien";
  const questionsRef = useRef<HTMLElement>(null);
  const resultRef = useRef<HTMLElement>(null);

  const [offer, setOffer] = useState<Offer | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [choix, setChoix] = useState<Record<string, Choice>>({});
  const [etape, setEtape] = useState(0);
  const [libre, setLibre] = useState("");
  const [company, setCompany] = useState<Company | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Generation | null>(null);
  const [quota, setQuota] = useState<{ restant: number; limite: number } | null>(null);
  const [error, setError] = useState("");
  const [analyse, setAnalyse] = useState<Analysis | null>(null);   // adéquation recalculée avec les réponses

  useEffect(() => {
    api.offer(id).then(setOffer).catch((e) => setError(e.message));
    api.questions(id).then(setQuestions).catch(() => {});
    api.quota().then(setQuota).catch(() => {});
    const d = loadDraft(id);
    setChoix(d.choix);
    setLibre(d.libre);
  }, [id]);

  useEffect(() => {
    if (depuisLien && questions.length) questionsRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [depuisLien, questions.length]);

  // Adéquation recalculée (sans IA) quand les réponses changent, avec un petit délai pendant la frappe.
  useEffect(() => {
    const reponses = payload();
    if (!reponses.length) { setAnalyse(null); return; }
    const t = setTimeout(() => { api.analyse(id, reponses).then(setAnalyse).catch(() => {}); }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, choix, questions]);

  useEffect(() => { if (result) resultRef.current?.scrollIntoView({ behavior: "smooth" }); }, [result]);

  function answer(qid: string, value: Choice) {
    const next = { ...choix, [qid]: value };
    setChoix(next);
    saveDraft(id, next, libre);
  }

  function payload() {
    return questions
      .filter((q) => toText(choix[q.id]))
      .map((q) => ({ question: q.question, reponse: toText(choix[q.id]) }));
  }

  async function generate(kinds: string[]) {
    setBusy(true); setError(""); setResult(null);
    try {
      setResult(await api.generate(id, kinds, libre, payload()));
      api.quota().then(setQuota).catch(() => {});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function fiche() {
    setError("");
    try { setCompany(await api.company(id)); } catch (e) { setError((e as Error).message); }
  }

  if (!offer) return error ? <p className="error">{error}</p> : <p className="muted">Chargement…</p>;
  const answered = questions.filter((q) => toText(choix[q.id])).length;
  const q = questions[etape];
  const a = analyse ?? offer.analyse;
  // Profil connu : l'adéquation a du sens tout de suite. Sinon elle vient après les questions.
  const carteAdequation = (
    <AnalysisCard a={a} base={offer.analyse.score_adequation} apres={!offer.profil_connu} />
  );

  return (
    <>
      <button className="btn ghost" onClick={() => router.back()}>← Retour</button>

      <section className="card">
        <h1>{offer.intitule}</h1>
        <p className="muted">{[offer.entreprise, offer.lieu].filter(Boolean).join(" · ")}</p>
        <div className="meta"><span className="pill">{CONTRAT_LABEL[offer.contrat]}</span>
          {offer.url && <a href={offer.url} target="_blank" rel="noopener noreferrer">Voir l&apos;annonce d&apos;origine</a>}
        </div>
        <Description texte={offer.description} motsCles={a.mots_cles} />
      </section>

      {offer.profil_connu && carteAdequation}

      <section className="card" ref={questionsRef}>
        <h2>{questions.length} questions pour adapter ton CV</h2>
        <p className="small muted">
          Clique sur une réponse ou écris la tienne dans « Autre ». Tu peux en passer.
          {questions.length > 0 && ` ${answered}/${questions.length} répondues.`}
        </p>
        {q && (
          <QuestionBox key={q.id} q={q} num={etape + 1} total={questions.length}
                       value={choix[q.id] ?? VIDE} onChange={(v) => answer(q.id, v)} />
        )}
        {questions.length > 0 && (
          <div className="q-nav">
            <button className="btn ghost small" disabled={etape === 0} onClick={() => setEtape(etape - 1)}>
              ← Précédente
            </button>
            <div className="dots">
              {questions.map((x, i) => (
                <button key={x.id} aria-label={`Question ${i + 1}`} onClick={() => setEtape(i)}
                        className={`dot${i === etape ? " cur" : ""}${toText(choix[x.id]) ? " done" : ""}`} />
              ))}
            </div>
            {etape < questions.length - 1
              ? <button className="btn small" onClick={() => setEtape(etape + 1)}>
                  {q && toText(choix[q.id]) ? "Suivante →" : "Passer →"}
                </button>
              : <span className="small muted">Fini ✔</span>}
          </div>
        )}
        <div className="q">
          <label htmlFor="libre">Libre (facultatif)</label>
          <textarea id="libre" maxLength={1500} value={libre}
                    placeholder="Tout ce que tu veux ajouter pour cette offre : un projet, un angle, un ton…"
                    onChange={(e) => { setLibre(e.target.value); saveDraft(id, choix, e.target.value); }} />
        </div>
      </section>

      {!offer.profil_connu && carteAdequation}

      <section className="card">
        <h2>Générer</h2>
        <div className="actions">
          {ACTIONS.map((act) => (
            <button key={act.label} className="btn primary" disabled={busy} onClick={() => generate(act.kinds)}>
              {act.label}
            </button>
          ))}
          <button className="btn" onClick={fiche}>Fiche entreprise</button>
        </div>
        {quota && <p className="small muted">Générations restantes aujourd&apos;hui : {quota.restant}/{quota.limite}</p>}
        {busy && <p className="muted">Génération en cours…</p>}
        {error && (
          <p className="error">{error} {error.includes("profil") && <Link href="/profil">Compléter mon profil</Link>}</p>
        )}
      </section>

      {result && (
        <section className="card" ref={resultRef}>
          <h2>Ta candidature</h2>
          {result.ats && result.analyse && (
            <div className="summary">
              <div><b>{result.analyse.score_adequation}/10</b><span>adéquation</span></div>
              <div><b>{result.ats.score}/100</b><span>score ATS</span></div>
              <div><b>{result.ats.couverture_obligatoires} %</b><span>obligatoires couverts</span></div>
            </div>
          )}
          {result.ats && (
            <p className={"small " + (result.seuils_atteints ? "ok" : "muted")}>
              {result.seuils_atteints
                ? `Seuils atteints (90/100 et 80 % des obligatoires) en ${result.iterations} version(s).`
                : `Meilleure version gardée après ${result.iterations} essai(s). Ce qui manque ne peut pas être ajouté sans inventer : réponds aux questions sur ces mots-clés ou compense dans la lettre.`}
            </p>
          )}
          {result.candidature_id && (
            <p className="small ok">Ajoutée à ton <Link href="/suivi">suivi de candidatures</Link> ✔</p>
          )}
          {result.analyse && result.analyse.points_forts.length > 0 && (
            <p className="small"><b>Points forts :</b> {result.analyse.points_forts.slice(0, 3).join(", ")}</p>
          )}
          <div className="actions">
            {result.urls.cv && <a className="btn primary" href={API_URL + result.urls.cv} target="_blank">Ouvrir le CV (PDF)</a>}
            {result.urls.lettre && <a className="btn primary" href={API_URL + result.urls.lettre} target="_blank">Ouvrir la lettre (PDF)</a>}
          </div>
          {result.ats && (
            <>
              <h3>Grille ATS (estimation)</h3>
              <ul className="checks">
                {result.ats.checks.map((c) => (
                  <li key={c.label}>
                    <span>{c.label}</span>
                    <b>{c.points}/{c.max_points}</b>
                    <div className="small muted">{c.detail}</div>
                  </li>
                ))}
              </ul>
              {result.ats.mots_cles_manquants.length > 0 && (
                <p className="small">Mots-clés absents du CV : {result.ats.mots_cles_manquants.join(", ")}</p>
              )}
            </>
          )}
        </section>
      )}

      {company && (
        <section className="card">
          <h2>Fiche entreprise</h2>
          <dl className="fiche">
            <dt>Nom</dt><dd>{company.nom}</dd>
            {company.activite && <><dt>Activité</dt><dd>{company.activite}</dd></>}
            {company.effectif && <><dt>Effectif</dt><dd>{company.effectif}</dd></>}
            {company.date_creation && <><dt>Création</dt><dd>{company.date_creation}</dd></>}
            {company.categorie && <><dt>Catégorie</dt><dd>{company.categorie}</dd></>}
            {company.adresse && <><dt>Siège</dt><dd>{company.adresse}</dd></>}
            {company.siren && <><dt>SIREN</dt><dd>{company.siren}</dd></>}
            {company.dirigeants.length > 0 && <><dt>Dirigeants</dt><dd>{company.dirigeants.join(", ")}</dd></>}
          </dl>
          <p className="small muted">Source : {company.source}</p>
        </section>
      )}
    </>
  );
}

function Score({ label, value, display }: { label: string; value: number; display?: string }) {
  const color = value >= 75 ? "var(--ok)" : value >= 50 ? "var(--warn)" : "var(--bad)";
  return (
    <div className="score">
      <div className="score-head"><span>{label}</span><b style={{ color }}>{display ?? `${value}%`}</b></div>
      <div className="bar"><div style={{ width: `${value}%`, background: color }} /></div>
    </div>
  );
}

const NIVEAUX: { key: Keyword["niveau"]; label: string }[] = [
  { key: "obligatoire", label: "Obligatoires" },
  { key: "important", label: "Importants" },
  { key: "bonus", label: "Bonus" },
];
const ICON = { oui: "✔", partiel: "~", non: "✘" } as const;

// Étape 3 de la skill : table des mots-clés en 3 niveaux, adéquation /10, points forts, écarts.
function AnalysisCard({ a, base, apres }: { a: Analysis; base: number; apres: boolean }) {
  const [open, setOpen] = useState(false);
  const delta = Math.round((a.score_adequation - base) * 10) / 10;
  return (
    <section className="card">
      <h2>Analyse de l&apos;offre</h2>
      <Score label="Adéquation avec ton profil" value={Math.round(a.score_adequation * 10)}
             display={`${a.score_adequation}/10`} />
      {delta > 0 && <p className="small ok">+{String(delta).replace(".", ",")} grâce à tes réponses</p>}
      {apres && delta <= 0 && (
        <p className="small muted">On ne te connaît pas encore : réponds aux questions au-dessus pour affiner ce score.</p>
      )}
      {a.points_forts.length > 0 && <p className="small"><b>Tes points forts :</b> {a.points_forts.join(", ")}</p>}
      {a.ecarts.length > 0 && (
        <p className="small"><b>Écarts :</b> {a.ecarts.join(", ")}. Les questions {apres ? "au-dessus" : "ci-dessous"} servent à vérifier si tu
          peux les couvrir honnêtement.</p>
      )}
      <button className="btn ghost small" onClick={() => setOpen(!open)}>
        {open ? "Masquer les mots-clés" : `Voir les ${a.mots_cles.length} mots-clés`}
      </button>
      {open && NIVEAUX.map((n) => {
        const kws = a.mots_cles.filter((k) => k.niveau === n.key);
        if (!kws.length) return null;
        return (
          <div key={n.key} className="kw-group">
            <div className="small muted">{n.label}</div>
            <div className="kws">
              {kws.map((k) => (
                <span key={k.terme} className={`kw ${k.couverture}`} title={`${k.occurrences} fois dans l'offre`}>
                  {ICON[k.couverture]} {k.terme}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}

// Description lisible : titres (« Missions : »), listes, mots-clés surlignés, repliée si longue.
type Bloc = { titre?: string; texte?: string; items?: string[] };
const PUCE = /^[-•*·▪●–]\s+/;
const TITRE = /^([A-ZÀ-Ý][^:.!?]{1,40}?)\s*:\s*(.*)$/;

function splitHorsParentheses(s: string): string[] {
  const out: string[] = []; let cur = ""; let depth = 0;
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth = Math.max(0, depth - 1);
    if ((ch === "," || ch === ";") && depth === 0) { out.push(cur.trim()); cur = ""; } else cur += ch;
  }
  out.push(cur.trim());
  return out.filter(Boolean);
}

function corps(texte: string): Bloc {
  const t = texte.trim().replace(/\.$/, "");
  const parts = splitHorsParentheses(t);
  // une seule phrase énumérative -> liste
  if (parts.length >= 3 && !/\.\s/.test(t) && parts.every((p) => p.length < 140)) return { items: parts };
  return { texte: texte.trim() };
}

function parseDescription(desc: string): Bloc[] {
  const blocs: Bloc[] = [];
  for (const brut of desc.split(/\n+/)) {
    const l = brut.trim();
    if (!l) continue;
    const last = blocs[blocs.length - 1];
    if (PUCE.test(l)) {
      const item = l.replace(PUCE, "");
      if (last && last.items && !last.texte) last.items.push(item); else blocs.push({ items: [item] });
      continue;
    }
    const m = l.match(TITRE);
    if (m) { blocs.push({ titre: m[1], ...(m[2] ? corps(m[2]) : { items: [] }) }); continue; }
    if (l.length < 50 && (l.endsWith(":") || (l === l.toUpperCase() && /[A-Z]/.test(l)))) {
      blocs.push({ titre: l.replace(/:$/, "").trim(), items: [] }); continue;
    }
    blocs.push({ texte: l });
  }
  return blocs;
}

function Surligne({ texte, motsCles }: { texte: string; motsCles: Keyword[] }) {
  const termes = motsCles.filter((k) => k.terme.length > 2).sort((a, b) => b.terme.length - a.terme.length);
  if (!termes.length) return <>{texte}</>;
  const esc = termes.map((k) => k.terme.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(?<![\\p{L}\\p{N}])(${esc.join("|")})(?![\\p{L}\\p{N}])`, "giu");
  const parts = texte.split(re);
  return <>{parts.map((p, i) => {
    if (i % 2 === 0) return p;
    const k = termes.find((t) => t.terme.toLowerCase() === p.toLowerCase());
    return <mark key={i} className={`hl ${k?.couverture ?? ""}`} title={k ? `Dans ton profil : ${k.couverture}` : ""}>{p}</mark>;
  })}</>;
}

function Description({ texte, motsCles }: { texte: string; motsCles: Keyword[] }) {
  const [ouvert, setOuvert] = useState(false);
  if (!texte.trim()) return null;
  const blocs = parseDescription(texte);
  const longue = texte.length > 450 && blocs.length > 2;
  const visibles = longue && !ouvert ? blocs.slice(0, 2) : blocs;
  return (
    <div className="desc">
      {visibles.map((b, i) => (
        <div key={i} className="desc-bloc">
          {b.titre && <h3>{b.titre}</h3>}
          {b.texte && <p><Surligne texte={b.texte} motsCles={motsCles} /></p>}
          {b.items && b.items.length > 0 && (
            <ul>{b.items.map((it, j) => <li key={j}><Surligne texte={it} motsCles={motsCles} /></li>)}</ul>
          )}
        </div>
      ))}
      {longue && (
        <button className="btn ghost small" onClick={() => setOuvert(!ouvert)}>
          {ouvert ? "Réduire" : "Lire la suite"}
        </button>
      )}
      <p className="small muted legend">
        <mark className="hl oui">déjà dans ton profil</mark> <mark className="hl non">pas encore dans ton profil</mark>
      </p>
    </div>
  );
}
