# No More Busywork – content spec guide

Account: @nomorebusywork, faceless, English, for small business owners and non-technical
professionals (US/UK). Promise: "AI workflows that kill busywork. Copy-paste prompts & tools.
No jargon, no hype."

## Files
- One JSON spec per post in `specs/<id>.json`. Ids: `YYYY-MM-DD-am` (carousel, 12:00 ET),
  `YYYY-MM-DD-pm` (reel, 18:00 ET), `YYYY-MM-DD-story` (story, 09:00 ET).
  Take `publish_at` (UTC) exactly from `plan/calendar.json`.
- Render: `python3 tools/nmb_render.py specs/<id>.json ...` → `queue/<id>/`.
  The renderer prints PROBLEMS if any text overflows: shorten text until there are none.
- Example of a finished carousel: `specs/2026-10-15-pm.json`.

## Spec schema
```json
{"id": "2026-10-16-am", "type": "carousel", "series": "MYTH VS REALITY",
 "publish_at": "2026-10-16T16:00:00Z", "slides": [ {...}, ... ], "caption": "..."}
{"id": "2026-10-16-pm", "type": "reel", "series": "ONE-MINUTE TIP", "publish_at": "...",
 "slides": [ {..., "seconds": 4}, ... ], "caption": "..."}
{"id": "2026-10-16-story", "type": "story", "series": "TODAY", "publish_at": "...",
 "story": { one slide object }}
```
Inline markup in any text: `**words**` = lime highlight (use 1–2 per slide), `[PLACEHOLDER]` =
lime placeholder (prompts), `\n` = line break.

## Layouts (field "layout")
- `cover`: kicker, big (optional huge number/word), title, sub, tag, size ("xl"|"l"|"m")
- `text`: kicker, title, size, paras [..], stats [[value,label],..] (max 3), note
- `prompt`: kicker, cards [{n, title, text}] (1–3 cards), note
- `chat`: kicker, messages [{role:"you"|"ai", text}], note
- `beforeafter`: kicker, before {label,text}, after {label,text}, note
- `checklist`: kicker, title, items [string | {t, d}] (max 5)
- `steps`: kicker, title, steps [{t, d}] (max 5), start
- `quiz`: kicker, question, options [..] (2–4), answer (index), reveal (bool), explain
  → put the same question twice: first `reveal:false`, next slide `reveal:true` + explain
- `compare`: kicker, title, cols [..], rows [[..],..] (max 5 rows, short cells), note
- `cta`: kicker, title, keyword, body, after

## Rules for every post
1. **Original and honest.** Every example output on a slide must be real: write the prompt, then
   actually produce the answer yourself and paste a faithful, shortened version. "Prompt Duel" =
   vague prompt vs specific prompt, both answered by you; never claim results from named
   products you didn't use. Example businesses/people are invented: label once ("Example
   business, invented").
2. **No numbers you can't back up.** No statistics, studies, prices, plan limits or "X% of
   businesses". Time savings only as "about" and only for the shown example.
3. **No brand logos, no product screenshots, no copyrighted text.** Naming common tools
   generically is fine ("your AI chat assistant", "your calendar app").
4. **No hype**: no "make money", no "10x", no "secret". Plain, warm, practical. US English.
5. **Privacy**: when a prompt involves customer data, add a short note to remove private details.
6. Every carousel: 7–10 slides. Slide 1 = hook that promises a concrete result (number, time,
   before/after). Second-to-last = recap or checklist (saveable). Last = CTA.
7. Reels: 6–9 frames, 35–50 seconds total (`seconds` per frame: 3 for short text, 5–7 for
   prompt cards or chat). Frame 1 = hook of max 8 words (layout cover, size xl). Show the
   problem, the prompt, the real result, one tip. Last frame: "Send this to someone who still
   [does X by hand]" + follow. Keep frames uncluttered: phone full screen.
8. Stories: one bold slide (layout cover or text). Tease the day's noon carousel ("New post at
   noon ET"). Rotate the closing line: "DM me PACK for 21 free prompts" / "DM me PROMPTS for
   the free 25-prompt pack" / "DM me TOOLS for our starter kit".
9. CTAs, one per post:
   - carousels: "Follow + comment PACK" (mostly), sometimes PROMPTS or TOOLS (keywords that
     exist in offers/offers.json). Say what they get. Delivery is automatic by DM.
   - reels: share CTA ("Send this to…") + "Follow @nomorebusywork for one fix a day".
10. Captions (English):
   - First line = what a person would search ("How to sort your inbox with AI in 5 minutes"),
     under 125 characters.
   - 80–180 words, short paragraphs, the full prompt(s) in the caption when the post has one.
   - End with the CTA, then "Save this for later. 📌", then 3–5 specific hashtags
     (e.g. #smallbusiness #aitools #productivity #smallbusinessowner #chatgptprompts — vary them).
11. Vary layouts: don't open two consecutive days with the same cover style; mix chat,
    beforeafter, compare, quiz, steps, checklist.

## Brand look (handled by the renderer)
Dark background, lime #C6F432 accents, Inter. Don't add colours or emojis inside slides
except an occasional ✓ → ↓ 📌.
