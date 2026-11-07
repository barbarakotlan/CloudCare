"use client";

import { CheckCircle2, FileText, LoaderCircle, Upload } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Input";
import { errorMessage } from "@/lib/api/client";
import { uploadCarePlan } from "@/lib/api/patients";
import type { CarePlanOut } from "@/lib/api/types";
import { DEMO_CARE_PLAN_TEXT, DEMO_CARE_PLAN_TITLE, splitIntoChunks } from "@/lib/demo/demoCarePlan";

export function CarePlanUpload({
  patientId,
  patientName,
  hasPlan = false,
  onSaved,
}: {
  patientId: string;
  patientName: string;
  /** A plan is already active: word the form as replacing it. */
  hasPlan?: boolean;
  onSaved?: (plan: CarePlanOut) => void;
}) {
  const [title, setTitle] = useState("");
  const [raw, setRaw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<CarePlanOut | null>(null);
  const ids = useId();
  const preview = raw.trim() ? splitIntoChunks(raw) : [];

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!raw.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const plan = await uploadCarePlan(patientId, { title: title.trim() || "Care plan", raw_text: raw });
      setSaved(plan);
      onSaved?.(plan);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (saved) {
    return (
      <div role="status" className="rounded-3xl bg-ok/8 p-5 ring-1 ring-ok/25">
        <p className="flex items-center gap-2 font-extrabold text-[#146b49]">
          <CheckCircle2 className="size-5" aria-hidden="true" />
          Care plan updated for {patientName}
        </p>
        <p className="mt-1 text-sm text-ink-soft">
          &ldquo;{saved.title}&rdquo; is now active with {saved.chunks.length} section{saved.chunks.length === 1 ? "" : "s"}.
          Foggy answers from it immediately.
        </p>
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {saved.chunks.map((c) => (
            <li key={c.id} className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-brand-cyan-strong ring-1 ring-line">
              {c.section ?? `Part ${c.chunk_index + 1}`}
            </li>
          ))}
        </ul>
        <Button
          variant="secondary"
          size="sm"
          className="mt-4"
          onClick={() => {
            setSaved(null);
            setTitle("");
            setRaw("");
          }}
        >
          Replace plan again
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <p className="rounded-2xl bg-surface-soft px-4 py-3 text-sm text-ink-soft">
        {hasPlan
          ? `Saving replaces ${patientName}’s current plan above.`
          : `${patientName} has no care plan yet. Foggy answers from the one you save here.`}{" "}
        Separate sections with a blank line; a short first line ending in &ldquo;:&rdquo; becomes the section name
        Foggy cites.
      </p>
      <Field label="Plan title" htmlFor={`${ids}-title`}>
        <Input
          id={`${ids}-title`}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={DEMO_CARE_PLAN_TITLE}
        />
      </Field>
      <Field
        label="Instructions"
        htmlFor={`${ids}-raw`}
        hint={preview.length ? `${preview.length} section${preview.length === 1 ? "" : "s"}: ${preview.map((p) => p.section ?? "untitled").join(", ")}` : undefined}
      >
        <Textarea
          id={`${ids}-raw`}
          rows={12}
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          placeholder={"Wound care:\nKeep the incision clean and dry…\n\nWhen to call:\nCall your surgeon if…"}
          className="font-mono text-sm"
          required
        />
      </Field>
      {error ? (
        <p role="alert" className="rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
          {error}
        </p>
      ) : null}
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <Button type="submit" disabled={!raw.trim() || submitting}>
          {submitting ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Upload className="size-4" aria-hidden="true" />}
          {hasPlan ? "Replace plan" : "Save care plan"}
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            setTitle(DEMO_CARE_PLAN_TITLE);
            setRaw(DEMO_CARE_PLAN_TEXT);
          }}
        >
          <FileText className="size-4" aria-hidden="true" />
          Insert knee-replacement template
        </Button>
      </div>
    </form>
  );
}
