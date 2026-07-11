# Backlog Cockpit

**Turn the trail your Claude Code agent leaves behind into a live, prioritized task board.**

🔎 **Live demo (synthetic data):** https://backlog-cockpit-demo.pages.dev

Reference plumbing for Claude Code (and any Markdown-native workflow). As your agent works it
scatters unfinished threads across memory files and project notes — `NEXT:`, `TODO`, `Deferred`,
`Parked`, `Not sent`, `Awaiting`, gate/blocker lines. This harvests those lines, **names and ranks
them** (stalest-first, by kind), drops them into one self-contained dashboard, and links each one
back to a fresh Claude session to actually work it. You never hand-maintain a task list — the
agent's own working notes *are* the list.

Fork it, point the config at your `~/.claude` memory and your note folders, run it (or wire it
into a session hook), and open the dashboard. That's the whole loop.

> It's a line-based heuristic harvest — it catches marker lines, not multiline task trees; treat
> it as a fast triage surface, not a complete task system.

## What it does

- Scans the note folders you point it at (Obsidian vault, a `memory/` dir, plain notes — anything Markdown).
- Pulls open threads using a tuned marker vocabulary (tuned to skip noun false-positives like "signature *block*").
- Classifies each by kind, routes it to a goal bucket you define, dates it from frontmatter (`last_worked:`) or file mtime.
- Emits **one self-contained `.html`** — no server, no build step, no dependencies. Open it in any browser.

## Two builds, one run

| Build | Contains | Use |
|-------|----------|-----|
| **local** (`cockpit.local.html`) | full detail + exact note paths + click-to-Claude | keep on your machine |
| **public** (`public/index.html`) | **redacted** — numbers, paths, emails, urls, and your own term list stripped | safe to host |

The redacted build is what you deploy. If it's ever exposed, an attacker gets a vague to-do list,
not your data. See *Hosting* below.

## Quickstart

```bash
cp config.example.json config.local.json     # edit: point "sources.dir" at your notes
python harvest.py                             # writes both builds
open cockpit.local.html                       # (or double-click it)
```

No pip installs — standard library only. Python 3.8+.

## Use it with Claude Code (the plumbing)

The loop is: **your agent writes notes → the harvester names + ranks them → you click back into a
fresh session to work one.** Nothing to hand-maintain.

1. **Marker conventions.** Have your agent end work-in-progress notes with a marker it already uses
   naturally: `NEXT:`, `TODO:`, `Deferred`, `Parked`, `NOT SENT`, `Awaiting …`, `GATE:` / `Blocked`,
   `Open decision:`. Each becomes a typed, ranked item. (One line per thread; the line *is* the task
   name.) Put a `last_worked: YYYY-MM-DD` in a note's frontmatter and it drives the staleness sort.

2. **Point the config at what your agent writes.** In `config.local.json`, aim `sources` at your
   Claude Code memory and your notes, e.g.:
   ```json
   "sources": [
     { "label": "memory", "dir": "~/.claude/projects/<your-project>/memory", "glob": "*.md",
       "include_prefix": ["project_", "event_"] },
     { "label": "notes",  "dir": "~/notes", "glob": "*.md", "exclude_prefix": ["_"] }
   ]
   ```

3. **Run it** — manually, on a schedule, or wired into a session hook (a `SessionStart` hook or a
   slash command that shells out to `python harvest.py`) so every session opens with a fresh board.

4. **Click any item's ↗** to open a new Claude session pre-prompted to load that note and work the
   thread — closing the loop back into the agent that created it.

The dashboard is a single self-contained HTML file (no server, no deps), so it drops into any
setup. See `docs/RETHINK.md` for the React frontend + hosting architecture.

## Configure

Everything specific to you lives in `config.local.json` (gitignored):

- **`sources`** — folders + globs to scan, with `include_prefix` / `exclude_prefix` filters.
- **`goals`** — buckets. Each `match` is a case-insensitive regex tested against `"<project> <filename>"`; first match wins. Keep a `".*"` catch-all last.
- **`markers`** *(optional)* — override the default kind→regex map from `harvest.py`.
- **`redact.terms_file`** — a plain text file (one term per line) of names to strip from the public build. Put your client/company names here. Gitignored.

## Hosting (safe by design)

The engine holds no personal data and the repo never contains your notes (`.gitignore` keeps
config + generated HTML out). To view your backlog anywhere:

1. Deploy **only** the public build to a static host (never the local build).
2. Put it behind an identity gate — e.g. **Cloudflare Access (Zero Trust)** with SSO + MFA, so
   it's unreachable without proving it's you. No password lives on the app; every entry is logged.
   **This identity gate is the real security boundary** — treat everything below as defense-in-depth.

### Read this before hosting real data

**Denylist redaction is not a guarantee.** The `denylist` mode masks known patterns (IDs, paths,
emails) plus a term list you maintain. In testing it repeatedly leaked things the list didn't yet
know about — an org name, a permit-number format, a path fragment — because you cannot enumerate
every sensitive token in free-text notes. Use it as blast-radius reduction, not as a safety
guarantee.

**For provable safety, use `structural` mode** (`"redact": {"mode": "structural"}`). It drops all
harvested prose from the hosted build and publishes only structure — goal, kind, age, counts — so
there is no free text to leak. You lose per-item detail on the hosted view (you still drill into
the real item by clicking through to Claude). Recommended for any build that leaves your machine
without an identity gate in front of it.

Rule of thumb: **denylist behind Access**, or **structural anywhere**.

## Click → Claude (know what this sends)

Each item links to a new Claude session pre-prompted to open the underlying note (via your vault
MCP) and work the item. On a machine running Claude Code with vault access it pulls the real file;
from the hosted build it prompts Claude to find the note by description.

Be aware this is a deliberate outbound channel: clicking sends the (redacted, in the public build)
task text to claude.ai as a URL query string, which can land in browser history and proxy logs.
The link carries only the note's **basename**, never its full local path. If that trade isn't
acceptable for a given deployment, use `structural` mode (its links carry no task text at all).

## License

MIT © 2026 Tyler Gorman
