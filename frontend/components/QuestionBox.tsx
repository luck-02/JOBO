"use client";
import type { Question } from "../lib/api";

// Réponse à une question : choix cliqués + texte (précision, ou réponse libre si « Autre »).
export type Choice = { sel: string[]; autre: boolean; texte: string };
export const VIDE: Choice = { sel: [], autre: false, texte: "" };

export function toText(c: Choice | undefined): string {
  if (!c) return "";
  const texte = c.texte.trim();
  if (c.autre) return [...c.sel, texte].filter(Boolean).join(", ");
  return c.sel.join(", ") + (c.sel.length && texte ? ` : ${texte}` : texte);
}

// Une question à la fois, comme un encart à choix : on clique, ou on écrit dans « Autre ».
export default function QuestionBox({ q, num, total, value, onChange }: {
  q: Question; num: number; total: number; value: Choice; onChange: (v: Choice) => void;
}) {
  const sansChoix = q.options.length === 0;
  function pick(opt: string) {
    if (q.multiple) {
      const sel = value.sel.includes(opt) ? value.sel.filter((s) => s !== opt) : [...value.sel, opt];
      onChange({ ...value, sel });
    } else {
      onChange(value.sel[0] === opt ? VIDE : { sel: [opt], autre: false, texte: value.autre ? "" : value.texte });
    }
  }
  function autre() {
    if (q.multiple) onChange({ ...value, autre: !value.autre });
    else onChange(value.autre ? VIDE : { sel: [], autre: true, texte: "" });
  }
  const showTexte = sansChoix || value.autre || value.sel.length > 0;
  return (
    <div className="qbox">
      <div className="qbox-head">
        <span className="small muted">Question {num}/{total}{q.multiple && " · plusieurs choix possibles"}</span>
        <div className="qbox-title">{q.question}</div>
      </div>
      {!sansChoix && (
        <div className="opts" role={q.multiple ? "group" : "radiogroup"}>
          {q.options.map((opt) => {
            const on = value.sel.includes(opt);
            return (
              <button key={opt} type="button" role={q.multiple ? "checkbox" : "radio"} aria-checked={on}
                      className={`opt${on ? " on" : ""}`} onClick={() => pick(opt)}>
                <span className={`mark${q.multiple ? " sq" : ""}`}>{on && "✓"}</span>{opt}
              </button>
            );
          })}
          <button type="button" role={q.multiple ? "checkbox" : "radio"} aria-checked={value.autre}
                  className={`opt${value.autre ? " on" : ""}`} onClick={autre}>
            <span className={`mark${q.multiple ? " sq" : ""}`}>{value.autre && "✓"}</span>Autre…
          </button>
        </div>
      )}
      {showTexte && (
        <textarea className="qbox-text" maxLength={600} value={value.texte}
                  autoFocus={value.autre} onChange={(e) => onChange({ ...value, texte: e.target.value })}
                  placeholder={sansChoix || value.autre
                    ? (q.exemple ? `Ta réponse. Ex. : ${q.exemple}` : "Ta réponse")
                    : (q.exemple ? `Préciser (facultatif). Ex. : ${q.exemple}` : "Préciser (facultatif)")} />
      )}
    </div>
  );
}

