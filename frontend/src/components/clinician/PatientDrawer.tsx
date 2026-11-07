"use client";

import {
  Activity,
  BookOpen,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  MessagesSquare,
  Thermometer,
  UserRoundPen,
} from "lucide-react";
import { useState } from "react";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { fromApiMessage } from "@/components/chat/types";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { getChatHistory } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/client";
import { getPatient, getPatientCarePlan } from "@/lib/api/patients";
import { getSymptoms } from "@/lib/api/symptoms";
import {
  PENDING_SETUP_PROCEDURE,
  type CarePlanOut,
  type ChatMessageOut,
  type EscalationOut,
  type PatientOut,
  type PatientRow,
  type SymptomOut,
} from "@/lib/api/types";
import { cn } from "@/lib/cn";
import {
  daysSince,
  factorLabel,
  formatDate,
  formatDateTime,
  MOBILITY_LABEL,
  relativeTime,
  RISK_LABEL,
  SEVERITY_LABEL,
  TRIGGER_LABEL,
} from "@/lib/format";
import { useAsync } from "@/lib/hooks/useAsync";
import { CarePlanUpload } from "./CarePlanUpload";
import { PatientProfileForm } from "./PatientProfileForm";
import { RISK_TONE, SEVERITY_TONE, STATUS_LABEL } from "./severity";

type Tab = "overview" | "checkins" | "chat" | "plan" | "profile";

type PlanState = { kind: "ok"; plan: CarePlanOut | null } | { kind: "unavailable" };

export function PatientDrawer({
  patientId,
  row,
  escalations,
  now,
  onClose,
  onProfileSaved,
}: {
  patientId: string | null;
  row: PatientRow | undefined;
  escalations: EscalationOut[];
  now: number | null;
  onClose: () => void;
  onProfileSaved: (patient: PatientOut) => void;
}) {
  const pending = row?.procedure_name === PENDING_SETUP_PROCEDURE;
  return (
    <Modal
      open={patientId !== null}
      onClose={onClose}
      variant="drawer"
      title={row?.full_name ?? "Patient"}
      description={row && !pending ? row.procedure_name : undefined}
      headerExtra={pending ? <FinishSetupBadge className="mt-1.5" /> : null}
      bodyClassName="bg-surface-soft"
    >
      {patientId ? (
        <DrawerBody
          key={patientId}
          patientId={patientId}
          row={row}
          escalations={escalations}
          now={now}
          onProfileSaved={onProfileSaved}
        />
      ) : null}
    </Modal>
  );
}

/** Patients who signed up before their care team added a procedure. */
export function FinishSetupBadge({ className }: { className?: string }) {
  return (
    <Badge tone="amber" dot className={className}>
      Finish setup
    </Badge>
  );
}

function CurrentPlan({ plan }: { plan: CarePlanOut }) {
  const sections = [...plan.chunks].sort((a, b) => a.chunk_index - b.chunk_index);
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-extrabold break-words text-ink">{plan.title}</p>
        <p className="text-xs text-brand-gray">
          Saved {formatDate(plan.created_at, { month: "short", day: "numeric", year: "numeric" })} · {sections.length}{" "}
          section{sections.length === 1 ? "" : "s"}
        </p>
      </div>
      <ul className="mt-3 flex flex-col gap-2">
        {sections.map((c) => (
          <li key={c.id}>
            <details className="group rounded-2xl bg-surface-soft ring-1 ring-line/60">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-2 font-bold text-ink [&::-webkit-details-marker]:hidden">
                <span className="min-w-0 break-words">{c.section ?? `Part ${c.chunk_index + 1}`}</span>
                <ChevronDown
                  className="size-4 shrink-0 text-brand-gray transition-transform group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <p className="px-4 pb-3 text-sm leading-relaxed break-words whitespace-pre-line text-ink-soft">{c.content}</p>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Patient messages that Foggy could not answer from the plan. */
function unansweredQuestions(history: ChatMessageOut[]) {
  const out: Array<{ question: ChatMessageOut; reply: ChatMessageOut }> = [];
  history.forEach((m, i) => {
    if (m.role !== "assistant" || m.answered_from_plan !== false) return;
    const prev = history[i - 1];
    if (prev && prev.role === "patient") out.push({ question: prev, reply: m });
  });
  return out.reverse();
}

function DrawerBody({
  patientId,
  row,
  escalations,
  now,
  onProfileSaved,
}: {
  patientId: string;
  row: PatientRow | undefined;
  escalations: EscalationOut[];
  now: number | null;
  onProfileSaved: (patient: PatientOut) => void;
}) {
  // New sign-ups land on the profile form first.
  const [tab, setTab] = useState<Tab>(row?.procedure_name === PENDING_SETUP_PROCEDURE ? "profile" : "overview");
  const profile = useAsync(`patient:${patientId}`, (s) => getPatient(patientId, s));
  const plan = useAsync<PlanState>(`patient-plan:${patientId}`, async (s) => {
    try {
      return { kind: "ok", plan: await getPatientCarePlan(patientId, s) };
    } catch (err) {
      // Older API: clinicians can upload a plan but not read it back yet.
      if (err instanceof ApiError && (err.status === 404 || err.status === 405)) return { kind: "unavailable" };
      throw err;
    }
  });
  const symptoms = useAsync(`symptoms:${patientId}`, (s) => getSymptoms(patientId, s));
  const chat = useAsync(`chat:${patientId}`, (s) => getChatHistory(patientId, s));
  const unanswered = chat.data ? unansweredQuestions(chat.data) : [];
  const open = escalations.filter((e) => e.patient_id === patientId && e.status !== "resolved");
  const name = row?.full_name ?? profile.data?.full_name ?? "this patient";
  // Unknown (older API) counts as having one: "replace" is the safe wording.
  const hasPlan = plan.data?.kind === "unavailable" || Boolean(plan.data?.kind === "ok" && plan.data.plan);

  return (
    <div className="flex flex-col gap-5 p-4 sm:p-6">
      {/* Five tabs don't fit a phone: let the row scroll sideways inside the drawer. */}
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <SegmentedControl<Tab>
          label="Patient details"
          size="sm"
          value={tab}
          onChange={setTab}
          className="min-w-max sm:min-w-0"
          options={[
            { value: "overview", label: "Overview" },
            { value: "checkins", label: "Check-ins" },
            { value: "chat", label: "Chat" },
            { value: "plan", label: "Care plan" },
            { value: "profile", label: "Profile" },
          ]}
        />
      </div>

      {tab === "overview" ? (
        <>
          <section aria-labelledby="ov-profile" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
            <h3 id="ov-profile" className="font-extrabold text-ink">Profile</h3>
            {profile.loading ? <SkeletonLines lines={3} className="mt-3" /> : null}
            {profile.error ? <p role="alert" className="mt-2 text-sm text-brand-red-dark">{profile.error}</p> : null}
            {profile.data ? (
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div>
                  <dt className="text-brand-gray">Procedure</dt>
                  <dd className="font-bold text-ink">{profile.data.procedure_name}</dd>
                </div>
                <div>
                  <dt className="text-brand-gray">Type</dt>
                  <dd className="font-bold text-ink capitalize">{profile.data.procedure_type}</dd>
                </div>
                <div>
                  <dt className="text-brand-gray">Surgery</dt>
                  <dd className="font-bold text-ink">
                    {formatDate(profile.data.surgery_date)}
                    {now !== null ? ` · day ${daysSince(profile.data.surgery_date, now)}` : ""}
                  </dd>
                </div>
                <div>
                  <dt className="text-brand-gray">Discharged</dt>
                  <dd className="font-bold text-ink">
                    {profile.data.discharge_date ? formatDate(profile.data.discharge_date) : "Not yet"}
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-brand-gray">Comorbidities</dt>
                  <dd className="mt-1 flex flex-wrap gap-1.5">
                    {profile.data.comorbidities.length ? (
                      profile.data.comorbidities.map((c) => (
                        <Badge key={c} tone="pale" className="capitalize">
                          {c}
                        </Badge>
                      ))
                    ) : (
                      <span className="font-bold text-ink">None recorded</span>
                    )}
                  </dd>
                </div>
              </dl>
            ) : null}
          </section>

          <section aria-labelledby="ov-risk" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
            <h3 id="ov-risk" className="flex items-center gap-2 font-extrabold text-ink">
              <Activity className="size-4 text-brand-cyan-strong" aria-hidden="true" />
              Latest risk
            </h3>
            {row?.latest_risk ? (
              <div className="mt-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={RISK_TONE[row.latest_risk.risk_level]} dot>
                    {RISK_LABEL[row.latest_risk.risk_level]}
                  </Badge>
                  <span className="text-sm text-brand-gray">
                    Score {Math.round(row.latest_risk.score * 100)}% · model {row.latest_risk.model_version}
                    {now !== null ? ` · ${relativeTime(row.latest_risk.created_at, now)}` : ""}
                  </span>
                </div>
                {row.latest_risk.top_factors.length ? (
                  <ul className="mt-3 flex flex-col gap-2">
                    {row.latest_risk.top_factors.map((f) => (
                      <li key={f.feature} className="flex items-center gap-3 text-sm">
                        <span className="w-32 shrink-0 font-semibold text-ink sm:w-40">{factorLabel(f.feature)}</span>
                        <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-pale" aria-hidden="true">
                          <span
                            className="block h-full rounded-full bg-brand-cyan"
                            style={{ width: `${Math.min(100, Math.round(f.impact * 250))}%` }}
                          />
                        </span>
                        <span className="w-12 text-right text-xs font-bold text-brand-gray tabular-nums">
                          +{Math.round(f.impact * 100)}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <p className="mt-2 text-sm text-brand-gray">No check-ins scored yet.</p>
            )}
          </section>

          <section aria-labelledby="ov-open" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
            <h3 id="ov-open" className="font-extrabold text-ink">Open escalations ({open.length})</h3>
            {open.length === 0 ? <p className="mt-2 text-sm text-brand-gray">None. All clear.</p> : null}
            <ul className="mt-3 flex flex-col gap-2">
              {open.map((e) => (
                <li key={e.id} className="rounded-2xl bg-surface-soft p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={SEVERITY_TONE[e.severity]} dot>
                      {SEVERITY_LABEL[e.severity]}
                    </Badge>
                    <span className="font-bold text-ink-soft">{TRIGGER_LABEL[e.trigger_type] ?? e.trigger_type}</span>
                    <span className="ml-auto text-xs text-brand-gray">{STATUS_LABEL[e.status]}</span>
                  </div>
                  <p className="mt-1 text-ink-soft">{e.summary}</p>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="ov-unanswered" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
            <h3 id="ov-unanswered" className="flex items-center gap-2 font-extrabold text-ink">
              <CircleHelp className="size-4 text-brand-cyan-strong" aria-hidden="true" />
              Questions Foggy couldn&rsquo;t answer ({unanswered.length})
            </h3>
            {chat.loading ? <SkeletonLines lines={2} className="mt-3" /> : null}
            {chat.data && unanswered.length === 0 ? (
              <p className="mt-2 text-sm text-brand-gray">Every question so far was covered by the care plan.</p>
            ) : null}
            <ul className="mt-3 flex flex-col gap-2">
              {unanswered.map(({ question, reply }) => (
                <li
                  key={question.id}
                  className={cn(
                    "rounded-2xl p-3 text-sm",
                    reply.red_flag ? "bg-brand-red/8 ring-1 ring-brand-red/20" : "bg-surface-soft",
                  )}
                >
                  <p className="font-bold text-ink">&ldquo;{question.content}&rdquo;</p>
                  <p className="mt-1 text-xs text-brand-gray">
                    {reply.red_flag ? "Red flag · " : "Not in plan · "}
                    {formatDateTime(question.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}

      {tab === "checkins" ? (
        <section aria-label="Check-in history" className="flex flex-col gap-3">
          {symptoms.loading ? <SkeletonLines lines={4} /> : null}
          {symptoms.error ? <p role="alert" className="text-sm text-brand-red-dark">{symptoms.error}</p> : null}
          {symptoms.data && symptoms.data.length === 0 ? (
            <p className="rounded-3xl bg-white p-5 text-sm text-brand-gray ring-1 ring-line/70">No check-ins yet.</p>
          ) : null}
          {symptoms.data?.map((s) => <SymptomItem key={s.id} s={s} now={now} />)}
        </section>
      ) : null}

      {tab === "chat" ? (
        <section aria-label="Chat transcript" className="rounded-3xl bg-white p-4 ring-1 ring-line/70 sm:p-5">
          <p className="mb-4 flex items-center gap-2 text-sm text-brand-gray">
            <MessagesSquare className="size-4" aria-hidden="true" />
            Read-only transcript between {name} and Foggy.
          </p>
          {chat.loading ? <SkeletonLines lines={4} /> : null}
          {chat.error ? <p role="alert" className="text-sm text-brand-red-dark">{chat.error}</p> : null}
          {chat.data && chat.data.length === 0 ? <p className="text-sm text-brand-gray">No messages yet.</p> : null}
          <div className="flex flex-col gap-3">
            {chat.data?.map((m) => <MessageBubble key={m.id} message={fromApiMessage(m)} />)}
          </div>
        </section>
      ) : null}

      {tab === "plan" ? (
        <>
          <section aria-labelledby="plan-current-title" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
            <h3 id="plan-current-title" className="mb-3 flex items-center gap-2 font-extrabold text-ink">
              <BookOpen className="size-4 text-brand-cyan-strong" aria-hidden="true" />
              Current care plan
            </h3>
            {plan.loading && !plan.data ? <SkeletonLines lines={3} /> : null}
            {plan.error ? <p role="alert" className="text-sm text-brand-red-dark">{plan.error}</p> : null}
            {plan.data?.kind === "unavailable" ? (
              <p className="text-sm text-brand-gray">
                Viewing the current plan isn&rsquo;t available on this server yet. You can still replace it below.
              </p>
            ) : null}
            {plan.data?.kind === "ok" && plan.data.plan === null ? (
              <p className="text-sm text-brand-gray">No care plan yet. Foggy can&rsquo;t answer {name}&rsquo;s questions until you add one.</p>
            ) : null}
            {plan.data?.kind === "ok" && plan.data.plan ? <CurrentPlan plan={plan.data.plan} /> : null}
          </section>

          <section aria-labelledby="plan-upload-title" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
            <h3 id="plan-upload-title" className="mb-3 flex items-center gap-2 font-extrabold text-ink">
              <ClipboardList className="size-4 text-brand-cyan-strong" aria-hidden="true" />
              {hasPlan ? "Replace plan" : "Add a care plan"}
            </h3>
            <CarePlanUpload
              patientId={patientId}
              patientName={name}
              hasPlan={hasPlan}
              onSaved={(saved) => plan.setData(() => ({ kind: "ok", plan: saved }))}
            />
          </section>
        </>
      ) : null}

      {tab === "profile" ? (
        <section aria-labelledby="profile-edit-title" className="rounded-3xl bg-white p-5 ring-1 ring-line/70">
          <h3 id="profile-edit-title" className="mb-3 flex items-center gap-2 font-extrabold text-ink">
            <UserRoundPen className="size-4 text-brand-cyan-strong" aria-hidden="true" />
            Edit profile
          </h3>
          {profile.loading && !profile.data ? <SkeletonLines lines={4} /> : null}
          {profile.error ? <p role="alert" className="text-sm text-brand-red-dark">{profile.error}</p> : null}
          {profile.data ? (
            <PatientProfileForm
              key={JSON.stringify(profile.data)}
              patient={profile.data}
              onSaved={(saved) => {
                profile.setData(() => saved);
                onProfileSaved(saved);
              }}
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function SymptomItem({ s, now }: { s: SymptomOut; now: number | null }) {
  const flags = [
    s.shortness_of_breath && "Shortness of breath",
    s.wound_redness && "Wound redness",
    s.wound_drainage && "Wound drainage",
    s.swelling && "Swelling",
    s.nausea && "Nausea",
  ].filter((f): f is string => Boolean(f));
  const pain = s.pain_level ?? 0;
  const fever = s.temperature_f !== null && s.temperature_f >= 100.4;

  return (
    <article className="rounded-3xl bg-white p-4 ring-1 ring-line/70 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-extrabold text-ink">{formatDateTime(s.logged_at)}</p>
        <span className="text-xs font-bold text-brand-gray">
          {now !== null ? relativeTime(s.logged_at, now) : ""} · via {s.source}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-sm">
        <Badge tone={pain >= 7 ? "red" : pain >= 4 ? "amber" : "cyan"}>Pain {s.pain_level ?? "–"}/10</Badge>
        {s.temperature_f !== null ? (
          <Badge tone={fever ? "red" : "gray"}>
            <Thermometer className="size-3.5" aria-hidden="true" />
            {s.temperature_f.toFixed(1)} °F
          </Badge>
        ) : null}
        {s.mobility_level !== null ? <Badge tone="gray">{MOBILITY_LABEL[s.mobility_level] ?? `Mobility ${s.mobility_level}`}</Badge> : null}
        {flags.map((f) => (
          <Badge key={f} tone={f === "Shortness of breath" ? "red" : "orange"}>
            {f}
          </Badge>
        ))}
      </div>
      {s.free_text ? <p className="mt-3 rounded-2xl bg-surface-soft px-3 py-2 text-sm text-ink-soft">&ldquo;{s.free_text}&rdquo;</p> : null}
    </article>
  );
}
