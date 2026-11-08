import type { Metadata } from "next";
import Link from "next/link";
import { Callout, CounselNote, LegalPage, LegalSection, Placeholder, type TocEntry } from "@/components/legal/LegalPage";
import { SalesBubble } from "@/components/sales/SalesBubble";

export const metadata: Metadata = {
  title: "Terms and Conditions",
  description:
    "The terms for using CloudCare: the medical disclaimer, shared demo accounts, automated phone calls and texts, the optional Epic MyChart test connection, the limits of Foggy's AI-generated answers, and our warranty and liability terms.",
};

const TOC: TocEntry[] = [
  { id: "about", label: "1. About CloudCare" },
  { id: "eligibility", label: "2. Who can use CloudCare" },
  { id: "medical-disclaimer", label: "3. Medical Disclaimer" },
  { id: "demo-accounts", label: "4. Demo Accounts" },
  { id: "account-responsibilities", label: "5. Account Responsibilities" },
  { id: "ai-generated-information", label: "6. Foggy and AI-Generated Information" },
  { id: "phone", label: "7. Phone Calls and Texts" },
  { id: "epic-mychart", label: "8. Epic MyChart Connection" },
  { id: "patient-authorization", label: "9. Patient Authorization" },
  { id: "data-usage", label: "10. Data Usage" },
  { id: "privacy-security", label: "11. Privacy and Security" },
  { id: "acceptable-use", label: "12. Acceptable Use" },
  { id: "third-parties", label: "13. Third-Party Services" },
  { id: "service-availability", label: "14. Service Availability" },
  { id: "warranty", label: "15. No Warranties" },
  { id: "liability", label: "16. Limitation of Liability" },
  { id: "law", label: "17. Governing Law and Disputes" },
  { id: "contact", label: "18. Contact Information" },
  { id: "changes", label: "Changes to these Terms" },
  { id: "acceptance", label: "Acceptance" },
];

export default function TermsPage() {
  return (
    <>
    <LegalPage
      title="Terms and Conditions"
      toc={TOC}
      meta={
        <>
          <p>
            <span className="font-bold text-ink">Last updated:</span> 8 November 2026
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
          and ask questions to Foggy, CloudCare&rsquo;s automated recovery assistant.
        </p>
        <p>
          CloudCare is provided by <Placeholder>Legal entity name</Placeholder> (&ldquo;CloudCare,&rdquo;
          &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;). These Terms and Conditions (&ldquo;Terms&rdquo;)
          are the rules for using the CloudCare website and app, including the demos on our home page (the
          &ldquo;Service&rdquo;). Please read them carefully.
        </p>
        <p>
          <strong>CloudCare is an early-stage service.</strong> It is still being tested and improved, and some features
          may change.
        </p>
      </LegalSection>

      <LegalSection id="eligibility" number={2} title="Who can use CloudCare">
        <ul>
          <li>You must be at least 18 years old.</li>
          <li>
            CloudCare is offered in the United States only. Phone calls and texts go only to numbers with the +1
            country code.
          </li>
          <li>Use CloudCare for your own recovery. Do not create an account for someone else.</li>
        </ul>
      </LegalSection>

      <LegalSection id="medical-disclaimer" number={3} title="Medical Disclaimer">
        <p>
          CloudCare gives information and support to help you follow the care plan from your care team. It does{" "}
          <strong>not</strong> give medical advice, diagnosis, or treatment. It does not replace your doctor, nurse, or
          anyone else on your care team. Using CloudCare does not create a doctor-patient or other care relationship
          with us.
        </p>
        <p>
          CloudCare is not intended to diagnose, treat, cure, or prevent any disease or condition, and it has not been
          reviewed, cleared, or approved by the U.S. Food and Drug Administration (FDA).
        </p>
        <p>
          CloudCare is <strong>not an emergency service</strong>. It does not watch your health in real time. Nobody
          monitors CloudCare around the clock, and your care team may not see a message or alert for hours or days.
        </p>
        <Callout tone="alert">
          In an emergency, call 911 or your local emergency number right away. Do not wait for a reply from CloudCare or
          Foggy. Foggy cannot call 911 for you.
        </Callout>
        <p>
          <strong>Check-in results are estimates.</strong> When you finish a check-in, CloudCare may show a risk level.
          It comes from an experimental computer model that was built using made-up (synthetic) practice data, not
          real patient records. It is not a medical assessment. A &ldquo;low&rdquo; result does not mean you are safe,
          and a &ldquo;high&rdquo; result does not mean something is wrong. If you are worried, contact your care team.
        </p>
        <p>
          Always follow the instructions from your care team. If something in CloudCare seems different from what your
          care team told you, follow your care team and contact them with your question.
        </p>
      </LegalSection>

      <LegalSection id="demo-accounts" number={4} title="Demo Accounts">
        <p>
          Our sign-in page shows demo accounts, with their passwords, so anyone can try CloudCare. The demo patient,
          &ldquo;Jordan Lee,&rdquo; is fictional, and so is the demo clinician.
        </p>
        <ul>
          <li>
            <strong>Demo accounts are shared and public.</strong> Anything you type or save in them, including chat
            messages, check-ins, and phone numbers, can be seen and changed by anyone else who signs in.
          </li>
          <li>
            <strong>Anyone can reset the demo.</strong> A reset deletes the demo patient&rsquo;s messages, check-ins,
            alerts, and dose history for everyone.
          </li>
          <li>
            <strong>Do not enter real health information</strong>, real names, or anyone&rsquo;s real contact details
            in a demo account.
          </li>
          <li>
            Do not save a phone number in a demo account unless it is your own, and remove it when you are done. Never
            enter someone else&rsquo;s number.
          </li>
        </ul>
        <p>
          The check-in call on our home page is a dramatized sample made with computer-generated voices, with the
          fictional demo patient. It shows what a check-in call can sound like, not a call with a real patient. Some
          lines in it do not match what Foggy does today: for example, Foggy does not give advice about missed doses and
          does not schedule calls for the next day.
        </p>
      </LegalSection>

      <LegalSection id="account-responsibilities" number={5} title="Account Responsibilities">
        <p>To use most features, you need a CloudCare account. When you use your own account, you agree to:</p>
        <ul>
          <li>Keep your password and other login details private and secure.</li>
          <li>Give us information that is accurate and up to date, including a mobile number that is your own.</li>
          <li>Use your account only for yourself, and sign out when you use a shared or public device.</li>
          <li>
            Tell us right away if you think someone used your account without your permission. Contact us at{" "}
            <Placeholder>CloudCare contact email</Placeholder>.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="ai-generated-information" number={6} title="Foggy and AI-Generated Information">
        <p>
          Foggy is CloudCare&rsquo;s recovery assistant. <strong>Foggy is not a person.</strong> Foggy&rsquo;s
          responses, in text, in voice conversations, and on phone calls, are generated by artificial intelligence (AI)
          and spoken with a computer-generated voice. Please keep these limits in mind:
        </p>
        <ul>
          <li>
            <strong>AI can make mistakes.</strong> Foggy&rsquo;s answers may contain errors, leave out important
            details, or word something differently from your care plan.
          </li>
          <li>
            <strong>Foggy is designed to stay within your care plan.</strong> It is built to answer care questions only
            from the care plan your care team provided, but a language model writes the wording, so it can still get
            things wrong. On voice calls, Foggy also handles greetings and small talk on its own. Check important
            details against your written plan.
          </li>
          <li>
            <strong>Foggy offers before it sends.</strong> If your care plan does not cover a question, Foggy is
            designed to say so instead of guessing, and to offer to message your care team. Nothing is sent without
            your OK. A message goes into your care team&rsquo;s queue; it does not mean anyone has read it yet.
          </li>
          <li>
            <strong>Foggy cannot call 911.</strong> If you mention an emergency warning sign, such as chest pain or
            trouble breathing, Foggy tells you to call 911 yourself. It cannot place emergency calls for you.
          </li>
          <li>
            <strong>Your care team comes first.</strong> Foggy&rsquo;s answers never override instructions from your
            doctors, nurses, or other qualified healthcare professionals.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="phone" number={7} title="Phone Calls and Texts">
        <p>
          If you add a mobile number, you can ask Foggy to call or text you from your dashboard. Here is how that works:
        </p>
        <ul>
          <li>
            <strong>Only when you ask.</strong> CloudCare calls or texts only after you press &ldquo;Call me&rdquo; or
            &ldquo;Text me,&rdquo; and only once each time you press. We do not schedule follow-up calls, and we do not
            send marketing calls or texts.
          </li>
          <li>
            <strong>Your consent.</strong> By pressing &ldquo;Call me&rdquo; or &ldquo;Text me,&rdquo; you ask
            CloudCare to place one automated call, using an AI-generated voice, or send one automated text to the
            mobile number saved on your account. You confirm that the number is yours or that you are allowed to use
            it.
          </li>
          <li>
            <strong>Only your own number.</strong> CloudCare calls or texts only the number saved on your account. It
            never calls 911 or other emergency or service numbers.
          </li>
          <li>
            <strong>Who is calling.</strong> Calls and texts come from CloudCare&rsquo;s phone number. Foggy introduces
            itself by name and says it is calling about your recovery check-in.
          </li>
          <li>
            <strong>Stopping.</strong> You can hang up at any time, or tell Foggy it is not a good time and it will end
            the call. To stop calls and texts completely, remove your number from your dashboard. You can reply STOP
            to any text to stop texts.
          </li>
          <li>
            <strong>Not recorded.</strong> We do not record the audio of calls. A written transcript is kept, as
            described in our <Link href="/privacy">Privacy Policy</Link>.
          </li>
          <li>
            <strong>Charges.</strong> Your mobile carrier&rsquo;s normal message and data rates may apply.
          </li>
          <li>
            Texting may not be available yet. The dashboard shows which options are turned on.
          </li>
        </ul>
        <CounselNote>
          Confirm the consent basis for patient-initiated automated calls that use an AI-generated voice (47 CFR
          64.1200), and whether up-front automation disclosure and a spoken opt-out are needed on every call.
        </CounselNote>
      </LegalSection>

      <LegalSection id="epic-mychart" number={8} title="Epic MyChart Connection">
        <p>
          CloudCare is building an optional connection to MyChart. <strong>Today it works only with Epic&rsquo;s
          public test (sandbox) environment</strong>, using Epic&rsquo;s made-up test patients. It cannot connect to
          a real MyChart account yet. The connection uses SMART on FHIR, a standard way for health apps to read records
          with a patient&rsquo;s permission. You sign in on Epic&rsquo;s own page, so CloudCare never sees the MyChart
          password.
        </p>
        <p>With permission, CloudCare can read these types of records:</p>
        <ul>
          <li>
            <strong>Medication orders</strong>: medicines prescribed by the care team.
          </li>
          <li>
            <strong>Medication details</strong>: more information about those medicines.
          </li>
          <li>
            <strong>Lab results</strong>: results from tests such as blood work.
          </li>
          <li>
            <strong>Past visits</strong>: appointments and other visits with the health system.
          </li>
          <li>
            <strong>Clinical notes</strong>: notes written by the care team.
          </li>
        </ul>
        <p>
          We ask only for the information needed for CloudCare&rsquo;s recovery features. CloudCare can read these
          records, but it cannot change records in MyChart. Not every health system shares every type of record, so
          some information may be missing or out of date.
        </p>
        <p className="text-sm text-brand-gray">
          Epic and MyChart are trademarks of Epic Systems Corporation. CloudCare is not affiliated with, endorsed by,
          or sponsored by Epic Systems Corporation.
        </p>
      </LegalSection>

      <LegalSection id="patient-authorization" number={9} title="Patient Authorization">
        <ul>
          <li>
            <strong>Connecting is optional.</strong> You can use CloudCare without connecting MyChart.
          </li>
          <li>
            <strong>You choose.</strong> CloudCare reads MyChart records only after you sign in on Epic&rsquo;s page
            and agree.
          </li>
          <li>
            <strong>You can disconnect in CloudCare at any time.</strong> When you disconnect, CloudCare deletes the
            stored connection and its access tokens and stops reading information from MyChart.
          </li>
          <li>
            <strong>You can also remove access in MyChart.</strong> MyChart lets you manage which apps are connected to
            your account.
          </li>
        </ul>
        <p>
          If you disconnect, features that use MyChart records may stop working or show less information.
        </p>
      </LegalSection>

      <LegalSection id="data-usage" number={10} title="Data Usage">
        <p>
          We use the information you give us, and the records you choose to share from MyChart, only to provide
          CloudCare&rsquo;s recovery features. This includes:
        </p>
        <ul>
          <li>Showing your records in your CloudCare dashboard.</li>
          <li>Helping Foggy answer your questions from your care plan.</li>
          <li>Supporting symptom check-ins.</li>
          <li>Calling or texting your phone when you ask.</li>
          <li>
            Messaging your care team when you agree to it. Foggy offers first and sends nothing without your OK.
            High-risk check-in results and emergency warning signs also appear as alerts in your care team&rsquo;s
            queue.
          </li>
        </ul>
        <p>
          The care team assigned to you can see your check-ins and your conversations with Foggy so they can follow up
          with you. A new account has no care team until one is assigned.
        </p>
        <Callout>We do not sell your information. We do not use your information for advertising.</Callout>
        <p>
          Our <Link href="/privacy">Privacy Policy</Link> explains what we collect, which companies process it for us,
          and the choices you have.
        </p>
      </LegalSection>

      <LegalSection id="privacy-security" number={11} title="Privacy and Security">
        <p>We take steps to protect your information. Today, CloudCare works like this:</p>
        <ul>
          <li>
            The CloudCare website and the server it talks to use HTTPS, which encrypts information while it travels
            over the internet.
          </li>
          <li>You sign in through an authentication (login) provider.</li>
          <li>
            If you connect MyChart, the digital keys (called tokens) that let CloudCare read records are stored
            encrypted at rest on our server. They are never sent to or stored in your web browser.
          </li>
          <li>Only you, when signed in to your own account, can view your MyChart records in CloudCare.</li>
        </ul>
        <p>
          <strong>HIPAA.</strong> CloudCare is not offered by your health care provider. At this early stage, CloudCare
          is not operating as a HIPAA covered entity or as a business associate of a health care provider, and we
          have not signed business associate agreements with the companies that process information for us. This
          means information you give CloudCare does not have the same legal protections as the records your doctor
          keeps. Please keep this in mind before you enter health information.
        </p>
        <CounselNote>
          Confirm HIPAA status before any pilot with a health system, and whether the FTC Health Breach Notification
          Rule (16 CFR Part 318) and state consumer health data laws apply.
        </CounselNote>
        <p>
          No website or app can be perfectly secure. You can help protect your account by keeping your login details
          private.
        </p>
      </LegalSection>

      <LegalSection id="acceptable-use" number={12} title="Acceptable Use">
        <p>When you use CloudCare, you agree not to:</p>
        <ul>
          <li>Enter someone else&rsquo;s phone number, or use calls or texts to bother anyone.</li>
          <li>Enter real health information into a shared demo account.</li>
          <li>Try to get Foggy to ignore its safety rules, or present Foggy&rsquo;s answers as advice from a clinician.</li>
          <li>Try to access other people&rsquo;s accounts or data, or test, probe, or overload our systems without permission.</li>
          <li>Use automated tools to copy, scrape, or flood the Service.</li>
          <li>Break any law while using CloudCare.</li>
        </ul>
        <p>We may limit, suspend, or close an account that breaks these rules.</p>
      </LegalSection>

      <LegalSection id="third-parties" number={13} title="Third-Party Services">
        <p>
          CloudCare relies on other companies to run, such as our hosting, sign-in, voice, phone, and language-model
          providers, and Epic for the MyChart connection. Our <Link href="/privacy">Privacy Policy</Link> lists them.
          Their services have their own terms, and we are not responsible for how they work or for outages on their
          side. Signing in to MyChart on Epic&rsquo;s page is covered by Epic&rsquo;s and your health system&rsquo;s
          terms.
        </p>
      </LegalSection>

      <LegalSection id="service-availability" number={14} title="Service Availability">
        <p>
          CloudCare is an early-stage service. We may change, pause, or stop any feature, or the whole Service, at any
          time. The Service may sometimes be slow or unavailable, for example during updates or outages, or when our
          server is waking up.
        </p>
        <p>
          We do not guarantee that CloudCare will always be available or free of errors. Do not rely on CloudCare as
          your only way to reach your care team. Keep your care team&rsquo;s phone number where you can find it.
        </p>
        <p>
          You can stop using CloudCare at any time and ask us to delete your account (see our{" "}
          <Link href="/privacy">Privacy Policy</Link>).
        </p>
      </LegalSection>

      <LegalSection id="warranty" number={15} title="No Warranties">
        <p>
          CloudCare is an early-stage service, and we provide it <strong>&ldquo;as is&rdquo;</strong> and{" "}
          <strong>&ldquo;as available.&rdquo;</strong> To the fullest extent the law allows, we make no promises or
          warranties of any kind, whether stated or implied. This includes any promise that CloudCare will be
          accurate, complete, reliable, safe, available, or free of errors, or that it will fit your particular needs.
          It also includes implied warranties of merchantability, fitness for a particular purpose, and
          non-infringement.
        </p>
        <p>
          We do not promise that Foggy&rsquo;s answers, check-in risk levels, reminders, or MyChart records will be
          correct or up to date, or that a message or alert will be seen by your care team within any period of time.
        </p>
        <p>Some states do not allow these limits, so some of them may not apply to you.</p>
        <CounselNote>
          Plain-language draft. Confirm wording, conspicuousness requirements, and state-law carve-outs.
        </CounselNote>
      </LegalSection>

      <LegalSection id="liability" number={16} title="Limitation of Liability">
        <p>To the fullest extent the law allows:</p>
        <ul>
          <li>
            We are not responsible for indirect, incidental, special, consequential, or punitive damages, or for lost
            data, lost profits, or similar losses, that come from using or not being able to use CloudCare, even if we
            were told they might happen.
          </li>
          <li>
            We are not responsible for decisions you or anyone else makes based on information from CloudCare,
            including Foggy&rsquo;s answers and check-in risk levels.
          </li>
          <li>
            Our total responsibility to you for all claims about CloudCare is limited to the greater of the amount you
            paid us to use CloudCare in the 12 months before the claim, or{" "}
            <Placeholder>Liability cap amount, for example US$100</Placeholder>. CloudCare is free today.
          </li>
        </ul>
        <p>
          Nothing in these Terms limits responsibility that the law does not allow us to limit, such as for fraud,
          gross negligence, willful misconduct, or, where applicable, death or personal injury caused by our
          negligence. Some states do not allow these limits, so some of them may not apply to you.
        </p>
        <CounselNote>
          Plain-language draft. Confirm the cap, carve-outs for personal injury in a health context, enforceability
          against consumers, and whether an indemnity clause is wanted (none is included).
        </CounselNote>
      </LegalSection>

      <LegalSection id="law" number={17} title="Governing Law and Disputes">
        <p>
          These Terms are governed by the laws of <Placeholder>Governing law</Placeholder>, without regard to its
          conflict-of-laws rules. Any dispute about these Terms or CloudCare will be handled in the courts of{" "}
          <Placeholder>Venue / jurisdiction</Placeholder>, unless the law where you live gives you the right to bring
          it somewhere else.
        </p>
        <p>
          Before bringing a formal claim, please contact us first so we can try to resolve the problem informally.
        </p>
        <CounselNote>
          Owner decision pending on dispute resolution. No arbitration clause or class-action waiver is included.
        </CounselNote>
      </LegalSection>

      <LegalSection id="contact" number={18} title="Contact Information">
        <p>If you have questions about these Terms or about your data, contact us:</p>
        <ul>
          <li>
            <strong>Email:</strong> <Placeholder>CloudCare contact email</Placeholder>
          </li>
          <li>
            <strong>Mail:</strong> <Placeholder>Mailing address, if applicable</Placeholder>
          </li>
        </ul>
        <p>
          If something in CloudCare is hard to use with a screen reader, keyboard, or other assistive technology, please
          tell us so we can fix it.
        </p>
        <p>For medical questions, contact your care team. In an emergency, call 911.</p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to these Terms">
        <p>
          We may update these Terms from time to time. When we do, we will change the &ldquo;Last updated&rdquo; date at
          the top of this page. If a change is important, we will tell you through CloudCare or by email at least{" "}
          <Placeholder>Notice period, for example 30 days</Placeholder> before it takes effect, unless the change is
          needed sooner for legal or safety reasons. If you keep using CloudCare after a change takes effect, the new
          Terms apply. If you do not agree, stop using CloudCare.
        </p>
      </LegalSection>

      <LegalSection id="acceptance" title="Acceptance">
        <p>
          By using CloudCare, including the demos on our home page, or by creating an account, signing in, or
          connecting MyChart, you agree to these Terms. If you do not agree, please do not use CloudCare.
        </p>
      </LegalSection>
    </LegalPage>
    <SalesBubble />
    </>
  );
}
