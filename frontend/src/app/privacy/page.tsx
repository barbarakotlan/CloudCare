import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage, LegalSection, Placeholder } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "CloudCare's Privacy Policy is being written and will be published here.",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      meta={
        <p>
          <span className="font-bold text-ink">Status:</span> coming soon
        </p>
      }
    >
      <LegalSection id="coming-soon" title="Privacy Policy, coming soon">
        <p>
          We are writing a Privacy Policy that will explain how CloudCare collects, uses, and protects your
          information. It will be published on this page.
        </p>
        <p>
          Until then, our <Link href="/terms#privacy-security">Terms and Conditions</Link> describe how CloudCare
          protects your information today. If you have questions, contact us at{" "}
          <Placeholder>CloudCare contact email</Placeholder>.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
