"use client";

import { useEffect, useRef, useState } from "react";

// Count-up on mount, ~800ms ease-out. Renders via a formatter so we can show
// ₹ Cr / plain integers with tabular-nums (no digit jitter).
export function CountUp({
  to,
  duration = 850,
  format,
  className,
}: {
  to: number;
  duration?: number;
  format?: (v: number) => string;
  className?: string;
}) {
  const [val, setVal] = useState(0);
  const raf = useRef<number>();

  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setVal(to * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
      else setVal(to);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [to, duration]);

  const display = format
    ? format(val)
    : Math.round(val).toLocaleString("en-IN");
  return <span className={`metric ${className ?? ""}`}>{display}</span>;
}
