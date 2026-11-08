import { Audiences } from "@/components/landing/Audiences";
import { ClosingCta } from "@/components/landing/ClosingCta";
import { DemoProvider } from "@/components/landing/DemoProvider";
import { HearFoggy } from "@/components/landing/HearFoggy";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { OurPromise } from "@/components/landing/Promise";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { SalesBubble } from "@/components/sales/SalesBubble";

export default function HomePage() {
  return (
    <DemoProvider>
      <SiteHeader />
      <main id="main" className="flex-1">
        <Hero />
        <HearFoggy />
        <HowItWorks />
        <OurPromise />
        <Audiences />
        <ClosingCta />
      </main>
      <SiteFooter />
      <SalesBubble />
    </DemoProvider>
  );
}
