"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Brand } from "./Brand";
import { createBrowserClient } from "@/lib/supabase-browser";

const links = [
  ["Overview", "/admin", "◫"], ["Processing queue", "/admin/processing-queue", "⇄"],
  ["Exceptions", "/admin/exceptions", "!"], ["Sources", "/admin/sources", "◎"],
  ["Editorial rules", "/admin/editorial-rules", "≡"], ["LinkedIn studio", "/admin/linkedin-studio", "in"],
  ["System health", "/admin/system-health", "⌁"], ["Settings", "/admin/settings", "⚙"],
];

export function AdminNav() {
  const pathname = usePathname(); const router = useRouter();
  async function signOut() { await createBrowserClient()?.auth.signOut(); router.replace("/owner-login"); }
  return <aside className="admin-nav"><Brand /><div className="workspace-label">OWNER WORKSPACE</div><nav>{links.map(([label, href, icon]) => <Link className={pathname === href ? "active" : ""} key={href} href={href}><i>{icon}</i>{label}</Link>)}</nav><button onClick={signOut}>Sign out</button></aside>;
}
