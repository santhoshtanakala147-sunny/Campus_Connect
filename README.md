# CampusConnect

A private, inter-college social network for verified students, built to show
classical data structures doing real work behind a Flask + SQLite REST API and
a single-page HTML/CSS/JS frontend.

## Run it

```bash
pip install -r requirements.txt
python run.py                # http://127.0.0.1:5000
```

Sign-up requires an official college email (`.edu`, `.ac.in`, `.edu.in`, `.ac.uk`
or a listed institution domain — see `config.py`) **and** clicking the emailed
verification link. With no SMTP configured the link is printed in the server
console, so you can demo without a mail server. To skip verification while
developing: `CC_REQUIRE_VERIFICATION=0 python run.py`.

| Environment variable | Purpose |
|---|---|
| `SECRET_KEY` | Session signing key. If unset, a random key is generated once into `instance/secret_key`. |
| `CC_REQUIRE_VERIFICATION` | `1` (default) / `0` — require email verification. |
| `CC_SMTP_HOST/PORT/USER/PASSWORD`, `CC_MAIL_FROM` | Send real verification emails. |
| `CC_SECURE_COOKIES` | Set to `1` when serving over HTTPS. |
| `CC_DATABASE_PATH` | Use a different SQLite file. |
| `FLASK_DEBUG` | `1` enables the debugger/reloader (off by default). |
| `GEMINI_API_KEY` | Turns on Gemini safety checks and the AI pet (get a key in Google AI Studio). Server-side only. |
| `GEMINI_MODEL` | Model id, default `gemini-3.5-flash-lite` (fast and cheap; use any model that supports `generateContent`). |
| `CC_MODERATION` | `1` (default) / `0` — content safety checks on/off. |
| `CC_EDUCATION_ONLY` | `1` (default): everything students write must be about education; off-topic content is rejected. |
| `CC_REEL_VERIFY` | `1` (default): shared YouTube videos are checked via YouTube oEmbed (real title judged, private/removed videos refused). |
| `CC_MODERATION_FAIL_CLOSED` | `0` (default): if Gemini is down, fall back to local rules. `1`: reject posts until it's back. |
| `CC_CHAT_EDUCATION_ONLY` | `0` (default): chat between friends gets the safety checks but not the education-only gate. `1`: hold messages to the same rule as posts. |
| `CC_CHAT_MESSAGES_PER_MINUTE` | Per-student message rate limit (default 30). |
| `CC_PET_NAME`, `CC_PET_CHATS_PER_MINUTE` | Pet's name (default Mochi) and per-student chat rate limit (default 15). |

## Interface

A sidebar app shell with light and dark themes (toggle in the top bar, remembered per browser). The dashboard
centres on a live **friend-network graph**: the server runs a BFS from you out to 2 hops (`GET /api/network`), the
browser lays it out with a small force simulation, and clicking a classmate runs a second BFS to trace the shortest
path from you. Press **Ctrl K** (⌘ K on Mac) or **/** anywhere for the command palette; typing a name there uses the
Trie-backed student search.

## Messages (chat)

Open **Messages** in the sidebar, or press **Message** next to a friend on the Friends page.

- **Friends only.** You can message someone only while you are friends; removing a friend closes the conversation.
- **Live without websockets.** The open conversation asks the server for messages newer than the last one it has every
  3 seconds (`GET /api/chat/<id>?after=<last id>`), the conversation list refreshes every 8 s and the sidebar badge every
  20 s, and polling pauses while the tab is hidden. Plain Flask, nothing extra to run.
- **Unread badge, read receipts.** The sidebar and the bell show unread counts; the sender sees *Seen* once the other
  student opens the conversation.
- **Friendly starters.** An empty conversation offers one-tap *Hi*, *How are you?* and *Introduce myself* (prefilled with your name and college, editable before sending). Small talk is never blocked.
- **Safe by default.** Messages go through the same safety checks as posts (scam/phishing links, passwords and OTPs,
  card numbers, harassment, spam; Gemini too when a key is set). The education-only gate is off for chat, see
  `CC_CHAT_EDUCATION_ONLY`. Max 1000 characters, rate-limited, always rendered as plain text.
- **Data structures.** Each conversation is an array keyed by the pair of student ids (O(1) append, in order), unread
  counts live in a hash map, and SQLite (`messages` table) is the source of truth, rebuilt at startup like the rest.

API: `GET /api/chat/conversations`, `GET /api/chat/unread`, `GET /api/chat/<id>[?after=n]`, `POST /api/chat/<id>`.

## Sample data for demos

Sample content is added **automatically the first time the app starts** (20 classmates from 12 institutions (Amrita Vishwa Vidyapeetham, SRM, VIT, IIT Madras, IIT Bombay, BITS Pilani, NIT Tiruchirappalli, IIIT Hyderabad, IISc Bangalore, PSG, Anna University, University of Delhi), friendships, 8 groups, 33 posts
with comments and lecture videos, events, announcements, shared links, reel comments). Each student you sign up or log in
with is introduced once to five of the sample classmates, who know the others, so the friend graph, "People you may
know", the feed, groups and events are never empty. Sample students use a first.last address on their own college's domain (for example `aarav.menon@amrita.edu`); they
are fictional and cannot log in. Because those look like real addresses, nobody can register with the same address while
the sample data is present.

```bash
CC_DEMO_DATA=0 python run.py       # start without any sample content
python seed_demo.py --reset        # remove the sample content (it is not re-added on the next start)
python seed_demo.py                # add it manually to an existing database (server stopped)
```

## Features → data structures

| Feature | Structure (`datastructures/`) | How it is used | Cost |
|---|---|---|---|
| Login, duplicate-email check | **Hash table** (separate chaining, doubles at 0.75 load) | email → user, no SQL on login | O(1) avg |
| Friends, mutual friends | **Graph** (adjacency sets) | user ↔ user edges | mutual: O(min(deg)) |
| "Degrees away", **People you may know** | Graph + **BFS** | shortest path / level-order BFS to 3 hops, ranked by mutual friends | O(V+E) |
| Student search with autocomplete | **Trie** | name, college and email-handle words → user ids; multi-word queries intersect | O(len(prefix)) |
| Group / topic search | **Trie** | group name + topic words → group ids | O(len(prefix)) |
| Chronological feed | **AVL tree** | key `(timestamp, post_id)`; lazy reverse in-order iterator; O(log n) insert **and delete** | O(log n) |
| Trending feed | **Max heap** | score `(likes + 2·comments, recency)`; build in O(n), top-k pops | O(n + k log n) |
| Comments | **Arrays** (Python lists) | per-post list in posting order | O(1) append |

SQLite is the source of truth. The structures are loaded at startup and updated
alongside every write, so reads never touch SQL for these paths.
`tests/test_api.py::test_state_survives_restart` proves they rebuild correctly.

Other features: profiles, friend requests, academic discussion groups (members-only
posts), events (per college or all colleges), shared resource links, college
announcements, notifications (friend requests, events this week, announcements),
and Tic-Tac-Toe (minimax CPU) + sliding puzzle.

## AI features (Gemini)

Set the key and start the server (PowerShell: `$env:GEMINI_API_KEY="..."`; bash: `export GEMINI_API_KEY=...`).
Everything below still works without a key, using local rules and an offline pet.

**Safety checks** (`ai/moderation.py`) run on posts, comments, group names/topics, events, announcements,
shared links and profile bios:

1. *Local rules, always on:* javascript:/data: links, raw-IP, punycode look-alike and `user@host` links, URL
   shorteners, passwords/PINs/OTPs, payment-card (Luhn) and Aadhaar-style numbers, character floods, link spam,
   duplicate posts within a minute.
2. *Gemini classifier:* harassment, hate, threats, sexual content, scams/phishing, malware, spam, doxxing. The
   author sees a short, kind reason. Possible self-harm is **never blocked**; the post goes through with a
   supportive note (Tele-MANAS 14416 for India).
3. Verdicts are cached, every check is logged to `moderation_log` (blocked text kept only as a 120-char excerpt),
   and 3 blocks in 10 minutes triggers a cooldown.

User text reaches the model only as quoted, labelled data with a fixed JSON verdict schema, and local rules are
not overridable by the model. Prompt injection can't be ruled out for any LLM classifier, so treat this as a
strong filter, not a guarantee.

**The pet** (`ai/pet.py`, widget in `frontend/index.html`): a small cat in the corner that pops up page-specific
tips, answers questions about the site, and offers "Take me to …" buttons. Gemini sees only the student's first
name, the current page and the last few chat turns — no emails and no other users' data. Replies are rendered as
plain text. Without a key (or if Gemini errors) a rule-based guide answers instead. Students can turn tips off
from the panel header.

**Privacy:** with a key set, text being posted and pet chat messages are sent to Google's Gemini API. Mention this
in your privacy notice, and check Google's data-use terms for your API tier.

## Education-only enforcement

CampusConnect accepts only educational content (coursework, exams, notes, research, projects, skills, placements,
academic clubs/events/notices). It is enforced on posts, comments, group names/topics, events, announcements, shared
resources, shared videos, profile bio/interests and the pet chatbot:

1. **Offline word-list gate** (`ai/education.py`, no network): text is labelled `edu`, `off`, `mixed` or `unclear`.
   `off` is rejected immediately; `edu` passes.
2. **Gemini judge** for `mixed`/`unclear` text (when a key is set), told to block everything non-educational with the
   category `off_topic`. Without a key, or if Gemini is down, unclear text is rejected (strict).
3. **Comments** get the parent post as context, so short replies like "thanks, this helped!" are allowed.
4. **Videos**: the real YouTube title (oEmbed) is judged, so an off-topic video can't hide behind an educational title.
5. **Wellbeing exception**: posts that signal distress are not rejected; the author gets the Tele-MANAS 14416 notice.
6. Off-topic rejections don't count towards the repeat-offender cooldown. The gate works even if `CC_MODERATION=0`.

Limit: the offline word list is a first filter, not a reader of meaning; set `GEMINI_API_KEY` for the strongest check.
The "Games" are framed as algorithm demos (minimax tic-tac-toe, BFS sliding puzzle).

## Posters, reel comments and saved posts

- **Add image** (feed, group posts and event creation): the browser shrinks the picture (max 1280 px, JPEG) and sends it
  as base64 inside the normal JSON request. The server checks the file's real header bytes (PNG, JPEG, GIF or WebP only,
  never SVG), caps it at 2 MB, stores it in `instance/uploads/` under a random name, and serves it back only to logged-in
  students with a fixed image type, `nosniff` and a sandbox CSP. Deleting the post deletes the file.
  A post with an image must have a caption, and the caption goes through the same safety and education-only checks.
  With `GEMINI_API_KEY` set, Gemini also looks at the picture itself and rejects anything not educational (memes, selfies,
  ads, other people's IDs); if Gemini is down the upload is refused with "try again". Without a key only the caption is
  checked, so set a key for the strongest protection.
- **Add video** (feed and group posts): paste a YouTube link. Only the 11-character id is stored and the player is rebuilt
  server-side (click-to-play through `youtube-nocookie.com`). The caption and the video's real YouTube title both go through
  the education-only gate, so an off-topic video is rejected. A post carries an image or a video, not both.
- **Reel comments**: every reel (animations, open lectures, community videos) has a Comments button. Comments use the
  same checks as posts, the reel title gives context so short replies like "thanks, this helped!" pass, and you can delete
  your own. Table: `reel_comments`.
- **Save**: bookmark any post privately; see them under Feed > Saved. Table: `post_saves`, cached like post likes.

## Reels (learning videos + reference library)

Open **Reels** in the nav. Tabs: **All · Pre-built · Open lectures · Community · Reference**, with topic filter,
sort (curated / most liked / newest), likes, and a *Share a video* form.

| Kind | What it is | Licence / source |
|---|---|---|
| **Pre-built** (6) | Animated explainers drawn in the browser: hash table, BFS "People you may know", trie, AVL rotations, max heap, safety pipeline. Each shows the project file where the idea lives, so they double as viva revision. | Original, made for CampusConnect |
| **Open lectures** (6) | MIT OpenCourseWare 6.006 lectures on AVL trees, heaps, hashing, BSTs and BFS, plus Gilbert Strang's linear algebra Lecture 1. Embedded from the course's YouTube uploads. | CC BY-NC-SA 4.0 (verified on each OCW page) |
| **Community** | A YouTube link a student shares. Only the 11-character video id is stored, the embed URL is rebuilt server-side, title and description go through the safety checks, max 5 per day, duplicates rejected. | Whatever the video's owner chose; the card says so |
| **Reference** | Open textbooks (Open Data Structures, Erickson's *Algorithms*), free courses, docs used here (Flask, SQLite, Gemini) and the three related papers from the project deck, each with its licence. | See each entry |

Notes:
- Videos are **embedded, not copied or re-hosted**. They play click-to-play through `youtube-nocookie.com`, and every card links back to its source.
- CC BY-NC-SA means **non-commercial** use with attribution. That suits a college project; check the licences again if CampusConnect ever becomes a paid product.
- Embeds and thumbnails contact Google/YouTube when shown or played. Mention it in your privacy notice.
- To add more curated reels, append an entry to `content/reels_seed.py`. Copy the video id and licence from the video's own page. Entries are upserted on every start, so likes are kept.
- Animations live in `frontend/reels.js` as data (one frame = one picture, nodes tween between frames), so adding a scene needs no new drawing code.

## Layout

```
app.py              Flask app factory + all routes (JSON API under /api)
content/            Curated reels and the reference library (reels_seed.py)
ai/                 gemini.py (REST client), moderation.py (safety checks), pet.py (chatbot)
config.py           Settings and the allowed college-email domains
schema.sql          SQLite schema (auto-applied; older DBs are migrated)
datastructures/     HashTable, Graph, Trie, AVLTree, MaxHeap (no third-party code)
frontend/index.html The UI (single page, served at /); reels.js + reels.css hold the Reels page
tests/              pytest: data structures + API (test_chat.py covers messaging)
archive/legacy/     Earlier blueprint/multi-page versions, kept for reference only
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Security notes

Passwords are hashed (Werkzeug); login and resend are rate-limited; verification
tokens are stored hashed, single-use, 24 h; state-changing API calls must be
`application/json` and cookies are `SameSite=Lax` + `HttpOnly` (CSRF); all user
text is HTML-escaped in the UI.

## Known limits

- In-memory structures live in one process. Run a single worker (or move the
  structures behind Redis/a shared store) before scaling out.
- Rate-limit counters are in memory and reset on restart.
- No password reset yet. Chat is text-only 1:1 (no group chat, attachments, or message deletion) and uses polling, so a new message can take up to 3 s to appear.
- The sample classmates are fictional and never reply, so demo chat with a second real account.
- Moderation adds one Gemini round trip (usually under a second; 8 s timeout) to each submission.
- The Gemini integration is covered by mocked tests; try it once with your own key before demoing.


## Before publishing to GitHub

- Keep `.env`, `instance/`, local databases, generated secret keys, and real user data out of Git.
- Copy `.env.example` to `.env` only if you choose to use environment-file tooling; never put real credentials in the example file.
- Install development dependencies with `python -m pip install -r requirements-dev.txt`.
- Run the test suite with `python -m pytest -q` before publishing.
- Start locally with `python run.py` and manually verify registration, login, feed, friends, chat, groups, events, and games.
- For public deployment, configure a strong `SECRET_KEY`, HTTPS/secure cookies, and real email settings. Do not use Flask debug mode in production.

## Development checks

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python run.py
```
"# Campus_Connect" 
