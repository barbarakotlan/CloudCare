import type { Metadata, Viewport } from "next";
import { Nunito } from "next/font/google";
import { SupabaseSessionSync } from "@/components/app/SupabaseSessionSync";
import { AUTH_PROVIDER_NAME } from "@/lib/auth/provider";
import "./globals.css";

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "CloudCare · Post-op recovery companion",
    template: "%s · CloudCare",
  },
  description:
    "Your head's in the clouds. Your care shouldn't be. CloudCare brings your care team's recovery plan home, with Foggy, a companion that answers only from your plan and brings in a human when it matters.",
  applicationName: "CloudCare",
  icons: {
    icon: [
      { url: "/brand/icon-64.png", sizes: "64x64", type: "image/png" },
      { url: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/brand/icon-192.png", sizes: "192x192", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${nunito.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only z-[100] rounded-full bg-brand-cyan px-5 py-3 font-bold text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>
        {AUTH_PROVIDER_NAME === "supabase" ? <SupabaseSessionSync /> : null}
        {children}
      </body>
    </html>
  );
}
