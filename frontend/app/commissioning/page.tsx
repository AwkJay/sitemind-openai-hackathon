"use client";

import { useRef, useState } from "react";
import {
  Upload,
  Loader2,
  AlertTriangle,
  ThermometerSun,
  CheckCircle2,
  MinusCircle,
  FileDown,
} from "lucide-react";
import { ingestCommissioningLog, qualityPackageHtmlUrl, CommissioningUnavailableError } from "@/lib/api";
import type { CommissioningFinding, CommissioningIngestResult } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Button, Chip } from "@/components/ui/primitives";
import { NCRCard } from "@/components/NCRCard";
import { CitedClauseBox } from "@/components/CitedClauseBox";
import { commissioningVerdictMeta } from "@/lib/format";

function FindingRow({ finding, index }: { finding: CommissioningFinding; index: number }) {
  const meta = commissioningVerdictMeta[finding.verdict];
  return (
    <div
      className="flex flex-col gap-2 border-b border-line px-4 py-3 last:border-0"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold text-text-hi">{finding.test_id}</span>
          <span className="text-text-lo">·</span>
          <span className="text-sm text-text-mid">{finding.location_zone}</span>
        </div>
        <Chip color={meta.color} bg={meta.bg}>
          {meta.label}
        </Chip>
      </div>
      <div className="font-mono text-[0.72rem] text-text-lo">
        {finding.parameter.replace(/_/g, " ")} = {finding.measured_value} {finding.unit}
        {finding.recommended_range && (
          <>
            {" "}
            · recommended {finding.recommended_range} {finding.unit}
          </>
        )}
        {finding.allowable_range && (
          <>
            {" "}
            · allowable {finding.allowable_range} {finding.unit}
          </>
        )}
      </div>
      {finding.citation && !finding.ncr && (
        <div className="mt-1">
          <CitedClauseBox citation={finding.citation} />
        </div>
      )}
    </div>
  );
}

export default function CommissioningPage() {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [result, setResult] = useState<CommissioningIngestResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(file: File) {
    setUploading(true);
    setUploadError(null);
    try {
      const r = await ingestCommissioningLog(file);
      setResult(r);
    } catch (e) {
      setUploadError(
        e instanceof CommissioningUnavailableError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Upload failed.",
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const pkg = result?.package;
  const failNcrs = (pkg?.findings ?? []).filter((f) => f.ncr).map((f) => f.ncr!);
  const otherFindings = (pkg?.findings ?? []).filter((f) => !f.ncr);

  return (
    <div>
      <PageHeader
        eyebrow="Commissioning QA Copilot (cooling-only slice)"
        title="Commissioning QA"
        subtitle="For the commissioning manager — upload a real cooling test log; it's checked deterministically against the ASHRAE TC9.9 thermal envelope and compiled into an as-commissioned quality package."
      />

      <Card className="mb-5 px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Overline>Upload test log</Overline>
            <p className="mt-1 max-w-xl text-sm text-text-mid">
              CSV with columns: test_id, system, parameter, measured_value, unit, timestamp,
              location_zone, equipment_class. Only <span className="font-mono text-text-hi">cooling</span>{" "}
              records are checked (supply/return air temp, relative humidity) — power/IT rows parse but are
              always <span className="font-mono">NOT_CHECKABLE</span>. Try{" "}
              <span className="font-mono text-text-hi">backend/data/project_docs/sample_commissioning_log.csv</span>.
            </p>
          </div>
          <div className="shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
              }}
            />
            <Button disabled={uploading} onClick={() => fileInputRef.current?.click()}>
              {uploading ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Parsing…
                </>
              ) : (
                <>
                  <Upload size={16} /> Upload test log (CSV)
                </>
              )}
            </Button>
          </div>
        </div>
        {uploadError && (
          <p className="mt-3 flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
            {uploadError}
          </p>
        )}
        {result && result.parse_errors.length > 0 && (
          <div className="mt-3 rounded border-l-2 border-warning/40 bg-bg-900/50 px-3 py-2">
            <div className="text-[0.7rem] font-medium uppercase tracking-wide text-warning">
              {result.parse_errors.length} row(s) skipped
            </div>
            <ul className="mt-1 space-y-0.5">
              {result.parse_errors.map((e, i) => (
                <li key={i} className="text-[0.72rem] text-text-lo">
                  {e}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {pkg && (
        <div className="space-y-5">
          {/* Corpus limitation — must always be shown, never hidden */}
          <Card className="flex items-start gap-3 border-warning/30 px-5 py-4">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warning" />
            <div>
              <div className="overline mb-1 text-warning">Corpus limitation</div>
              <p className="text-sm leading-relaxed text-text-mid">{pkg.corpus_limitation}</p>
            </div>
          </Card>

          {/* Summary row */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-bg-800 px-5 py-3.5">
            <div className="flex items-center gap-2">
              <ThermometerSun size={16} className="text-accent" />
              <span className="text-sm text-text-mid">
                <span className="font-mono text-text-hi">{pkg.total_records}</span> record(s)
              </span>
            </div>
            <div className="text-sm text-text-mid">
              <span className="font-mono text-pass">{pkg.pass_count}</span> pass
            </div>
            <div className="text-sm text-text-mid">
              <span className="font-mono text-warning">{pkg.within_allowable_count}</span> within-allowable
              only
            </div>
            <div className="text-sm text-text-mid">
              <span className="font-mono text-critical">{pkg.fail_count}</span> fail
            </div>
            <div className="text-sm text-text-mid">
              <span className="font-mono text-text-lo">{pkg.not_checkable_count}</span> not checkable
            </div>
            <a
              href={qualityPackageHtmlUrl(pkg.run_id)}
              target="_blank"
              rel="noreferrer"
              className="ml-auto inline-flex items-center gap-1.5 text-sm font-medium text-data hover:text-[#7cd4fb]"
            >
              <FileDown size={14} /> As-commissioned quality package ({pkg.run_id})
            </a>
          </div>

          {/* Findings that raised an NCR — reuse the compliance NCRCard, same schema */}
          {failNcrs.length > 0 && (
            <div className="space-y-4">
              <Overline>Findings with an NCR</Overline>
              {failNcrs.map((ncr, i) => (
                <NCRCard key={ncr.id} ncr={ncr} index={i} />
              ))}
            </div>
          )}

          {/* Remaining findings: PASS / NOT_CHECKABLE */}
          {otherFindings.length > 0 && (
            <Card className="overflow-hidden">
              <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
                <CheckCircle2 size={15} strokeWidth={1.5} className="text-pass" />
                <Overline>Other test records</Overline>
              </div>
              <div>
                {otherFindings.map((f, i) => (
                  <FindingRow key={f.test_id} finding={f} index={i} />
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {!pkg && (
        <Card className="grid place-items-center px-5 py-16 text-center">
          <MinusCircle size={28} strokeWidth={1.2} className="mb-3 text-text-lo" />
          <p className="text-sm text-text-mid">
            No test log uploaded yet — upload a CSV to run the cooling-envelope check.
          </p>
        </Card>
      )}
    </div>
  );
}
