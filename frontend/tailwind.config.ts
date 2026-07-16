import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          900: "var(--bg-900)",
          800: "var(--bg-800)",
          700: "var(--bg-700)",
          600: "var(--bg-600)",
        },
        line: "var(--line)",
        text: {
          hi: "var(--text-hi)",
          mid: "var(--text-mid)",
          lo: "var(--text-lo)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          300: "var(--accent-300)",
          600: "var(--accent-600)",
        },
        data: "var(--data)",
        critical: "var(--critical)",
        warning: "var(--warning)",
        pass: "var(--pass)",
        info: "var(--info)",
      },
      fontFamily: {
        display: ["var(--font-display)", "Space Grotesk", "sans-serif"],
        sans: ["var(--font-sans)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        chip: "4px",
        card: "10px",
      },
      boxShadow: {
        glow: "0 0 0 1px var(--accent-glow), 0 0 24px -4px var(--accent-glow)",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(0)", opacity: "0" },
          "10%": { opacity: "1" },
          "90%": { opacity: "1" },
          "100%": { transform: "translateY(100%)", opacity: "0" },
        },
        pulseGlow: {
          "0%,100%": { boxShadow: "0 0 0 0 var(--accent-glow)" },
          "50%": { boxShadow: "0 0 0 6px transparent" },
        },
        blink: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.25" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        scan: "scan 1.6s linear infinite",
        pulseGlow: "pulseGlow 1.4s ease-in-out infinite",
        blink: "blink 1s ease-in-out infinite",
        fadeUp: "fadeUp 240ms ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
