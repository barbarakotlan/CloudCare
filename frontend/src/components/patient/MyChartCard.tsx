"use client";

import { Hospital, Info, LoaderCircle, RefreshCw, ShieldCheck, Unlink } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import type { ToastItem } from "@/components/ui/Toast";
import { ApiError, errorMessage } from "@/lib/api/client";
import { disconnectEpic, epicErrorText, getEpicStatus, startEpicConnect, type EpicStatus } from "@/lib/api/epic";
import { formatDate, relativeTime } from "@/lib/format";
import { useAsync } from "@/lib/hooks/useAsync";
import { MyChartRecords } from "./MyChartRecords";

type Notify = (toast: Omit<ToastItem, "id">) => void;
type Loaded = { kind: "ok"; status: EpicStatus } | { kind: "unconfigured" };

const SHARED = ["Medications", "Lab results", "Visits", "Clinical notes"];

function issuerLabel(status: EpicStatus): string {
  if (!status.issuer) return "Epic";
  try {
    const host = new URL(status.issuer).hostname;
    return host === "fhir.epic.com" ? "Epic sandbox" : host;
  } catch {
    return "Epic";
  }
}

/** Reads ?epic=connected|error&reason= once (set by our OAuth callback), toasts, and cleans the URL. */
function useEpicReturnToast(notify: Notify) {
  useEffect(() => {
    const url = new URL(window.location.href);
    const result = url.searchParams.get("epic");
    if (!result) return;
    if (result === "connected") {
      notify({ tone: "success", title: "MyChart connected", body: "Your records are loading below." });
    } else if (result === "error") {
      notify({ tone: "alert", title: "MyChart wasn't connected", body: epicErrorText(url.searchParams.get("reason")) });
    }
    url.searchParams.delete("epic");
    url.searchParams.delete("reason");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }, [notify]);
}

export function MyChartCard({ notify, now }: { notify: Notify; now: number | null }) {
  const status = useAsync<Loaded>("epic-status", async (signal) => {
    try {
      return { kind: "ok", status: await getEpicStatus(signal) };
    } catch (err) {
      // 503 = the API has no Epic client id / encryption key yet. Not an error for the patient.
      if (err instanceof ApiError && err.status === 503) return { kind: "unconfigured" };
      throw err;
    }
  });
  const [connecting, setConnecting] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [recordsVersion, setRecordsVersion] = useState(0);

  useEpicReturnToast(notify);

  const reloadStatus = status.reload;
  const onGone = useCallback(() => reloadStatus(), [reloadStatus]);

  async function connect() {
    setConnecting(true);
    try {
      const url = await startEpicConnect();
      window.location.assign(url);
      // Leave the button in its busy state while the browser navigates away.
    } catch (err) {
      setConnecting(false);
      if (err instanceof ApiError && err.status === 503) {
        reloadStatus();
        return;
      }
      notify({ tone: "alert", title: "Couldn't open MyChart", body: errorMessage(err) });
    }
  }

  async function disconnect() {
    setDisconnecting(true);
    try {
      await disconnectEpic();
      notify({ tone: "info", title: "MyChart disconnected", body: "CloudCare no longer has access to your records." });
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        notify({ tone: "alert", title: "Couldn't disconnect", body: errorMessage(err) });
      }
    } finally {
      setDisconnecting(false);
      setConfirmDisconnect(false);
      reloadStatus();
    }
  }

  const data = status.data;
  const epic = data?.kind === "ok" ? data.status : null;

  let badge = null;
  if (epic?.connected) badge = <Badge tone="green" dot>Connected</Badge>;
  else if (epic?.revoked) badge = <Badge tone="amber" dot>Needs reconnecting</Badge>;

  return (
    <Card aria-labelledby="mychart-title">
      <CardHeader
        id="mychart-title"
        icon={<Hospital className="size-5" aria-hidden="true" />}
        title="MyChart records"
        description="Medications, labs, visits and notes from your health system"
        action={badge}
      />

      {status.loading && !data ? <SkeletonLines lines={3} /> : null}

      {status.error && !data ? (
        <div className="flex flex-wrap items-center gap-3">
          <p role="alert" className="flex-1 text-sm font-semibold text-brand-red-dark">
            Couldn&rsquo;t check your MyChart connection: {status.error}
          </p>
          <Button variant="secondary" size="sm" onClick={status.reload}>
            Try again
          </Button>
        </div>
      ) : null}

      {data?.kind === "unconfigured" ? (
        <p className="flex items-start gap-3 rounded-2xl bg-surface-soft p-4 text-sm text-ink-soft">
          <Info className="mt-0.5 size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
          <span>
            MyChart connection isn&rsquo;t configured yet. Your care plan, check-ins and Foggy work as usual.
          </span>
        </p>
      ) : null}

      {epic && !epic.connected ? (
        <div>
          {epic.revoked ? (
            <p className="rounded-2xl bg-sev-medium/10 p-4 text-[0.95rem] text-ink ring-1 ring-sev-medium/25">
              MyChart access expired or was turned off. Reconnect to keep your records up to date.
            </p>
          ) : (
            <>
              <p className="text-[0.95rem] leading-relaxed text-ink-soft">
                Connect your MyChart account so your recovery companion can see the same records your hospital has,
                without uploading anything.
              </p>
              <ul className="mt-3 flex flex-wrap gap-2" aria-label="What CloudCare can read">
                {SHARED.map((item) => (
                  <li key={item}>
                    <Badge tone="pale">{item}</Badge>
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex items-start gap-2 text-sm text-brand-gray">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden="true" />
                <span>
                  Read-only. You sign in on MyChart, so CloudCare never sees your MyChart password, and you can
                  disconnect any time.
                </span>
              </p>
            </>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={connect} disabled={connecting} aria-live="polite">
              {connecting ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
              {connecting ? "Opening MyChart…" : epic.revoked ? "Reconnect MyChart" : "Connect MyChart"}
            </Button>
            {epic.revoked ? (
              <Button variant="ghost" size="sm" onClick={() => void disconnect()} disabled={disconnecting}>
                Remove connection
              </Button>
            ) : null}
          </div>

          {epic.sandbox ? (
            <p className="mt-3 text-xs text-brand-gray">
              Uses Epic&rsquo;s sandbox. Sign in with an Epic test patient, not your real MyChart account.
            </p>
          ) : null}
        </div>
      ) : null}

      {epic?.connected ? (
        <div>
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-2xl bg-surface-soft p-3">
              <dt className="text-brand-gray">Health system</dt>
              <dd className="mt-0.5 truncate font-bold text-ink">{issuerLabel(epic)}</dd>
            </div>
            <div className="rounded-2xl bg-surface-soft p-3">
              <dt className="text-brand-gray">Connected</dt>
              <dd className="mt-0.5 font-bold text-ink">
                {epic.connected_at ? formatDate(epic.connected_at, { month: "short", day: "numeric", year: "numeric" }) : "—"}
              </dd>
            </div>
            <div className="rounded-2xl bg-surface-soft p-3">
              <dt className="text-brand-gray">Last synced</dt>
              <dd className="mt-0.5 font-bold text-ink">
                {epic.last_sync_at
                  ? now === null
                    ? formatDate(epic.last_sync_at)
                    : relativeTime(epic.last_sync_at, now)
                  : "Not yet"}
              </dd>
            </div>
          </dl>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button variant="soft" size="sm" onClick={() => setRecordsVersion((v) => v + 1)}>
              <RefreshCw className="size-4" aria-hidden="true" />
              Refresh records
            </Button>
            {confirmDisconnect ? (
              <span className="flex flex-wrap items-center gap-2" role="group" aria-label="Confirm disconnect">
                <span className="text-sm font-semibold text-ink">Disconnect MyChart?</span>
                <Button variant="danger" size="sm" onClick={() => void disconnect()} disabled={disconnecting}>
                  {disconnecting ? "Disconnecting…" : "Yes, disconnect"}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmDisconnect(false)} disabled={disconnecting}>
                  Cancel
                </Button>
              </span>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setConfirmDisconnect(true)}>
                <Unlink className="size-4" aria-hidden="true" />
                Disconnect
              </Button>
            )}
          </div>

          <MyChartRecords version={recordsVersion} onGone={onGone} onSynced={onGone} />
        </div>
      ) : null}
    </Card>
  );
}
