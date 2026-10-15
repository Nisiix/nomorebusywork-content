"""Renders the No More Busywork profile kit (profile photo, highlight covers, pinned carousels)."""
import html
import os
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), "out")
os.makedirs(OUT, exist_ok=True)

BG = "#0F1115"
CARD = "#181B21"
LINE = "#262A33"
TEXT = "#F5F5F7"
LIME = "#C6F432"
BLUE = "#5B8CFF"
GREY = "#8B8F98"

BASE_CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:100%; height:100%; background:{BG}; color:{TEXT};
  font-family:'Inter', sans-serif; -webkit-font-smoothing:antialiased; }}
.mono {{ font-family:'DejaVu Sans Mono', monospace; }}
.lime {{ color:{LIME}; }}
.grey {{ color:{GREY}; }}
"""

CHECK_ICON = f"""<svg viewBox="0 0 100 100" width="100%" height="100%">
  <rect x="8" y="8" width="84" height="84" rx="22" fill="none" stroke="{LIME}" stroke-width="7"/>
  <path d="M28 52 L44 67 L73 34" fill="none" stroke="{LIME}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def slide_frame(inner, idx=None, total=None, footer_left="", w=1080, h=1350):
    counter = f"{idx}/{total}" if idx else ""
    return f"""<html><head><style>{BASE_CSS}
.wrap {{ position:relative; width:{w}px; height:{h}px; padding:72px 80px; display:flex; flex-direction:column; }}
.top {{ display:flex; justify-content:space-between; align-items:center; font-size:22px; letter-spacing:3px; font-weight:700; }}
.brand {{ display:flex; align-items:center; gap:14px; color:{LIME}; }}
.brand .ic {{ width:34px; height:34px; }}
.count {{ color:{GREY}; font-weight:600; letter-spacing:1px; }}
.body {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
.foot {{ display:flex; justify-content:space-between; font-size:21px; color:{GREY}; font-weight:500; }}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><div class="ic">{CHECK_ICON}</div>NO MORE BUSYWORK</div><div class="count">{counter}</div></div>
<div class="body">{inner}</div>
<div class="foot"><div>{footer_left}</div><div>@nomorebusywork</div></div>
</div></body></html>"""


def esc(s):
    return html.escape(s)


def prompt_text(s):
    """Escape and highlight [PLACEHOLDERS] in lime."""
    out, buf, inside = [], "", False
    for ch in s:
        if ch == "[" and not inside:
            out.append(esc(buf)); buf = "["; inside = True
        elif ch == "]" and inside:
            buf += "]"; out.append(f'<span class="ph">{esc(buf)}</span>'); buf = ""; inside = False
        else:
            buf += ch
    out.append(esc(buf))
    return "".join(out)


# ---------------------------------------------------------------- content
PROMPT_SLIDES = [
    ("Customer emails", [
        ("Answer an inquiry", "You're my assistant at [BUSINESS], a [TYPE OF BUSINESS]. Write a friendly reply to this customer email in under 120 words. Answer the question, suggest one next step, end with a clear call to action. Email: [PASTE]"),
        ("Follow up on a quote", "Write a short, polite follow-up to a client who hasn't replied to my quote for [SERVICE], sent [X] days ago. No pressure, offer to answer questions. Max 80 words."),
        ("Late payment reminder", "Write a firm but friendly reminder for invoice [NUMBER] of [AMOUNT], now [X] days overdue. Keep the relationship warm. Max 100 words."),
    ]),
    ("Reviews", [
        ("Thank a 5-star review", "Reply to this 5-star review in 2–3 sentences. Thank them by name, mention one detail they wrote, invite them back. Review: [PASTE]"),
        ("Handle a bad review", "Reply to this negative review calmly. Acknowledge the issue, no excuses, offer to fix it privately at [CONTACT]. Max 90 words. Review: [PASTE]"),
        ("Find what customers say", "Here are my last [N] reviews. List the 3 things customers love most and the 3 most common complaints, each with a short example. Reviews: [PASTE]"),
    ]),
    ("Quotes & proposals", [
        ("Notes to quote", "Turn these rough notes into a clear quote for [CLIENT]: short intro, itemized work with prices, timeline, payment terms and validity date. Notes: [PASTE]"),
        ("\"Your price is too high\"", "A client says [PRICE] for [SERVICE] is too high. Write a calm reply that explains the value in 3 bullet points and offers one cheaper option."),
        ("One-page proposal", "Write a one-page proposal for [SERVICE] for [CLIENT TYPE]. Sections: their problem, my solution, what's included, timeline, price, next step. Plain language."),
    ]),
    ("Social media", [
        ("A week of captions", "Write 5 Instagram captions for [BUSINESS] for this week: 1 tip, 1 behind the scenes, 1 product, 1 customer story, 1 question. Max 60 words and 3 hashtags each."),
        ("Photo to caption", "Write 3 caption options for a photo of [DESCRIBE THE PHOTO] for [BUSINESS]: one funny, one informative, one with a clear offer."),
        ("One post, many formats", "Turn this post into 1 Instagram caption, 1 short story text and 3 one-line hooks. Post: [PASTE]"),
    ]),
    ("Hiring & team", [
        ("Job ad", "Write a job ad for a [ROLE] at [BUSINESS] in [CITY]: what the day looks like, must-haves, nice-to-haves, pay range [RANGE], how to apply. Friendly, under 200 words."),
        ("Messy notes to checklist", "Turn these notes into a numbered checklist a new employee can follow for [TASK]. Add a short \"common mistakes\" section. Notes: [PASTE]"),
        ("Welcome a new hire", "Write a welcome message for a new team member starting on [DATE]: what to bring, who to ask for, the plan for day one. Warm and short."),
    ]),
    ("Customer service", [
        ("Build your FAQ", "From these customer emails, write the 10 most common questions with short, clear answers for a FAQ. Emails: [PASTE]"),
        ("Calm an angry customer", "A customer is upset because [SITUATION]. Write a reply that calms them down, takes responsibility where fair and offers [SOLUTION]. Max 100 words."),
        ("Say no politely", "Write a polite way to say no to [REQUEST] while keeping the customer happy. Offer this alternative instead: [ALTERNATIVE]."),
    ]),
    ("Marketing & offers", [
        ("4-week promotion", "Plan a 4-week promotion for [PRODUCT OR SERVICE] at [BUSINESS]. For each week give the angle, one post idea and one email subject line."),
        ("Product description", "Write a product description for [PRODUCT] in under 80 words. Lead with the main benefit, include 3 key features, end with who it's perfect for."),
        ("Monthly customer update", "Write a short monthly update for my customers: one piece of news, one tip, one offer ([OFFER]). Under 150 words, with a subject line."),
    ]),
    ("Admin & planning", [
        ("Meeting notes to actions", "Summarize these meeting notes into decisions made, action items with owner and deadline, and open questions. Notes: [PASTE]"),
        ("Plan my week", "Here's my to-do list. Group it into must-do, should-do and can-wait, then suggest a realistic plan for [N] hours a day this week. List: [PASTE]"),
        ("Translate for customers", "Translate this into [LANGUAGE] for customers. Keep it friendly and natural, not literal, and flag any phrase that might sound odd. Text: [PASTE]"),
    ]),
]
BONUS = ("Check before you hit send", "Review this email before I send it. Point out anything unclear, too long or possibly rude, then give me an improved version. Email: [PASTE]")

START_SLIDES = [
    """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">START HERE</div>
       <div style="font-size:96px;font-weight:800;line-height:1.02;letter-spacing:-2px;">AI that does<br>your <span class="lime">busywork.</span></div>
       <div style="font-size:38px;font-weight:500;color:#C9CBD1;margin-top:40px;line-height:1.35;">So you can do the work<br>only you can do.</div>""",
    """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">WHO IT'S FOR</div>
       <div style="font-size:64px;font-weight:800;line-height:1.1;letter-spacing:-1px;margin-bottom:48px;">Small business owners,<br>freelancers &amp; solo pros.</div>
       <div class="list">
         <div><span class="lime">✓</span> No coding</div>
         <div><span class="lime">✓</span> No jargon</div>
         <div><span class="lime">✓</span> No 50-tool lists</div>
         <div><span class="lime">✓</span> Just the task, done faster</div>
       </div>""",
    """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">WHAT YOU'LL FIND HERE</div>
       <div class="row"><div class="tag">WORKFLOWS</div><div>One real task, solved step by step.</div></div>
       <div class="row"><div class="tag">PROMPTS</div><div>Copy, paste, replace the [brackets].</div></div>
       <div class="row"><div class="tag">TOOL PICKS</div><div>3 options, free plans first, prices dated.</div></div>
       <div class="row"><div class="tag">WHAT CHANGED</div><div>New features explained for your business.</div></div>""",
    """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">OUR RULES</div>
       <div class="rule"><span class="lime">01</span>Every workflow is tried before it's posted.</div>
       <div class="rule"><span class="lime">02</span>Every price shows the date we checked it.</div>
       <div class="rule"><span class="lime">03</span>No "make $10k with AI". Ever.</div>
       <div class="rule"><span class="lime">04</span>Affiliate links are always labeled.</div>""",
    """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">FREE, IN YOUR DMs</div>
       <div class="dm"><div class="kw">PROMPTS</div><div>25 copy-paste prompts for emails, reviews, quotes &amp; posts</div></div>
       <div class="dm"><div class="kw">TOOLS</div><div>The tools we recommend right now, free plans first</div></div>
       <div class="dm"><div class="kw blue">CHANNEL</div><div>Join from our profile: one exclusive workflow every week</div></div>""",
    """<div style="font-size:96px;font-weight:800;line-height:1.02;letter-spacing:-2px;">Get your<br><span class="lime">hours back.</span></div>
       <div style="font-size:38px;font-weight:500;color:#C9CBD1;margin-top:48px;line-height:1.5;">Save this post 📌<br>Follow for one workflow a day<br>DM me <span class="lime" style="font-weight:700;">PROMPTS</span> for the free pack</div>""",
]

START_CSS = f"""
.list div {{ font-size:44px; font-weight:600; margin:14px 0; }}
.row {{ display:flex; flex-direction:column; gap:10px; padding:26px 0; border-top:2px solid {LINE}; font-size:36px; font-weight:500; }}
.row:last-child {{ border-bottom:2px solid {LINE}; }}
.tag {{ font-size:24px; font-weight:800; letter-spacing:3px; color:{LIME}; }}
.rule {{ font-size:46px; font-weight:700; line-height:1.2; margin:22px 0; display:flex; gap:28px; }}
.rule span {{ font-size:30px; padding-top:10px; min-width:52px; }}
.dm {{ background:{CARD}; border:2px solid {LINE}; border-radius:28px; padding:34px 38px; margin:14px 0; font-size:34px; font-weight:500; line-height:1.35; }}
.kw {{ display:inline-block; font-family:'DejaVu Sans Mono',monospace; font-weight:700; font-size:30px; color:{BG}; background:{LIME}; border-radius:12px; padding:6px 16px; margin-bottom:16px; }}
.kw.blue {{ background:{BLUE}; }}
"""

PROMPT_CSS = f"""
.cat {{ font-size:30px; font-weight:700; color:{GREY}; letter-spacing:3px; text-transform:uppercase; margin-bottom:26px; }}
.card {{ background:{CARD}; border:2px solid {LINE}; border-radius:28px; padding:32px 36px; margin:12px 0; }}
.head {{ display:flex; align-items:center; gap:16px; margin-bottom:14px; }}
.num {{ font-family:'DejaVu Sans Mono',monospace; font-size:25px; font-weight:700; color:{BG}; background:{LIME}; border-radius:10px; padding:4px 12px; }}
.title {{ font-size:35px; font-weight:700; }}
.ptext {{ font-size:30px; line-height:1.4; color:#D7D9DE; font-weight:450; }}
.ph {{ color:{LIME}; font-weight:600; }}
"""


def render(page, html_str, path, w, h):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(html_str)
    page.evaluate("document.fonts.ready")
    page.screenshot(path=path, full_page=False)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()

        # ---- profile photo
        prof = f"""<html><head><style>{BASE_CSS}</style></head><body>
        <div style="width:1080px;height:1080px;display:flex;align-items:center;justify-content:center;background:{BG};">
          <div style="width:560px;height:560px;">{CHECK_ICON}</div></div></body></html>"""
        render(page, prof, f"{OUT}/00_profile_photo.png", 1080, 1080)

        # ---- highlight covers (icon centered for circular crop)
        icons = {
            "start_here": f'<svg viewBox="0 0 100 100" width="100%" height="100%"><path d="M22 50 H74 M56 30 L76 50 L56 70" fill="none" stroke="{LIME}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            "workflows": f'<svg viewBox="0 0 100 100" width="100%" height="100%"><circle cx="22" cy="50" r="11" fill="none" stroke="{LIME}" stroke-width="7"/><circle cx="78" cy="24" r="11" fill="none" stroke="{LIME}" stroke-width="7"/><circle cx="78" cy="76" r="11" fill="none" stroke="{LIME}" stroke-width="7"/><path d="M32 45 L68 29 M32 55 L68 71" stroke="{LIME}" stroke-width="7" stroke-linecap="round"/></svg>',
            "prompts": f'<svg viewBox="0 0 100 100" width="100%" height="100%"><path d="M14 22 H86 V68 H46 L28 84 V68 H14 Z" fill="none" stroke="{LIME}" stroke-width="7" stroke-linejoin="round"/><path d="M32 38 L42 46 L32 54 M50 54 H66" fill="none" stroke="{LIME}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
            "tools": f'<svg viewBox="0 0 100 100" width="100%" height="100%"><rect x="14" y="14" width="30" height="30" rx="8" fill="none" stroke="{LIME}" stroke-width="7"/><rect x="56" y="14" width="30" height="30" rx="8" fill="none" stroke="{LIME}" stroke-width="7"/><rect x="14" y="56" width="30" height="30" rx="8" fill="none" stroke="{LIME}" stroke-width="7"/><rect x="56" y="56" width="30" height="30" rx="8" fill="{LIME}"/></svg>',
            "channel": f'<svg viewBox="0 0 100 100" width="100%" height="100%"><circle cx="50" cy="56" r="8" fill="{LIME}"/><path d="M34 40 A22 22 0 0 0 34 72 M66 40 A22 22 0 0 1 66 72 M22 28 A38 38 0 0 0 22 84 M78 28 A38 38 0 0 1 78 84" fill="none" stroke="{LIME}" stroke-width="7" stroke-linecap="round"/></svg>',
        }
        for i, (name, svg) in enumerate(icons.items(), start=1):
            cov = f"""<html><head><style>{BASE_CSS}</style></head><body>
            <div style="width:1080px;height:1920px;display:flex;align-items:center;justify-content:center;background:{BG};">
              <div style="width:440px;height:440px;border-radius:50%;background:{CARD};border:4px solid {LINE};display:flex;align-items:center;justify-content:center;">
                <div style="width:240px;height:240px;">{svg}</div></div></div></body></html>"""
            render(page, cov, f"{OUT}/1{i}_highlight_cover_{name}.png", 1080, 1920)

        # ---- Start here carousel
        for i, inner in enumerate(START_SLIDES, start=1):
            doc = slide_frame(inner, i, len(START_SLIDES), "Swipe →" if i < len(START_SLIDES) else "")
            doc = doc.replace("</style>", START_CSS + "</style>", 1)
            render(page, doc, f"{OUT}/2{i}_start_here_{i:02d}.png", 1080, 1350)

        # ---- Free prompt pack carousel (10 slides)
        total = 10
        cover = """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">FREE PROMPT PACK</div>
          <div style="font-size:150px;font-weight:800;line-height:0.95;letter-spacing:-4px;" class="lime">25</div>
          <div style="font-size:84px;font-weight:800;line-height:1.05;letter-spacing:-2px;margin-top:12px;">copy-paste prompts<br>for small business.</div>
          <div style="font-size:36px;font-weight:500;color:#C9CBD1;margin-top:44px;line-height:1.45;">Emails · Reviews · Quotes · Social posts<br>Hiring · Customer service · Marketing · Admin</div>
          <div style="font-size:30px;font-weight:600;margin-top:44px;">Works with any AI chat assistant. <span class="lime">Save it 📌</span></div>"""
        doc = slide_frame(cover, 1, total, "Swipe →")
        render(page, doc, f"{OUT}/31_prompt_pack_01.png", 1080, 1350)

        n = 1
        for s_idx, (cat, prompts) in enumerate(PROMPT_SLIDES, start=2):
            cards = ""
            for title, body in prompts:
                cards += f"""<div class="card"><div class="head"><span class="num">{n:02d}</span><span class="title">{esc(title)}</span></div>
                  <div class="ptext">{prompt_text(body)}</div></div>"""
                n += 1
            inner = f'<div class="cat">{esc(cat)}</div>{cards}'
            doc = slide_frame(inner, s_idx, total, "Replace the [brackets]")
            doc = doc.replace("</style>", PROMPT_CSS + "</style>", 1)
            render(page, doc, f"{OUT}/3{s_idx}_prompt_pack_{s_idx:02d}.png" if s_idx < 10 else f"{OUT}/3z_prompt_pack_{s_idx:02d}.png", 1080, 1350)

        title, body = BONUS
        last = f"""<div class="cat">Bonus</div>
          <div class="card"><div class="head"><span class="num">{n:02d}</span><span class="title">{esc(title)}</span></div>
          <div class="ptext">{prompt_text(body)}</div></div>
          <div style="font-size:76px;font-weight:800;line-height:1.05;letter-spacing:-2px;margin-top:70px;">Want one new<br>workflow <span class="lime">every week?</span></div>
          <div style="font-size:34px;font-weight:500;color:#C9CBD1;margin-top:34px;line-height:1.5;">Join our channel from the profile<br>and follow <span class="lime" style="font-weight:700;">@nomorebusywork</span></div>"""
        doc = slide_frame(last, 10, total, "Save · Share · Follow")
        doc = doc.replace("</style>", PROMPT_CSS + "</style>", 1)
        render(page, doc, f"{OUT}/3z_prompt_pack_10.png", 1080, 1350)
        b.close()


if __name__ == "__main__":
    main()
