import { supabase } from "./supabase";

let _cachedSession: { userId: string; email: string } | null = null;
const _recent = new Map<string, number>();
const DEDUP_MS = 2000;

async function getSession(): Promise<{ userId: string; email: string } | null> {
  if (_cachedSession) return _cachedSession;
  const { data } = await supabase.auth.getSession();
  const user = data?.session?.user;
  if (!user) return null;
  _cachedSession = { userId: user.id, email: user.email || "" };
  return _cachedSession;
}

export function track(
  eventType: string,
  resource: string,
  metadata?: Record<string, unknown>,
): void {
  const key = `${eventType}:${resource}`;
  const now = Date.now();
  const last = _recent.get(key);
  if (last && now - last < DEDUP_MS) return;
  _recent.set(key, now);

  getSession().then(s => {
    if (!s) return;
    supabase.from("usage_events").insert({
      user_id: s.userId,
      email: s.email,
      event_type: eventType,
      resource,
      metadata: metadata ?? {},
      user_agent: navigator.userAgent,
    }).then(() => {});
  }).catch(() => {});
}
