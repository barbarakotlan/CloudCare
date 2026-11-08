"use client";

import { AudioLines } from "lucide-react";
import { useCallback, useState, useSyncExternalStore } from "react";
import { AppHeader } from "@/components/app/AppHeader";
import { DemoResetControl } from "@/components/app/DemoResetControl";
import { DemoResetNotice } from "@/components/app/DemoResetNotice";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { isEmergency, type UiMessage } from "@/components/chat/types";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ToastViewport, useToasts } from "@/components/ui/Toast";
import { TalkToFoggy } from "@/components/voice/TalkToFoggy";
import { isDemoEmail } from "@/lib/api/demo";
import { getMyCarePlan, getMyProfile } from "@/lib/api/patients";
import type { Session } from "@/lib/auth";
import { RequireRole } from "@/lib/auth/RequireRole";
import { useAsync } from "@/lib/hooks/useAsync";
import { useNow } from "@/lib/hooks/useNow";
import { isEpicPopupReturn } from "@/lib/epicPopup";
import { CarePlanCard } from "./CarePlanCard";
import { CheckInCard } from "./CheckInCard";
import { EpicPopupReturn } from "./EpicPopupReturn";
import { GreetingBanner } from "./GreetingBanner";
import { MyChartCard } from "./MyChartCard";
import { RemindersCard } from "./RemindersCard";
import { TestOnPhoneCard } from "./TestOnPhoneCard";

const noSubscribe = () => () => {};

/** Route entry: guards the dashboard for signed-in patients. */
export function PatientDashboardRoute() {
  // In the MyChart popup on its way back from Epic: report to the opener instead of loading the dashboard.
  const popupReturn = useSyncExternalStore(noSubscribe, isEpicPopupReturn, () => false);
  if (popupReturn) return <EpicPopupReturn />;
  return <RequireRole role="patient">{(session) => <PatientDashboard session={session} />}</RequireRole>;
}

export function PatientDashboard({ session }: { session: Session }) {
  const now = useNow();
  const profile = useAsync("me", (signal) => getMyProfile(signal));
  const plan = useAsync("care-plan", (signal) => getMyCarePlan(signal));
  const [voiceOpen, setVoiceOpen] = useState(false);
  const { toasts, push, dismiss } = useToasts();

  // Fires only when the backend really filed an escalation this turn.
  const onEscalated = useCallback(
    (m: UiMessage) =>
      push(
        isEmergency(m)
          ? { tone: "alert", title: "Call 911 now", body: "Your care team’s queue also has this alert." }
          : m.actionResult?.status === "sent"
            ? { tone: "info", title: "Message sent", body: "It’s in your care team’s queue." }
            : { tone: "info", title: "Added to your care team’s queue", body: "If you need help now, call your medical team." },
      ),
    [push],
  );

  return (
    <>
      <AppHeader user={session.user} />
      <main id="main" className="flex-1 bg-surface-soft">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-10">
          <DemoResetNotice className="mb-4" />
          <GreetingBanner
            profile={profile.data}
            fallbackName={session.user.full_name}
            now={now}
            error={profile.error}
            onTalk={() => setVoiceOpen(true)}
          />

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]">
            <div className="min-w-0 lg:col-start-1 lg:row-start-1">
              <RemindersCard now={now} notify={push} />
            </div>

            <section
              aria-labelledby="foggy-title"
              className="flex h-[min(640px,85dvh)] flex-col overflow-hidden rounded-[1.75rem] bg-white shadow-soft ring-1 ring-line/70 lg:sticky lg:top-24 lg:col-start-2 lg:row-span-3 lg:row-start-1 lg:h-[calc(100dvh-8rem)] lg:max-h-[760px] lg:self-start"
            >
              <div className="flex items-center gap-3 border-b border-line/70 px-5 py-4">
                <FoggyAvatar size={42} decorative />
                <div className="min-w-0 flex-1">
                  <h2 id="foggy-title" className="text-lg leading-tight font-extrabold text-ink">
                    Foggy
                  </h2>
                  <p className="truncate text-sm text-brand-gray">Answers from your care plan, 24/7</p>
                </div>
                <Button variant="soft" size="sm" onClick={() => setVoiceOpen(true)} aria-haspopup="dialog">
                  <AudioLines className="size-4" aria-hidden="true" />
                  Talk
                </Button>
              </div>
              <ChatPanel mode="live" className="flex-1" onEscalated={onEscalated} />
            </section>

            <div className="min-w-0 lg:col-start-1 lg:row-start-2">
              <CheckInCard now={now} />
            </div>
            <div className="min-w-0 lg:col-start-1 lg:row-start-3">
              <TestOnPhoneCard />
            </div>
            <div className="min-w-0 lg:col-start-1 lg:row-start-4">
              <CarePlanCard plan={plan.data} loading={plan.loading} error={plan.error} />
            </div>
            <div className="min-w-0 lg:col-start-1 lg:row-start-5">
              {/* Includes the MyChartRecords tabs once a connection exists. */}
              <MyChartCard notify={push} now={now} />
            </div>
          </div>

          {isDemoEmail(session.user.email) ? (
            // Renders nothing (no divider either) when the server has no reset route.
            <DemoResetControl
              variant="link"
              className="mt-10 border-t border-line/70 pt-6"
              onReset={() => {
                // Chat, check-ins and doses all changed underneath this page: start fresh.
                window.location.reload();
              }}
            />
          ) : null}
        </div>
      </main>

      <Modal
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        title="Talk to Foggy"
        description="Hands-free answers from your care plan."
      >
        <TalkToFoggy />
      </Modal>
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
  );
}
