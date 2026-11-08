"use client";

import { LoaderCircle, Save, X } from "lucide-react";
import { useId, useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Input";
import { ApiError, errorMessage } from "@/lib/api/client";
import { updatePatient } from "@/lib/api/patients";
import { PENDING_SETUP_PROCEDURE, type PatientOut, type PatientUpdate, type ProcedureType } from "@/lib/api/types";
import { formatAsTyped, formatPhone, optionalE164 } from "@/lib/phone";

const PROCEDURE_TYPES: { value: ProcedureType | string; label: string }[] = [
  { value: "orthopedic", label: "Orthopedic" },
  { value: "abdominal", label: "Abdominal" },
  { value: "cardiac", label: "Cardiac" },
  { value: "spine", label: "Spine" },
  { value: "other", label: "Other" },
];

const isProcedureType = (v: string): v is ProcedureType => PROCEDURE_TYPES.some((t) => t.value === v);

/** "a, b,c" -> ["a", "b", "c"], trimmed, no blanks. */
function splitList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function addUnique(list: string[], items: string[]): string[] {
  const seen = new Set(list.map((c) => c.toLowerCase()));
  const out = [...list];
  for (const item of items) {
    if (!seen.has(item.toLowerCase())) {
      seen.add(item.toLowerCase());
      out.push(item);
    }
  }
  return out;
}

/**
 * Clinician edit of a patient's profile. Sends only the fields that changed.
 * Used to finish patients who signed up themselves ("Pending clinician setup").
 */
export function PatientProfileForm({
  patient,
  onSaved,
}: {
  patient: PatientOut;
  onSaved: (patient: PatientOut) => void;
}) {
  const ids = useId();
  const pending = patient.procedure_name === PENDING_SETUP_PROCEDURE;
  const [procedureName, setProcedureName] = useState(pending ? "" : patient.procedure_name);
  // Keep a type the backend already has (e.g. "general") selectable; "unknown" means not set yet.
  const existingType = patient.procedure_type && patient.procedure_type !== "unknown" ? patient.procedure_type : "";
  const typeOptions =
    existingType && !isProcedureType(existingType)
      ? [...PROCEDURE_TYPES, { value: existingType, label: existingType.replace(/^\w/, (c) => c.toUpperCase()) }]
      : PROCEDURE_TYPES;
  const [procedureType, setProcedureType] = useState(existingType);
  const [surgeryDate, setSurgeryDate] = useState(patient.surgery_date);
  const [dischargeDate, setDischargeDate] = useState(patient.discharge_date ?? "");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [phone, setPhone] = useState(formatPhone(patient.phone));
  const [comorbidities, setComorbidities] = useState<string[]>(patient.comorbidities);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  function commitDraft(text = draft) {
    const items = splitList(text);
    if (items.length) setComorbidities((list) => addUnique(list, items));
    setDraft("");
  }

  function onDraftKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commitDraft();
    } else if (e.key === "Backspace" && !draft && comorbidities.length) {
      setComorbidities((list) => list.slice(0, -1));
    }
  }

  function buildUpdate(): PatientUpdate {
    const body: PatientUpdate = {};
    const name = procedureName.trim();
    if (name && name !== patient.procedure_name) body.procedure_name = name;
    if (procedureType && procedureType !== patient.procedure_type) body.procedure_type = procedureType;
    if (surgeryDate && surgeryDate !== patient.surgery_date) body.surgery_date = surgeryDate;
    if (dischargeDate && dischargeDate !== (patient.discharge_date ?? "")) body.discharge_date = dischargeDate;
    if (dateOfBirth) body.date_of_birth = dateOfBirth;
    const finalList = addUnique(comorbidities, splitList(draft));
    if (finalList.join("\u0000") !== patient.comorbidities.join("\u0000")) body.comorbidities = finalList;
    const mobile = optionalE164(phone);
    if (mobile.ok && mobile.e164 !== (patient.phone ?? null)) body.phone = mobile.e164;
    return body;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (saving) return;
    setError(null);
    if (!procedureName.trim()) return setError("Enter the procedure name.");
    if (!procedureType) return setError("Choose the procedure type.");
    if (dischargeDate && surgeryDate && dischargeDate < surgeryDate) {
      return setError("The discharge date can't be before the surgery date.");
    }
    const mobile = optionalE164(phone);
    if (!mobile.ok) return setError(mobile.error);
    const body = buildUpdate();
    commitDraft();
    if (Object.keys(body).length === 0) return setError("Nothing changed yet.");
    setSaving(true);
    try {
      onSaved(await updatePatient(patient.id, body));
      setDateOfBirth("");
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 405)) setUnavailable(true);
      else setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (unavailable) {
    return (
      <p role="status" className="rounded-2xl bg-surface-soft px-4 py-3 text-sm text-ink-soft">
        Editing profiles isn&rsquo;t available on this server yet.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {pending ? (
        <p className="rounded-2xl bg-sev-medium/10 px-4 py-3 text-sm text-ink ring-1 ring-sev-medium/30">
          This patient signed up on their own. Add their procedure and dates so reminders, check-ins and Foggy fit
          their recovery.
        </p>
      ) : null}

      <Field label="Procedure" htmlFor={`${ids}-name`}>
        <Input
          id={`${ids}-name`}
          value={procedureName}
          onChange={(e) => setProcedureName(e.target.value)}
          placeholder="Total knee replacement (right)"
          required
        />
      </Field>

      <Field label="Procedure type" htmlFor={`${ids}-type`}>
        <Select id={`${ids}-type`} value={procedureType} onChange={(e) => setProcedureType(e.target.value)} required>
          <option value="" disabled>
            Choose a type
          </option>
          {typeOptions.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Surgery date" htmlFor={`${ids}-surgery`}>
          <Input id={`${ids}-surgery`} type="date" value={surgeryDate} onChange={(e) => setSurgeryDate(e.target.value)} />
        </Field>
        <Field label="Discharge date" htmlFor={`${ids}-discharge`}>
          <Input
            id={`${ids}-discharge`}
            type="date"
            value={dischargeDate}
            min={surgeryDate || undefined}
            onChange={(e) => setDischargeDate(e.target.value)}
          />
        </Field>
      </div>

      <Field label="Date of birth" htmlFor={`${ids}-dob`} hint="Leave blank to keep what's on file.">
        <Input id={`${ids}-dob`} type="date" value={dateOfBirth} onChange={(e) => setDateOfBirth(e.target.value)} />
      </Field>

      <Field label="Mobile number" htmlFor={`${ids}-phone`} hint="Used only for the patient's own check-in texts and calls. Clear it to remove.">
        <Input
          id={`${ids}-phone`}
          type="tel"
          inputMode="tel"
          autoComplete="off"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onBlur={() => setPhone((p) => formatAsTyped(p))}
          placeholder="(555) 123-4567"
        />
      </Field>

      <Field label="Comorbidities" htmlFor={`${ids}-comorb`} hint="Type and press Enter or a comma, e.g. diabetes, smoker.">
        <div className="flex flex-wrap items-center gap-1.5 rounded-2xl border border-line bg-white px-2 py-2 focus-within:border-brand-cyan">
          {comorbidities.map((c) => (
            <span
              key={c}
              className="inline-flex items-center gap-0.5 rounded-full bg-surface-pale py-0.5 pr-0.5 pl-3 text-sm font-bold text-brand-cyan-strong"
            >
              {c}
              <button
                type="button"
                onClick={() => setComorbidities((list) => list.filter((x) => x !== c))}
                aria-label={`Remove ${c}`}
                className="grid size-9 place-items-center rounded-full hover:bg-white"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            </span>
          ))}
          <input
            id={`${ids}-comorb`}
            value={draft}
            onChange={(e) => {
              const v = e.target.value;
              if (v.includes(",")) commitDraft(v);
              else setDraft(v);
            }}
            onKeyDown={onDraftKey}
            onBlur={() => commitDraft()}
            placeholder={comorbidities.length ? "Add another" : "None recorded"}
            className="h-9 min-w-[8rem] flex-1 bg-transparent px-2 text-base sm:text-[0.98rem] text-ink placeholder:text-brand-gray/70 focus:outline-none"
          />
        </div>
      </Field>

      {error ? (
        <p role="alert" className="rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
          {error}
        </p>
      ) : null}

      <div>
        <Button type="submit" disabled={saving}>
          {saving ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
          Save profile
        </Button>
      </div>
    </form>
  );
}
