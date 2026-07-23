import type { Metadata } from "next";
import Script from "next/script";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Shell } from "@/components/Shell";

// Render's free tier spins services down after ~15min idle; waking one up
// takes 40-70s (and the backend's own call to Codebook can add another
// 40-70s on top if that one's also cold). Firing these pings the instant the
// HTML starts parsing — before React hydrates, before any component mounts —
// shaves that whole window off the time-to-first-real-request. Fire-and-forget:
// we never read the response, just need Render to see traffic and boot the dyno.
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const CODEBOOK_URL = (
  process.env.NEXT_PUBLIC_CODEBOOK_URL || "https://sitemind-codebook.onrender.com"
).replace(/\/$/, "");

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SiteMind — Command Center",
  description:
    "Blueprint Intelligence — AI compliance, copilot and schedule risk for construction megaprojects.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable}`}
    >
      <body>
        <Script id="warm-backend" strategy="beforeInteractive">
          {`
            (function () {
              function ping(url) {
                try {
                  fetch(url, { method: "GET", mode: "no-cors", cache: "no-store", keepalive: true });
                } catch (e) {}
              }
              ping(${JSON.stringify(`${API_URL}/api/health`)});
              ping(${JSON.stringify(`${CODEBOOK_URL}/health`)});
            })();
          `}
        </Script>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
