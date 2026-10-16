# nomorebusywork-content

Publishing queue for the Instagram account @nomorebusywork.

- `queue/<date>-<slot>/` holds one post: `post.json` plus its images (JPEG) or video (MP4).
- A post on the `main` branch is approved. New posts arrive first on a `pending/<date>` branch and reach `main` only after approval.
- Publishing runs in Supabase: the Edge Function `ig-publisher` is called by pg_cron every 5 minutes and publishes every approved post (`queue/<id>/post.json` on main) whose `publish_at` has passed, through the official Instagram API. State is in table `ig_publish`, so nothing is published twice. (GitHub's own schedule runs hours late, so it is no longer used for publishing.)
- `.github/workflows/publish.yml` only copies the results into `queue/<id>/published.json` (with the link) or `error.json`. Run it manually with mode=publish only as an emergency fallback.
- `.github/workflows/refresh-token.yml` refreshes the Instagram token twice a month.

Secrets (Settings → Secrets and variables → Actions):
- `IG_ACCESS_TOKEN` — required.
- `GH_PAT` — optional, lets the refresh job save the new token.

`post.json` example:

```json
{
  "type": "carousel",
  "caption": "Text of the caption",
  "publish_at": "2026-10-16T12:00:00Z",
  "media": ["01.jpg", "02.jpg", "03.jpg"]
}
```

`tools/render_reference.py` is the reference renderer (Python + Playwright, HTML → PNG) with the brand style
used for the first carousels. New posts reuse its `slide_frame()` layout and colours.

Daily flow: the agent pushes the two posts of the day to a `pending/<date>` branch, the owner replies "ok",
the agent merges the branch into `main`, and the workflow publishes each post at its `publish_at` time.
