"use client";

import { useCallback, useEffect, useState } from "react";
import { createBrowserClient } from "@/lib/supabase-browser";

type Row = Record<string, unknown>;
const labels: Record<string, [string, string]> = {
  dashboard: ["Automation dashboard", "Live operational status across collection, local processing, and publication."],
  "processing-queue": ["Processing queue", "Pending, claimed, failed, and recently completed local-intelligence jobs."],
  exceptions: ["Exception queue", "Conflicting, sensitive, or insufficiently supported developments awaiting review."],
  sources: ["Source management", "Pause, resume, and inspect the configured source registry."],
  "editorial-rules": ["Editorial rules", "Transparent deterministic gates used after local-model extraction."],
  "linkedin-studio": ["LinkedIn studio", "Private temporary drafts. Unpinned drafts expire 48 hours after creation."],
  "system-health": ["System health", "Collection and local-worker freshness without verbose long-term logs."],
  settings: ["Settings", "Owner identity and queue/retention policy stored privately in Supabase."],
};

function relative(value: unknown) {
  if (!value) return "Never";
  const minutes = Math.round((Date.now() - new Date(String(value)).getTime()) / 60000);
  if (minutes < 60) return `${Math.max(0, minutes)}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
  return `${Math.floor(minutes / 1440)}d ago`;
}

export function AdminWorkspace({ section = "dashboard" }: { section?: string }) {
  const [rows, setRows] = useState<Row[]>([]); const [loading, setLoading] = useState(true); const [message, setMessage] = useState("");
  const [title, subtitle] = labels[section] ?? labels.dashboard;
  const load = useCallback(async () => {
    const client = createBrowserClient(); if (!client) return;
    setLoading(true); setMessage("");
    let result;
    if (section === "processing-queue") result = await client.from("processing_jobs").select("id,status,job_type,priority,attempt_count,claimed_by,created_at,last_error").order("created_at", { ascending: false }).limit(100);
    else if (section === "exceptions") result = await client.from("exceptions").select("id,exception_type,reason,status,created_at,developments(headline)").order("created_at", { ascending: false }).limit(100);
    else if (section === "sources") result = await client.from("sources").select("id,name,source_type,retrieval_method,active,last_success_at,last_error").order("name");
    else if (section === "linkedin-studio") result = await client.from("linkedin_drafts").select("id,content,angle,status,pinned,created_at,expires_at,external_url,developments(headline)").order("created_at", { ascending: false });
    else if (section === "settings") result = await client.from("private_settings").select("owner_email,max_pending_jobs,max_pending_age_days,linkedin_draft_ttl_hours,updated_at").limit(1);
    else if (section === "system-health" || section === "dashboard") { const rpc = await client.rpc("system_health_snapshot"); result = { data: rpc.data ? [rpc.data as Row] : [], error: rpc.error }; }
    else result = { data: [], error: null };
    if (result.error) setMessage(result.error.message); else setRows((result.data ?? []) as Row[]);
    setLoading(false);
  }, [section]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function patch(table: string, id: unknown, values: Row) { const client = createBrowserClient(); if (!client) return; const { error } = await client.from(table).update(values).eq("id", id); setMessage(error?.message ?? "Saved"); await load(); }
  async function remove(table: string, id: unknown) { const client = createBrowserClient(); if (!client || !confirm("Delete this temporary record?")) return; const { error } = await client.from(table).delete().eq("id", id); setMessage(error?.message ?? "Deleted"); await load(); }

  return <><header className="admin-head"><div><span>AUTOMATION CONTROL</span><h1>{title}</h1><p>{subtitle}</p></div><div className="health-pill"><i /> Owner only</div></header>{message ? <div className="admin-message">{message}</div> : null}<section className="admin-content">{loading ? <p>Loading private workspace…</p> : section === "dashboard" || section === "system-health" ? <Health rows={rows} /> : section === "processing-queue" ? <Queue rows={rows} /> : section === "exceptions" ? <Exceptions rows={rows} patch={patch} /> : section === "sources" ? <Sources rows={rows} patch={patch} /> : section === "linkedin-studio" ? <Drafts rows={rows} patch={patch} remove={remove} /> : section === "settings" ? <Settings rows={rows} /> : <Rules />}</section></>;
}

function Health({ rows }: { rows: Row[] }) { const health = rows[0] ?? {}; const cards = [["Healthy sources", health.healthy_sources ?? 0], ["Failing sources", health.failing_sources ?? 0], ["Pending jobs", health.pending_jobs ?? 0], ["Failed jobs", health.failed_jobs ?? 0], ["Open exceptions", health.open_exceptions ?? 0]]; return <><div className="admin-metrics">{cards.map(([label, value]) => <div key={String(label)}><span>{String(label)}</span><strong>{String(value)}</strong></div>)}</div><div className="health-timeline"><div><span>Last successful collection</span><strong>{relative(health.last_collection)}</strong></div><div><span>Last local-model processing</span><strong>{relative(health.last_processing)}</strong></div><div><span>Cloud collection</span><strong className="good">Continues while local worker is offline</strong></div></div></>; }
function Queue({ rows }: { rows: Row[] }) { return rows.length ? <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Status</th><th>Job</th><th>Priority</th><th>Attempts</th><th>Worker</th><th>Created</th></tr></thead><tbody>{rows.map((row) => <tr key={String(row.id)}><td><span className={`status ${String(row.status).toLowerCase()}`}>{String(row.status)}</span></td><td>{String(row.job_type)}</td><td>{String(row.priority)}</td><td>{String(row.attempt_count)}</td><td>{String(row.claimed_by ?? "—")}</td><td>{relative(row.created_at)}</td></tr>)}</tbody></table></div> : <AdminEmpty text="No processing jobs." />; }
function Exceptions({ rows, patch }: { rows: Row[]; patch: (table: string, id: unknown, values: Row) => Promise<void> }) { return rows.length ? <div className="exception-list">{rows.map((row) => <article key={String(row.id)}><div><span className="status held">{String(row.exception_type)}</span><h3>{String((row.developments as Row | null)?.headline ?? "Held development")}</h3><p>{String(row.reason)}</p></div><button onClick={() => patch("exceptions", row.id, { status: "Resolved", resolved_at: new Date().toISOString() })}>Resolve</button></article>)}</div> : <AdminEmpty text="No open exceptions." />; }
function Sources({ rows, patch }: { rows: Row[]; patch: (table: string, id: unknown, values: Row) => Promise<void> }) { return <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Source</th><th>Type</th><th>Method</th><th>Last success</th><th>Status</th></tr></thead><tbody>{rows.map((row) => <tr key={String(row.id)}><td><strong>{String(row.name)}</strong>{row.last_error ? <small>{String(row.last_error).slice(0, 100)}</small> : null}</td><td>{String(row.source_type)}</td><td>{String(row.retrieval_method)}</td><td>{relative(row.last_success_at)}</td><td><button className={`toggle ${row.active ? "on" : ""}`} onClick={() => patch("sources", row.id, { active: !row.active })} aria-label={`${row.active ? "Pause" : "Resume"} ${row.name}`}><i /></button></td></tr>)}</tbody></table></div>; }
function Drafts({ rows, patch, remove }: { rows: Row[]; patch: (table: string, id: unknown, values: Row) => Promise<void>; remove: (table: string, id: unknown) => Promise<void> }) { return rows.length ? <div className="draft-grid">{rows.map((row) => <article className="draft-card" key={String(row.id)}><div className="eyebrow"><span>{String(row.angle)}</span><span>Expires {relative(row.expires_at).replace(" ago", "")}</span></div><h3>{String((row.developments as Row | null)?.headline ?? "LinkedIn draft")}</h3><textarea defaultValue={String(row.content)} onBlur={(event) => patch("linkedin_drafts", row.id, { content: event.currentTarget.value })} /><label className="external-url">Published post URL<input type="url" defaultValue={String(row.external_url ?? "")} placeholder="https://www.linkedin.com/posts/…" onBlur={(event) => patch("linkedin_drafts", row.id, { external_url: event.currentTarget.value || null })} /></label><div><button onClick={() => navigator.clipboard.writeText(String(row.content))}>Copy</button><button onClick={() => patch("linkedin_drafts", row.id, { pinned: !row.pinned })}>{row.pinned ? "Unpin" : "Pin"}</button><button onClick={() => patch("linkedin_drafts", row.id, { status: "Published", published_at: new Date().toISOString() })}>Mark published</button><button onClick={() => remove("linkedin_drafts", row.id)}>Delete</button></div></article>)}</div> : <AdminEmpty text="No temporary LinkedIn draft. At most one is recommended each day." />; }
function Rules() { return <div className="rules-grid"><article><span>01</span><h3>Strong primary evidence</h3><p>An official announcement, documentation, repository, or research paper is required.</p></article><article><span>02</span><h3>No material contradiction</h3><p>Conflicting claims enter the exception queue and cannot auto-publish.</p></article><article><span>03</span><h3>Importance threshold</h3><p>Only Major or Notable developments can publish automatically.</p></article><article><span>04</span><h3>Sensitive claims are held</h3><p>Security, medical, political, misconduct, job-loss, and unverified financial claims require review.</p></article></div>; }
function Settings({ rows }: { rows: Row[] }) { const row = rows[0] ?? {}; return <div className="settings-card"><dl><div><dt>Owner email</dt><dd>{String(row.owner_email ?? "Set after first Supabase user")}</dd></div><div><dt>Maximum pending jobs</dt><dd>{String(row.max_pending_jobs ?? 500)}</dd></div><div><dt>Maximum pending age</dt><dd>{String(row.max_pending_age_days ?? 7)} days</dd></div><div><dt>LinkedIn draft retention</dt><dd>{String(row.linkedin_draft_ttl_hours ?? 48)} hours</dd></div></dl><p>Secrets and model configuration stay in server or local-worker environment variables; they are never returned to this browser.</p></div>; }
function AdminEmpty({ text }: { text: string }) { return <div className="admin-empty"><span className="pulse-ring" /><p>{text}</p></div>; }
