"""Renders the follower-only "Extended Prompt Pack" sent by DM (keyword PACK) into offers/pack/."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from playwright.sync_api import sync_playwright  # noqa: E402
from render_reference import PROMPT_CSS, esc, prompt_text, render, slide_frame  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "offers", "pack")
os.makedirs(OUT, exist_ok=True)

SLIDES = [
    ("Sales & leads", [
        ("Qualify a new lead", "A potential client sent this message. In 3 bullets: what they want, how urgent it seems, what I should ask before quoting. Then draft a short reply asking those questions. Message: [PASTE]"),
        ("Revive old leads", "Write a short, no-pressure message to people who asked about [SERVICE] in the last [N] months but never booked. Give one reason to come back now: [REASON]. Max 70 words."),
        ("Ask for a referral", "Write a friendly message asking a happy client, [NAME], for a referral. Mention the result we got together: [RESULT]. Make it easy to say yes. Max 80 words."),
    ]),
    ("Bookings", [
        ("Booking confirmation", "Write a booking confirmation for [SERVICE] on [DATE] at [TIME]: what to bring, how to reschedule, our address [ADDRESS]. Friendly, under 90 words."),
        ("Missed appointment", "A client missed their [SERVICE] appointment today. Write a kind message offering two new times and mentioning our policy: [POLICY]. Max 70 words."),
        ("A spot just opened", "Write a short, upbeat message for our waitlist: a spot opened on [DATE] at [TIME], first to reply gets it."),
    ]),
    ("Money & admin", [
        ("Announce a price change", "Write a message telling clients that [SERVICE] goes from [OLD PRICE] to [NEW PRICE] on [DATE]. One sentence on why, a thank-you, no apologizing. Max 100 words."),
        ("Sort my expenses", "Sort these expenses into software, supplies, travel, marketing and other. Total each group, show your math and flag possible duplicates. List: [PASTE]"),
        ("Ask a supplier for a better price", "Write an email to [SUPPLIER] asking for a better price on [ITEM]. We order about [QUANTITY] per [PERIOD]. Polite, specific, ask for a reply by [DATE]."),
    ]),
    ("Content", [
        ("Questions to posts", "Turn each of these customer questions into a social post idea: a hook, a 2-line answer and a call to action. Questions: [PASTE]"),
        ("Article to newsletter", "Turn this article into a newsletter: subject line, 3-sentence intro, 3 takeaways and one call to action to [ACTION]. Article: [PASTE]"),
        ("Customer story", "Turn these notes into a short before-and-after customer story, max 120 words. Don't invent details: mark anything missing as [MISSING]. Notes: [PASTE]"),
    ]),
    ("Website & listings", [
        ("About section", "Write an About section for [BUSINESS] in [CITY]: who we help, what makes us different ([DIFFERENCE]) and one line about the owner. Under 150 words, no buzzwords."),
        ("Business profile updates", "Write 3 short updates for our Google Business Profile: one offer, one tip, one event on [DATE]. Under 60 words each, each with a call to action."),
        ("Service page FAQ", "Write 6 FAQs with short answers for our [SERVICE] page. Cover price, timing, what's included, what's not and how to book."),
    ]),
    ("Team & operations", [
        ("Shift handover", "Turn these notes into a handover for the next shift: done, in progress, watch out for. Bullet points only. Notes: [PASTE]"),
        ("Reply templates", "Write 5 short reply templates for the questions we get most: [QUESTIONS]. Tone: [TONE]. Mark the parts to personalize with [brackets]."),
        ("Feedback to a team member", "Help me give feedback to [NAME] about [ISSUE]: what I noticed, why it matters, what I'd like instead. Kind but clear. Max 120 words."),
    ]),
    ("Decisions", [
        ("Think it through", "I'm deciding whether to [DECISION]. Ask me 5 questions first, then list the pros, the cons and what you'd want to know before deciding."),
        ("Check my pricing", "Here's how I price [SERVICE]: [DETAILS]. Point out where I might be undercharging or confusing customers and suggest 2 simpler options."),
        ("Weekly review", "Here's what happened this week: [NOTES]. Summarize wins, problems and one thing to change next week. Max 120 words."),
    ]),
]


def main():
    total = len(SLIDES) + 2
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()

        cover = """<div style="font-size:30px;font-weight:600;color:#8B8F98;margin-bottom:28px;">FOLLOWER EDITION</div>
          <div style="font-size:150px;font-weight:800;line-height:0.95;letter-spacing:-4px;" class="lime">+21</div>
          <div style="font-size:84px;font-weight:800;line-height:1.05;letter-spacing:-2px;margin-top:12px;">more prompts<br>for small business.</div>
          <div style="font-size:36px;font-weight:500;color:#C9CBD1;margin-top:44px;line-height:1.45;">Sales · Bookings · Money · Content<br>Website · Team · Decisions</div>
          <div style="font-size:30px;font-weight:600;margin-top:44px;">Thanks for following. <span class="lime">Save these 📌</span></div>"""
        render(page, slide_frame(cover, 1, total, "Swipe →"), f"{OUT}/01.png", 1080, 1350)

        n = 26  # continues the numbering of the free 25-prompt pack
        for s_idx, (cat, prompts) in enumerate(SLIDES, start=2):
            cards = ""
            for title, body in prompts:
                cards += f"""<div class="card"><div class="head"><span class="num">{n:02d}</span><span class="title">{esc(title)}</span></div>
                  <div class="ptext">{prompt_text(body)}</div></div>"""
                n += 1
            doc = slide_frame(f'<div class="cat">{esc(cat)}</div>{cards}', s_idx, total, "Replace the [brackets]")
            doc = doc.replace("</style>", PROMPT_CSS + "</style>", 1)
            render(page, doc, f"{OUT}/{s_idx:02d}.png", 1080, 1350)

        last = """<div style="font-size:84px;font-weight:800;line-height:1.05;letter-spacing:-2px;">You're in.<br><span class="lime">New packs land<br>here first.</span></div>
          <div style="font-size:36px;font-weight:500;color:#C9CBD1;margin-top:48px;line-height:1.5;">Reply <span class="lime" style="font-weight:700;">TOOLS</span> for the tools we use<br>with these prompts.</div>
          <div style="font-size:30px;font-weight:600;margin-top:48px;color:#8B8F98;">Works with any AI chat assistant.<br>Check facts and numbers before you send.</div>"""
        render(page, slide_frame(last, total, total, "Save · Share"), f"{OUT}/{total:02d}.png", 1080, 1350)
        b.close()


if __name__ == "__main__":
    main()
