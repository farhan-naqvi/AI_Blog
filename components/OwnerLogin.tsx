"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Brand } from "./Brand";
import { createBrowserClient } from "@/lib/supabase-browser";

export function OwnerLogin() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const client = createBrowserClient();
    if (!client) { setError("Supabase browser configuration is missing."); setBusy(false); return; }
    const { error: signInError } = await client.auth.signInWithPassword({ email: String(form.get("email")), password: String(form.get("password")) });
    if (signInError) { setError(signInError.message); setBusy(false); return; }
    const { data } = await client.from("private_settings").select("id").limit(1);
    if (!data?.length) { await client.auth.signOut(); setError("This account is not authorized as the owner."); setBusy(false); return; }
    router.replace("/admin"); router.refresh();
  }
  return <main className="login-page"><div className="login-card"><Brand /><div className="panel-label">PRIVATE OWNER WORKSPACE</div><h1>Automation control</h1><p>Sign in with the owner account configured in Supabase. No private records are available to public sessions.</p><form onSubmit={submit}><label>Email<input required type="email" name="email" autoComplete="email" /></label><label>Password<input required type="password" name="password" autoComplete="current-password" /></label>{error ? <div className="form-error">{error}</div> : null}<button disabled={busy} className="button primary" type="submit">{busy ? "Verifying…" : "Sign in →"}</button></form></div></main>;
}
