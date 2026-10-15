"""Renders No More Busywork posts from a JSON spec.

Usage:
    python3 tools/nmb_render.py specs/2026-10-16-am.json [more.json ...]
    python3 tools/nmb_render.py --all specs/          # every spec in a folder

A spec describes one post (carousel, image, reel or story). Output goes to queue/<id>/ with
01.jpg, 02.jpg ... (or reel.mp4 / story.jpg) plus post.json. The renderer fails if any text
overflows its slide, so every slide that renders is safe to publish.

Inline markup in any text field:
    **words**   -> lime highlight
    [BRACKETS]  -> lime placeholder (in prompt texts)
    \n          -> line break
"""
import html
import json
import os
import re
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BG, CARD, LINE, TEXT, LIME, BLUE, GREY, SOFT = "#0F1115", "#181B21", "#262A33", "#F5F5F7", "#C6F432", "#5B8CFF", "#8B8F98", "#C9CBD1"

CHECK_ICON = f"""<svg viewBox="0 0 100 100" width="100%" height="100%">
  <rect x="8" y="8" width="84" height="84" rx="22" fill="none" stroke="{LIME}" stroke-width="7"/>
  <path d="M28 52 L44 67 L73 34" fill="none" stroke="{LIME}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ background:{BG}; color:{TEXT}; font-family:'Inter', sans-serif; -webkit-font-smoothing:antialiased; }}
.wrap {{ position:relative; width:var(--w); height:var(--h); padding:72px 80px; display:flex; flex-direction:column; overflow:hidden; }}
.story .wrap {{ padding:150px 84px 170px; }}
.top {{ display:flex; justify-content:space-between; align-items:center; font-size:22px; letter-spacing:3px; font-weight:700; flex:none; }}
.brand {{ display:flex; align-items:center; gap:14px; color:{LIME}; }}
.brand .ic {{ width:34px; height:34px; }}
.count {{ color:{GREY}; font-weight:600; letter-spacing:1px; }}
.series {{ color:{GREY}; font-weight:700; letter-spacing:3px; font-size:20px; }}
.body {{ flex:1; display:flex; flex-direction:column; justify-content:center; min-height:0; }}
.foot {{ display:flex; justify-content:space-between; font-size:21px; color:{GREY}; font-weight:500; flex:none; }}
.lime {{ color:{LIME}; }} .blue {{ color:{BLUE}; }} .grey {{ color:{GREY}; }}
.mono {{ font-family:'DejaVu Sans Mono', monospace; }}
.kicker {{ font-size:28px; font-weight:700; color:{GREY}; letter-spacing:3px; text-transform:uppercase; margin-bottom:26px; }}
.h-xl {{ font-size:96px; font-weight:800; line-height:1.02; letter-spacing:-2px; }}
.h-l {{ font-size:72px; font-weight:800; line-height:1.06; letter-spacing:-1.5px; }}
.h-m {{ font-size:54px; font-weight:800; line-height:1.1; letter-spacing:-1px; }}
.big {{ font-size:170px; font-weight:800; line-height:0.92; letter-spacing:-5px; color:{LIME}; }}
.sub {{ font-size:36px; font-weight:500; color:{SOFT}; line-height:1.42; margin-top:36px; }}
.p {{ font-size:34px; font-weight:450; color:#D7D9DE; line-height:1.45; margin-top:22px; }}
.card {{ background:{CARD}; border:2px solid {LINE}; border-radius:28px; padding:30px 36px; margin:12px 0; }}
.head {{ display:flex; align-items:center; gap:16px; margin-bottom:12px; }}
.num {{ font-family:'DejaVu Sans Mono',monospace; font-size:25px; font-weight:700; color:{BG}; background:{LIME}; border-radius:10px; padding:4px 12px; flex:none; }}
.title {{ font-size:35px; font-weight:700; line-height:1.2; }}
.ptext {{ font-size:30px; line-height:1.42; color:#D7D9DE; font-weight:450; }}
.ph {{ color:{LIME}; font-weight:600; }}
.bubble {{ border-radius:30px; padding:26px 32px; margin:12px 0; font-size:30px; line-height:1.42; max-width:88%; }}
.you {{ background:{BLUE}; color:#fff; align-self:flex-end; border-bottom-right-radius:8px; }}
.ai {{ background:{CARD}; border:2px solid {LINE}; color:#D7D9DE; align-self:flex-start; border-bottom-left-radius:8px; }}
.who {{ font-size:20px; font-weight:700; letter-spacing:2px; color:{GREY}; margin:10px 6px 0; }}
.who.r {{ align-self:flex-end; }}
.ba {{ display:flex; flex-direction:column; gap:18px; }}
.ba .lbl {{ font-family:'DejaVu Sans Mono',monospace; font-size:24px; font-weight:700; letter-spacing:2px; margin-bottom:12px; }}
.ba .before {{ border-color:#3A2A2A; }} .ba .before .lbl {{ color:#FF7A6B; }}
.ba .after {{ border-color:#3B4A1A; }} .ba .after .lbl {{ color:{LIME}; }}
.ck {{ display:flex; gap:22px; align-items:flex-start; font-size:38px; font-weight:600; line-height:1.3; padding:20px 0; border-top:2px solid {LINE}; }}
.ck:last-child {{ border-bottom:2px solid {LINE}; }}
.ck .box {{ width:44px; height:44px; border:4px solid {LIME}; border-radius:12px; flex:none; margin-top:2px; display:flex; align-items:center; justify-content:center; color:{LIME}; font-size:30px; }}
.ck small {{ display:block; font-size:28px; font-weight:450; color:{SOFT}; margin-top:6px; }}
.step {{ display:flex; gap:26px; padding:20px 0; border-top:2px solid {LINE}; }}
.step:last-child {{ border-bottom:2px solid {LINE}; }}
.step .n {{ font-family:'DejaVu Sans Mono',monospace; font-size:30px; font-weight:700; color:{LIME}; min-width:56px; padding-top:4px; }}
.step .t {{ font-size:38px; font-weight:700; line-height:1.2; }}
.step .d {{ font-size:29px; color:{SOFT}; line-height:1.4; margin-top:6px; font-weight:450; }}
.opt {{ display:flex; gap:22px; align-items:center; background:{CARD}; border:2px solid {LINE}; border-radius:24px; padding:26px 32px; margin:10px 0; font-size:34px; font-weight:600; line-height:1.3; }}
.opt .l {{ font-family:'DejaVu Sans Mono',monospace; width:54px; height:54px; border-radius:14px; background:{LINE}; display:flex; align-items:center; justify-content:center; flex:none; font-size:28px; }}
.opt.right {{ border-color:{LIME}; }} .opt.right .l {{ background:{LIME}; color:{BG}; }}
table.cmp {{ width:100%; border-collapse:collapse; font-size:29px; line-height:1.3; }}
table.cmp th {{ text-align:left; font-size:24px; letter-spacing:2px; color:{GREY}; padding:0 14px 16px; text-transform:uppercase; }}
table.cmp td {{ padding:20px 14px; border-top:2px solid {LINE}; vertical-align:top; color:#D7D9DE; }}
table.cmp td:first-child {{ color:{TEXT}; font-weight:700; width:30%; }}
.kw {{ display:inline-block; font-family:'DejaVu Sans Mono',monospace; font-weight:700; font-size:44px; color:{BG}; background:{LIME}; border-radius:16px; padding:10px 26px; }}
.stat {{ display:flex; gap:26px; margin-top:34px; }}
.stat div {{ flex:1; background:{CARD}; border:2px solid {LINE}; border-radius:24px; padding:26px; }}
.stat b {{ display:block; font-size:62px; font-weight:800; color:{LIME}; letter-spacing:-1px; }}
.stat span {{ font-size:26px; color:{SOFT}; font-weight:500; line-height:1.3; display:block; margin-top:6px; }}
.note {{ font-size:24px; color:{GREY}; margin-top:28px; line-height:1.4; }}
"""


def md(s, prompt=False):
    """Escape text; **x** -> lime; [X] -> placeholder; newlines -> <br>."""
    s = html.escape(s or "")
    s = re.sub(r"\*\*(.+?)\*\*", r'<span class="lime">\1</span>', s)
    s = re.sub(r"\[([^\]\n]{1,40})\]", r'<span class="ph">[\1]</span>', s)
    return s.replace("\n", "<br>")


def frame(inner, idx, total, foot_left, series, w, h, story=False):
    counter = f"{idx}/{total}" if total and total > 1 else ""
    right = f'<div class="count">{counter}</div>' if counter else f'<div class="series">{html.escape(series or "")}</div>'
    return f"""<html><head><meta charset="utf-8"><style>:root{{--w:{w}px;--h:{h}px}}{CSS}</style></head>
<body class="{'story' if story else ''}"><div class="wrap">
<div class="top"><div class="brand"><div class="ic">{CHECK_ICON}</div>NO MORE BUSYWORK</div>{right}</div>
<div class="body" id="body">{inner}</div>
<div class="foot"><div>{html.escape(foot_left or '')}</div><div>@nomorebusywork</div></div>
</div></body></html>"""


def layout(s):
    k = s.get("layout", "text")
    kicker = f'<div class="kicker">{md(s["kicker"])}</div>' if s.get("kicker") else ""
    if k == "cover":
        big = f'<div class="big">{md(s["big"])}</div>' if s.get("big") else ""
        size = s.get("size", "xl" if not s.get("big") else "l")
        title = f'<div class="h-{size}" style="margin-top:{12 if big else 0}px">{md(s.get("title",""))}</div>'
        sub = f'<div class="sub">{md(s["sub"])}</div>' if s.get("sub") else ""
        tag = f'<div style="font-size:30px;font-weight:600;margin-top:40px;">{md(s["tag"])}</div>' if s.get("tag") else ""
        return kicker + big + title + sub + tag
    if k == "text":
        title = f'<div class="h-{s.get("size","m")}">{md(s.get("title",""))}</div>' if s.get("title") else ""
        body = "".join(f'<div class="p">{md(p)}</div>' for p in s.get("paras", []))
        stats = ""
        if s.get("stats"):
            stats = '<div class="stat">' + "".join(f'<div><b>{md(a)}</b><span>{md(b)}</span></div>' for a, b in s["stats"]) + "</div>"
        note = f'<div class="note">{md(s["note"])}</div>' if s.get("note") else ""
        return kicker + title + body + stats + note
    if k == "prompt":
        cards = ""
        for c in s.get("cards", []):
            num = f'<span class="num">{html.escape(str(c["n"]))}</span>' if c.get("n") is not None else ""
            cards += f'<div class="card"><div class="head">{num}<span class="title">{md(c.get("title",""))}</span></div><div class="ptext">{md(c["text"], True)}</div></div>'
        note = f'<div class="note">{md(s["note"])}</div>' if s.get("note") else ""
        return kicker + cards + note
    if k == "chat":
        out = '<div style="display:flex;flex-direction:column;">'
        for m in s.get("messages", []):
            you = m.get("role") == "you"
            out += f'<div class="who {"r" if you else ""}">{"YOU" if you else "AI ASSISTANT"}</div>'
            out += f'<div class="bubble {"you" if you else "ai"}">{md(m["text"], True)}</div>'
        out += "</div>"
        note = f'<div class="note">{md(s["note"])}</div>' if s.get("note") else ""
        return kicker + out + note
    if k == "beforeafter":
        b, a = s["before"], s["after"]
        return kicker + f"""<div class="ba">
          <div class="card before"><div class="lbl">{md(b.get("label","BEFORE"))}</div><div class="ptext">{md(b["text"])}</div></div>
          <div class="card after"><div class="lbl">{md(a.get("label","AFTER"))}</div><div class="ptext">{md(a["text"])}</div></div></div>""" + (f'<div class="note">{md(s["note"])}</div>' if s.get("note") else "")
    if k == "checklist":
        title = f'<div class="h-m" style="margin-bottom:24px">{md(s["title"])}</div>' if s.get("title") else ""
        items = ""
        for it in s.get("items", []):
            t, d = (it, "") if isinstance(it, str) else (it["t"], it.get("d", ""))
            items += f'<div class="ck"><div class="box">✓</div><div>{md(t)}{f"<small>{md(d)}</small>" if d else ""}</div></div>'
        return kicker + title + items
    if k == "steps":
        title = f'<div class="h-m" style="margin-bottom:24px">{md(s["title"])}</div>' if s.get("title") else ""
        steps = ""
        for i, st in enumerate(s.get("steps", []), start=s.get("start", 1)):
            steps += f'<div class="step"><div class="n">{i:02d}</div><div><div class="t">{md(st["t"])}</div>{f"<div class=d>{md(st.get("d",""), True)}</div>" if st.get("d") else ""}</div></div>'
        return kicker + title + steps
    if k == "quiz":
        q = f'<div class="h-m" style="margin-bottom:30px">{md(s["question"])}</div>'
        letters = "ABCD"
        opts = "".join(
            f'<div class="opt {"right" if s.get("reveal") and i == s.get("answer") else ""}"><div class="l">{letters[i]}</div><div>{md(o)}</div></div>'
            for i, o in enumerate(s.get("options", [])))
        ex = f'<div class="p">{md(s["explain"])}</div>' if s.get("reveal") and s.get("explain") else ""
        return kicker + q + opts + ex
    if k == "compare":
        title = f'<div class="h-m" style="margin-bottom:30px">{md(s["title"])}</div>' if s.get("title") else ""
        head = "<tr>" + "".join(f"<th>{md(c)}</th>" for c in s.get("cols", [])) + "</tr>"
        rows = "".join("<tr>" + "".join(f"<td>{md(c)}</td>" for c in r) + "</tr>" for r in s.get("rows", []))
        return kicker + title + f'<table class="cmp">{head}{rows}</table>' + (f'<div class="note">{md(s["note"])}</div>' if s.get("note") else "")
    if k == "cta":
        title = f'<div class="h-l">{md(s.get("title",""))}</div>'
        body = f'<div class="sub">{md(s["body"])}</div>' if s.get("body") else ""
        kw = f'<div style="margin-top:44px"><span class="kw">{html.escape(s["keyword"])}</span></div>' if s.get("keyword") else ""
        after = f'<div class="sub" style="margin-top:28px">{md(s["after"])}</div>' if s.get("after") else ""
        return kicker + title + body + kw + after
    raise ValueError(f"unknown layout {k}")


OVERFLOW_JS = """() => {
  const b = document.getElementById('body');
  const kids = [...b.children];
  if (!kids.length) return 0;
  const bottom = Math.max(...kids.map(k => k.getBoundingClientRect().bottom));
  const top = Math.min(...kids.map(k => k.getBoundingClientRect().top));
  const box = b.getBoundingClientRect();
  return Math.max(0, Math.round(bottom - box.bottom), Math.round(box.top - top));
}"""


def shoot(page, doc, path, w, h):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(doc)
    page.evaluate("document.fonts.ready")
    over = page.evaluate(OVERFLOW_JS)
    png = path.rsplit(".", 1)[0] + ".png"
    page.screenshot(path=png, full_page=False)
    from PIL import Image
    Image.open(png).convert("RGB").save(path, quality=90)
    os.remove(png)
    return over


def make_reel(slide_paths, out_mp4, seconds=3.2):
    """Slides (1080x1350) -> 1080x1920 silent-audio MP4 with crossfades."""
    with tempfile.TemporaryDirectory() as td:
        frames = []
        from PIL import Image
        for i, p in enumerate(slide_paths):
            canvas = Image.new("RGB", (1080, 1920), BG)
            im = Image.open(p)
            canvas.paste(im, (0, 285))
            fp = os.path.join(td, f"f{i:02d}.png")
            canvas.save(fp)
            frames.append(fp)
        n = len(frames)
        fade = 0.4
        inputs = []
        for fp in frames:
            inputs += ["-loop", "1", "-t", str(seconds), "-i", fp]
        filt, last = [], "[0:v]"
        offset = seconds - fade
        for i in range(1, n):
            outl = f"[v{i}]"
            filt.append(f"{last}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.2f}{outl}")
            last = outl
            offset += seconds - fade
        total = seconds * n - fade * (n - 1)
        fc = ";".join(filt) if filt else "[0:v]null[v1]"
        vout = last if filt else "[v1]"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
               "-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
               "-filter_complex", fc + f";{vout}format=yuv420p,fps=30[vf]",
               "-map", "[vf]", "-map", f"{n}:a", "-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
               "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out_mp4]
        subprocess.run(cmd, check=True)


def render_spec(spec, page):
    pid = spec["id"]
    kind = spec.get("type", "carousel")
    out = os.path.join(ROOT, "queue", pid)
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith((".jpg", ".mp4")):
            os.remove(os.path.join(out, f))
    problems = []
    series = spec.get("series", "")
    if kind == "story":
        s = spec["story"]
        doc = frame(layout(s), None, None, s.get("foot", ""), series, 1080, 1920, story=True)
        over = shoot(page, doc, os.path.join(out, "story.jpg"), 1080, 1920)
        if over:
            problems.append(f"{pid} story overflows by {over}px")
        media = ["story.jpg"]
    else:
        slides = spec["slides"]
        total = len(slides)
        media = []
        for i, s in enumerate(slides, start=1):
            foot = s.get("foot", "Swipe →" if i == 1 and total > 1 else ("Save · Share · Follow" if i == total else ""))
            doc = frame(layout(s), i, total, foot, series, 1080, 1350)
            name = f"{i:02d}.jpg"
            over = shoot(page, doc, os.path.join(out, name), 1080, 1350)
            if over:
                problems.append(f"{pid} slide {i} overflows by {over}px")
            media.append(name)
        if kind == "reel":
            make_reel([os.path.join(out, m) for m in media], os.path.join(out, "reel.mp4"), spec.get("seconds_per_slide", 3.2))
            for m in media:
                os.rename(os.path.join(out, m), os.path.join(out, "cover_" + m)) if m == "01.jpg" else os.remove(os.path.join(out, m))
            media = ["reel.mp4"]
    post = {"type": kind, "caption": spec.get("caption", ""), "publish_at": spec["publish_at"], "media": media}
    if kind == "reel":
        post["cover"] = "cover_01.jpg"
    json.dump(post, open(os.path.join(out, "post.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return problems


def main(argv):
    paths = []
    if argv and argv[0] == "--all":
        folder = argv[1]
        paths = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".json"))
    else:
        paths = argv
    problems = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        for sp in paths:
            spec = json.load(open(sp, encoding="utf-8"))
            try:
                problems += render_spec(spec, page)
                print("rendered", spec["id"])
            except Exception as e:  # keep going, report at the end
                problems.append(f"{sp}: {e}")
        b.close()
    if problems:
        print("\nPROBLEMS:\n" + "\n".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
