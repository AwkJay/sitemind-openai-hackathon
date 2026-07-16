import type { ReactNode } from "react";

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export function Card({
  children,
  className,
  glow,
}: {
  children: ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-card border border-line bg-bg-800",
        glow && "shadow-glow",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Overline({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("overline", className)}>{children}</div>;
}

export function Chip({
  children,
  color,
  bg,
  className,
}: {
  children: ReactNode;
  color: string;
  bg: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-chip px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wide font-mono",
        className,
      )}
      style={{ color, background: bg, border: `1px solid ${color}33` }}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  className,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost";
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded font-medium text-sm transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2";
  const styles =
    variant === "primary"
      ? "bg-accent text-[#0B0F14] hover:bg-accent-300 active:bg-accent-600 font-semibold"
      : "bg-bg-700 text-text-hi border border-line hover:border-text-lo hover:bg-bg-600";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(base, styles, className)}
    >
      {children}
    </button>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded bg-bg-700",
        className,
      )}
    />
  );
}
