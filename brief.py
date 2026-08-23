#!/usr/bin/env python3
"""
Daily brief — one combined email with four sections, every day.

Sections:
  1. Geopolitics   — today's story, a historical echo, why it matters
  2. Spanish       — advanced phrases, Peninsular and Colombian
  3. General Knowledge — pub-quiz-grade facts with context
  4. The Long Game — a Psycho-Cybernetics-anchored idea and a practice

Replaces the earlier geo/Spanish alternation. Runs seven days a week, so the
rotations below are keyed on the date's ordinal rather than a weekday count.

Runs on the Gemini API's free tier (Google AI Studio). One brief a day is one
or two requests, comfortably inside the free daily quota, so the whole pipeline
— Actions, Resend, model — costs nothing.

Environment variables required:
  GEMINI_API_KEY      free key from aistudio.google.com/apikey
  RESEND_API_KEY      from resend.com
  MAIL_TO             recipient address
  MAIL_FROM           verified sender, e.g. brief@yourdomain.com
                      (or onboarding@resend.dev for testing)

Optional:
  GEMINI_MODEL        defaults to gemini-2.5-pro
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

GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
RESEND_URL = "https://api.resend.com/emails"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")

# Gemini 2.5 Pro is a thinking model and its reasoning tokens are charged
# against this same ceiling, so it needs to be far more generous than the
# equivalent figure was on Claude. Nothing is billed on the free tier; an
# unused ceiling costs only the risk of a longer wait.
#
# Original note, still true of the visible output: three sections in one
# response need real headroom. At 8000 the brief was
# silently losing its General Knowledge section: the geopolitics half ran long
# once bracketed glosses were added, the response hit the ceiling mid-sentence,
# and the tidy-up below trimmed back to the last complete </section>. Keep this
# generous — an unused ceiling costs nothing.
MAX_TOKENS = 32000

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

# Rotates the strand of Section 4. Anchored in Maxwell Maltz's
# Psycho-Cybernetics (1960), widened with adjacent capability topics so it
# doesn't become sixteen paraphrases of the same chapter.
LONG_GAME_STRANDS = [
    "Psycho-Cybernetics: the self-image as the governing mechanism — why "
    "performance tends to snap back to how you privately see yourself",
    "Skill acquisition: deliberate practice — working at the edge of your "
    "competence with immediate feedback, rather than repeating what you can "
    "already do comfortably",
    "Psycho-Cybernetics: the Theatre of the Mind — vivid mental rehearsal "
    "treated as genuine practice, and how Maltz says to run a session",
    "Composure: stress inoculation — rehearsing the conditions rather than "
    "the outcome, so that pressure feels familiar when it arrives",
    "Psycho-Cybernetics: the servo-mechanism — setting a clear target and "
    "letting the automatic guidance system correct course, instead of "
    "consciously steering every step",
    "Attention: protecting a deep block — treating uninterrupted focus as the "
    "genuinely scarce resource and defending it structurally",
    "Psycho-Cybernetics: synthetic experience — the nervous system's poor "
    "discrimination between a vividly imagined event and a real one, and what "
    "that licenses you to practise",
    "Physical discipline: consistency over intensity — the training principle "
    "that the session you will actually repeat beats the one that impresses",
    "Psycho-Cybernetics: rational thinking about the self — auditing a belief "
    "about yourself against evidence, rather than arguing with the feeling",
    "Preparation: systems over motivation — arranging the environment so the "
    "action you want is the default rather than a decision",
    "Psycho-Cybernetics: the relaxed mechanism — why excessive effort degrades "
    "performance, and Maltz's deliberate practice of doing nothing",
    "Skill acquisition: plateaus and consolidation — why progress is stepwise, "
    "and what is actually happening during the flat stretches",
    "Psycho-Cybernetics: the failure mechanism — reading frustration, "
    "aggressiveness, insecurity, loneliness, uncertainty, resentment and "
    "emptiness as signals to adjust course rather than verdicts on you",
    "Presence: bearing, pace and voice — how posture and tempo change both how "
    "you are read by others and how you feel from the inside",
    "Psycho-Cybernetics: emotional scar tissue — how a defence built for an "
    "old situation quietly constrains the current one",
    "Recovery: sleep and genuine downtime as inputs to performance rather than "
    "what is left over once the work is done",
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
    """Region, Spanish theme, three knowledge categories, Long Game strand."""
    n = d.toordinal()
    region = REGIONS[n % len(REGIONS)]
    theme = SPANISH_THEMES[n % len(SPANISH_THEMES)]
    cats = [
        KNOWLEDGE_CATEGORIES[(n * 3 + i) % len(KNOWLEDGE_CATEGORIES)]
        for i in range(3)
    ]
    strand = LONG_GAME_STRANDS[n % len(LONG_GAME_STRANDS)]
    return region, theme, cats, strand


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
    region, theme, cats, strand = rotations(today)
    date_str = today.strftime("%A, %-d %B %Y")
    cat_list = "; ".join(cats)

    return f"""Today is {date_str}. Produce a combined daily brief with four
sections: geopolitics, Spanish practice, general knowledge, and a short
self-development section called The Long Game.

Write in British English throughout. Measured, analytical, no hype, no
throat-clearing. Assume an intelligent reader who follows the news but is not
a specialist.

GLOSS THE UNFAMILIAR — APPLIES TO ALL THREE SECTIONS
The reader does not carry world geography or military vocabulary in his head,
and would rather be told than guess. The first time you name something he may
not place, gloss it in brackets in a few words and move on:
  - cities and regions, with the country: Baghdad (Iraq), Tehran (Iran),
    Kryvyi Rih (central Ukraine)
  - weapons and military jargon: Scud missiles (Soviet-designed ballistic
    missiles), MANPADS (shoulder-fired anti-aircraft launchers)
  - organisations and acronyms on first use: the RSF (Rapid Support Forces, a
    Sudanese paramilitary group)
  - treaties, doctrines, historical figures and institutions: the Althing
    (Iceland's parliament), the Porte (the Ottoman government)
Gloss generously rather than sparingly — if you find yourself wondering
whether he'd know it, he would rather you told him. Keep each gloss to a few
words inside brackets so the prose still flows. Do not add a glossary at the
end, and do not gloss the obvious (Paris, NATO, the Second World War).

WRITE IT YOURSELF — APPLIES TO ALL FOUR SECTIONS
Sources are for facts, not for phrasing. Read what you find, understand it,
close it, and write the sentence yourself. Do not assemble a paragraph out of
clauses lifted from three different articles and stitched together — that is
what produces prose that states the same fact twice in slightly different
words, switches register mid-sentence, or trails off into an unrelated clause.
Concretely:
  - Do not paste or lightly reword sentences from your sources.
  - Quote directly only when the exact words matter, such as a named official's
    statement. Keep it to one short sentence, in quotation marks, attributed to
    the person who said it.
  - Never cite a source inside the prose as the basis for a fact — no
    "according to Wikipedia's timeline", no "analytics firm Kpler said". Where
    the fact is contested or is somebody's claim rather than established, name
    the claimant; otherwise attribution belongs in the Sources list at the end.
  - Do not treat Wikipedia as a citable source at all. Use it to find the
    primary reporting, then read and cite that instead.
Before you finish, reread what you have written. If a fact appears twice, cut
one. If a sentence does not parse cleanly when read aloud, rewrite it.

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

WHY IT MATTERS — WRITE THIS PART DIFFERENTLY
This is the one part of the brief that should be genuinely simple. Drop the
analytical register entirely and explain it the way you would to a friend in
the pub who has not been following the story: short sentences, plain words, no
jargon, no hedging clauses, nothing that needs re-reading. If a sentence has a
subordinate clause, break it in two. Say what is actually going on and why
anyone should care. Two short paragraphs, around 40 words each, and no more.
The three things to watch should be one plain sentence each.

LENGTH — TREAT THESE AS CEILINGS, NOT TARGETS
About 200 words on today's story, 200 on the historical echo, and about 80
plain-English words on why it matters. Do not exceed 250 words on either of
the first two: going long here has repeatedly squeezed out the later sections
of the brief. Three tight paragraphs beat five loose ones, and the glosses
should stay inside the word count rather than expand it. Flowing paragraphs in
the first two parts, not bullet fragments.

BUDGET THE WHOLE BRIEF
All four sections must fit in one reply. Spanish, General Knowledge and The
Long Game matter just as much as the geopolitics, so do not spend your length
on the first section and rush the rest. If you are running long, cut the
geopolitics prose — never drop a Spanish phrase, a quiz fact, or the practice
at the end.

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
SECTION 4 — THE LONG GAME
============================================================

A short daily section on building capability over time. The reader is a
capable adult who wants to get better at things and is interested in
Psycho-Cybernetics (Maxwell Maltz, 1960) as a starting point, but does not
want to be sold to.

TODAY'S STRAND
{strand}

WHAT TO PRODUCE
Two parts, no more:
  - The Idea: about 110 words explaining today's strand in plain English. If
    it comes from Psycho-Cybernetics, say so and represent Maltz accurately —
    the self-image mechanism, the servo-mechanism, the Theatre of the Mind and
    so on are his actual concepts, so use them as he meant them. Do not invent
    quotations, and do not attribute modern neuroscience claims to a 1960
    book. Where a claim is contested or has aged badly, say so in a clause
    rather than laundering it.
  - The Practice: about 70 words giving one specific thing to do today.
    Concrete and bounded — a named exercise, a duration, a time of day, or a
    single question to sit with. Something that can actually be done between
    other commitments, not a lifestyle overhaul.

TONE AND LIMITS — READ THIS CAREFULLY
Write it like a sane coach, not a motivational account. Specifically:
  - No hustle or grind framing, no "most people won't do this", no implication
    that rest is weakness.
  - Maltz's own position is that self-criticism and self-punishment are the
    problem, not the cure. Keep to that. Nothing that encourages harsh
    self-talk, shame as motivation, or measuring worth by output.
  - No prescriptions about diet, calorie restriction, fasting, extreme
    training loads, or sleep deprivation. Physical strands stay at the level
    of general principle.
  - No superhero cosplay. The reader mentioned Batman as shorthand for
    building capability; do not run with the bit, and never mention Batman or
    Bruce Wayne.
  - It is a daily email. Assume today is an ordinary Tuesday, not a turning
    point.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY an HTML fragment — no markdown, no code fences, no preamble, no
<html> or <body> tags. Use exactly this structure and these class names:

<div class="dateline">
  <span>{date_str}</span>
  <span class="region">REGION LABEL</span>
</div>

<div class="divider first"><span>Geopolitics</span></div>

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
    <p>Plain-English paragraph: what is really going on here.</p>
    <p>Plain-English paragraph: why it should matter to anyone.</p>
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

<div class="divider"><span>The Long Game</span></div>

<section>
  <h2>Today's Idea</h2>
  <h3>A SHORT TITLE FOR THE IDEA<span class="era">SOURCE OR FIELD</span></h3>
  <p class="lead">First paragraph.</p>
  <p>Second paragraph if needed.</p>
</section>

<section>
  <h2>The Practice</h2>
  <div class="practice">
    <p>The specific thing to do today.</p>
  </div>
</section>

If research fails or sources are too thin for the geopolitics section, say so
honestly in the same format rather than padding it with speculation.

============================================================
BEFORE YOU SEND — CHECK THIS
============================================================

Your reply must contain all four divider divs, in this order:

  <div class="divider first"><span>Geopolitics</span></div>
  <div class="divider"><span>Spanish Practice</span></div>
  <div class="divider"><span>General Knowledge</span></div>
  <div class="divider"><span>The Long Game</span></div>

The single most common failure is stopping after General Knowledge. Do not end
your reply until The Long Game and its practice are written. If you are short
on room, shorten the geopolitics section — do not omit the last one."""


# --------------------------------------------------------------------------

def call_model(prompt, search=True):
    """One Gemini generateContent call. Returns the model's text output.

    Grounding with Google Search replaces Claude's web_search tool. Only the
    first pass needs it: the follow-up that fills in a missing section is
    writing from the same instructions, not researching again.
    """
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS,
            "temperature": 1,
        },
    }
    if search:
        payload["tools"] = [{"google_search": {}}]

    headers = {
        "x-goog-api-key": os.environ["GEMINI_API_KEY"],
        "content-type": "application/json",
    }

    url = f"{GEMINI_API_ROOT}/{MODEL}:generateContent"
    result = post_json(url, payload, headers)

    candidates = result.get("candidates") or []
    if not candidates:
        # Usually a safety block or a malformed request; the payload explains.
        raise RuntimeError(
            f"Gemini returned no candidates. Response: {json.dumps(result)[:2000]}"
        )

    candidate = candidates[0]

    # Thinking models return their reasoning as parts flagged thought=true.
    # Those are not the brief and must not be pasted into the email.
    text = "".join(
        part.get("text", "")
        for part in candidate.get("content", {}).get("parts", [])
        if not part.get("thought")
    ).strip()

    finish = candidate.get("finishReason")
    if finish and finish not in ("STOP", "MAX_TOKENS"):
        print(f"WARNING: unusual finishReason {finish}.", file=sys.stderr)
    if finish == "MAX_TOKENS":
        print(
            "WARNING: response hit the output ceiling and may be truncated. "
            f"Consider raising MAX_TOKENS above {MAX_TOKENS}.",
            file=sys.stderr,
        )

    if not text:
        raise RuntimeError(
            "Gemini returned no usable text (only reasoning, or an empty "
            f"candidate). finishReason={finish}."
        )

    return text


# The sections the email must contain, and the marker that proves each one is
# present. Geopolitics is not listed: if that is missing there is no brief at
# all and the run should be looked at by hand.
EXPECTED_SECTIONS = (
    ("Spanish Practice", "<span>Spanish Practice</span>"),
    ("General Knowledge", "<span>General Knowledge</span>"),
    ("The Long Game", "<span>The Long Game</span>"),
)


def missing_sections(fragment):
    return [name for name, marker in EXPECTED_SECTIONS if marker not in fragment]


def request_missing(today, missing):
    """Second pass asking only for the sections the first reply left out."""
    names = ", ".join(missing)
    prompt = f"""{build_prompt(today)}

============================================================
CORRECTION — READ THIS LAST, IT OVERRIDES THE OUTPUT FORMAT ABOVE
============================================================

You already wrote this brief and left out: {names}.

Write ONLY those section(s) now, to exactly the specification and HTML
structure given above, including the divider div that introduces each one. Do
not repeat any section you are not asked for here, do not re-write the
geopolitics section, and do not add any preamble, apology or closing remark.
Return only the HTML fragment for the missing section(s)."""

    extra = call_model(prompt, search=False)

    if extra.startswith("```"):
        extra = extra.split("\n", 1)[1] if "\n" in extra else extra
        extra = extra.rsplit("```", 1)[0].strip()

    # Same defensive trim as the main pass: drop anything before the first
    # divider and anything after the last closing section tag.
    start = extra.find('<div class="divider"')
    if start > 0:
        extra = extra[start:]
    end = extra.rfind("</section>")
    if end != -1:
        extra = extra[: end + len("</section>")]

    print(f"Second pass returned {len(extra)} characters.", file=sys.stderr)
    return extra


def generate(today):
    fragment = call_model(build_prompt(today), search=True)

    if fragment.startswith("```"):
        fragment = fragment.split("\n", 1)[1] if "\n" in fragment else fragment
        fragment = fragment.rsplit("```", 1)[0].strip()

    # With web search enabled the reply arrives as several text blocks, and the
    # ones between tool calls are the model talking to itself ("Now I'll verify
    # the Spanish phrases..."). Joining them all put that commentary at the top
    # of the email. Keep only the HTML fragment: everything from the opening
    # dateline div to the final closing section tag.
    start = fragment.find('<div class="dateline"')
    if start > 0:
        fragment = fragment[start:]
    end = fragment.rfind("</section>")
    if end != -1:
        fragment = fragment[: end + len("</section>")]

    # That trim is what makes an incomplete reply look deceptively tidy: it
    # cuts back to the last complete section, so a brief missing its final
    # third still arrives looking finished.
    #
    # In practice the model sometimes just stops after General Knowledge — this
    # is not a token-ceiling problem (a full brief is nowhere near MAX_TOKENS),
    # it simply ends its turn early. So rather than only reporting the gap, ask
    # once more for the sections that are missing and splice them in. The
    # notice below is the fallback for when even that fails.
    missing = missing_sections(fragment)
    if missing:
        print(
            f"Brief is missing section(s): {', '.join(missing)}. "
            "Requesting them in a second pass.",
            file=sys.stderr,
        )
        try:
            extra = request_missing(today, missing)
        except RuntimeError as e:
            print(f"Second pass failed: {e}", file=sys.stderr)
            extra = ""
        if extra:
            fragment = f"{fragment}\n{extra}"
        missing = missing_sections(fragment)

    if missing:
        print(
            f"WARNING: brief is still missing section(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        fragment += (
            '\n<section><h2>Incomplete Brief</h2><div class="takeaway"><p>'
            "This morning's brief is missing the following section(s): "
            f"{', '.join(missing)}. The model stopped before writing them and "
            "a second attempt did not recover them. Nothing has been silently "
            "dropped from the sections above.</p></div></section>"
        )

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

    required = ["GEMINI_API_KEY"]
    if not dry_run:
        required += ["RESEND_API_KEY", "MAIL_TO", "MAIL_FROM"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        sys.exit(f"Missing required environment variables: {', '.join(missing)}")

    forced = os.environ.get("FORCE_DATE", "").strip()
    today = (
        datetime.date.fromisoformat(forced) if forced else datetime.date.today()
    )

    region, theme, cats, strand = rotations(today)
    print(f"{today} — combined brief using {MODEL}")
    print(f"  region:     {region}")
    print(f"  Spanish:    {theme}")
    print(f"  knowledge:  {'; '.join(cats)}")
    print(f"  long game:  {strand}")

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
