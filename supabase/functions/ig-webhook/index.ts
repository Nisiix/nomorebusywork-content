// Instagram webhook for @nomorebusywork (Instagram API with Instagram Login).
//
// Flow
//  1. Someone comments a keyword (e.g. PACK) on a post -> one private reply asking them to reply with the keyword.
//  2. They answer in DM (or DM a keyword directly) -> we read is_user_follow_business.
//     Follower -> the offer is delivered (text + images). Not yet a follower -> we ask them to follow and reply again.
//
// Offers live in the GitHub repo (offers/offers.json), so new offers need no redeploy.
//
// Secrets (Supabase -> Edge Functions -> Secrets):
//   IG_ACCESS_TOKEN  first Instagram user token (later kept fresh in table ig_token)
//   IG_APP_SECRET    Instagram app secret, used to check webhook signatures
//   VERIFY_TOKEN     optional; defaults to the public string below (used only for Meta's setup handshake —
//                    every event is authenticated by its signature, not by this string)
import { createClient } from "npm:@supabase/supabase-js@2";

const GRAPH = "https://graph.instagram.com/v25.0";
const OFFERS_URL = "https://raw.githubusercontent.com/Nisiix/nomorebusywork-content/main/offers/offers.json";
const RAW_BASE = "https://raw.githubusercontent.com/Nisiix/nomorebusywork-content/main/";
const DEFAULT_VERIFY_TOKEN = "nomorebusywork-webhook";
const YES_WORDS = ["YES", "Y", "YEP", "YEAH", "SEND", "SEND IT", "OK", "OKAY", "SI", "SÌ", "PLEASE"];

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});

type OfferMessage = { text?: string; image?: string };
type Offer = {
  id: string;
  keywords: string[];
  follower_only: boolean;
  invite: string;        // private reply to the comment
  not_following: string; // sent when the person does not follow yet
  messages: OfferMessage[];
};

let offersCache: { at: number; offers: Offer[] } | null = null;
let myIdCache: string | null = null;

async function log(kind: string, row: Record<string, unknown>) {
  const { error } = await db.from("ig_events").insert({ kind, ...row });
  if (error) console.error("log failed", error.message);
}

// ---------------------------------------------------------------- token
async function getToken(): Promise<string> {
  const { data } = await db.from("ig_token").select("access_token, refreshed_at").eq("id", 1).maybeSingle();
  if (data?.access_token) return data.access_token;
  const env = Deno.env.get("IG_ACCESS_TOKEN") ?? "";
  if (env) await db.from("ig_token").upsert({ id: 1, access_token: env, refreshed_at: new Date().toISOString() });
  return env;
}

// Long-lived tokens last 60 days; refresh ours when it is more than 7 days old.
async function refreshTokenIfOld(force = false) {
  const { data } = await db.from("ig_token").select("access_token, refreshed_at").eq("id", 1).maybeSingle();
  const token = data?.access_token ?? (await getToken());
  if (!token) return { refreshed: false, reason: "no token" };
  const age = data ? Date.now() - new Date(data.refreshed_at).getTime() : Infinity;
  if (!force && age < 7 * 86400_000) return { refreshed: false, reason: "recent" };
  const r = await fetch(`https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=${encodeURIComponent(token)}`);
  const j = await r.json();
  if (!r.ok || !j.access_token) {
    await log("error", { detail: { where: "refresh", status: r.status, error: j.error?.message } });
    return { refreshed: false, reason: j.error?.message ?? `HTTP ${r.status}` };
  }
  const expires = new Date(Date.now() + (j.expires_in ?? 0) * 1000).toISOString();
  await db.from("ig_token").upsert({ id: 1, access_token: j.access_token, refreshed_at: new Date().toISOString(), expires_at: expires });
  return { refreshed: true, expires_at: expires };
}

// ---------------------------------------------------------------- graph helpers
async function graph(method: string, path: string, body?: unknown) {
  const token = await getToken();
  const r = await fetch(`${GRAPH}/${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`${method} ${path.split("?")[0]} -> ${r.status} ${j?.error?.message ?? ""}`);
  return j;
}

async function myId(): Promise<string> {
  if (myIdCache) return myIdCache;
  const me = await graph("GET", "me?fields=user_id,username");
  myIdCache = String(me.user_id ?? me.id);
  return myIdCache;
}

async function sendText(recipient: Record<string, string>, text: string) {
  return graph("POST", `${await myId()}/messages`, { recipient, message: { text } });
}

async function sendImage(igsid: string, path: string) {
  const url = path.startsWith("http") ? path : RAW_BASE + path;
  return graph("POST", `${await myId()}/messages`, {
    recipient: { id: igsid },
    message: { attachment: { type: "image", payload: { url } } },
  });
}

// ---------------------------------------------------------------- offers
async function offers(): Promise<Offer[]> {
  if (offersCache && Date.now() - offersCache.at < 5 * 60_000) return offersCache.offers;
  const r = await fetch(OFFERS_URL, { headers: { "Cache-Control": "no-cache" } });
  const list = r.ok ? ((await r.json()).offers as Offer[]) : offersCache?.offers ?? [];
  offersCache = { at: Date.now(), offers: list };
  return list;
}

function normalize(s: string) {
  return s.normalize("NFKD").replace(/[^\p{L}\p{N} ]/gu, " ").replace(/\s+/g, " ").trim().toUpperCase();
}

function matchOffer(text: string, list: Offer[]): Offer | undefined {
  const words = ` ${normalize(text)} `;
  return list.find((o) => o.keywords.some((k) => words.includes(` ${normalize(k)} `)));
}

function isYes(text: string) {
  const t = normalize(text);
  return YES_WORDS.some((w) => t === w || t.startsWith(w + " "));
}

// ---------------------------------------------------------------- handlers
async function onComment(v: any) {
  const commenter = v?.from?.id ? String(v.from.id) : undefined;
  const text: string = v?.text ?? "";
  if (!commenter || !v?.id || commenter === (await myId())) return;
  const offer = matchOffer(text, await offers());
  await log("comment", { ig_user_id: commenter, username: v.from?.username, comment_id: v.id, media_id: v.media?.id, keyword: offer?.id, detail: { text } });
  if (!offer) return;

  // Only one private reply per comment.
  const { count } = await db.from("ig_events").select("id", { count: "exact", head: true })
    .eq("kind", "private_reply").eq("comment_id", v.id);
  if (count) return;

  await sendText({ comment_id: v.id }, offer.invite);
  await db.from("ig_contacts").upsert({
    ig_user_id: commenter, username: v.from?.username, pending_keyword: offer.id,
    pending_since: new Date().toISOString(), updated_at: new Date().toISOString(),
  });
  await log("private_reply", { ig_user_id: commenter, comment_id: v.id, keyword: offer.id });
}

async function onMessage(m: any) {
  if (m?.message?.is_echo || m?.message?.is_deleted || !m?.sender?.id) return;
  const igsid = String(m.sender.id);
  if (igsid === (await myId())) return;
  const text: string = m.message?.text ?? m.message?.quick_reply?.payload ?? "";
  if (!text) return;

  const list = await offers();
  const { data: contact } = await db.from("ig_contacts").select("*").eq("ig_user_id", igsid).maybeSingle();
  let offer = matchOffer(text, list);
  if (!offer && isYes(text) && contact?.pending_keyword) offer = list.find((o) => o.id === contact.pending_keyword);
  await log("message", { ig_user_id: igsid, keyword: offer?.id, detail: { text: text.slice(0, 300) } });
  if (!offer) return;

  // Ignore repeats within 10 minutes of a delivery.
  const last = contact?.delivered?.[offer.id];
  if (last && Date.now() - new Date(last).getTime() < 10 * 60_000) return;

  let follows = true;
  let username = contact?.username;
  if (offer.follower_only) {
    const p = await graph("GET", `${igsid}?fields=username,is_user_follow_business`);
    follows = p.is_user_follow_business === true;
    username = p.username ?? username;
    await log("follow_check", { ig_user_id: igsid, username, keyword: offer.id, detail: { follows } });
  }

  if (!follows) {
    await sendText({ id: igsid }, offer.not_following);
    await db.from("ig_contacts").upsert({
      ig_user_id: igsid, username, pending_keyword: offer.id,
      pending_since: new Date().toISOString(), updated_at: new Date().toISOString(),
      delivered: contact?.delivered ?? {},
    });
    return;
  }

  for (const msg of offer.messages) {
    if (msg.text) await sendText({ id: igsid }, msg.text);
    if (msg.image) await sendImage(igsid, msg.image);
  }
  await db.from("ig_contacts").upsert({
    ig_user_id: igsid, username, pending_keyword: null, pending_since: null,
    delivered: { ...(contact?.delivered ?? {}), [offer.id]: new Date().toISOString() },
    updated_at: new Date().toISOString(),
  });
  await log("delivery", { ig_user_id: igsid, username, keyword: offer.id });
}

// ---------------------------------------------------------------- signature
async function validSignature(raw: string, header: string | null) {
  const secret = Deno.env.get("IG_APP_SECRET");
  if (!secret || !header?.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw)));
  const hex = Array.from(sig, (b) => b.toString(16).padStart(2, "0")).join("");
  const given = header.slice(7);
  if (given.length !== hex.length) return false;
  let diff = 0;
  for (let i = 0; i < hex.length; i++) diff |= hex.charCodeAt(i) ^ given.charCodeAt(i);
  return diff === 0;
}

// ---------------------------------------------------------------- server
Deno.serve(async (req) => {
  const url = new URL(req.url);

  if (req.method === "GET") {
    // Meta verification handshake.
    if (url.searchParams.get("hub.mode") === "subscribe") {
      const ok = url.searchParams.get("hub.verify_token") === (Deno.env.get("VERIFY_TOKEN") || DEFAULT_VERIFY_TOKEN);
      return ok ? new Response(url.searchParams.get("hub.challenge") ?? "", { status: 200 }) : new Response("forbidden", { status: 403 });
    }
    // Health check and token refresh (safe to call: it never returns the token).
    const action = url.searchParams.get("action");
    if (action === "refresh") return Response.json(await refreshTokenIfOld());
    if (action === "status") {
      try {
        const me = await graph("GET", "me?fields=user_id,username");
        const { data } = await db.from("ig_token").select("refreshed_at, expires_at").eq("id", 1).maybeSingle();
        return Response.json({ ok: true, username: me.username, token: data ?? null });
      } catch (e) {
        return Response.json({ ok: false, error: String(e) }, { status: 500 });
      }
    }
    return new Response("ok");
  }

  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  const raw = await req.text();
  if (!(await validSignature(raw, req.headers.get("x-hub-signature-256")))) {
    await log("error", { detail: { where: "signature", note: "invalid or missing signature" } });
    return new Response("invalid signature", { status: 401 });
  }

  let body: any;
  try { body = JSON.parse(raw); } catch { return new Response("bad json", { status: 400 }); }

  const work = (async () => {
    for (const entry of body.entry ?? []) {
      for (const change of entry.changes ?? []) {
        if (change.field === "comments") {
          try { await onComment(change.value); } catch (e) { await log("error", { detail: { where: "comment", error: String(e) } }); }
        }
      }
      for (const m of entry.messaging ?? []) {
        try { await onMessage(m); } catch (e) { await log("error", { ig_user_id: m?.sender?.id, detail: { where: "message", error: String(e) } }); }
      }
    }
    await refreshTokenIfOld().catch(() => {});
  })();

  // Answer Meta quickly; keep working in the background.
  // @ts-ignore EdgeRuntime is provided by Supabase
  if (typeof EdgeRuntime !== "undefined") EdgeRuntime.waitUntil(work); else await work;
  return new Response("EVENT_RECEIVED", { status: 200 });
});
