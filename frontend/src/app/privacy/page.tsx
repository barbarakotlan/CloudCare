import type { Metadata } from "next";
import Link from "next/link";
import { Callout, CounselNote, LegalPage, LegalSection, Placeholder, type TocEntry } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "What information CloudCare collects, where it is stored, which service providers process it, how Foggy's answers and calls work, and the choices you have.",
};

const TOC: TocEntry[] = [
  { id: "about", label: "1. About this policy" },
  { id: "what-we-collect", label: "2. Information we collect" },
  { id: "how-we-use", label: "3. How we use it" },
  { id: "foggy", label: "4. How Foggy's answers are made" },
  { id: "voice-phone", label: "5. Voice, phone calls, and texts" },
  { id: "mychart", label: "6. Epic MyChart connection" },
  { id: "sharing", label: "7. Who we share it with" },
  { id: "hipaa", label: "8. HIPAA and health information" },
  { id: "security", label: "9. How we protect it" },
  { id: "demo-accounts", label: "10. Demo accounts" },
  { id: "browser-storage", label: "11. Cookies and browser storage" },
  { id: "retention", label: "12. How long we keep it" },
  { id: "your-choices", label: "13. Your choices" },
  { id: "children", label: "14. Children" },
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
          <li>
            Your symptom check-ins (for example pain level, medicines taken, numbness or tingling, falls) and the risk
            level an experimental model calculates from them. The model was built with made-up (synthetic) data, not
            real patient records.
          </li>
          <li>
            Your conversations with Foggy as written messages. This includes what you type and, for voice
            conversations and phone calls, the care questions and answers Foggy passes to our server.
          </li>
          <li>Medicine reminders, doses you mark as taken or skipped, and appointments.</li>
          <li>Alerts in your care team&rsquo;s queue and any notes your care team adds when they review them.</li>
        </ul>
        <p>
          <strong>Phone activity.</strong> If you ask Foggy to call or text you, we record that you asked, whether it
          started or was sent, and the last four digits of the number it went to.
        </p>
        <p>
          <strong>MyChart records.</strong> Only if you connect MyChart. See section 6.
        </p>
        <p>
          <strong>Technical information.</strong> Our servers keep basic logs, such as which feature was used, when, and
          whether it worked (status codes). These logs do not contain the text of your messages, your care plan, or
          your MyChart records. Our hosting providers may also keep standard logs, such as IP addresses and request
          times.
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
          <li>Calling or texting your phone when you ask.</li>
          <li>Keeping the service secure and fixing problems.</li>
        </ul>
        <Callout>
          We do not sell your information. We do not use it for advertising. We do not use it to train our own AI
          models.
        </Callout>
      </LegalSection>

      <LegalSection id="foggy" number={4} title="How Foggy's answers are made">
        <p>
          Foggy&rsquo;s replies are written with the help of a third-party language model, Google Gemini. When you
          send Foggy a message, our server sends Google the text of your care plan, your message, and up to six of your
          recent messages so the reply fits the conversation.
        </p>
        <p>
          <strong>Important:</strong> today CloudCare uses Google&rsquo;s free (unpaid) Gemini API. Under Google&rsquo;s
          terms for unpaid use, Google may use what is sent to improve its products, and people at Google may read it.
          This is a key reason not to enter real health information in CloudCare yet. We plan to move to a paid
          service with stronger data protections before CloudCare is used with real patients.
        </p>
        <p>
          Our own code decides what Foggy is allowed to do: it is designed to answer only from your care plan, never
          change a dose, and, for emergency warning signs such as chest pain or trouble breathing, tell you to call
          911. Foggy cannot place calls to 911.
        </p>
        <p>
          The &ldquo;Try texting Foggy&rdquo; demo on our home page is different: it runs entirely in your web browser
          with a sample care plan and does not send your messages to us or to Google.
        </p>
      </LegalSection>

      <LegalSection id="voice-phone" number={5} title="Voice, phone calls, and texts">
        <p>
          Talking to Foggy in your browser (including the &ldquo;Talk to Foggy&rdquo; demo on our home page), and phone
          calls from Foggy, run through ElevenLabs. ElevenLabs turns your voice into text, runs the conversation with a
          language model (currently Google Gemini, used through ElevenLabs), and turns Foggy&rsquo;s replies into
          speech. When you are signed in, each care question is sent to our server and answered the same way as a text
          message. To do that, ElevenLabs receives your first name and a temporary access key for your account (your
          current sign-in key in the browser, or a key made for one phone call that stops working after 30 minutes).
          The key is not shown to the language model.
        </p>
        <ul>
          <li>
            <strong>No audio recording.</strong> Voice recording is turned off in our ElevenLabs settings, and call
            recording is turned off in our phone settings.
          </li>
          <li>
            Under our current settings, ElevenLabs keeps a written transcript of each voice conversation and phone call
            for up to 30 days.
          </li>
          <li>Your browser asks for microphone permission only when you press the button to start talking.</li>
        </ul>
        <p>
          Phone calls and texts use a phone number from Twilio, and the call or text shows that number. ElevenLabs and
          Twilio handle the call or text itself and receive the number being called, along with call details such as
          time and length. CloudCare only calls or texts the number saved on your own account, and only when you press
          &ldquo;Call me&rdquo; or &ldquo;Text me.&rdquo; Calls are automated and use a computer-generated voice. You
          can reply STOP to any text.
        </p>
      </LegalSection>

      <LegalSection id="mychart" number={6} title="Epic MyChart connection">
        <p>
          Connecting MyChart is optional. Today CloudCare connects only to Epic&rsquo;s sandbox (test) environment,
          which holds made-up test patients, not real MyChart accounts. You sign in on Epic&rsquo;s own page, so
          CloudCare never sees the MyChart password.
        </p>
        <ul>
          <li>
            We store the connection details Epic gives us, including the access tokens that let CloudCare read
            records. These tokens are encrypted at rest on our server and are never sent to your browser.
          </li>
          <li>
            MyChart records (medicines, lab results, visits, and notes) are read from Epic when you view them. We do
            not save copies of those records in our database.
          </li>
          <li>
            You can press <strong>Disconnect</strong> in your dashboard at any time. This deletes the stored connection
            and its tokens. Epic&rsquo;s test environment has no way for apps to cancel a token early, so the access
            Epic granted ends when the token expires on its own (usually within about an hour). You can also remove
            CloudCare&rsquo;s access from inside MyChart.
          </li>
        </ul>
        <p className="text-sm text-brand-gray">
          Epic and MyChart are trademarks of Epic Systems Corporation. CloudCare is not affiliated with, endorsed by,
          or sponsored by Epic Systems Corporation.
        </p>
      </LegalSection>

      <LegalSection id="sharing" number={7} title="Who we share it with">
        <p>
          <strong>Your care team.</strong> The clinician assigned to you can see your profile, care plan, check-ins,
          conversations with Foggy, alerts, and mobile number, so they can follow up with you. A new account has no
          clinician until one is assigned.
        </p>
        <p>
          <strong>Service providers.</strong> These companies process information for us so CloudCare can work:
        </p>
        <ul>
          <li>
            <strong>Supabase</strong>: sign-in (Supabase Auth) and our database (Postgres hosted by Supabase in the
            United States), where your account, care plan, check-ins, messages, and alerts are stored.
          </li>
          <li>
            <strong>Render</strong>: hosts the CloudCare server (our API).
          </li>
          <li>
            <strong>Vercel</strong>: hosts the CloudCare website.
          </li>
          <li>
            <strong>Google (Gemini)</strong>: writes Foggy&rsquo;s text replies, as described in section 4, and runs
            voice conversations through ElevenLabs, as described in section 5.
          </li>
          <li>
            <strong>ElevenLabs</strong>: voice conversations and phone calls, as described in section 5.
          </li>
          <li>
            <strong>Twilio</strong>: provides the phone number used for calls and texts, and carries them.
          </li>
          <li>
            <strong>Epic</strong>: only if you connect MyChart, as described in section 6.
          </li>
        </ul>
        <p>
          Each of these companies handles information under its own terms and privacy policy. We may also share
          information if the law requires it, to protect someone&rsquo;s safety, or as part of a sale or merger of
          CloudCare, in which case this policy would continue to apply. We do not share your information with
          advertisers or data brokers.
        </p>
      </LegalSection>

      <LegalSection id="hipaa" number={8} title="HIPAA and health information">
        <p>
          CloudCare is not offered by your health care provider. At this early stage, CloudCare is not operating as a
          HIPAA covered entity or as a business associate of a health care provider, and we have not signed business
          associate agreements with the service providers listed above. This means the information you give CloudCare
          does not have the same legal protections as the records your doctor keeps. We still treat it as sensitive
          health information and protect it as described in this policy.
        </p>
        <p>
          If a security breach affects your information, we will notify you as the law requires.
        </p>
        <CounselNote>
          Confirm HIPAA status, FTC Health Breach Notification Rule (16 CFR Part 318) duties, and whether state
          consumer health data laws (for example Washington&rsquo;s My Health My Data Act, RCW 19.373) require a
          separate consumer health data policy and opt-in consent before real users are invited.
        </CounselNote>
      </LegalSection>

      <LegalSection id="security" number={9} title="How we protect it">
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
      </LegalSection>

      <LegalSection id="demo-accounts" number={10} title="Demo accounts">
        <p>
          The demo accounts shown on our sign-in page are shared with everyone who tries CloudCare. Their names and
          details are fictional.
        </p>
        <ul>
          <li>Anything entered in a demo account, including a phone number, can be seen and changed by anyone.</li>
          <li>
            Anyone can reset the demo patient. A reset deletes its messages, check-ins, alerts, dose history, and phone
            activity for everyone.
          </li>
          <li>
            Please do not enter real health information, or anyone&rsquo;s real name or contact details, while using a
            demo account. If you save your own number to test a call, remove it when you are done.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="browser-storage" number={11} title="Cookies and browser storage">
        <p>
          CloudCare keeps your sign-in session in your browser&rsquo;s local storage so you stay signed in. After you
          connect MyChart, we set a short-lived cookie that only tells the page the connection worked. We do not use
          advertising or tracking cookies.
        </p>
      </LegalSection>

      <LegalSection id="retention" number={12} title="How long we keep it">
        <p>
          We have not yet set a retention period. Today, your information is kept until you or your care team delete
          it, you ask us to delete it, or the service is discontinued. Deleted information may stay in our
          providers&rsquo; backups for a limited time. MyChart tokens are deleted when you press Disconnect. Voice and
          call transcripts kept by ElevenLabs follow the setting described in section 5. Twilio keeps call and text
          records under its own policies.
        </p>
      </LegalSection>

      <LegalSection id="your-choices" number={13} title="Your choices">
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
            <strong>Stop calls and texts.</strong> Remove your mobile number from your dashboard, or reply STOP to a
            text.
          </li>
          <li>
            <strong>Disconnect MyChart</strong> at any time from your dashboard.
          </li>
          <li>
            <strong>Skip optional features.</strong> You can use CloudCare without a mobile number, voice, or MyChart.
          </li>
        </ul>
        <p>
          Depending on where you live, you may have other privacy rights under state law. To make a request, contact
          us at <Placeholder>CloudCare contact email</Placeholder>. We may need to confirm it is really you before we
          act, and we will not treat you differently for making a request.
        </p>
      </LegalSection>

      <LegalSection id="children" number={14} title="Children">
        <p>
          CloudCare is not intended for anyone under 18. We do not knowingly collect information from children. If you
          think a child has given us information, contact us and we will delete it.
        </p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to this policy">
        <p>
          We may update this policy as CloudCare changes. When we do, we will change the &ldquo;Last updated&rdquo; date
          at the top of this page, and if the changes are important we will let you know through CloudCare or by email
          before they take effect. This policy is governed by the laws of{" "}
          <Placeholder>Governing law and jurisdiction</Placeholder>.
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
