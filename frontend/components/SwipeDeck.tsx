"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api, ApiError, API_URL, CONTRAT_LABEL, RAISON_LABEL,
  type Contrat, type Generation, type OfferSummary, type Preferences, type Question, type Raison, type TypeReaction,
} from "../lib/api";
import QuestionBox, { toText, VIDE, type Choice } from "./QuestionBox";

// Swipe d'offres (mobile) : droite = postuler, gauche = pas pour moi, haut = favori, tap = détail.
// Chaque geste a aussi son bouton (accessibilité) et ses touches clavier (← → ↑, Retour arrière = annuler).

const SEUIL = 100;          // px pour valider un geste
const MAX_ANNULER = 10;
const CONTRATS: Contrat[] = ["alternance", "stage", "cdi", "cdd"];

type Fait = { offer: OfferSummary; type: TypeReaction };
type Panneau =
  | null
  | { kind: "postuler"; offer: OfferSummary }
  | { kind: "compte"; type: TypeReaction }
  | { kind: "criteres" };
type Bandeau = null | { kind: "passer"; offer: OfferSummary; raison: Raison | null } | { kind: "favori" } | { kind: "info"; text: string };

export default function SwipeDeck() {
  const router = useRouter();
  const [pile, setPile] = useState<OfferSummary[] | null>(null);
  const [error, setError] = useState("");
  const [faits, setFaits] = useState<Fait[]>([]);
  const [panneau, setPanneau] = useState<Panneau>(null);
  const [bandeau, setBandeau] = useState<Bandeau>(null);
  const [drag, setDrag] = useState({ x: 0, y: 0, actif: false });
  const [sortie, setSortie] = useState<TypeReaction | null>(null);
  const depart = useRef<{ x: number; y: number } | null>(null);
  const occupe = useRef(false);

  const charger = useCallback(async (garder: OfferSummary[] = []) => {
    try {
      const p = await api.pile();
      const deja = new Set(garder.map((o) => o.id));
      setPile([...garder, ...p.filter((o) => !deja.has(o.id))]);
    } catch (e) { setError((e as Error).message); setPile(garder); }
  }, []);
  useEffect(() => { charger(); }, [charger]);

  const carte = pile?.[0];

  // Recharge quand il reste peu de cartes
  useEffect(() => {
    if (pile && pile.length > 0 && pile.length < 4) charger(pile);
  }, [pile?.length]); // eslint-disable-line react-hooks/exhaustive-deps

  async function agir(type: TypeReaction) {
    if (!carte || occupe.current || panneau) return;
    occupe.current = true;
    setSortie(type);
    await new Promise((r) => setTimeout(r, 180));
    setSortie(null); setDrag({ x: 0, y: 0, actif: false });
    const offer = carte;
    setPile((p) => p?.slice(1) ?? null);
    try {
      await api.react(offer.id, type);
      setFaits((f) => [{ offer, type }, ...f].slice(0, MAX_ANNULER));
      if (type === "postuler") { setBandeau(null); setPanneau({ kind: "postuler", offer }); }
      else if (type === "passer") setBandeau({ kind: "passer", offer, raison: null });
      else setBandeau({ kind: "favori" });
    } catch (e) {
      setPile((p) => [offer, ...(p ?? [])]);    // la carte revient
      if (e instanceof ApiError && e.status === 401) setPanneau({ kind: "compte", type });
      else setError((e as Error).message);
    } finally { occupe.current = false; }
  }

  async function annuler() {
    const dernier = faits[0];
    if (!dernier || occupe.current) return;
    occupe.current = true;
    try {
      await api.undo(dernier.offer.id);
      setFaits((f) => f.slice(1));
      setPile((p) => [dernier.offer, ...(p ?? []).filter((o) => o.id !== dernier.offer.id)]);
      setPanneau(null);
      setBandeau({ kind: "info", text: "Swipe annulé" });
    } catch (e) { setError((e as Error).message); } finally { occupe.current = false; }
  }

  async function raison(r: Raison) {
    if (bandeau?.kind !== "passer") return;
    const nouvelle = bandeau.raison === r ? null : r;
    setBandeau({ ...bandeau, raison: nouvelle });
    api.raison(bandeau.offer.id, nouvelle).catch(() => {});
  }

  // Clavier
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (panneau || (e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight") agir("postuler");
      else if (e.key === "ArrowLeft") agir("passer");
      else if (e.key === "ArrowUp") { e.preventDefault(); agir("favori"); }
      else if (e.key === "Backspace") annuler();
      else if (e.key === "Enter" && carte) router.push(`/offres/${encodeURIComponent(carte.id)}`);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Gestes
  function down(e: React.PointerEvent) {
    if (panneau) return;
    depart.current = { x: e.clientX, y: e.clientY };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    setDrag({ x: 0, y: 0, actif: true });
  }
  function move(e: React.PointerEvent) {
    if (!depart.current) return;
    setDrag({ x: e.clientX - depart.current.x, y: Math.min(0, e.clientY - depart.current.y), actif: true });
  }
  function up() {
    if (!depart.current) return;
    depart.current = null;
    const { x, y } = drag;
    if (Math.abs(x) < 8 && Math.abs(y) < 8) {            // tap = détail
      setDrag({ x: 0, y: 0, actif: false });
      if (carte) router.push(`/offres/${encodeURIComponent(carte.id)}`);
      return;
    }
    if (-y > SEUIL && -y > Math.abs(x)) agir("favori");
    else if (x > SEUIL) agir("postuler");
    else if (x < -SEUIL) agir("passer");
    else setDrag({ x: 0, y: 0, actif: false });          // bas ou trop court : rien
  }

  const intention: TypeReaction | null = sortie
    ?? (-drag.y > 60 && -drag.y > Math.abs(drag.x) ? "favori" : drag.x > 60 ? "postuler" : drag.x < -60 ? "passer" : null);
  const transform = sortie === "postuler" ? "translate(140%, 0) rotate(18deg)"
    : sortie === "passer" ? "translate(-140%, 0) rotate(-18deg)"
    : sortie === "favori" ? "translate(0, -140%)"
    : `translate(${drag.x}px, ${drag.y}px) rotate(${drag.x / 18}deg)`;

  return (
    <div className="swipe">
      <div className="swipe-top">
        <button className="chip" onClick={() => setPanneau({ kind: "criteres" })}>⚙ Mes critères</button>
        <Link className="chip" href="/offres-passees">Offres passées</Link>
      </div>

      {error && <p className="error small" onClick={() => setError("")}>{error}</p>}

      <div className="deck" aria-live="polite">
        {pile === null && <p className="muted center">Chargement…</p>}
        {pile?.length === 0 && (
          <div className="card deck-empty">
            <b>Tu as tout vu pour l&apos;instant</b>
            <p className="small muted">Élargis tes critères ou colle le lien d&apos;une offre trouvée ailleurs.</p>
            <button className="btn primary" onClick={() => setPanneau({ kind: "criteres" })}>Modifier mes critères</button>
          </div>
        )}
        {pile?.[1] && <Carte o={pile[1]} className="behind" />}
        {carte && (
          <Carte o={carte} intention={intention}
                 style={{ transform, transition: drag.actif && !sortie ? "none" : "transform .18s ease-out" }}
                 onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />
        )}
      </div>

      <div className="swipe-actions" role="group" aria-label="Actions sur l'offre">
        <button className="round small-r" onClick={annuler} disabled={!faits.length} aria-label="Annuler le dernier swipe"
                title="Annuler (Retour arrière)">↶</button>
        <button className="round no" onClick={() => agir("passer")} disabled={!carte} aria-label="Pas pour moi"
                title="Pas pour moi (←)">✕</button>
        <button className="round fav" onClick={() => agir("favori")} disabled={!carte} aria-label="Mettre en favori"
                title="Favori (↑)">★</button>
        <button className="round yes" onClick={() => agir("postuler")} disabled={!carte} aria-label="Postuler"
                title="Postuler (→)">✓</button>
      </div>
      <p className="small muted center">Glisse à droite pour postuler, à gauche si ce n&apos;est pas pour toi, vers le haut pour
        garder en favori. Touche la carte pour tout lire.</p>

      {bandeau && (
        <div className="toast" role="status">
          {bandeau.kind === "passer" && (
            <>
              <div className="toast-row"><span>Offre masquée. Pourquoi ? <span className="muted">(facultatif)</span></span>
                <button className="btn ghost small" onClick={() => setBandeau(null)} aria-label="Fermer">✕</button></div>
              <div className="chips">
                {(Object.keys(RAISON_LABEL) as Raison[]).map((r) => (
                  <button key={r} className={`chip ${bandeau.raison === r ? "on" : ""}`} onClick={() => raison(r)}>
                    {RAISON_LABEL[r]}
                  </button>
                ))}
              </div>
            </>
          )}
          {bandeau.kind === "favori" && (
            <div className="toast-row"><span>★ Ajoutée à tes favoris (Suivi). Rappel dans 7 jours.</span>
              <button className="btn ghost small" onClick={() => setBandeau(null)} aria-label="Fermer">✕</button></div>
          )}
          {bandeau.kind === "info" && (
            <div className="toast-row"><span>{bandeau.text}</span>
              <button className="btn ghost small" onClick={() => setBandeau(null)} aria-label="Fermer">✕</button></div>
          )}
        </div>
      )}

      {panneau && (
        <div className="sheet-bg" onClick={(e) => e.target === e.currentTarget && panneau.kind !== "postuler" && setPanneau(null)}>
          <div className="sheet" role="dialog" aria-modal="true">
            {panneau.kind === "postuler" && (
              <Postuler offer={panneau.offer} onClose={() => setPanneau(null)} onAnnuler={annuler} />
            )}
            {panneau.kind === "compte" && (
              <>
                <h2>Crée ton compte pour {panneau.type === "favori" ? "garder tes favoris" : "postuler"}</h2>
                <p className="small muted">Tu peux swiper sans compte. Pour postuler ou garder une offre, importe ton CV :
                  ensuite, un swipe suffit.</p>
                <Link href="/bienvenue" className="btn primary block">Créer mon compte</Link>
                <button className="btn ghost block" onClick={() => setPanneau(null)}>Plus tard</button>
              </>
            )}
            {panneau.kind === "criteres" && (
              <Criteres onClose={(changed) => { setPanneau(null); if (changed) { setPile(null); charger(); } }} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Carte({ o, intention, className = "", ...rest }: {
  o: OfferSummary; intention?: TypeReaction | null; className?: string;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`card swipe-card ${className}`} {...rest}>
      {intention && (
        <span className={`stamp ${intention}`}>
          {intention === "postuler" ? "Postuler" : intention === "passer" ? "Pas pour moi" : "Favori"}
        </span>
      )}
      <span className="pill">{CONTRAT_LABEL[o.contrat] ?? o.contrat}</span>
      <div className="swipe-title">{o.intitule}</div>
      <div className="swipe-ent">{o.entreprise}</div>
      <div className="meta">
        <span>📍 {o.lieu}</span>
        {o.date_publication && <span>Publiée le {new Date(o.date_publication).toLocaleDateString("fr-FR")}</span>}
      </div>
      <div className="swipe-hint small muted">Touche pour voir le détail</div>
    </div>
  );
}

// Swipe à droite : 3 questions, puis Générer CV + lettre, ou garder en brouillon (seule option si quota épuisé).
function Postuler({ offer, onClose, onAnnuler }: { offer: OfferSummary; onClose: () => void; onAnnuler: () => void }) {
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [choix, setChoix] = useState<Record<string, Choice>>({});
  const [restant, setRestant] = useState<number | null>(null);
  const [busy, setBusy] = useState<"" | "gen" | "draft">("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<Generation | null>(null);
  const [garde, setGarde] = useState(false);

  useEffect(() => {
    api.questions(offer.id, 3).then(setQuestions).catch(() => setQuestions([]));
    api.quota().then((q) => setRestant(q.restant)).catch(() => setRestant(0));
  }, [offer.id]);

  const reponses = () => (questions ?? []).map((q) => ({ question: q.question, reponse: toText(choix[q.id]) }))
    .filter((r) => r.reponse);

  async function generer() {
    setBusy("gen"); setError("");
    try { setResult(await api.generate(offer.id, ["cv", "lettre"], "", reponses())); }
    catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status === 429) setRestant(0);
    } finally { setBusy(""); }
  }
  async function brouillon() {
    setBusy("draft"); setError("");
    try { await api.brouillon(offer.id, reponses()); setGarde(true); }
    catch (e) { setError((e as Error).message); } finally { setBusy(""); }
  }

  if (result) {
    return (
      <>
        <h2>C&apos;est prêt ✓</h2>
        <p className="small muted">{offer.intitule} · {offer.entreprise}</p>
        {result.ats && <p>Score ATS : <b>{result.ats.score}/100</b></p>}
        <div className="actions">
          {result.urls.cv && <a className="btn primary" href={API_URL + result.urls.cv} target="_blank">Mon CV</a>}
          {result.urls.lettre && <a className="btn" href={API_URL + result.urls.lettre} target="_blank">Ma lettre</a>}
        </div>
        <p className="small muted">L&apos;offre est dans ton Suivi, « À envoyer ».</p>
        <button className="btn block" onClick={onClose}>Offre suivante</button>
      </>
    );
  }
  if (garde) {
    return (
      <>
        <h2>Gardée en brouillon</h2>
        <p className="small muted">Retrouve-la dans ton Suivi pour générer le CV et la lettre plus tard.</p>
        <button className="btn primary block" onClick={onClose}>Offre suivante</button>
      </>
    );
  }
  const epuise = restant === 0;
  return (
    <>
      <div className="toast-row">
        <h2>Postuler : {offer.intitule}</h2>
        <button className="btn ghost small" onClick={onAnnuler} aria-label="Annuler ce swipe">Annuler</button>
      </div>
      <p className="small muted">3 questions rapides pour adapter ton CV, toutes facultatives.</p>
      {questions === null && <p className="muted">Chargement…</p>}
      {questions?.map((q, i) => (
        <QuestionBox key={q.id} q={q} num={i + 1} total={questions.length} value={choix[q.id] ?? VIDE}
                     onChange={(v) => setChoix((c) => ({ ...c, [q.id]: v }))} />
      ))}
      {error && <p className="error small">{error} {error.includes("profil") && <Link href="/profil">Compléter mon profil</Link>}</p>}
      {!epuise && (
        <button className="btn primary block" disabled={!!busy || restant === null} onClick={generer}>
          {busy === "gen" ? "Génération en cours…" : `Générer CV + lettre${restant !== null ? ` (${restant} restante${restant > 1 ? "s" : ""} aujourd'hui)` : ""}`}
        </button>
      )}
      {epuise && <p className="small muted">Tu as utilisé tes générations du jour : garde l&apos;offre en brouillon, tu la
        retrouveras demain dans ton Suivi.</p>}
      <button className={`btn block ${epuise ? "primary" : ""}`} disabled={!!busy} onClick={brouillon}>
        {busy === "draft" ? "…" : "Garder en brouillon"}
      </button>
    </>
  );
}

function Criteres({ onClose }: { onClose: (changed: boolean) => void }) {
  const [p, setP] = useState<Preferences | null>(null);
  const [depts, setDepts] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    api.preferences().then((x) => { setP(x); setDepts(x.departements.join(", ")); })
      .catch(() => setP({ contrats: [], departements: [], mots_cles: "" }));
  }, []);
  if (!p) return <p className="muted">Chargement…</p>;
  const toggle = (c: Contrat) =>
    setP({ ...p, contrats: p.contrats.includes(c) ? p.contrats.filter((x) => x !== c) : [...p.contrats, c] });
  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.savePreferences({ ...p!, departements: depts.split(/[\s,;]+/).filter(Boolean) });
      onClose(true);
    } catch (err) { setError((err as Error).message); }
  }
  return (
    <form onSubmit={save}>
      <h2>Mes critères</h2>
      <p className="small muted">Contrats (plusieurs possibles, aucun = tous)</p>
      <div className="chips wrap">
        {CONTRATS.map((c) => (
          <button type="button" key={c} className={`chip ${p.contrats.includes(c) ? "on" : ""}`}
                  aria-pressed={p.contrats.includes(c)} onClick={() => toggle(c)}>{CONTRAT_LABEL[c]}</button>
        ))}
      </div>
      <label>Départements (ex. 44, 35 ; vide = toute la France)
        <input value={depts} onChange={(e) => setDepts(e.target.value)} inputMode="numeric" placeholder="44, 35" />
      </label>
      <label>Mots-clés (facultatif)
        <input value={p.mots_cles} maxLength={100} onChange={(e) => setP({ ...p, mots_cles: e.target.value })}
               placeholder="ex. commercial" />
      </label>
      {error && <p className="error small">{error}</p>}
      <div className="actions">
        <button className="btn primary">Enregistrer</button>
        <button type="button" className="btn ghost" onClick={() => onClose(false)}>Annuler</button>
      </div>
    </form>
  );
}
