#!/usr/bin/env python3
"""
Daily brief — one combined email with three sections, every day.

Sections:
  1. Geopolitics   — today's story, a historical echo, why it matters
  2. Spanish       — advanced phrases, Peninsular and Colombian
  3. General Knowledge — pub-quiz-grade facts with context

Replaces the earlier geo/Spanish alternation. Runs seven days a week, so the
rotations below are keyed on the date's ordinal rather than a weekday count.

Environment variables required:
  ANTHROPIC_API_KEY   from console.anthropic.com
  RESEND_API_KEY      from resend.com
  MAIL_TO             recipient address
  MAIL_FROM           verified sender, e.g. brief@yourdomain.com
                      (or onboarding@resend.dev for testing)

Optional:
  CLAUDE_MODEL        defaults to claude-sonnet-5
  FORCE_DATE          YYYY-MM-DD, overrides today's date. Useful for
                      previewing what a different day's rotation produces.
  DRY_RUN             set to "1" to write brief-output.html without emailing.
"""

import os
import sys
import datetime
import urllib.request
import urllib.error
import json

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
RESEND_URL = "https://api.resend.com/emails"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

# Bumped from 4000: three sections in one response need the headroom.
MAX_TOKENS = 8000

# --------------------------------------------------------------------------
# Rotations
#
# All three are indexed off date.toordinal() so they advance every calendar
# day, weekends included. The list lengths are deliberately coprime-ish (5,
# 12, 14) so the combination of region + theme + category doesn't settle into
# a short repeating cycle.
# --------------------------------------------------------------------------

REGIONS = [
    "the Middle East, the Gulf, or North Africa",
    "Europe, Russia, or the post-Soviet space",
    "East Asia, the South China Sea, or the Pacific",
    "the Americas — North, Central, or South",
    "sub-Saharan Africa, or South and Central Asia",
]

SPANISH_THEMES = [
    "reacting to what someone just said — surprise, agreement, scepticism, sympathy",
    "softening and hedging — disagreeing politely, declining, being tactfully vague",
    "business and formal register — meetings, email, negotiating, disagreeing upwards",
    "frustration and complaint — mild irritation through to genuine annoyance, kept printable",
    "making and changing plans — suggesting, postponing, cancelling without offence",
    "subtle grammar — subjunctive triggers, ser/estar edge cases, aspect, clitic quirks",
    "small talk with people you half-know — neighbours, colleagues, the same barista",
    "regional idioms — expressions that mark you as Madrid or Bogotá, and the traps between them",
    "enthusiasm and praise — liking something without reaching for 'muy bueno' every time",
    "getting things done — shops, admin, asking for help, explaining a problem",
    "storytelling — narrating something that happened to you, keeping someone's attention",
    "winding down a conversation — leaving politely, promising to be in touch",
]

KNOWLEDGE_CATEGORIES = [
    "science and the natural world",
    "history before 1500",
    "geography and borders",
    "literature and publishing",
    "music, classical through pop",
    "film and television",
    "sport",
    "art and architecture",
    "food and drink",
    "language and etymology",
    "inventions and technology",
    "records, firsts and lasts",
    "mythology and folklore",
    "notable people and their odd biographies",
]


def rotations(d):
    """Pick today's region, Spanish theme, and three knowledge categories."""
    n = d.toordinal()
    region = REGIONS[n % len(REGIONS)]
    theme = SPANISH_THEMES[n % len(SPANISH_THEMES)]
    cats = [
        KNOWLEDGE_CATEGORIES[(n * 3 + i) % len(KNOWLEDGE_CATEGORIES)]
        for i in range(3)
    ]
    return region, theme, cats


def post_json(url, payload, headers, timeout=900):
    data = json.dumps(payload).encode("utf-8")

    # Resend sits behind Cloudflare, which rejects urllib's default
    # "Python-urllib/3.x" User-Agent with a 403 and body "error code: 1010".
    # Any ordinary-looking UA gets through. Harmless for the Anthropic call.
    headers = dict(headers)
    headers.setdefault("User-Agent", "daily-brief/1.0")
    headers.setdefault("Accept", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {e.code}: {body}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach {url}: {e.reason}") from None


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

def build_prompt(today):
    region, theme, cats = rotations(today)
    date_str = today.strftime("%A, %-d %B %Y")
    cat_list = "; ".join(cats)

    return f"""Today is {date_str}. Produce a combined daily brief with three
sections: geopolitics, Spanish practice, and general knowledge.

Write in British English throughout. Measured, analytical, no hype, no
throat-clearing. Assume an intelligent reader who follows the news but is not
a specialist.

============================================================
SECTION 1 — GEOPOLITICS
============================================================

RESEARCH
Use web search to find the single most consequential geopolitical development
of the last 24 hours. Today's suggested regional focus is {region}, but ignore
that steer if a genuinely bigger story is breaking elsewhere. Prefer stories
with real strategic weight — territorial disputes, alliance shifts, sanctions
and trade coercion, military escalation, chokepoints, elections with external
consequences — over domestic political noise. Gather at least three credible
sources and confirm key facts appear in more than one outlet before asserting
them. Keep the exact URLs. Where outlets disagree on figures, say so rather
than picking one silently.

HISTORICAL ECHO
Identify one genuine historical parallel: a past episode whose mechanics, not
merely its mood, resemble today's story. Give specific dates, names and
outcomes. Vary the period from day to day — ancient, medieval, early modern,
nineteenth century, interwar, Cold War, post-1990 are all fair game. State
plainly where the analogy breaks down as well as where it holds. Avoid lazy
parallels; not every crisis is Munich 1938 or Sarajevo 1914.

LENGTH
Roughly 200 words on today's story, 200 on the historical echo, 100 on why it
matters. Flowing paragraphs, not bullet fragments.

============================================================
SECTION 2 — SPANISH PRACTICE
============================================================

THE LEARNER
Advanced. He holds conversations comfortably and his grammar is sound, but he
still sounds like a textbook. The goal is the connective tissue that makes
someone sound like they actually live there.

VARIETIES
Peninsular Spanish (Madrid, Barcelona) and Colombian Spanish (Bogotá, Medellín
— neutral educated register). Be explicit about which applies to each phrase,
and flag anything that would land badly in the other. Where a phrase is
genuinely pan-Hispanic, say so. Do NOT use Caribbean slang.

TODAY'S THEME
{theme}

WHAT TO PRODUCE
Exactly three phrases or expressions on that theme. For each:
  - the phrase in Spanish
  - a literal word-for-word gloss where the literal meaning is odd
  - English translation and what it actually means colloquially
  - when to use it: a concrete, real scenario
  - why it's tricky: the grammar point or regional nuance that trips people up
  - one example sentence with its English translation

RULES
Nothing a learner would already have from a textbook. Keep it clean; mild
irritation is fine, insults are not. Do not invent phrases or inflate a rare
regionalism into a common one — if you are unsure a phrase is genuinely
current, leave it out.

============================================================
SECTION 3 — GENERAL KNOWLEDGE
============================================================

Six facts that would (a) make good conversation and (b) plausibly appear in a
British pub quiz. Aim for the sweet spot: notable enough to be quizzable, not
so obvious that everyone already knows it.

Today draw mainly from these categories: {cat_list}. Mix eras and regions, and
include at least two items with British relevance.

Each item: a one-line hook fact, then one or two sentences of context that
make it memorable or give it a story.

ACCURACY IS THE PRIORITY HERE. Prefer facts that are firmly established over
anything that smells like internet trivia. Use web search to verify anything
you are not certain of, and discard rather than hedge. Specifically avoid the
well-known false or disputed chestnuts — the Great Wall being visible from
space, Romans being paid in salt, Einstein failing maths, and their kin.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY an HTML fragment — no markdown, no code fences, no preamble, no
<html> or <body> tags. Use exactly this structure and these class names:

<div class="dateline">
  <span>{date_str}</span>
  <span class="region">REGION LABEL</span>
</div>

<section>
  <h2>Today's Story</h2>
  <h3>HEADLINE</h3>
  <p class="lead">First paragraph.</p>
  <p>Further paragraphs, each in its own p tag.</p>
</section>

<section>
  <h2>Historical Echo</h2>
  <div class="echo">
    <h3>NAME OF EPISODE<span class="era">YEAR RANGE</span></h3>
    <p>Two paragraphs, each in its own p tag.</p>
  </div>
</section>

<section>
  <h2>Why It Matters</h2>
  <div class="takeaway">
    <p>The pattern that repeats.</p>
    <p>What is different this time.</p>
  </div>
  <p style="margin-top:16px"><strong>Three things to watch:</strong></p>
  <ul class="watch"><li>First.</li><li>Second.</li><li>Third.</li></ul>
</section>

<section>
  <h2>Sources</h2>
  <ol class="sources">
    <li><a href="URL">Headline</a> <span class="outlet">&mdash; Outlet</span></li>
  </ol>
</section>

<div class="divider"><span>Spanish Practice</span></div>

<section>
  <h2>Today's Theme</h2>
  <h3>A SHORT TITLE FOR THE THEME</h3>
  <p class="lead">Two or three sentences on what this set of phrases does for
  you and why textbook Spanish falls short here.</p>
</section>

<section>
  <h2>Phrases</h2>

  <div class="phrase">
    <p class="es">La frase en español</p>
    <p class="lit">Literally: word-for-word gloss</p>
    <p class="use">Translation, colloquial meaning, and the moment you would
    reach for it.</p>
    <p class="tricky"><strong>Why it's tricky:</strong> the grammar point or
    regional nuance.</p>
    <p class="example">Example sentence in Spanish.<br>
    <span class="translation-inline">English translation.</span></p>
    <p class="tags"><span class="tag">Register</span><span class="tag region-tag">Spain / Colombia / Both</span></p>
  </div>

  (repeat the phrase div for each of the three entries)
</section>

<div class="divider"><span>General Knowledge</span></div>

<section>
  <h2>Six For The Quiz</h2>

  <div class="fact">
    <p class="hook">The one-line hook fact.</p>
    <p class="context">One or two sentences of context.</p>
    <p class="tags"><span class="tag">Category</span></p>
  </div>

  (repeat the fact div for each of the six entries)
</section>

If research fails or sources are too thin for the geopolitics section, say so
honestly in the same format rather than padding it with speculation."""


# --------------------------------------------------------------------------

def generate(today):
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": build_prompt(today)}],
        "tools": [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": 12}
        ],
    }

    headers = {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    result = post_json(ANTHROPIC_URL, payload, headers)

    fragment = "".join(
        block.get("text", "")
        for block in result.get("content", [])
        if block.get("type") == "text"
    ).strip()

    if not fragment:
        raise RuntimeError(
            f"Model returned no text. Response: {json.dumps(result)[:2000]}"
        )

    if result.get("stop_reason") == "max_tokens":
        print(
            "WARNING: response hit the max_tokens ceiling and may be truncated. "
            f"Consider raising MAX_TOKENS above {MAX_TOKENS}.",
            file=sys.stderr,
        )

    if fragment.startswith("```"):
        fragment = fragment.split("\n", 1)[1] if "\n" in fragment else fragment
        fragment = fragment.rsplit("```", 1)[0].strip()

    return fragment


def render(fragment):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")
    with open(path, encoding="utf-8") as f:
        template = f.read()

    return (template
            .replace("<!--KICKER-->", "Daily Briefing")
            .replace("<!--TITLE-->", "Daily Brief")
            .replace("<!--CONTENT-->", fragment))


def send(html, today):
    subject = f"Daily Brief — {today.strftime('%A, %-d %B %Y')}"

    payload = {
        "from": os.environ["MAIL_FROM"],
        "to": [os.environ["MAIL_TO"]],
        "subject": subject,
        "html": html,
    }
    headers = {
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
        "content-type": "application/json",
    }
    return post_json(RESEND_URL, payload, headers, timeout=60).get("id", "unknown")


def main():
    dry_run = os.environ.get("DRY_RUN", "") == "1"

    required = ["ANTHROPIC_API_KEY"]
    if not dry_run:
        required += ["RESEND_API_KEY", "MAIL_TO", "MAIL_FROM"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        sys.exit(f"Missing required environment variables: {', '.join(missing)}")

    forced = os.environ.get("FORCE_DATE", "").strip()
    today = (
        datetime.date.fromisoformat(forced) if forced else datetime.date.today()
    )

    region, theme, cats = rotations(today)
    print(f"{today} — combined brief using {MODEL}")
    print(f"  region:     {region}")
    print(f"  Spanish:    {theme}")
    print(f"  knowledge:  {'; '.join(cats)}")

    fragment = generate(today)
    print(f"Received {len(fragment)} characters of HTML.")

    html = render(fragment)
    with open("brief-output.html", "w", encoding="utf-8") as f:
        f.write(html)

    if dry_run:
        print("DRY_RUN set — wrote brief-output.html, no email sent.")
        return

    print(f"Sent. Resend message id: {send(html, today)}")


if __name__ == "__main__":
    main()
