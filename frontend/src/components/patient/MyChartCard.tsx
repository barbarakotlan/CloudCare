"use client";

import { Check, Copy, Hospital, Info, LoaderCircle, RefreshCw, ShieldCheck, Unlink } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import type { ToastItem } from "@/components/ui/Toast";
import { ApiError, errorMessage } from "@/lib/api/client";
import { disconnectEpic, epicErrorText, getEpicStatus, startEpicConnect, type EpicStatus } from "@/lib/api/epic";
import {
  broadcastEpicResult,
  EPIC_POPUP_FEATURES,
  EPIC_POPUP_NAME,
  listenForEpicResult,
  readEpicResult,
  type EpicPopupMessage,
} from "@/lib/epicPopup";
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

function notifyResult(notify: Notify, result: EpicPopupMessage) {
  if (result.status === "connected") {
    notify({ tone: "success", title: "MyChart connected", body: "Your records are loading below." });
  } else {
    notify({ tone: "alert", title: "MyChart wasn't connected", body: epicErrorText(result.reason) });
  }
}

/**
 * Reads ?epic=connected|error&reason= once (set by our OAuth callback) when the
 * dashboard itself landed there (popup blocked, or a popup that lost its opener),
 * toasts, tells other CloudCare tabs, and cleans the URL.
 */
function useEpicReturnToast(notify: Notify) {
  useEffect(() => {
    const url = new URL(window.location.href);
    const result = readEpicResult(url.search);
    if (!url.searchParams.has("epic")) return;
    if (result) {
      notifyResult(notify, result);
      if (url.searchParams.get("popup") === "1") broadcastEpicResult(result);
    }
    url.searchParams.delete("epic");
    url.searchParams.delete("reason");
    url.searchParams.delete("popup");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }, [notify]);
}

/** Placeholder content while the popup waits for Epic's sign-in URL. */
function showOpening(popup: Window) {
  try {
    popup.document.title = "Opening MyChart";
    popup.document.body.style.cssText =
      "margin:0;height:100vh;display:grid;place-items:center;font:600 16px system-ui,sans-serif;color:#1C2630;background:#F5FAFC";
    popup.document.body.textContent = "Opening MyChart…";
  } catch {
    // Window already on another site from an earlier attempt; it navigates in a moment anyway.
  }
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
  // The MyChart popup we're waiting on, and the status poll that backs up its message.
  const [waiting, setWaiting] = useState(false);
  const popupRef = useRef<Window | null>(null);
  const pollRef = useRef<number | null>(null);
  const connectedRef = useRef(false);

  useEpicReturnToast(notify);

  const reloadStatus = status.reload;
  const onGone = useCallback(() => reloadStatus(), [reloadStatus]);

  const data = status.data;
  const epic = data?.kind === "ok" ? data.status : null;
  useEffect(() => {
    connectedRef.current = Boolean(epic?.connected);
  }, [epic?.connected]);

  const stopWaiting = useCallback(() => {
    if (pollRef.current !== null) window.clearInterval(pollRef.current);
    pollRef.current = null;
    popupRef.current = null;
    setWaiting(false);
    setConnecting(false);
  }, []);

  // Results from the popup (postMessage) or from a popup that lost its opener (BroadcastChannel).
  useEffect(
    () =>
      listenForEpicResult((result) => {
        stopWaiting();
        notifyResult(notify, result);
        // Records mount (and load) when the status flips to connected; refetch only if already showing.
        if (connectedRef.current) setRecordsVersion((v) => v + 1);
        reloadStatus();
      }),
    [notify, reloadStatus, stopWaiting],
  );

  useEffect(
    () => () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    },
    [],
  );

  /** Backup for a lost message: poll /epic/status every 2 s while the popup is open. */
  function watchPopup(popup: Window) {
    if (pollRef.current !== null) window.clearInterval(pollRef.current);
    popupRef.current = popup;
    setWaiting(true);
    pollRef.current = window.setInterval(() => {
      const current = popupRef.current;
      if (!current || current.closed) {
        stopWaiting();
        reloadStatus();
        return;
      }
      getEpicStatus().then(
        (s) => {
          if (s.connected && popupRef.current === current) {
            stopWaiting();
            reloadStatus();
          }
        },
        () => {
          // Keep waiting; the popup's own message or the next poll will tell us.
        },
      );
    }, 2000);
  }

  async function connect() {
    // Open the window inside the click so popup blockers allow it, then point it at Epic.
    const popup = window.open("", EPIC_POPUP_NAME, EPIC_POPUP_FEATURES);
    if (popup) showOpening(popup);
    setConnecting(true);
    try {
      const url = await startEpicConnect();
      if (!popup) {
        // Popup blocked: sign in in this tab instead. Stay busy while the browser navigates away.
        window.location.assign(url);
        return;
      }
      if (popup.closed) {
        setConnecting(false);
        return;
      }
      popup.location.href = url;
      popup.focus();
      watchPopup(popup);
    } catch (err) {
      popup?.close();
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
              {waiting
                ? "Waiting for MyChart…"
                : connecting
                  ? "Opening MyChart…"
                  : epic.revoked
                    ? "Reconnect MyChart"
                    : "Connect MyChart"}
            </Button>
            {waiting ? (
              <Button variant="ghost" size="sm" onClick={() => popupRef.current?.focus()}>
                Show the MyChart window
              </Button>
            ) : null}
            {epic.revoked ? (
              <Button variant="ghost" size="sm" onClick={() => void disconnect()} disabled={disconnecting}>
                Remove connection
              </Button>
            ) : null}
          </div>

          {epic.sandbox ? <SandboxLogin /> : null}
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

/** Epic's public sandbox test patient (from Epic's developer docs; not a real person). */
const SANDBOX_LOGIN = [
  { label: "Username", value: "fhircamila" },
  { label: "Password", value: "epicepic1" },
] as const;

/** Shown under Connect while the API points at Epic's sandbox. */
function SandboxLogin() {
  return (
    <div className="mt-4 rounded-2xl bg-surface-soft p-4 ring-1 ring-line/70">
      <p className="text-sm font-extrabold text-ink">Demo MyChart login</p>
      <p className="mt-0.5 text-sm text-ink-soft">Epic test patient</p>
      <dl className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-3">
        {SANDBOX_LOGIN.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-2 rounded-xl bg-white py-1 pr-1 pl-3 ring-1 ring-line">
            <dt className="text-xs font-bold text-brand-gray">{item.label}</dt>
            <dd id={`epic-demo-${item.label.toLowerCase()}`} className="min-w-0 flex-1 font-mono text-sm font-bold break-all text-ink select-all">
              {item.value}
            </dd>
            <CopyButton value={item.value} label={item.label.toLowerCase()} targetId={`epic-demo-${item.label.toLowerCase()}`} />
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs leading-relaxed text-brand-gray">
        Use this on Epic&rsquo;s login page; it is public test data, not a real person.
      </p>
    </div>
  );
}

/**
 * Clipboard API first; where it's blocked (some embedded browsers), select the text on
 * screen and try the legacy copy command, so at worst the value is selected for Ctrl/Cmd+C.
 */
function copyBySelecting(targetId: string): boolean {
  const node = document.getElementById(targetId);
  const selection = window.getSelection();
  if (!node || !selection) return false;
  const range = document.createRange();
  range.selectNodeContents(node);
  selection.removeAllRanges();
  selection.addRange(range);
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  }
}

function CopyButton({ value, label, targetId }: { value: string; label: string; targetId: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setState("copied");
    } catch {
      setState(copyBySelecting(targetId) ? "copied" : "failed");
    }
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState("idle"), 1800);
  }

  return (
    <button
      type="button"
      onClick={() => void copy()}
      aria-label={`Copy ${label}`}
      className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-xs font-bold text-brand-cyan-strong transition-colors hover:bg-surface-pale focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan"
    >
      {state === "copied" ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
      <span aria-live="polite">{state === "copied" ? "Copied" : state === "failed" ? "Selected" : "Copy"}</span>
    </button>
  );
}
