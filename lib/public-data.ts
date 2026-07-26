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

const importanceRank = { Major: 0, Notable: 1, Incremental: 2 } as const;
const evidenceRank = { Verified: 0, Reported: 1, Developing: 2 } as const;

export const publicCategoryGroups = [
  "Models",
  "Agents and developer tools",
  "Research and AI science",
  "Infrastructure and hardware",
  "Business and products",
  "Policy, safety and security",
] as const;

export type PublicCategoryGroup = (typeof publicCategoryGroups)[number];
export type DevelopmentFilters = {
  status?: "Verified" | "Reported";
  importance?: Development["importance_label"];
  category?: PublicCategoryGroup;
};

export function developmentPublicCategory(item: Development): PublicCategoryGroup {
  if (publicCategoryGroups.includes(item.public_category as PublicCategoryGroup)) {
    return item.public_category as PublicCategoryGroup;
  }
  if (item.category === "Models") return "Models";
  if (["Agents", "Developer tools"].includes(item.category)) return "Agents and developer tools";
  if (["Research", "Robotics"].includes(item.category)) return "Research and AI science";
  if (item.category === "Infrastructure") return "Infrastructure and hardware";
  if (["Regulation", "Security"].includes(item.category)) return "Policy, safety and security";
  return "Business and products";
}

function matchesCategory(item: Development, group: PublicCategoryGroup): boolean {
  return developmentPublicCategory(item) === group;
}

const routineReleaseTerms = /\b(bug fixes?|documentation updates?|dependency updates?|maintenance|code refactor(?:ing)?|code quality improvements?|housekeeping)\b/i;
const concreteChangeTerms = /\b(introduces?|adds?|enables?|supports?|launches?|removes?|changes?|makes available|open-sources?)\b/i;
const prereleaseTag = /(?:alpha|beta|rc|preview|dev|nightly)|^\d+(?:\.\d+)+(?:a|b|rc)\d+$/i;
const repositoryReleaseTitle = /^([^/\s]+)\/([^:]+):\s*(\S.+)$/;

export function isReaderValueCandidate(item: Development): boolean {
  if (item.importance_label !== "Incremental" || item.event_type !== "Release") return true;
  const match = item.headline.match(repositoryReleaseTitle);
  if (match && prereleaseTag.test(match[3])) return false;
  return !(routineReleaseTerms.test(item.summary) && !concreteChangeTerms.test(item.summary));
}

function developmentSubject(item: Development): string {
  if (item.product?.trim()) return `product:${item.product.trim().toLowerCase()}`;
  const repository = item.headline.match(repositoryReleaseTitle);
  if (repository) return `repository:${repository[1].toLowerCase()}/${repository[2].toLowerCase()}`;
  if (item.organisation?.trim()) return `organisation:${item.organisation.trim().toLowerCase()}`;
  return `development:${item.id}`;
}

export function selectReaderValueDevelopments(items: Development[], limit = 5): Development[] {
  const selected: Development[] = [];
  const seenSubjects = new Set<string>();
  for (const item of items) {
    if (!isReaderValueCandidate(item)) continue;
    const subject = developmentSubject(item);
    if (seenSubjects.has(subject)) continue;
    seenSubjects.add(subject);
    selected.push(item);
    if (selected.length === limit) break;
  }
  return selected;
}

export function readerFacingHeadline(item: Development): string {
  const release = item.headline.match(repositoryReleaseTitle);
  if (!release) return item.headline;
  const concrete = item.summary.match(/\b(introduces?|adds?|enables?|supports?|launches?|removes?|changes?|makes available|open-sources?)\s+(.+?)(?:\.\s|\.$|$)/i);
  if (!concrete) return item.headline;
  const product = item.product?.trim() || release[2];
  const headline = `${product} ${release[3]} ${concrete[1].toLowerCase()} ${concrete[2]}`;
  return headline.length <= 140 ? headline : `${headline.slice(0, 137).trimEnd()}…`;
}

export async function getDevelopments(
  limit = 20,
  filters: DevelopmentFilters = {},
): Promise<Development[]> {
  const boundedLimit = Math.max(1, Math.min(limit, 200));
  let rows = await publicQuery<Development>(
    "developments?select=*&publication_status=eq.Published&verification_status=in.(Verified,Reported)&limit=200",
  );
  rows = rows.filter((row) =>
    (!filters.status || row.verification_status === filters.status)
    && (!filters.importance || row.importance_label === filters.importance)
    && (!filters.category || matchesCategory(row, filters.category))
  );
  rows.sort((left, right) => {
    const leftRank = importanceRank[left.importance_label] * 2 + evidenceRank[left.verification_status];
    const rightRank = importanceRank[right.importance_label] * 2 + evidenceRank[right.verification_status];
    const difference = leftRank - rightRank;
    if (difference) return difference;
    return new Date(right.published_at ?? 0).getTime() - new Date(left.published_at ?? 0).getTime();
  });
  const selected = rows.slice(0, boundedLimit);
  if (!selected.length) return selected;
  const ids = selected.map((row) => row.id).join(",");
  const evidence = await publicQuery<{
    development_id: string;
    evidence_role: string;
    source_items: { title: string; canonical_url: string };
  }>(`development_sources?select=development_id,evidence_role,source_items(title,canonical_url)&is_primary=eq.true&development_id=in.(${ids})`);
  const primaryByDevelopment = new Map(evidence.map((row) => [row.development_id, row]));
  return selected.map((row) => {
    const primary = primaryByDevelopment.get(row.id);
    return {
      ...row,
      primary_source_title: primary?.source_items.title ?? null,
      primary_source_url: primary?.source_items.canonical_url ?? null,
      primary_evidence_role: primary?.evidence_role ?? null,
    };
  });
}

export async function getDevelopment(slug: string): Promise<Development | null> {
  const rows = await publicQuery<Development>(
    `developments?select=*&slug=eq.${encodeURIComponent(slug)}&publication_status=eq.Published&verification_status=in.(Verified,Reported)&limit=1`,
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
  return publicQuery<Development>(`developments?select=*&publication_status=eq.Published&verification_status=in.(Verified,Reported)&category=eq.${encodeURIComponent(item.category)}&id=neq.${item.id}&order=published_at.desc&limit=3`);
}

export async function getDevelopmentSources(developmentId: string) {
  return publicQuery<{
    evidence_role: string;
    is_primary: boolean;
    source_items: { title: string; canonical_url: string; published_at: string | null };
  }>(`development_sources?select=evidence_role,is_primary,source_items(title,canonical_url,published_at)&development_id=eq.${developmentId}&order=is_primary.desc`);
}
