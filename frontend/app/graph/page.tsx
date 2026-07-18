"use client";

import { useEffect, useMemo, useState } from "react";
import { getKg } from "@/lib/api";
import type { KgGraph, KgNode, KgNodeType } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Skeleton } from "@/components/ui/primitives";

const TYPE_META: Record<
  KgNodeType,
  { label: string; color: string; col: number }
> = {
  equipment: { label: "Equipment", color: "var(--accent)", col: 0 },
  spec: { label: "Spec", color: "var(--text-hi)", col: 1 },
  standard: { label: "Standard", color: "var(--data)", col: 2 },
  rfi: { label: "RFI", color: "var(--warning)", col: 3 },
};

const W = 1050;
const COL_X = [130, 400, 670, 940];
const NODE_W = 210;
const NODE_H = 54;

// Splits a label onto up to 2 lines at the nearest word boundary instead of
// hard-truncating it — clause-style labels ("IS 456:2000 Cl. 26.4.2.2") were
// getting cut mid-string ("IS 456:2000 Cl. 26.4...") with no way to read the
// full clause without opening the inspector panel.
function wrapLabel(label: string, maxLineChars = 22): [string, string?] {
  if (label.length <= maxLineChars) return [label];
  let breakAt = label.lastIndexOf(" ", maxLineChars);
  if (breakAt <= 0) breakAt = maxLineChars;
  const line1 = label.slice(0, breakAt);
  let line2 = label.slice(breakAt).trim();
  if (line2.length > maxLineChars) line2 = `${line2.slice(0, maxLineChars - 1)}…`;
  return [line1, line2];
}

interface Positioned extends KgNode {
  x: number;
  y: number;
}

function layout(g: KgGraph): { nodes: Positioned[]; height: number } {
  const byType: Record<string, KgNode[]> = {};
  g.nodes.forEach((n) => (byType[n.type] ??= []).push(n));
  const colHeights = Object.values(byType).map((a) => a.length);
  const maxRows = Math.max(1, ...colHeights);
  // Tighter row pitch than before (compacts sparse columns instead of
  // stretching them thin to match the busiest column's centered spread).
  const rowGap = 66;
  const height = maxRows * rowGap + 40;
  const nodes: Positioned[] = [];
  (Object.keys(byType) as KgNodeType[]).forEach((type) => {
    const list = byType[type];
    const colX = COL_X[TYPE_META[type].col];
    const colSpan = list.length * rowGap;
    const startY = (height - colSpan) / 2 + rowGap / 2;
    list.forEach((n, i) => {
      nodes.push({ ...n, x: colX, y: startY + i * rowGap });
    });
  });
  return { nodes, height };
}

export default function GraphPage() {
  const [graph, setGraph] = useState<KgGraph | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    getKg().then((r) => setGraph(r.data));
  }, []);

  const { nodes, height, neighbors } = useMemo(() => {
    if (!graph) return { nodes: [], height: 400, neighbors: new Set<string>() };
    const { nodes, height } = layout(graph);
    const nb = new Set<string>();
    if (selected) {
      nb.add(selected);
      graph.edges.forEach((e) => {
        if (e.source === selected) nb.add(e.target);
        if (e.target === selected) nb.add(e.source);
      });
    }
    return { nodes, height, neighbors: nb };
  }, [graph, selected]);

  const posMap = useMemo(
    () => Object.fromEntries(nodes.map((n) => [n.id, n])),
    [nodes],
  );

  const isDim = (id: string) => selected !== null && !neighbors.has(id);
  const edgeActive = (s: string, t: string) =>
    selected !== null && (s === selected || t === selected);

  return (
    <div>
      <PageHeader
        eyebrow="Connected Knowledge Graph"
        title="Knowledge Graph"
        subtitle="Equipment → spec → standard → RFI. SiteMind connects dots no single document shows. Click a node to trace its links."
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_280px]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <Overline>Subgraph · Transformer foundation</Overline>
            <div className="flex items-center gap-3 text-xs text-text-mid">
              {(Object.keys(TYPE_META) as KgNodeType[]).map((t) => (
                <span key={t} className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: TYPE_META[t].color }}
                  />
                  {TYPE_META[t].label}
                </span>
              ))}
            </div>
          </div>

          {graph ? (
            <div className="overflow-x-auto p-2">
              <svg
                viewBox={`0 0 ${W} ${height}`}
                width="100%"
                style={{ minWidth: 760, display: "block" }}
                role="img"
                aria-label="Knowledge graph"
              >
                <defs>
                  <marker
                    id="arrow"
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M0,0 L10,5 L0,10 z" fill="var(--line)" />
                  </marker>
                  <marker
                    id="arrowActive"
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M0,0 L10,5 L0,10 z" fill="var(--data)" />
                  </marker>
                </defs>

                {/* edges */}
                {graph.edges.map((e, i) => {
                  const s = posMap[e.source];
                  const t = posMap[e.target];
                  if (!s || !t) return null;
                  const x1 = s.x + NODE_W / 2;
                  const x2 = t.x - NODE_W / 2;
                  const active = edgeActive(e.source, e.target);
                  const dim =
                    selected !== null && !active;
                  const midX = (x1 + x2) / 2;
                  return (
                    <g key={i} opacity={dim ? 0.3 : 1}>
                      <path
                        d={`M ${x1} ${s.y} C ${midX} ${s.y}, ${midX} ${t.y}, ${x2} ${t.y}`}
                        fill="none"
                        stroke={active ? "var(--data)" : "var(--line)"}
                        strokeWidth={active ? 2 : 1.25}
                        markerEnd={`url(#${active ? "arrowActive" : "arrow"})`}
                      />
                      <text
                        x={midX}
                        y={(s.y + t.y) / 2 - 4}
                        textAnchor="middle"
                        fontSize="9.5"
                        fontFamily="var(--font-mono)"
                        fill={active ? "var(--data)" : "var(--text-lo)"}
                      >
                        {e.label}
                      </text>
                    </g>
                  );
                })}

                {/* nodes */}
                {nodes.map((n) => {
                  const meta = TYPE_META[n.type];
                  const dim = isDim(n.id);
                  const sel = selected === n.id;
                  const [line1, line2] = wrapLabel(n.label);
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x - NODE_W / 2}, ${n.y - NODE_H / 2})`}
                      opacity={dim ? 0.55 : 1}
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        setSelected((cur) => (cur === n.id ? null : n.id))
                      }
                    >
                      <rect
                        width={NODE_W}
                        height={NODE_H}
                        rx={6}
                        fill="var(--bg-700)"
                        stroke={sel ? meta.color : "var(--line)"}
                        strokeWidth={sel ? 2 : 1}
                      />
                      <rect
                        width={4}
                        height={NODE_H}
                        rx={2}
                        fill={meta.color}
                      />
                      <text
                        x={14}
                        y={16}
                        fontSize="8"
                        fontFamily="var(--font-mono)"
                        fill="var(--text-lo)"
                        style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}
                      >
                        {meta.label}
                      </text>
                      <text
                        x={14}
                        y={line2 ? 30 : 34}
                        fontSize="12"
                        fontFamily="var(--font-sans)"
                        fontWeight={500}
                        fill="var(--text-hi)"
                      >
                        {line1}
                      </text>
                      {line2 && (
                        <text
                          x={14}
                          y={44}
                          fontSize="12"
                          fontFamily="var(--font-sans)"
                          fontWeight={500}
                          fill="var(--text-hi)"
                        >
                          {line2}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>
          ) : (
            <Skeleton className="m-2 h-96" />
          )}
        </Card>

        {/* Side panel */}
        <Card className="h-fit px-5 py-4">
          <Overline>Inspector</Overline>
          {selected && graph ? (
            (() => {
              const node = graph.nodes.find((n) => n.id === selected)!;
              const links = graph.edges.filter(
                (e) => e.source === selected || e.target === selected,
              );
              return (
                <div className="mt-3">
                  <div
                    className="rounded px-3 py-2"
                    style={{
                      borderLeft: `3px solid ${TYPE_META[node.type].color}`,
                      background: "var(--bg-700)",
                    }}
                  >
                    <div className="overline">{TYPE_META[node.type].label}</div>
                    <div className="mt-0.5 text-sm font-medium text-text-hi">
                      {node.label}
                    </div>
                  </div>
                  <div className="mt-3 overline">
                    {links.length} connection(s)
                  </div>
                  <ul className="mt-2 space-y-1.5">
                    {links.map((e, i) => {
                      const otherId =
                        e.source === selected ? e.target : e.source;
                      const other = graph.nodes.find((n) => n.id === otherId);
                      return (
                        <li
                          key={i}
                          className="rounded bg-bg-700 px-2.5 py-1.5 text-xs"
                        >
                          <span className="font-mono text-data">{e.label}</span>
                          <span className="text-text-lo"> → </span>
                          <span className="text-text-hi">{other?.label}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })()
          ) : (
            <p className="mt-3 text-sm text-text-mid">
              Click any node to inspect its connections and trace how a piece of
              equipment links to the spec, the governing standard and the RFIs
              that referenced it.
            </p>
          )}
        </Card>

        <Card className="h-fit px-5 py-4">
          <Overline>How this is built</Overline>
          <p className="mt-2 text-xs leading-relaxed text-text-mid">
            Built with plain NetworkX from the same structured project data every other pillar
            reads — no LLM, no embeddings. <span className="text-text-hi">specified_in</span> edges
            come from the design-basis/submittal params; <span className="text-text-hi">governed_by</span>{" "}
            edges call the exact same <span className="font-mono text-text-lo">applicable_checks()</span>{" "}
            rule engine Compliance uses to decide which clause governs a parameter;{" "}
            <span className="text-text-hi">references</span> edges match an RFI to a document/clause by
            a real shared ID in the RFI&apos;s own <span className="font-mono text-text-lo">Ref</span>{" "}
            field. Every edge is a computed join over real data, not a generated or hand-placed
            connection.
          </p>
        </Card>
      </div>
    </div>
  );
}
