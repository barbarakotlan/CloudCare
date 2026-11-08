# CloudCare product brief

**Your head's in the clouds. Your care shouldn't be.**

## What CloudCare is

Patients get their most important recovery instructions right after surgery, while they are still foggy from anesthesia. Then they go home and are expected to remember all of it and to notice when something is wrong. Many don't, and complications get caught late.

CloudCare brings the care team's instructions home: a recovery plan written by the patient's clinician, a recovery assistant named **Foggy** that answers questions from that plan, guided symptom check-ins, reminders, and a clear path back to a human when it matters. Clinicians get one worklist that shows who needs attention first.

## Who it is for

Hospital surgical and anesthesia teams who send patients home after surgery, and their patients in the days between discharge and the first follow-up. The demo covers orthopedic and general surgery and anesthesia-specific recovery such as post-op nausea, post-spinal headache, nerve-block rebound pain and post-op confusion.

## What patients get

- **Foggy by text, voice, or phone.** Patients type to Foggy in the app, talk to it in the browser, or press "Call me" to get an automated check-in call from CloudCare's toll-free number. All channels follow the same rules on the server.
- **Answers from their own care plan.** Foggy is designed to answer only from what the clinician wrote. Text answers show the plan section they came from, and each answer is checked against that section first. If the plan doesn't cover a question, Foggy says so instead of guessing. Replies are two sentences at most.
- **Guided check-ins.** One question at a time: pain, symptoms such as fever, wound changes, numbness or falls, and one question per medicine dose due earlier that day. The care team sees the result.
- **Red flags get fixed rules first.** Chest pain, trouble breathing, heavy bleeding or fainting are caught by code before any language model runs, and the reply starts with "Call 911 now." Foggy cannot place emergency calls and says so. An alert also lands in the care team's queue.
- **Consent before contact.** Foggy offers to message the care team; nothing is sent unless the patient says yes to that specific offer.
- **Boundaries.** Foggy never changes or stops a medicine, never diagnoses, and never invents instructions.
- **Reminders.** Doses can be marked taken or skipped (with undo), and appointments are listed. Check-in texts are built but stay off until carrier verification of our toll-free number completes; calls work today.

## What care teams get

- **An urgency-first worklist.** Open emergencies first, then high alerts, then everyone else, with the risk estimate shown separately so a stale low score never hides a new emergency.
- **A review queue.** Clinicians acknowledge and resolve each alert with notes, and the dashboard records who reviewed it and when.
- **An explainable risk estimate.** Each check-in is scored by an XGBoost model that shows its top three reasons, such as fever or wound drainage. It is experimental and trained on synthetic data.
- **Care plans in minutes.** Paste discharge instructions as text; the plan splits into sections and Foggy uses it immediately. Clinicians can also edit patient profiles, claim new sign-ups, search, filter, and read chat transcripts and check-in history.
- **Role-based access.** Clinicians see only the patients assigned to them.

## Epic MyChart

Patients can connect MyChart through SMART on FHIR (OAuth 2.0 with PKCE) to bring in medications, labs, visits and clinical notes, read-only. CloudCare compares MyChart medications with the care plan and flags mismatches for the patient to raise with their care team. Tokens are encrypted and never reach the browser. **Today this runs against Epic's sandbox with test patients only;** production use needs Epic's approval and each health system enabling the app. Clinician-side EHR workflows and other EHR vendors are not built yet. CloudCare is not affiliated with or endorsed by Epic Systems Corporation.

## Try it

The live site is cloudcare.icu. On the home page anyone can text a demo Foggy and hear a sample check-in call. Shared demo accounts show both sides: `patient@demo.com` (Jordan Lee, recovering from a knee replacement) and `clinician@demo.com` (Dr. Priya Patel), password `demo123`. Demo accounts are public and reset often, so please don't enter real health information.

## Under the hood

Next.js on Vercel, a FastAPI service on Render, Supabase for sign-in and a Postgres database with row-level security, Google Gemini for understanding and phrasing messages, ElevenLabs for voice, and Twilio for calls and texts. Phone actions only go to the signed-in patient's own number. Without a language model, Foggy still routes every message by rules.

## Where we are today (honest caveats)

- CloudCare is an early-stage product with a working demo. It has no hospital customers yet and no published clinical outcomes.
- It has not been reviewed by the FDA, does not give medical advice, and is not intended to diagnose or treat any condition.
- It is not operating under HIPAA yet, and we have no business associate agreements (BAAs) with our vendors. Real patient data would first need HIPAA-eligible vendor plans and signed BAAs.
- The text assistant runs on Gemini's free tier today, which is not suitable for real health information; it would move to a paid tier with Google's data terms before a pilot with real patients.
- The risk model is trained on synthetic data and would need validation on real outcomes.
- The alert queue is not watched around the clock; a pilot would agree on who reviews it and when.
- Calls and texts are limited to US numbers. Foggy can make mistakes, which is why emergencies use fixed rules and a person closes every alert.

## The team

CloudCare has three co-founders:

- **Barbara Kotlan**, co-founder. Backend and data: an RPI student who builds the API, the database and the clinician workflows.
- **Jacob Foti**, co-founder. Business lead: has helped run a company with over $50M in annual recurring revenue.
- **Anna Kotlan**, co-founder. AI and ML: a data engineer at Fidelity with an MBA in data analytics, who builds Foggy's grounding, the risk model and the Epic integration.

## What we are looking for

We are looking for **pilot hospitals**: a surgical or anesthesia team willing to shape the product with us. A person on our team scopes each pilot with the hospital, including which patients take part, who reviews the alert queue, and how care plans are loaded. Getting started takes a two-minute form: hospital, contact, role, work email, rough monthly discharges, EHR, service lines and timeline.

## Pricing

We don't publish a price. **Pricing depends on discharge volume and integration scope, so a person on our team walks you through it.**
