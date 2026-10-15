"""Publishes due posts from queue/ to Instagram through the official Instagram API (Instagram Login).

Queue layout (one folder per post, on the main branch = approved):
  queue/2026-10-16-am/post.json   {"type": "carousel"|"image"|"reel"|"story",
                                   "caption": "...", "publish_at": "2026-10-16T12:00:00Z",
                                   "media": ["01.jpg", "02.jpg", ...]}   # or ["reel.mp4"]
  queue/2026-10-16-am/01.jpg ...
After publishing, the script writes queue/<id>/published.json (or error.json on failure).
Images are served to Instagram from raw.githubusercontent.com, so the repository must be public.
"""
import datetime as dt
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.instagram.com/" + (os.environ.get("IG_API_VERSION", "").strip("/") + "/" if os.environ.get("IG_API_VERSION") else "")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("PUBLISH_BRANCH", "main")
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"


def call(method, path, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = API + path
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode(), method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {body}") from None


def wait_ready(container_id, timeout_s=300):
    start = time.time()
    while time.time() - start < timeout_s:
        st = call("GET", container_id, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container_id} status {st}")
        time.sleep(5)
    raise RuntimeError(f"container {container_id} not ready after {timeout_s}s")


def media_param(name):
    return ("video_url" if name.lower().endswith((".mp4", ".mov")) else "image_url")


def publish(folder, post, ig_id):
    rel = os.path.relpath(folder).replace(os.sep, "/")
    urls = [RAW + rel + "/" + m for m in post["media"]]
    kind = post["type"]
    caption = post.get("caption", "")
    # Optional Collab invites (up to 3 usernames); they appear as co-authors once they accept in the app.
    collab = {"collaborators": json.dumps(post["collaborators"][:3])} if post.get("collaborators") else {}
    if kind == "carousel":
        children = []
        for u, m in zip(urls, post["media"]):
            c = call("POST", f"{ig_id}/media", {media_param(m): u, "is_carousel_item": "true",
                                                **({"media_type": "VIDEO"} if media_param(m) == "video_url" else {})})
            wait_ready(c["id"])
            children.append(c["id"])
        cont = call("POST", f"{ig_id}/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption, **collab})
    elif kind == "reel":
        params = {"media_type": "REELS", "video_url": urls[0], "caption": caption, "share_to_feed": "true", **collab}
        if post.get("cover"):
            params["cover_url"] = RAW + rel + "/" + post["cover"]
        cont = call("POST", f"{ig_id}/media", params)
    elif kind == "story":
        story_params = {"media_type": "STORIES", media_param(post["media"][0]): urls[0]}
        if media_param(post["media"][0]) == "video_url":
            story_params["media_type"] = "STORIES"
        cont = call("POST", f"{ig_id}/media", story_params)
    else:
        params = {"image_url": urls[0], "caption": caption, **collab}
        if post.get("alt_text"):
            try:
                cont = call("POST", f"{ig_id}/media", {**params, "alt_text": post["alt_text"][:1000]})
            except RuntimeError:
                cont = call("POST", f"{ig_id}/media", params)  # alt text is optional
        else:
            cont = call("POST", f"{ig_id}/media", params)
    wait_ready(cont["id"], timeout_s=900 if kind == "reel" else 300)
    res = call("POST", f"{ig_id}/media_publish", {"creation_id": cont["id"]})
    media_id = res["id"]
    link = call("GET", media_id, {"fields": "permalink"}).get("permalink")
    return media_id, link


def main():
    if not TOKEN:
        print("IG_ACCESS_TOKEN secret not set yet: nothing published.")
        return 0
    if not REPO:
        print("Missing GITHUB_REPOSITORY", file=sys.stderr)
        return 1
    now = dt.datetime.now(dt.timezone.utc)
    due = []
    for pj in sorted(glob.glob("queue/*/post.json")):
        folder = os.path.dirname(pj)
        if os.path.exists(os.path.join(folder, "published.json")) or os.path.exists(os.path.join(folder, "error.json")):
            continue
        post = json.load(open(pj, encoding="utf-8"))
        when = dt.datetime.fromisoformat(post["publish_at"].replace("Z", "+00:00"))
        if when <= now:
            due.append((folder, post))
    if not due:
        print("Nothing due.")
        return 0
    me = call("GET", "me", {"fields": "user_id,username"})
    ig_id = me.get("user_id") or me.get("id")
    failed = 0
    for folder, post in due:
        try:
            media_id, link = publish(folder, post, ig_id)
            json.dump({"media_id": media_id, "permalink": link, "published_at": now.isoformat()},
                      open(os.path.join(folder, "published.json"), "w"), indent=2)
            print(f"Published {folder}: {link}")
        except Exception as e:  # keep going with the other posts
            failed += 1
            json.dump({"error": str(e), "at": now.isoformat()}, open(os.path.join(folder, "error.json"), "w"), indent=2)
            print(f"FAILED {folder}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
