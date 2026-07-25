import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export async function createServerSupabaseClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  const cookieStore = await cookies();
  return createServerClient(url, key, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (entries) => {
        try {
          entries.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Server component render: token refresh is handled on the next browser auth operation.
        }
      },
    },
  });
}

export async function requireOwner() {
  const client = await createServerSupabaseClient();
  if (!client) redirect("/owner-login?reason=not-configured");
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) redirect("/owner-login");
  const { data: settings, error: settingsError } = await client
    .from("private_settings")
    .select("id")
    .limit(1);
  if (settingsError || !settings?.length) redirect("/owner-login?reason=not-owner");
  return userData.user;
}
