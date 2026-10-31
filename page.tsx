"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Scheme } from "../lib";

const FIELDS: { key: string; label: string; why: string; type: "text" | "number" | "select"; options?: string[] }[] = [
  { key: "course_level", label: "Course level", why: "Schemes are limited to certain levels of study.", type: "select", options: ["ug", "pg", "diploma", "phd", "other"] },
  { key: "course_name", label: "Course name", why: "Some schemes cover only certain courses.", type: "text" },
  { key: "study_mode", label: "Study mode", why: "Many schemes need regular, full-time study.", type: "select", options: ["regular", "distance", "part_time"] },
  { key: "state_domicile", label: "State of domicile", why: "Some schemes depend on your home state.", type: "text" },
  { key: "category", label: "Category", why: "Some schemes are reserved for specific categories.", type: "select", options: ["general", "sc", "st", "obc", "ews", "minority"] },
  { key: "family_income_annual", label: "Family income per year (Rs)", why: "Most schemes set an income limit.", type: "number" },
  { key: "last_exam_percentage", label: "Last exam percentage", why: "Some schemes set a minimum mark.", type: "number" },
];

const STATUS_TEXT = { OPEN: "Open", CLOSED: "Closed", UNKNOWN: "Deadline not verified" } as const;

export default function Discover() {
  const [schemes, setSchemes] = useState<Scheme[] | null>(null);
  const [profile, setProfile] = useState<Record<string, string | number>>({});
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Scheme[]>("/schemes").then(setSchemes).catch((e) => setError(e.message));
    api<Record<string, string | number>>("/profile").then(setProfile).catch(() => {});
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaved(""); setError("");
    const body: Record<string, unknown> = {};
    for (const f of FIELDS) {
      const v = profile[f.key];
      if (v !== undefined && v !== "") body[f.key] = f.type === "number" ? Number(v) : v;
    }
    try { await api("/profile", { method: "PUT", body: JSON.stringify(body) }); setSaved("Saved."); }
    catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="grid gap-8 md:grid-cols-[1fr_2fr]">
      <form onSubmit={save} className="space-y-4 rounded border border-line bg-white p-5">
        <h2 className="text-xl font-bold">Your details</h2>
        <p className="text-sm">Fill in only what you are comfortable sharing. Anything left blank is treated as unknown, never as a pass.</p>
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            {f.label}
            <span className="block text-sm text-ink/70">{f.why}</span>
            {f.type === "select" ? (
              <select className="mt-1 w-full rounded border border-line p-2" value={String(profile[f.key] ?? "")} onChange={(e) => setProfile({ ...profile, [f.key]: e.target.value })}>
                <option value="">Not provided</option>
                {f.options!.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input className="mt-1 w-full rounded border border-line p-2" type={f.type} value={String(profile[f.key] ?? "")} onChange={(e) => setProfile({ ...profile, [f.key]: e.target.value })} />
            )}
          </label>
        ))}
        <button className="rounded bg-teal px-4 py-2 font-bold text-white">Save details</button>
        {saved && <p role="status">{saved}</p>}
      </form>

      <section>
        <h1 className="text-2xl font-bold">Scholarships</h1>
        {error && <p role="alert" className="mt-2 text-rose">{error}</p>}
        {schemes && schemes.length === 0 && (
          <p className="mt-4 rounded border border-line bg-white p-5">
            No schemes have been added from official sources yet. An administrator needs to fetch an official page and add
            schemes with their source before they appear here. We do not show scholarships we cannot trace to an official source.
          </p>
        )}
        <ul className="mt-4 space-y-4">
          {schemes?.map((s) => (
            <li key={s.id} className="rounded border border-line bg-white p-5">
              <h2 className="text-lg font-bold">{s.name}</h2>
              <p className="text-sm">{s.provider ?? "Provider not recorded"} · Academic year {s.academic_year}</p>
              <p className="mt-2">
                <span className="font-bold">{STATUS_TEXT[s.application_status]}</span>
                {s.application_deadline && s.deadline_verified && ` · closes ${s.application_deadline}`}
              </p>
              {s.required_documents.length > 0 && <p className="mt-1 text-sm">Documents: {s.required_documents.join(", ")}</p>}
              <p className="mt-2 text-sm">
                Source:{" "}
                <a className="underline" href={s.official_url} target="_blank" rel="noreferrer">official page</a>
                {s.guideline_url && <> · <a className="underline" href={s.guideline_url} target="_blank" rel="noreferrer">guidelines</a></>}
                {" "}· retrieved {new Date(s.retrieved_at).toLocaleString()}
              </p>
              {s.possibly_outdated && <p className="mt-1 text-sm font-bold text-amber">This information is more than 7 days old and may be outdated.</p>}
              <div className="mt-3">
                {s.has_approved_rules
                  ? <Link className="rounded bg-ink px-3 py-2 font-bold text-white" href={`/eligibility/${s.id}`}>Check my eligibility</Link>
                  : <p className="text-sm">Eligibility rules for this scheme have not been verified yet, so we cannot assess it.</p>}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
