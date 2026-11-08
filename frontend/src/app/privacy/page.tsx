import type { Metadata } from "next";
import Link from "next/link";
import { Callout, LegalPage, LegalSection, Placeholder, type TocEntry } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "What information CloudCare collects, where it is stored, which service providers process it, how Foggy's answers are generated, and the choices you have.",
};

const TOC: TocEntry[] = [
  { id: "about", label: "1. About this policy" },
  { id: "what-we-collect", label: "2. Information we collect" },
  { id: "how-we-use", label: "3. How we use it" },
  { id: "foggy", label: "4. How Foggy's answers are made" },
  { id: "voice-phone", label: "5. Voice and phone calls" },
  { id: "mychart", label: "6. Epic MyChart connection" },
  { id: "sharing", label: "7. Who we share it with" },
  { id: "security", label: "8. How we protect it" },
  { id: "browser-storage", label: "9. Cookies and browser storage" },
  { id: "retention", label: "10. How long we keep it" },
  { id: "your-choices", label: "11. Your choices" },
  { id: "children", label: "12. Children" },
  { id: "changes", label: "Changes to this policy" },
  { id: "contact", label: "Contact us" },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      toc={TOC}
      meta={
        <>
          <p>
            <span className="font-bold text-ink">Last updated:</span> 8 November 2026
          </p>
          <p>
            <span className="font-bold text-ink">Effective date:</span>{" "}
            <Placeholder>Effective date</Placeholder>
          </p>
        </>
      }
    >
      <LegalSection id="about" number={1} title="About this policy">
        <p>
          CloudCare helps patients follow their recovery plan after surgery. This policy explains what information
          CloudCare collects, where it is kept, who helps us process it, and what you can do about it. It describes how
          the service works today.
        </p>
        <p>
          CloudCare is provided by <Placeholder>Legal entity name</Placeholder> (&ldquo;CloudCare,&rdquo;
          &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;). CloudCare is an early-stage service, so some
          features may change. When they do, we will update this page. Using CloudCare is also covered by our{" "}
          <Link href="/terms">Terms and Conditions</Link>.
        </p>
      </LegalSection>

      <LegalSection id="what-we-collect" number={2} title="Information we collect">
        <p>
          <strong>Account information.</strong> When you create an account, we collect your email address, your name,
          your password (handled by our sign-in provider, so we never see it in plain text), your role (patient or
          clinician), and, if you choose to give it, your mobile number.
        </p>
        <p>
          <strong>Recovery information.</strong> To run CloudCare we store:
        </p>
        <ul>
          <li>Your recovery profile: procedure, surgery and discharge dates, and health conditions your care team adds.</li>
          <li>The care plan your care team writes for you.</li>
          <li>Your symptom check-ins (for example pain level, medicines taken, falls) and the risk level calculated from them.</li>
          <li>Your conversations with Foggy, in text and in voice, saved as written messages.</li>
          <li>Medicine reminders, doses you mark as taken or skipped, and appointments.</li>
          <li>Alerts in your care team&rsquo;s queue and any notes your care team adds when they review them.</li>
        </ul>
        <p>
          <strong>Phone activity.</strong> If you ask Foggy to call you, we record that a call was requested, whether it
          started, and the last four digits of the number it went to.
        </p>
        <p>
          <strong>MyChart records.</strong> Only if you connect MyChart. See section 6.
        </p>
        <p>
          <strong>Technical information.</strong> Our servers keep basic logs, such as which feature was used, when, and
          whether it worked (status codes). These logs do not contain the text of your messages, your care plan, or
          your MyChart records.
        </p>
      </LegalSection>

      <LegalSection id="how-we-use" number={3} title="How we use it">
        <p>We use your information only to provide CloudCare&rsquo;s recovery features:</p>
        <ul>
          <li>Showing your care plan, reminders, and records in your dashboard.</li>
          <li>Letting Foggy answer your questions from your care plan.</li>
          <li>Running check-ins and showing your care team how your recovery is going.</li>
          <li>
            Messaging your care team when you ask Foggy to. Foggy offers first and sends nothing without your OK. Some
            check-in results or emergency warning signs also appear as alerts in your care team&rsquo;s queue.
          </li>
          <li>Calling your phone when you ask for a call.</li>
          <li>Keeping the service secure and fixing problems.</li>
        </ul>
        <Callout>We do not sell your information. We do not use it for advertising.</Callout>
      </LegalSection>

      <LegalSection id="foggy" number={4} title="How Foggy's answers are made">
        <p>
          Foggy&rsquo;s replies are written by a third-party language model, Google Gemini. When you send Foggy a
          message, our server sends Google the text of your care plan, your message, and a few of your recent messages
          so the reply fits the conversation. Google processes this information under its own terms for the Gemini API.
        </p>
        <p>
          Our own code decides what Foggy is allowed to do: it answers only from your care plan, never changes a dose,
          and, for emergency warning signs such as chest pain or trouble breathing, tells you to call 911. Foggy cannot
          place calls to 911.
        </p>
        <p>
          The &ldquo;Try texting Foggy&rdquo; demo on our home page is different: it runs entirely in your web browser
          with a sample care plan and does not send your messages to us or to Google.
        </p>
      </LegalSection>

      <LegalSection id="voice-phone" number={5} title="Voice and phone calls">
        <p>
          Talking to Foggy in your browser, and phone calls from Foggy, run through ElevenLabs. ElevenLabs processes
          your voice to turn it into text and turns Foggy&rsquo;s replies into speech. Each care question you ask is sent
          to our server and answered the same way as a text message.
        </p>
        <ul>
          <li>Recording of your voice is turned off by default.</li>
          <li>
            Under our current settings, ElevenLabs keeps a written transcript of each voice conversation for up to 30
            days.
          </li>
          <li>Your browser asks for microphone permission only when you press the button to start talking.</li>
        </ul>
        <p>
          Phone calls use a phone number provided by Twilio. ElevenLabs and Twilio handle the call itself and receive
          the number being called. CloudCare only calls the number saved on your own account, and only when you ask.
        </p>
      </LegalSection>

      <LegalSection id="mychart" number={6} title="Epic MyChart connection">
        <p>
          Connecting MyChart is optional. If you connect, you sign in on MyChart&rsquo;s own page, so CloudCare never
          sees your MyChart password. CloudCare currently connects through Epic&rsquo;s sandbox (test) environment.
        </p>
        <ul>
          <li>
            We store the connection details Epic gives us, including the access tokens that let CloudCare read your
            records. These tokens are encrypted at rest on our server and are never sent to your browser.
          </li>
          <li>
            Your MyChart records (medicines, lab results, visits, and notes) are read from Epic when you view them. We do
            not save copies of those records in our database.
          </li>
          <li>
            You can press <strong>Disconnect</strong> in your dashboard at any time. This deletes the stored connection
            and its tokens. You can also remove CloudCare&rsquo;s access from inside MyChart.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="sharing" number={7} title="Who we share it with">
        <p>
          <strong>Your care team.</strong> The clinician assigned to you can see your profile, care plan, check-ins,
          conversations with Foggy, alerts, and mobile number, so they can follow up with you.
        </p>
        <p>
          <strong>Service providers.</strong> These companies process information for us so CloudCare can work:
        </p>
        <ul>
          <li>
            <strong>Supabase</strong>: sign-in (Supabase Auth) and our database (Postgres hosted by Supabase), where your
            account, care plan, check-ins, messages, and alerts are stored.
          </li>
          <li>
            <strong>Render</strong>: hosts the CloudCare server (our API).
          </li>
          <li>
            <strong>Vercel</strong>: hosts the CloudCare website.
          </li>
          <li>
            <strong>Google (Gemini)</strong>: writes Foggy&rsquo;s replies, as described in section 4.
          </li>
          <li>
            <strong>ElevenLabs</strong>: voice conversations and phone calls, as described in section 5.
          </li>
          <li>
            <strong>Twilio</strong>: provides the phone number used for calls.
          </li>
          <li>
            <strong>Epic</strong>: only if you connect MyChart, as described in section 6.
          </li>
        </ul>
        <p>
          We may also share information if the law requires it. We do not share your information with advertisers or
          data brokers.
        </p>
      </LegalSection>

      <LegalSection id="security" number={8} title="How we protect it">
        <ul>
          <li>The website and our server use HTTPS, which encrypts information while it travels over the internet.</li>
          <li>Each request to our server must come from a signed-in account, and patients can see only their own data.</li>
          <li>Our database tables are closed to Supabase&rsquo;s public data interface; only our server reads them.</li>
          <li>MyChart tokens are encrypted at rest.</li>
          <li>Server logs record event names and status codes, not the text of your messages.</li>
        </ul>
        <p>
          No service can be perfectly secure. You can help by keeping your password private and signing out on shared
          devices.
        </p>
        <p>
          The demo accounts shown on our sign-in page are shared with everyone who tries CloudCare. Please do not enter
          real health information while using them.
        </p>
      </LegalSection>

      <LegalSection id="browser-storage" number={9} title="Cookies and browser storage">
        <p>
          CloudCare keeps your sign-in session in your browser&rsquo;s local storage so you stay signed in. After you
          connect MyChart, we set a short-lived cookie that only tells the page the connection worked. We do not use
          advertising or tracking cookies.
        </p>
      </LegalSection>

      <LegalSection id="retention" number={10} title="How long we keep it">
        <p>
          We have not yet set a retention period. Today, your information is kept until you or your care team delete
          it, you ask us to delete it, or the service is discontinued. MyChart tokens are deleted when you press
          Disconnect. Voice transcripts kept by ElevenLabs follow the setting described in section 5.
        </p>
      </LegalSection>

      <LegalSection id="your-choices" number={11} title="Your choices">
        <ul>
          <li>
            <strong>See your information.</strong> Your dashboard shows your care plan, check-ins, and conversations. You
            can ask us for a copy of what we hold about you.
          </li>
          <li>
            <strong>Correct it.</strong> You can update your mobile number in your dashboard, and ask your care team or
            us to fix anything else.
          </li>
          <li>
            <strong>Delete it.</strong> You can ask us to delete your account and your information.
          </li>
          <li>
            <strong>Disconnect MyChart</strong> at any time from your dashboard.
          </li>
          <li>
            <strong>Skip optional features.</strong> You can use CloudCare without a mobile number, voice, or MyChart.
          </li>
        </ul>
        <p>
          To make a request, contact us at <Placeholder>CloudCare contact email</Placeholder>. We may need to confirm it
          is really you before we act.
        </p>
      </LegalSection>

      <LegalSection id="children" number={12} title="Children">
        <p>
          CloudCare is not intended for anyone under 18. We do not knowingly collect information from children. If you
          think a child has given us information, contact us and we will delete it.
        </p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to this policy">
        <p>
          We may update this policy as CloudCare changes. When we do, we will change the &ldquo;Last updated&rdquo; date
          at the top of this page, and if the changes are important we will let you know through CloudCare. This policy
          is governed by the laws of <Placeholder>Governing law and jurisdiction</Placeholder>.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="Contact us">
        <p>For questions about this policy or your information:</p>
        <ul>
          <li>
            <strong>Email:</strong> <Placeholder>CloudCare contact email</Placeholder>
          </li>
          <li>
            <strong>Mail:</strong> <Placeholder>Mailing address</Placeholder>
          </li>
        </ul>
        <p>For medical questions, contact your care team. In an emergency, call 911.</p>
      </LegalSection>
    </LegalPage>
  );
}
