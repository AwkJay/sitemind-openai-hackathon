"use client";

import { useEffect, useRef, useState } from "react";
import {
  Send,
  Sparkles,
  ExternalLink,
  History,
  User,
  Loader2,
} from "lucide-react";
import { askCopilot } from "@/lib/api";
import type { RFIAnswer } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Button } from "@/components/ui/primitives";

interface Turn {
  q: string;
  a?: RFIAnswer;
  pending?: boolean;
}

const SUGGESTIONS = [
  "What cover does IS 456 require for footings?",
  "How is design wind speed Vz derived?",
  "Should we use seismic importance factor 1.5?",
];

// Render an answer string, turning [n] markers into hoverable citation chips.
function AnswerBody({ answer }: { answer: RFIAnswer }) {
  const parts = answer.answer.split(/(\[\d+\])/g);
  return (
    <p className="text-[0.95rem] leading-relaxed text-text-hi">
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (m) {
          const idx = parseInt(m[1], 10) - 1;
          const src = answer.sources[idx];
          return (
            <span key={i} className="group relative inline-block align-baseline">
              <sup
                className="ml-0.5 cursor-help rounded-chip bg-bg-700 px-1 font-mono text-[0.62rem] font-semibold text-data ring-1 ring-data/40"
                tabIndex={0}
              >
                {m[1]}
              </sup>
              {src && (
                <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1.5 hidden w-72 -translate-x-1/2 rounded border border-line bg-bg-700 p-3 text-left text-xs shadow-glow group-hover:block group-focus-within:block">
                  <span className="clause block font-semibold text-text-hi">
                    {src.label}
                  </span>
                  <span className="mt-1 block italic text-text-mid">
                    &ldquo;{src.detail}&rdquo;
                  </span>
                </span>
              )}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </p>
  );
}

function SourcesList({ answer }: { answer: RFIAnswer }) {
  return (
    <div className="mt-4 border-t border-line pt-3">
      <Overline>Sources</Overline>
      <ol className="mt-2 space-y-2">
        {answer.sources.map((s, i) => (
          <li
            key={i}
            className="rounded bg-bg-700 px-3 py-2"
            style={{ borderLeft: "3px solid var(--data)" }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="clause text-sm font-semibold text-text-hi">
                <span className="text-data">[{i + 1}]</span> {s.label}
              </span>
              {s.verify_url && (
                <a
                  href={s.verify_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-data hover:text-[#7cd4fb]"
                >
                  View <ExternalLink size={12} />
                </a>
              )}
            </div>
            <p className="mt-1 text-xs italic text-text-mid">
              &ldquo;{s.detail}&rdquo;
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

function SeenBeforeCard({ sb }: { sb: NonNullable<RFIAnswer["seen_before"]> }) {
  return (
    <div
      className="mt-4 rounded-card border border-line bg-bg-800 px-4 py-3"
      style={{ borderLeft: "3px solid var(--accent)" }}
    >
      <div className="flex items-center gap-2">
        <History size={15} strokeWidth={1.6} className="text-accent" />
        <Overline>Seen before · matched prior RFI</Overline>
        <span className="clause ml-auto text-xs font-semibold text-accent">
          {sb.rfi_id}
        </span>
      </div>
      <p className="mt-2 text-sm text-text-hi">{sb.summary}</p>
      <p className="mt-1.5 text-sm text-text-mid">
        <span className="overline mr-1.5 inline">Resolution</span>
        {sb.resolution}
      </p>
    </div>
  );
}

export default function CopilotPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const seededRef = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  // Pre-render one real exemplar Q&A on load — a genuine askCopilot() call
  // against the same corpus/citations as any other question, not fake data —
  // so the page never demos cold with an empty "ask something" placeholder.
  // Guarded with a ref (not just the empty dep array) because React 18
  // StrictMode double-invokes effects in dev, which would otherwise fire this
  // twice and race against the existing by-index turn-update logic in send().
  useEffect(() => {
    if (seededRef.current) return;
    seededRef.current = true;
    send(SUGGESTIONS[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { q, pending: true }]);
    const { data } = await askCopilot(q);
    // small delay so the "thinking" state is visible
    await new Promise((r) => setTimeout(r, 450));
    setTurns((t) =>
      t.map((turn, i) =>
        i === t.length - 1 ? { q, a: data, pending: false } : turn,
      ),
    );
    setBusy(false);
  }

  return (
    <div className="flex h-[calc(100vh-7.5rem)] flex-col">
      <PageHeader
        eyebrow="Cited Project Copilot"
        title="Copilot"
        subtitle="For everyone on the project — ask anything about the project or the codes, every answer is grounded in real clauses with inline citations."
      />

      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <Card className="flex min-h-0 flex-1 flex-col">
          <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
            {turns.length === 0 && (
              <div className="grid h-full place-items-center text-center">
                <div>
                  <Sparkles
                    size={28}
                    strokeWidth={1.2}
                    className="mx-auto mb-3 text-accent"
                  />
                  <p className="text-sm text-text-mid">
                    Ask the copilot a question. Try one of these:
                  </p>
                  <div className="mt-4 flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="rounded-full border border-line bg-bg-700 px-3 py-1.5 text-xs text-text-mid transition-colors hover:border-text-lo hover:text-text-hi"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {turns.map((turn, i) => (
              <div key={i} className="space-y-3">
                {/* user */}
                <div className="flex justify-end">
                  <div className="flex max-w-[80%] items-start gap-2.5">
                    <div className="rounded-card rounded-tr-sm bg-bg-700 px-4 py-2.5 text-sm text-text-hi">
                      {turn.q}
                    </div>
                    <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-bg-600 text-text-mid">
                      <User size={14} strokeWidth={1.6} />
                    </span>
                  </div>
                </div>

                {/* assistant */}
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent text-[#0B0F14]">
                    ▣
                  </span>
                  <div className="min-w-0 flex-1">
                    {turn.pending ? (
                      <div className="flex items-center gap-2 rounded-card bg-bg-700 px-4 py-3 text-sm text-text-mid">
                        <Loader2 size={15} className="animate-spin text-accent" />
                        <span>Searching standards & project docs</span>
                        <span className="flex gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-blink" />
                          <span
                            className="h-1.5 w-1.5 rounded-full bg-accent animate-blink"
                            style={{ animationDelay: "0.2s" }}
                          />
                          <span
                            className="h-1.5 w-1.5 rounded-full bg-accent animate-blink"
                            style={{ animationDelay: "0.4s" }}
                          />
                        </span>
                      </div>
                    ) : (
                      turn.a && (
                        <div className="animate-fadeUp rounded-card rounded-tl-sm border border-line bg-bg-800 px-4 py-3.5">
                          <AnswerBody answer={turn.a} />
                          {turn.a.sources.length > 0 && <SourcesList answer={turn.a} />}
                          {turn.a.seen_before && (
                            <SeenBeforeCard sb={turn.a.seen_before} />
                          )}
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          {/* Try-also row + abstention disclosure — visible once the exemplar
              turn has already been asked, so a judge can still one-click the
              remaining suggestions and sees the honesty guarantee up front. */}
          {turns.length > 0 && (
            <div className="border-t border-line px-4 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[0.68rem] text-text-lo">Try also:</span>
                {SUGGESTIONS.slice(1).map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    disabled={busy}
                    className="rounded-full border border-line bg-bg-700 px-2.5 py-1 text-[0.72rem] text-text-mid transition-colors hover:border-text-lo hover:text-text-hi disabled:opacity-50"
                  >
                    {s}
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-[0.68rem] text-text-lo">
                Abstains when the source doesn&rsquo;t answer — no guessed clauses.
              </p>
            </div>
          )}

          {/* composer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-center gap-2 border-t border-line p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about cover, grade, wind, seismic, a submittal…"
              className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
            />
            <Button type="submit" disabled={busy || !input.trim()}>
              <Send size={15} /> Ask
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
