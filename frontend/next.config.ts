import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

/** Origin (scheme://host[:port]) of a configured URL, or null when unset or invalid. */
function originOf(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

const apiOrigin = originOf(process.env.NEXT_PUBLIC_API_URL) ?? "http://localhost:8000";
const supabaseOrigin = originOf(process.env.NEXT_PUBLIC_SUPABASE_URL);
const supabaseWs = supabaseOrigin ? supabaseOrigin.replace(/^http/, "ws") : null;

/**
 * Content-Security-Policy (docs/security-review.md).
 *
 * - Scripts: same origin only. 'unsafe-inline' is required because pages are static
 *   shells (cacheComponents) and Next.js inlines its bootstrap scripts; nonces would
 *   force every page to render per request. 'unsafe-eval' only in `next dev`.
 * - Voice (ElevenLabs): the SDK fetches a token from api.elevenlabs.io, talks to
 *   LiveKit over WebSocket, and loads audio worklets from blob: URLs (or a pinned
 *   jsdelivr file when resampling is needed).
 * - connect-src: our API, Supabase (auth + realtime) and ElevenLabs only.
 * - The MyChart popup navigates to Epic; navigation isn't governed by CSP, and no
 *   Cross-Origin-Opener-Policy is set so the popup can post back to its opener.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} blob: https://cdn.jsdelivr.net/npm/@alexanderolsen/libsamplerate-js@2.1.2/`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "media-src 'self' blob: data:",
  [
    "connect-src 'self'",
    apiOrigin,
    supabaseOrigin,
    supabaseWs,
    "https://api.elevenlabs.io wss://api.elevenlabs.io",
    "https://*.elevenlabs.io wss://*.elevenlabs.io",
    isDev ? "ws://localhost:* ws://127.0.0.1:*" : null,
  ]
    .filter(Boolean)
    .join(" "),
  "worker-src 'self' blob:",
  "frame-src 'none'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  isDev ? null : "upgrade-insecure-requests",
]
  .filter(Boolean)
  .join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  // Two years; Vercel serves only HTTPS. No preload until the team decides to submit the domain.
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Microphone for "Talk to Foggy" on our own pages only; everything else off.
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=(), payment=(), usb=()" },
];

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
