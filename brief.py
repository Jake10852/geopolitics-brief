#!/usr/bin/env python3
"""
Daily brief — alternates between a geopolitics edition and a Spanish edition.

Alternation is by weekday count since a fixed epoch, so consecutive working
days always differ: Mon geo, Tue Spanish, Wed geo, Thu Spanish, Fri geo, then
the following Monday starts on Spanish. Weekends are skipped and do not break
the alternation.

Environment variables required:
    ANTHROPIC_API_KEY   from console.anthropic.com
    RESEND_API_KEY      from resend.com
    MAIL_TO             recipient address
    MAIL_FROM           verified sender, e.g. brief@yourdomain.com
                        (or onboarding@resend.dev for testing)

Optional:
    CLAUDE_MODEL        defaults to claude-sonnet-5
    FORCE_MODE          "geo" or "spanish", overrides the alternation.
                        Useful for testing both editions on the same day.
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

# Anchor for the alternation. A Monday. Changing this flips which edition
# lands on which day, which is the easiest way to adjust if the rhythm feels
# wrong once it's running.
EPOCH = datetime.date(2026, 8, 3)

# Rotates the regional focus of the geopolitics edition.
REGION_HINT = {
    0: "Europe, Russia, or the post-Soviet space",
    1: "the Middle East, the Gulf, or North Africa",
    2: "East Asia, the South China Sea, or the Pacific",
    3: "the Americas, sub-Saharan Africa, or South Asia",
    4: "global systems: trade, sanctions, energy, multilateral institutions",
}

# Rotates the situation the Spanish phrases are drawn from, so the editions
# don't converge on greetings and small talk forever.
SPANISH_THEMES = [
    "reacting to what someone just said — surprise, agreement, scepticism, sympathy",
    "softening and hedging — disagreeing politely, declining, being tactfully vague",
    "bars, restaurants and ordering — including how to get the bill and split it",
    "frustration and complaint — mild irritation through to genuine annoyance, kept printable",
    "making and changing plans — suggesting, postponing, cancelling without offence",
    "small talk with people you half-know — neighbours, colleagues, the same barista",
    "filler and hesitation — the noises native speakers make while thinking",
    "enthusiasm and praise — liking something without reaching for 'muy bueno' every time",
    "getting things done — shops, admin, asking for help, explaining a problem",
    "storytelling — narrating something that happened to you, keeping someone's attention",
    "affection and friendliness — warmth with friends without sounding sentimental",
    "winding down a conversation — leaving politely, promising to be in touch",
]


def weekday_index(d):
    """Number of weekdays between EPOCH and d. Negative before EPOCH."""
    step = 1 if d >= EPOCH else -1
    lo, hi = (EPOCH, d) if d >= EPOCH else (d, EPOCH)
    days = (hi - lo).days
    count = 0
    for i in range(days):
        if (lo + datetime.timedelta(days=i)).weekday() < 5:
            count += 1
    return count * step


def mode_for(d):
    forced = os.environ.get("FORCE_MODE", "").strip().lower()
    if forced in ("geo", "spanish"):
        return forced
    return "geo" if weekday_index(d) % 2 == 0 else "spanish"


def post_json(url, payload, headers, timeout=600):
    data = json.dumps(payload).encode("utf-8")
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
# Geopolitics edition
# --------------------------------------------------------------------------

def geo_prompt(today):
    region = REGION_HINT.get(today.weekday(), "anywhere in the world")
    date_str = today.strftime("%A, %-d %B %Y")

    return f"""Today is {date_str}. Produce a daily geopolitics brief.

STEP 1 - RESEARCH
Use web search to find the single most consequential geopolitical development
of the last 24 hours. Today's suggested regional focus is {region}, but ignore
that steer if a genuinely bigger story is breaking elsewhere. Prefer stories
with real strategic weight - territorial disputes, alliance shifts, sanctions
and trade coercion, military escalation, chokepoints, elections with external
consequences - over domestic political noise. Gather at least three credible
sources and confirm key facts appear in more than one outlet before asserting
them. Keep the exact URLs.

STEP 2 - HISTORICAL ECHO
Identify one genuine historical parallel: a past episode whose mechanics, not
merely its mood, resemble today's story. Give specific dates, names and
outcomes. State plainly where the analogy breaks down as well as where it
holds. Avoid lazy parallels; not every crisis is Munich 1938 or Sarajevo 1914.

STEP 3 - WRITE
Measured, analytical prose for an intelligent reader who follows world affairs
but is not a specialist. British spelling. Flowing paragraphs, not bullet
fragments. No hype, no throat-clearing. State uncertainty where it exists.

OUTPUT FORMAT
Return ONLY an HTML fragment - no markdown, no code fences, no preamble, no
<html> or <body> tags. Use exactly this structure and these class names:

<div class="dateline">
  <span>{date_str}</span>
  <span class="region">REGION LABEL</span>
</div>

<section>
  <h2>Today's Story</h2>
  <h3>HEADLINE</h3>
  <p class="lead">First paragraph.</p>
  <p>Three more paragraphs, each in its own p tag.</p>
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

If research fails or sources are too thin, say so honestly in the same format
rather than padding it with speculation."""


# --------------------------------------------------------------------------
# Spanish edition
# --------------------------------------------------------------------------

def spanish_prompt(today):
    theme = SPANISH_THEMES[weekday_index(today) // 2 % len(SPANISH_THEMES)]
    date_str = today.strftime("%A, %-d %B %Y")

    return f"""Today is {date_str}. Produce a short Spanish phrases edition.

THE LEARNER
Intermediate. He can hold a conversation and his grammar is broadly sound, but
he sounds like a textbook. The goal is not more vocabulary - it is the
connective tissue that makes someone sound like they actually live there: the
fillers, softeners, reactions and set phrases that native speakers use without
thinking and that courses rarely teach.

He wants BOTH peninsular Spanish (Spain) and neutral Latin American Spanish.
So for every phrase, be explicit about where it is used. This matters more
than anything else in this brief: a phrase that is warm in Madrid can be
baffling or crude in Bogotá. Flag those cases clearly. Where a phrase is
genuinely pan-Hispanic, say so - that is useful information too.

TODAY'S THEME
{theme}

WHAT TO PRODUCE
Six to eight phrases on that theme. For each one give:
  - the phrase in Spanish
  - a literal word-for-word gloss, where the literal meaning is odd or funny
  - what it actually means and the moment you would reach for it
  - register: with friends, neutral, or careful-with-strangers
  - where it is used: Spain, Latin America, or both - and any place it would
    land badly

Then one short exchange, four to six lines, showing two or three of the day's
phrases in a plausible conversation, with a translation underneath.

RULES
Nothing a learner would already have from a textbook - no "¿qué tal?", no
"me gusta", no "buenos días". Keep it clean; mild irritation is fine, insults
are not. Do not invent phrases or stretch a rare regionalism into a common
one - if you are unsure a phrase is genuinely current, leave it out. Prefer
eight solid entries over ten padded ones. Add a pronunciation note only where
the pronunciation is not obvious from the spelling.

OUTPUT FORMAT
Return ONLY an HTML fragment - no markdown, no code fences, no preamble, no
<html> or <body> tags. Use exactly this structure and these class names:

<div class="dateline">
  <span>{date_str}</span>
  <span class="region">SHORT THEME LABEL</span>
</div>

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
    <p class="use">What it means and when to use it.</p>
    <p class="tags"><span class="tag">Register</span><span class="tag region-tag">Spain / Latin America / Both</span></p>
  </div>

  (repeat the phrase div for each entry)
</section>

<section>
  <h2>In Conversation</h2>
  <div class="echo">
    <p class="dialogue"><strong>—</strong> Line of Spanish dialogue.<br>
    <strong>—</strong> Reply.</p>
    <p class="translation">English translation of the exchange.</p>
  </div>
</section>

<section>
  <h2>Worth Knowing</h2>
  <div class="takeaway">
    <p>One short paragraph on a divergence between Spain and Latin America
    that came up today, or a usage trap worth avoiding.</p>
  </div>
</section>"""


# --------------------------------------------------------------------------

def generate(today, mode):
    prompt = geo_prompt(today) if mode == "geo" else spanish_prompt(today)

    payload = {
        "model": MODEL,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Only the geopolitics edition needs live research. The Spanish edition
    # doesn't, and web search would just add latency and cost.
    if mode == "geo":
        payload["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}]

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
        raise RuntimeError(f"Model returned no text. Response: {json.dumps(result)[:2000]}")

    if fragment.startswith("```"):
        fragment = fragment.split("\n", 1)[1] if "\n" in fragment else fragment
        fragment = fragment.rsplit("```", 1)[0].strip()

    return fragment


def render(fragment, mode):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")
    with open(path, encoding="utf-8") as f:
        template = f.read()

    kicker = "Daily Briefing" if mode == "geo" else "Everyday Spanish"
    title = "Geopolitics Brief" if mode == "geo" else "Suena Nativo"

    return (template
            .replace("<!--KICKER-->", kicker)
            .replace("<!--TITLE-->", title)
            .replace("<!--CONTENT-->", fragment))


def send(html, today, mode):
    if mode == "geo":
        subject = f"Geopolitics Brief — {today.strftime('%A, %-d %B %Y')}"
    else:
        subject = f"Everyday Spanish — {today.strftime('%A, %-d %B %Y')}"

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
    missing = [
        v for v in ("ANTHROPIC_API_KEY", "RESEND_API_KEY", "MAIL_TO", "MAIL_FROM")
        if not os.environ.get(v)
    ]
    if missing:
        sys.exit(f"Missing required environment variables: {', '.join(missing)}")

    today = datetime.date.today()
    mode = mode_for(today)

    print(f"{today} — running {mode} edition using {MODEL}")
    fragment = generate(today, mode)
    print(f"Received {len(fragment)} characters of HTML.")

    html = render(fragment, mode)
    with open("brief-output.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Sent. Resend message id: {send(html, today, mode)}")


if __name__ == "__main__":
    main()
