import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        <div className="overline mb-1.5" style={{ color: "var(--accent-600)" }}>
          {eyebrow}
        </div>
        <h1 className="font-display text-3xl font-semibold text-text-hi">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-sm text-text-mid">{subtitle}</p>
        )}
      </div>
      {actions}
    </div>
  );
}
