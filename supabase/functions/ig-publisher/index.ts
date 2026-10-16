// Scheduled publisher for @nomorebusywork (Instagram API with Instagram Login).
//
// Why: GitHub's scheduled workflows run hours late, so publishing moved here.
// pg_cron calls this function every 5 minutes (POST ?action=tick, header x-cron-key).
// Content still lives in the GitHub repo: plan/calendar.json lists the ids, queue/<id>/post.json
// + media on main are the approved posts (a missing post.json = not approved = skipped).
//
// State per post lives in table ig_publish (id primary key = the claim, so a post can never be
// published twice):
//   creating -> waiting (container created, Instagram is processing) -> publishing -> published
//   any failure -> error (never retried automatically once media_publish may have run)
// GET ?action=status is public and read-only; GitHub copies it into queue/<id>/published.json.
import { createClient } from "npm:@supabase/supabase-js@2";

const GRAPH = "https://graph.instagram.com/v25.0";
const RAW = "https://raw.githubusercontent.com/Nisiix/nomorebusywork-content/main/";
const MAX_LATE_H = 36;          // never publish something more than 36 h late
const WAIT_LIMIT_MIN = 40;      // container still not ready after this -> error
const CREATING_STALE_MIN = 10;  // a crashed "creating" claim is released after this
const MAX_ATTEMPTS = 3;

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});

type Post = {
  type: "carousel" | "reel" | "story" | "image";
  caption?: string;
  publish_at: string;
  media: string[];
  cover?: string;
  alt_text?: string;
  collaborators?: string[];
};
type Row = {
  id: string; status: string; kind?: string; container_id?: string | null; media_id?: string | null;
  permalink?: string | null; error?: string | null; attempts?: number; publish_at?: string;
  claimed_at?: string; updated_at?: string; published_at?: string | null;
};

let token = "";
let igId = "";

const clean = (s: string) => s.replace(/access_token=[^&\s"]+/g, "access_token=***");

async function call(method: "GET" | "POST", path: string, params: Record<string, string> = {}) {
  const body = new URLSearchParams({ ...params, access_token: token });
  const res = method === "GET"
    ? await fetch(`${GRAPH}/${path}?${body}`)
    : await fetch(`${GRAPH}/${path}`, { method: "POST", body });
  const text = await res.text();
  if (!res.ok) throw new Error(clean(`${method} ${path} -> HTTP ${res.status}: ${text.slice(0, 500)}`));
  return JSON.parse(text);
}

async function raw(path: string) {
  const r = await fetch(RAW + path, { headers: { "cache-control": "no-cache" } });
  if (r.status === 404) { await r.body?.cancel(); return null; }
  if (!r.ok) throw new Error(`GitHub raw ${path} -> ${r.status}`);
  return await r.json();
}

async function save(id: string, patch: Partial<Row>) {
  const { error } = await db.from("ig_publish").update({ updated_at: new Date().toISOString(), ...patch }).eq("id", id);
  if (error) throw new Error("db update failed: " + error.message);
}

async function containerStatus(id: string) {
  return (await call("GET", id, { fields: "status_code" })).status_code as string;
}

async function waitChild(id: string, seconds = 25) {
  for (let i = 0; i < seconds / 2.5; i++) {
    const st = await containerStatus(id);
    if (st === "FINISHED") return;
    if (st === "ERROR" || st === "EXPIRED") throw new Error(`child container ${id} ${st}`);
    await new Promise((r) => setTimeout(r, 2500));
  }
  throw new Error(`child container ${id} not ready`);
}

// Create the Instagram container(s) for one post and return the container to publish.
async function createContainer(id: string, post: Post): Promise<string> {
  const base = RAW + "queue/" + id + "/";
  const urls = post.media.map((m) => base + m);
  const isVideo = (m: string) => /\.(mp4|mov)$/i.test(m);
  const collab: Record<string, string> = post.collaborators?.length
    ? { collaborators: JSON.stringify(post.collaborators.slice(0, 3)) } : {};
  const caption = post.caption ?? "";
  if (post.type === "carousel") {
    const children: string[] = [];
    for (let i = 0; i < urls.length; i++) {
      const p: Record<string, string> = isVideo(post.media[i])
        ? { media_type: "VIDEO", video_url: urls[i], is_carousel_item: "true" }
        : { image_url: urls[i], is_carousel_item: "true" };
      const c = await call("POST", `${igId}/media`, p);
      await waitChild(c.id, isVideo(post.media[i]) ? 60 : 25);
      children.push(c.id);
    }
    return (await call("POST", `${igId}/media`, { media_type: "CAROUSEL", children: children.join(","), caption, ...collab })).id;
  }
  if (post.type === "reel") {
    const p: Record<string, string> = { media_type: "REELS", video_url: urls[0], caption, share_to_feed: "true", ...collab };
    if (post.cover) p.cover_url = base + post.cover;
    return (await call("POST", `${igId}/media`, p)).id;
  }
  if (post.type === "story") {
    const p: Record<string, string> = { media_type: "STORIES" };
    p[isVideo(post.media[0]) ? "video_url" : "image_url"] = urls[0];
    return (await call("POST", `${igId}/media`, p)).id;
  }
  const p: Record<string, string> = { image_url: urls[0], caption, ...collab };
  if (post.alt_text) {
    try { return (await call("POST", `${igId}/media`, { ...p, alt_text: post.alt_text.slice(0, 1000) })).id; }
    catch { /* alt text is optional */ }
  }
  return (await call("POST", `${igId}/media`, p)).id;
}

// Move one claimed row forward; returns a short log line.
async function advance(row: Row): Promise<string> {
  const now = Date.now();
  if (row.status === "creating") {
    const age = (now - Date.parse(row.updated_at ?? row.claimed_at ?? "")) / 60000;
    if (age < CREATING_STALE_MIN) return `${row.id}: creating (busy)`;
    if ((row.attempts ?? 1) >= MAX_ATTEMPTS) {
      await save(row.id, { status: "error", error: "container creation kept failing" });
      return `${row.id}: error`;
    }
    await save(row.id, { status: "creating", attempts: (row.attempts ?? 1) + 1 });
    return await create(row.id);
  }
  if (row.status === "waiting") {
    const st = await containerStatus(row.container_id!);
    if (st === "ERROR" || st === "EXPIRED") {
      await save(row.id, { status: "error", error: `container ${st}` });
      return `${row.id}: container ${st}`;
    }
    if (st !== "FINISHED") {
      const age = (now - Date.parse(row.claimed_at ?? "")) / 60000;
      if (age > WAIT_LIMIT_MIN) {
        await save(row.id, { status: "error", error: `container not ready after ${WAIT_LIMIT_MIN} min (${st})` });
        return `${row.id}: timeout`;
      }
      return `${row.id}: processing (${st})`;
    }
    await save(row.id, { status: "publishing" });
    try {
      const res = await call("POST", `${igId}/media_publish`, { creation_id: row.container_id! });
      let link: string | null = null;
      try { link = (await call("GET", res.id, { fields: "permalink" })).permalink ?? null; } catch { /* optional */ }
      await save(row.id, { status: "published", media_id: res.id, permalink: link, published_at: new Date().toISOString(), error: null });
      return `${row.id}: published ${link}`;
    } catch (e) {
      // media_publish may or may not have gone through: never retry automatically.
      await save(row.id, { status: "error", error: "media_publish: " + String((e as Error).message) });
      return `${row.id}: publish error`;
    }
  }
  return `${row.id}: ${row.status}`;
}

async function create(id: string): Promise<string> {
  try {
    const post = await raw(`queue/${id}/post.json`) as Post | null;
    if (!post) { await save(id, { status: "error", error: "queue post.json disappeared" }); return `${id}: missing`; }
    const cid = await createContainer(id, post);
    await save(id, { status: "waiting", container_id: cid, error: null });
    const st = await containerStatus(cid);   // images are usually ready at once
    if (st === "FINISHED") {
      const { data } = await db.from("ig_publish").select("*").eq("id", id).single();
      return await advance(data as Row);
    }
    return `${id}: container created (${st})`;
  } catch (e) {
    const msg = String((e as Error).message);
    const { data } = await db.from("ig_publish").select("attempts").eq("id", id).single();
    if ((data?.attempts ?? 1) >= MAX_ATTEMPTS) await save(id, { status: "error", error: msg });
    else await save(id, { status: "creating", error: msg, updated_at: new Date(0).toISOString() } as Partial<Row>);
    return `${id}: create failed (${msg.slice(0, 120)})`;
  }
}

async function tick() {
  const { data: t } = await db.from("ig_token").select("access_token").eq("id", 1).maybeSingle();
  token = t?.access_token ?? "";
  if (!token) return ["no token"];
  const out: string[] = [];

  // 1. Rows already in flight.
  const { data: open } = await db.from("ig_publish").select("*").in("status", ["creating", "waiting"]);

  // 2. New due posts from the calendar.
  const cal = await raw("plan/calendar.json") as { days: Record<string, { id: string; publish_at: string }>[] };
  const now = Date.now();
  const due: { id: string; publish_at: string }[] = [];
  for (const d of cal.days) for (const slot of ["story", "am", "pm"]) {
    const s = d[slot];
    if (!s?.id) continue;
    const at = Date.parse(s.publish_at);
    if (at <= now && now - at < MAX_LATE_H * 3600e3) due.push(s);
  }
  const known = new Set<string>();
  if (due.length) {
    const { data } = await db.from("ig_publish").select("id").in("id", due.map((d) => d.id));
    for (const r of data ?? []) known.add(r.id);
  }
  const fresh = due.filter((d) => !known.has(d.id));
  if (!open?.length && !fresh.length) return ["nothing due"];

  const me = await call("GET", "me", { fields: "user_id" });
  igId = me.user_id ?? me.id;

  for (const r of open ?? []) {
    try { out.push(await advance(r as Row)); } catch (e) { out.push(`${r.id}: ${String((e as Error).message).slice(0, 160)}`); }
  }
  for (const d of fresh) {
    const post = await raw(`queue/${d.id}/post.json`) as Post | null;
    if (!post) { out.push(`${d.id}: not approved (no queue/post.json on main)`); continue; }
    if (Date.parse(post.publish_at) > now) continue;
    if (await raw(`queue/${d.id}/published.json`)) {   // already published by the old GitHub publisher
      await db.from("ig_publish").insert({ id: d.id, status: "published", kind: post.type, publish_at: post.publish_at, error: "recorded from GitHub" });
      out.push(`${d.id}: already published via GitHub`);
      continue;
    }
    // The claim: primary key insert. If another run got here first, this fails and we skip.
    const { error } = await db.from("ig_publish").insert({
      id: d.id, status: "creating", kind: post.type, publish_at: post.publish_at, attempts: 1,
      claimed_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    });
    if (error) { out.push(`${d.id}: already claimed`); continue; }
    out.push(await create(d.id));
  }
  return out;
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const action = url.searchParams.get("action");
  if (action === "status") {
    const since = new Date(Date.now() - 14 * 86400e3).toISOString();
    const { data, error } = await db.from("ig_publish")
      .select("id, status, kind, publish_at, media_id, permalink, published_at, error, updated_at")
      .gte("publish_at", since).order("publish_at");
    if (error) return Response.json({ error: error.message }, { status: 500 });
    return Response.json({ posts: data });
  }
  if (action === "tick" && req.method === "POST") {
    const { data: k } = await db.from("ig_settings").select("value").eq("key", "cron_key").maybeSingle();
    if (!k?.value || req.headers.get("x-cron-key") !== k.value) return new Response("forbidden", { status: 403 });
    try {
      const out = await tick();
      console.log(out.join("\n"));
      return Response.json({ ok: true, log: out });
    } catch (e) {
      console.error(e);
      return Response.json({ ok: false, error: clean(String((e as Error).message)) }, { status: 500 });
    }
  }
  return new Response("ig-publisher", { status: 200 });
});
