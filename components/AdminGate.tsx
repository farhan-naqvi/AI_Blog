"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createBrowserClient } from "@/lib/supabase-browser";

export function AdminGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  useEffect(() => {
    const client = createBrowserClient();
    if (!client) { router.replace("/owner-login"); return; }
    client.auth.getSession().then(async ({ data }) => {
      if (!data.session) { router.replace("/owner-login"); return; }
      const { data: settings } = await client.from("private_settings").select("id").limit(1);
      if (!settings?.length) { await client.auth.signOut(); router.replace("/owner-login"); return; }
      setAllowed(true);
    });
  }, [router]);
  return allowed ? children : <div className="admin-loading"><span className="pulse-ring" /><p>Verifying owner access…</p></div>;
}
