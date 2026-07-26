import type { Development, PublicPlatformStats, Report, Source } from "./types";

const baseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, "");
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

async function publicQuery<T>(path: string): Promise<T[]> {
  if (!baseUrl || !anonKey) return [];
  try {
    const response = await fetch(`${baseUrl}/rest/v1/${path}`, {
      headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}` },
      cache: "no-store",
    });
    if (!response.ok) return [];
    return (await response.json()) as T[];
  } catch {
    return [];
  }
}

async function publicRpc<T>(name: string, body: Record<string, string>): Promise<T[]> {
  if (!baseUrl || !anonKey) return [];
  try {
    const response = await fetch(`${baseUrl}/rest/v1/rpc/${name}`, {
      method: "POST",
      headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}`, "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    return response.ok ? (await response.json()) as T[] : [];
  } catch {
    return [];
  }
}

async function publicRpcObject<T>(name: string): Promise<T | null> {
  if (!baseUrl || !anonKey) return null;
  try {
    const response = await fetch(`${baseUrl}/rest/v1/rpc/${name}`, {
      method: "POST",
      headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}`, "content-type": "application/json" },
      body: "{}",
      cache: "no-store",
    });
    return response.ok ? await response.json() as T : null;
  } catch {
    return null;
  }
}

export function getDevelopments(limit = 20): Promise<Development[]> {
  return publicQuery<Development>(
    `developments?select=*&publication_status=eq.Published&verification_status=eq.Verified&order=published_at.desc&limit=${limit}`,
  );
}

export async function getDevelopment(slug: string): Promise<Development | null> {
  const rows = await publicQuery<Development>(
    `developments?select=*&slug=eq.${encodeURIComponent(slug)}&publication_status=eq.Published&verification_status=eq.Verified&limit=1`,
  );
  return rows[0] ?? null;
}

export function getReports(type?: "Daily" | "Weekly", limit = 12): Promise<Report[]> {
  const filter = type ? `&report_type=eq.${type}` : "";
  return publicQuery<Report>(
    `reports?select=*&publication_status=eq.Published${filter}&order=published_at.desc&limit=${limit}`,
  );
}

export function getSources(): Promise<Source[]> {
  return publicRpc<Source>("get_public_sources", {});
}

export function getPublicPlatformStats(): Promise<PublicPlatformStats | null> {
  return publicRpcObject<PublicPlatformStats>("get_public_platform_stats");
}

export function searchDevelopments(query: string): Promise<Development[]> {
  const safe = query.trim().slice(0, 100).replace(/[&|!:*()]/g, " ");
  if (!safe) return Promise.resolve([]);
  return publicRpc<Development>("search_public_developments", { p_query: safe });
}

export function getRelatedDevelopments(item: Development): Promise<Development[]> {
  return publicQuery<Development>(`developments?select=*&publication_status=eq.Published&verification_status=eq.Verified&category=eq.${encodeURIComponent(item.category)}&id=neq.${item.id}&order=published_at.desc&limit=3`);
}

export async function getDevelopmentSources(developmentId: string) {
  return publicQuery<{
    evidence_role: string;
    is_primary: boolean;
    source_items: { title: string; canonical_url: string; published_at: string | null };
  }>(`development_sources?select=evidence_role,is_primary,source_items(title,canonical_url,published_at)&development_id=eq.${developmentId}&order=is_primary.desc`);
}
