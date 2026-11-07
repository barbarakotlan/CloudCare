import type { Metadata } from "next";
import Link from "next/link";
import { Callout, LegalPage, LegalSection, Placeholder, type TocEntry } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Terms and Conditions",
  description:
    "The terms for using CloudCare, including the medical disclaimer, how the optional Epic MyChart connection works, how authorized information is used, and the limits of Foggy's AI-generated answers.",
};

const TOC: TocEntry[] = [
  { id: "about", label: "1. About CloudCare" },
  { id: "medical-disclaimer", label: "2. Medical Disclaimer" },
  { id: "account-responsibilities", label: "3. Account Responsibilities" },
  { id: "epic-mychart", label: "4. Epic MyChart Integration" },
  { id: "patient-authorization", label: "5. Patient Authorization" },
  { id: "data-usage", label: "6. Data Usage" },
  { id: "ai-generated-information", label: "7. AI-Generated Information" },
  { id: "privacy-security", label: "8. Privacy and Security" },
  { id: "service-availability", label: "9. Service Availability" },
  { id: "contact", label: "10. Contact Information" },
  { id: "changes", label: "Changes to these Terms" },
  { id: "acceptance", label: "Acceptance" },
];

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms and Conditions"
      toc={TOC}
      meta={
        <>
          <p>
            <span className="font-bold text-ink">Last updated:</span> 7 November 2026
          </p>
          <p>
            <span className="font-bold text-ink">Effective date:</span>{" "}
            <Placeholder>Effective date, if different from the last-updated date</Placeholder>
          </p>
        </>
      }
    >
      <LegalSection id="about" number={1} title="About CloudCare">
        <p>
          CloudCare is an AI-powered platform that helps patients recover after surgery. It brings your care
          team&rsquo;s recovery plan home with you. You can read your plan, get reminders, check in about how you feel,
          and ask questions to Foggy, CloudCare&rsquo;s recovery assistant.
        </p>
        <p>
          CloudCare is provided by <Placeholder>Legal entity name</Placeholder> (&ldquo;CloudCare,&rdquo;
          &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;). These Terms and Conditions (&ldquo;Terms&rdquo;)
          are the rules for using the CloudCare website and app (the &ldquo;Service&rdquo;). Please read them carefully.
        </p>
        <p>
          <strong>CloudCare is a prototype.</strong> It was built for a hackathon and is still being tested and
          improved. It is not a finished product.
        </p>
      </LegalSection>

      <LegalSection id="medical-disclaimer" number={2} title="Medical Disclaimer">
        <p>
          CloudCare gives information and support to help you follow the care plan from your care team. It does{" "}
          <strong>not</strong> give medical advice, diagnosis, or treatment. It does not replace your doctor, nurse, or
          anyone else on your care team.
        </p>
        <p>
          CloudCare is <strong>not an emergency service</strong>. It does not watch your health in real time, and your
          care team may not see a message or alert right away.
        </p>
        <Callout tone="alert">
          In an emergency, call 911 or your local emergency number right away. Do not wait for a reply from CloudCare or
          Foggy.
        </Callout>
        <p>
          Always follow the instructions from your care team. If something in CloudCare seems different from what your
          care team told you, follow your care team and contact them with your question.
        </p>
      </LegalSection>

      <LegalSection id="account-responsibilities" number={3} title="Account Responsibilities">
        <p>To use most features, you need a CloudCare account. When you use your account, you agree to:</p>
        <ul>
          <li>Keep your password and other login details private and secure.</li>
          <li>Give us information that is accurate and up to date.</li>
          <li>Use your account only for yourself, and sign out when you use a shared or public device.</li>
          <li>
            Tell us right away if you think someone used your account without your permission. Contact us at{" "}
            <Placeholder>CloudCare contact email</Placeholder>.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="epic-mychart" number={4} title="Epic MyChart Integration">
        <p>
          If your health system uses Epic, you can choose to connect your MyChart account to CloudCare. The connection
          uses Epic&rsquo;s SMART on FHIR APIs, a standard way for health apps to read records with a patient&rsquo;s
          permission. You sign in on MyChart&rsquo;s own page, so CloudCare never sees your MyChart password.
        </p>
        <p>With your permission, CloudCare can read these types of records:</p>
        <ul>
          <li>
            <strong>Medication orders</strong>: medicines your care team has prescribed for you.
          </li>
          <li>
            <strong>Medication details</strong>: more information about those medicines.
          </li>
          <li>
            <strong>Lab results</strong>: results from tests such as blood work.
          </li>
          <li>
            <strong>Past visits</strong>: appointments and other visits with your health system.
          </li>
          <li>
            <strong>Clinical notes</strong>: notes written by your care team.
          </li>
        </ul>
        <p>
          We ask only for the information needed for CloudCare&rsquo;s recovery features. CloudCare can read these
          records, but it cannot change your records in MyChart.
        </p>
        <p>
          Not every health system shares every type of record, so some information may be missing or out of date. If
          you have questions about your records, ask your care team.
        </p>
        <p className="text-sm text-brand-gray">Epic and MyChart are trademarks of Epic Systems Corporation.</p>
      </LegalSection>

      <LegalSection id="patient-authorization" number={5} title="Patient Authorization">
        <ul>
          <li>
            <strong>Connecting is optional.</strong> You can use CloudCare without connecting MyChart.
          </li>
          <li>
            <strong>You choose.</strong> CloudCare reads your MyChart records only if you sign in to MyChart and agree.
          </li>
          <li>
            <strong>You can disconnect in CloudCare at any time.</strong> When you disconnect, CloudCare removes the
            stored connection to your MyChart account and stops reading new information from MyChart.
          </li>
          <li>
            <strong>You can also remove access in MyChart.</strong> MyChart lets you manage which apps are connected to
            your account.
          </li>
        </ul>
        <p>
          If you disconnect, features that use your MyChart records may stop working or show less information.
        </p>
      </LegalSection>

      <LegalSection id="data-usage" number={6} title="Data Usage">
        <p>
          We use the information you give us, and the records you choose to share from MyChart, only to provide
          CloudCare&rsquo;s recovery features. This includes:
        </p>
        <ul>
          <li>Showing your records in your CloudCare dashboard.</li>
          <li>Helping Foggy answer your questions from your care plan.</li>
          <li>
            Supporting symptom check-ins and sending alerts to your care team when something may need their attention.
          </li>
        </ul>
        <p>
          Your care team can see your check-ins and your conversations with Foggy so they can follow up with you.
        </p>
        <Callout>We do not sell your information. We do not use your information for advertising.</Callout>
        <p>
          If you have questions about your data, contact us at <Placeholder>CloudCare contact email</Placeholder> to
          ask about it.
        </p>
      </LegalSection>

      <LegalSection id="ai-generated-information" number={7} title="AI-Generated Information">
        <p>
          Foggy is CloudCare&rsquo;s recovery assistant. Foggy&rsquo;s responses, in text and in voice conversations,
          are generated by artificial intelligence (AI). Please keep these limits in mind:
        </p>
        <ul>
          <li>
            <strong>AI can make mistakes.</strong> Foggy&rsquo;s answers may contain errors or leave out important
            details.
          </li>
          <li>
            <strong>Foggy is limited to your care plan.</strong> It is designed to answer only from the care plan your
            care team provided.
          </li>
          <li>
            <strong>Questions outside your plan go to your care team.</strong> If your care plan does not cover a
            question, Foggy is designed not to guess. Instead, it sends the question to your care team.
          </li>
          <li>
            <strong>Your care team comes first.</strong> Foggy&rsquo;s answers never override instructions from your
            doctors, nurses, or other qualified healthcare professionals.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="privacy-security" number={8} title="Privacy and Security">
        <p>We take steps to protect your information. Today, CloudCare works like this:</p>
        <ul>
          <li>
            The CloudCare website and the server it talks to use HTTPS, which encrypts information while it travels
            over the internet.
          </li>
          <li>You sign in through an authentication (login) provider.</li>
          <li>
            If you connect MyChart, the digital keys (called tokens) that let CloudCare read your records are stored
            encrypted at rest on our server. They are never sent to or stored in your web browser.
          </li>
          <li>Only you, when signed in to your own account, can view your MyChart records in CloudCare.</li>
        </ul>
        <p>
          No website or app can be perfectly secure. You can help protect your account by keeping your login details
          private.
        </p>
        <p>
          We will publish a separate Privacy Policy that explains in more detail how we collect, use, and protect your
          information: <Link href="/privacy">[Privacy Policy, coming soon]</Link>.
        </p>
      </LegalSection>

      <LegalSection id="service-availability" number={9} title="Service Availability">
        <p>
          CloudCare is a prototype. We may change, pause, or stop any feature at any time. The Service may sometimes be
          slow or unavailable, for example during updates or outages.
        </p>
        <p>
          We do not guarantee that CloudCare will always be available or free of errors. Do not rely on CloudCare as
          your only way to reach your care team. Keep your care team&rsquo;s phone number where you can find it.
        </p>
      </LegalSection>

      <LegalSection id="contact" number={10} title="Contact Information">
        <p>If you have questions about these Terms or about your data, contact us:</p>
        <ul>
          <li>
            <strong>Email:</strong> <Placeholder>CloudCare contact email</Placeholder>
          </li>
          <li>
            <strong>Mail:</strong> <Placeholder>Mailing address, if applicable</Placeholder>
          </li>
        </ul>
        <p>For medical questions, contact your care team. In an emergency, call 911.</p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to these Terms">
        <p>
          We may update these Terms from time to time. When we do, we will change the &ldquo;Last updated&rdquo; date at
          the top of this page. If the changes are important, we will let you know through CloudCare. These Terms are
          governed by the laws of <Placeholder>Governing law and jurisdiction</Placeholder>.
        </p>
      </LegalSection>

      <LegalSection id="acceptance" title="Acceptance">
        <p>
          By creating an account, signing in, or connecting MyChart, you agree to these Terms. If you do not agree,
          please do not use CloudCare.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
