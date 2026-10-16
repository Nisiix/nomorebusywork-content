"""Copies publishing results from the Supabase publisher (ig-publisher, the real scheduler) into the repo:
queue/<id>/published.json or queue/<id>/error.json. Safe to run at any time; GitHub's schedule delay doesn't matter."""
import json
import os
import sys
import urllib.request

STATUS_URL = "https://mnecumcjsosmcqvmokrf.supabase.co/functions/v1/ig-publisher?action=status"


def fetch_status():
    with urllib.request.urlopen(STATUS_URL, timeout=30) as r:
        return json.loads(r.read().decode())["posts"]


def main():
    changed = 0
    for p in fetch_status():
        folder = os.path.join("queue", p["id"])
        if not os.path.isdir(folder):
            continue
        pub, err = os.path.join(folder, "published.json"), os.path.join(folder, "error.json")
        if p["status"] == "published" and p.get("media_id") and not os.path.exists(pub):
            json.dump({"media_id": p["media_id"], "permalink": p.get("permalink"),
                       "published_at": p.get("published_at"), "by": "ig-publisher"}, open(pub, "w"), indent=2)
            if os.path.exists(err):
                os.remove(err)
            changed += 1
        elif p["status"] == "error" and not os.path.exists(pub) and not os.path.exists(err):
            json.dump({"error": p.get("error"), "at": p.get("updated_at"), "by": "ig-publisher"}, open(err, "w"), indent=2)
            changed += 1
    print(f"synced {changed} result(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
