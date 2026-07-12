#!/usr/bin/env python3
"""
backlog-cockpit — surface every open thread buried in your Markdown / Obsidian notes,
grouped by goal and sorted stalest-first, in one self-contained HTML dashboard.

Two builds from one run:
  * LOCAL  — full detail + exact note paths + click-to-Claude. Stays on your machine.
  * PUBLIC — redacted (numbers, paths, emails, your own term list stripped). Safe to host.

Usage:
  python harvest.py                 # uses config.local.json if present, else config.example.json
  python harvest.py --config X.json
  python harvest.py --public-only   # only emit the redacted build

The engine holds NO personal data. Everything specific to you lives in your config
(paths, goals) and an optional redaction term list — both kept out of version control.
MIT licensed.
"""
import os, re, sys, json, glob, argparse, datetime, urllib.parse
from fnmatch import fnmatch

VERSION = "1.0.0"
# dirs never descended into during recursive source scans / self-heal search
SKIP_DIRS = {"node_modules", ".git", ".obsidian", "__pycache__", "_archive", "90-Archive",
             ".venv", "venv", "dist", "build", ".idea", ".vscode"}

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today()

# ------------------------------------------------------------------ defaults
DEFAULTS = {
    "sources": [
        # {"label":"notes","dir":"~/notes","glob":"*.md","include_prefix":[],"exclude_prefix":["_"]}
    ],
    # kind -> regex (first match wins). Tuned to avoid noun false-positives (e.g. "signature block").
    "markers": {
        "not_sent": r"(?i:\bnot sent\b|\bunsent\b|\bpending send\b)",
        "gate":     r"\bGATE\b|(?i:\bgated\b|\bgate\s*[:=]|\bblocked\b|\bblocker\b|\bblocking\b)",
        "decision": r"(?i:\bopen decision\b|\bopen question\b|\bto decide\b|\bdecision\s*[:=]|\bdecide\s*[:=])",
        "deferred": r"(?i:\bdeferred\b)",
        "parked":   r"(?i:\bparked\b|\bon hold\b)",
        "awaiting": r"(?i:\bawaiting\b|\bwaiting on\b)",
        "next":     r"(?i:\bnext\s*[:\-–]|\bnext (?:action|step|up|move|ideas?|phase)\b)",
        "todo":     r"(?i:\bTODO\b|\bto[- ]?do\s*[:\-]|\bopen follow|\bfollow-?ups?\s*[:\-]|\bopen\s*[:=])",
    },
    "kind_order": ["not_sent", "gate", "decision", "deferred", "parked", "awaiting", "next", "todo"],
    "kind_labels": {"not_sent": "Not sent", "gate": "Gate", "decision": "Decide", "deferred": "Deferred",
                    "parked": "Parked", "awaiting": "Awaiting", "next": "Next", "todo": "To do"},
    # goal buckets: first match on "<project> <file>" wins. Last entry is the catch-all.
    "goals": [
        {"id": "work",     "name": "Work",             "icon": "\U0001F4BC", "color": "#a2641b", "match": r"work|client|project|bid|proposal"},
        {"id": "product",  "name": "Build & ship",     "icon": "⛏️", "color": "#4d7488", "match": r"app|build|ship|code|product|feature|design"},
        {"id": "ops",      "name": "Run the business", "icon": "⚙️", "color": "#3f7d4e", "match": r"invoice|payroll|ops|admin|billing|hiring|compliance"},
        {"id": "personal", "name": "Personal",         "icon": "\U0001F331", "color": "#b8801f", "match": r"personal|home|health|money|family"},
        {"id": "other",    "name": "Everything else",  "icon": "\U0001F4CC", "color": "#8b948b", "match": r".*"},
    ],
    # what to strip in the PUBLIC build (applied to task text + project + file label)
    "redact": {
        "patterns": [
            r"\b\d{2,6}(?:-[A-Za-z0-9]{1,6}){1,3}\b",         # multi-segment ids (e.g. 1234-56-789, 450000-1, 12-345678-X)
            r"[A-Za-z]:\\[^\s]*",                              # windows drive paths (C:\...)
            r"\b[A-Za-z]:(?![\w])",                            # bare drive refs (J:, M:)
            r"[\w .\-]+\\[\w .\-\\]+",                         # relative windows paths (Agent Suite\projects\..)
            r"[\w.\-]+(?:/[\w.\- ]+){1,}",                     # forward-slash relative paths (Agent Suite/projects/..)
            r"/[^\s]*/[^\s]+",                                 # unix-ish absolute paths
            r"\b[\w\-. ]+\.(?:md|xlsx?|xlsm|docx?|pdf|py|js|json|html|csv|kmz|gpx)\b",  # filenames (leak project identity)
            r"\b[\w.+-]+@[\w.-]+\.\w+\b",                      # emails
            r"https?://\S+",                                  # urls
        ],
        "mode": "structural",   # DEFAULT: provably safe (no prose in the public build). Set "denylist" (masks patterns+terms — NOT a guarantee) only behind an identity gate.
        "terms_file": "redact_terms.local.txt",  # one term per line; kept out of git
        "mask": "█",                          # replacement glyph
    },
    "claude": {
        "url": "https://claude.ai/new?q=",
        "prompt_local": "Open item from my notes — file \"{file}\", area \"{project}\":\n\n\"{text}\"\n\nIf you can open that note for context (e.g. a vault or Drive connector), do; otherwise ask me for what you need. Then give me the concrete next step.",
        "prompt_public": "Open item from my backlog (area \"{project}\"):\n\n\"{text}\"\n\nAsk me for the underlying note if you need more context, then give me the concrete next step.",
    },
    "output": {
        "local":  "./cockpit.local.html",
        "public": "./public/index.html",
    },
    # optional LLM naming/ranking pass (see llm.py). OFF by default; core tool never needs it.
    "llm": {
        "enabled": False,
        "model": None,               # None = the claude CLI / API default
        "max_items": 60,             # enrich only the top-N by priority (where naming matters most)
        "exclude": [],               # regexes; matching items are NEVER sent to the model
    },
    # when a source dir is missing, search its nearest existing ancestor for a folder of the same
    # name (a moved/renamed folder) and auto-repair — writes the fix back to your config file.
    "self_heal": True,
    "title": "Backlog Cockpit",
}

def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out

def load_config(path):
    cfg = DEFAULTS
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = deep_merge(DEFAULTS, json.load(f))
    if not cfg.get("goals"):
        raise SystemExit("config error: 'goals' must be a non-empty list (keep a '.*' catch-all last).")
    if not cfg.get("sources"):
        print("WARNING: no 'sources' configured — nothing to harvest. Point config.sources[].dir at your notes.", file=sys.stderr)
    return cfg

def xpath(p):
    return os.path.expanduser(p)

# ------------------------------------------------------------------ self-heal (moved source dirs)
def find_moved_dir(missing, glob_pat="*.md", max_climb=3, max_depth=5):
    """A source dir vanished — search its nearest EXISTING ancestor for a folder of the same
    basename that actually contains matching files (the 'I reorganized my vault' case).
    Best-effort and conservative: heals only on exactly ONE validated match, won't climb far to
    find an existing ancestor (a very stale path is too risky to guess), skips junk/archive dirs,
    and bounds the walk depth. Returns None (-> caller warns loudly) when unsure."""
    missing = os.path.normpath(missing)
    target = os.path.basename(missing.rstrip("/\\"))
    if not target:
        return None
    anc, climbed = os.path.dirname(missing), 0
    while anc and not os.path.isdir(anc):
        parent = os.path.dirname(anc)
        if parent == anc or climbed >= max_climb:   # existing ancestor too far up -> too risky
            return None
        anc, climbed = parent, climbed + 1
    if not os.path.isdir(anc):
        return None
    base = anc.rstrip("/\\").count(os.sep)
    matches = []
    for root, dirs, _ in os.walk(anc):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        if root.count(os.sep) - base >= max_depth:
            dirs[:] = []
            continue
        if target in dirs:
            cand = os.path.join(root, target)
            try:                        # validate: the folder must actually hold matching files
                if any(fnmatch(f, glob_pat) for f in os.listdir(cand)):
                    matches.append(cand)
            except OSError:
                pass
    return matches[0] if len(matches) == 1 else None

def to_config_path(p):
    """Absolute path -> the tilde/forward-slash form used in configs (nicer to persist)."""
    home = os.path.expanduser("~")
    if p.startswith(home):
        p = "~" + p[len(home):]
    return p.replace("\\", "/")

def persist_source_fix(cfg_path, old_value, healed_abs):
    """Surgically rewrite the moved source path in the config file (preserves formatting). Matches
    the JSON-ESCAPED form so Windows backslash paths heal too; never mutates the tracked template."""
    if not cfg_path or not os.path.exists(cfg_path) or os.path.basename(cfg_path) == "config.example.json":
        return
    new_value = to_config_path(healed_abs)
    try:
        with open(cfg_path, encoding="utf-8") as f:
            txt = f.read()
        old_json, new_json = json.dumps(old_value), json.dumps(new_value)   # exact on-disk (escaped) form
        if old_json in txt:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(txt.replace(old_json, new_json, 1))
            print(f"self-heal: updated {os.path.basename(cfg_path)} — source path -> {new_value}", file=sys.stderr)
    except OSError:
        pass

# ------------------------------------------------------------------ harvest
DONE = re.compile(r"(?i)\b(done|complete[d]?|committed|executed|shipped|resolved|delivered)\b|✅|✓")
# Only unambiguously-still-open words, so "Next: X — DONE" is excludable (not kept forever).
FORWARD = re.compile(r"(?i)\b(not sent|unsent|awaiting|waiting on|blocked|on hold|pending|deferred|parked)\b")
CHECK_OPEN = re.compile(r"^\s*[-*+]\s*\[\s\]\s+")     # "- [ ] " unchecked task (open, first-class)
CHECK_DONE = re.compile(r"^\s*[-*+]\s*\[[xX]\]")      # "- [x]" checked task (done -> skip)
STRIKE = re.compile(r"~~.+~~")                          # ~~struck~~ (done -> skip)
HEADING = re.compile(r"^\s*#{1,6}\s")

# Priority = how much a kind demands attention, before staleness is layered on.
KIND_PRIORITY = {"not_sent": 5, "gate": 5, "decision": 4, "awaiting": 3, "next": 3, "todo": 2, "deferred": 1, "parked": 1}
def score(kind, age):
    base = KIND_PRIORITY.get(kind, 2)
    stale = min((age or 0) / 7.0, 5.0)     # up to +5 as a thread ages toward ~5 weeks
    return round(base + stale, 1)
def tier(s):
    return "high" if s >= 6 else "med" if s >= 3.5 else "low"

def compile_markers(cfg):
    return [(k, re.compile(cfg["markers"][k])) for k in cfg["kind_order"] if k in cfg["markers"]]

def parse_frontmatter(txt):
    fm = {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", txt, re.S)   # tolerate CRLF (Windows-authored notes)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip().lower()] = v.strip()
    return fm

def days_old(fm, path):
    for key in ("last_worked", "last worked", "updated", "date"):
        v = fm.get(key)
        if v:
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
            if m:
                try:
                    return (TODAY - datetime.date(int(m[1]), int(m[2]), int(m[3]))).days
                except ValueError:
                    pass
    try:
        return (TODAY - datetime.date.fromtimestamp(os.path.getmtime(path))).days
    except OSError:
        return None

def clean(line):
    # strip only genuine leading markdown markers (bullet, "N.", heading, blockquote, checkbox) —
    # never content digits/dashes, so a leading id like "2607-491 …" survives.
    s = re.sub(r"^\s*(?:[-*+•]\s+|\d+\.\s+|#{1,6}\s+|>\s*|\[[ xX]\]\s*)+", "", line).strip()
    s = re.sub(r"[*_`]{1,2}", "", s)
    return re.sub(r"\s+", " ", s)[:220]

def classify(line, markers):
    for kind, rx in markers:
        if rx.search(line):
            return kind
    return None

def indent(raw):
    return len(raw) - len(raw.lstrip())

def harvest_file(path, label, markers):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except OSError:
        return []
    fm = parse_frontmatter(txt)
    proj = fm.get("name") or os.path.splitext(os.path.basename(path))[0]
    proj = re.sub(r"^(project|reference|feedback|event|user)[_\-]", "", proj).replace("_", " ").strip()
    age = days_old(fm, path)
    lines = txt.splitlines()
    out, seen, i, n = [], set(), 0, len(lines)
    while i < n:
        raw = lines[i]; line = raw.strip(); i += 1
        if not line or HEADING.match(raw):
            continue
        if CHECK_DONE.match(raw) or STRIKE.search(line):     # explicitly-closed items — skip
            continue
        checkbox = bool(CHECK_OPEN.match(raw))
        kind = classify(line, markers) or ("todo" if checkbox else None)
        if not kind:
            continue
        # prose "DONE" only excludes non-checkbox marker lines with no still-open word
        if not checkbox and DONE.search(line) and not FORWARD.search(line):
            continue
        # capture up to 2 deeper-indented continuation lines (multiline sub-bullets/detail)
        block, base, taken = [line], indent(raw), 0
        while i < n and taken < 2:
            nxt = lines[i]; nstr = nxt.strip()
            if (not nstr or HEADING.match(nxt) or indent(nxt) <= base
                    or CHECK_OPEN.match(nxt) or CHECK_DONE.match(nxt) or classify(nstr, markers)):
                break
            block.append(nstr); i += 1; taken += 1
        c = clean(" ".join(block))
        key = c.lower()                 # dedup on the full text, not an 80-char prefix (avoid collisions)
        if len(c) < 6 or key in seen:
            continue
        seen.add(key)
        out.append({"kind": kind, "text": c, "checkbox": checkbox, "project": proj, "source": label,
                    "file": os.path.basename(path), "path": path, "age": age,
                    "priority": score(kind, age), "tier": tier(score(kind, age))})
    return out

def route(cfg, key):
    for g in cfg["goals"]:
        if re.search(g["match"], key, re.I):
            return g
    return cfg["goals"][-1]

# ------------------------------------------------------------------ redaction
def load_redactor(cfg):
    pats = [re.compile(p) for p in cfg["redact"]["patterns"]]
    tf = cfg["redact"].get("terms_file")
    tf_path = tf if tf and os.path.isabs(tf) else os.path.join(HERE, tf or "")
    if tf and os.path.exists(tf_path):
        with open(tf_path, encoding="utf-8") as f:
            terms = [t.strip() for t in f if t.strip() and not t.startswith("#")]
        if terms:
            pats.append(re.compile("|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)), re.I))
        else:
            print(f"WARNING: terms_file '{tf}' is empty — no names masked in the public build.", file=sys.stderr)
    elif tf:
        print(f"WARNING: terms_file '{tf}' not found — public build masks patterns only, NOT your name list.", file=sys.stderr)
    mask = cfg["redact"].get("mask", "█")
    def redact(s):
        for p in pats:
            s = p.sub(lambda m: mask * max(3, min(len(m.group()), 8)), s)
        return s
    return redact

# ------------------------------------------------------------------ build
def claude_link(cfg, text, path, project, public):
    tmpl = cfg["claude"]["prompt_public" if public else "prompt_local"]
    prompt = tmpl.format(file=path, text=text, project=project)
    return cfg["claude"]["url"] + urllib.parse.quote(prompt)

def build_dataset(cfg, items, public, redact):
    # "structural" mode drops ALL harvested free text from the hosted build (provably safe:
    # nothing to leak). "denylist" masks known patterns/terms (blast-radius reduction, NOT a guarantee).
    structural = public and cfg.get("redact", {}).get("mode") == "structural"
    goals = {}
    for i, it in enumerate(items):
        g = route(cfg, it["project"] + " " + it["file"])
        gd = goals.setdefault(g["id"], {"id": g["id"], "name": g["name"], "icon": g["icon"], "color": g["color"], "items": []})
        if structural:
            text = f"{cfg['kind_labels'].get(it['kind'], it['kind'])} item"   # generic, no prose
            proj = "—"
            path = ""
        else:
            # Redact FIRST, then build the link from the redacted text so nothing leaks via the URL.
            text = redact(it["text"]) if public else it["text"]
            proj = redact(it["project"]) if public else it["project"]
            # basename only — keep the local filesystem path out of the click-to-Claude URL
            # (URLs land in browser history / proxy logs); the vault MCP resolves by note name.
            path = "" if public else os.path.basename(it["path"])
        gd["items"].append({"kind": it["kind"], "text": text, "project": proj,
                            "source": it["source"], "age": it["age"],
                            "priority": it.get("priority", 0), "tier": it.get("tier", "low"),
                            "link": claude_link(cfg, text if not structural else "an open item", path, proj, public)})
    for gd in goals.values():
        # rank by priority (kind weight + staleness), then age
        gd["items"].sort(key=lambda x: (x["priority"], -1 if x["age"] is None else x["age"]), reverse=True)
    order = [g["id"] for g in cfg["goals"]]
    goal_list = [goals[i] for i in order if i in goals]
    return {
        "generated": TODAY.isoformat(),
        "title": cfg["title"],
        "mode": "public" if public else "local",
        "total": len(items),
        "labels": cfg["kind_labels"],
        "goals": goal_list,
        "counts": {
            "not_sent": sum(1 for i in items if i["kind"] == "not_sent"),
            "decision": sum(1 for i in items if i["kind"] == "decision"),
            "high": sum(1 for i in items if i.get("tier") == "high"),
            "stale": sum(1 for i in items if i["age"] is not None and i["age"] > 10),
        },
    }

def write_html(cfg, data, out_path):
    out_path = xpath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    # Escape <, >, & so no note text can break out of the inline <script> (stored-XSS defense).
    # These only appear inside JSON string values; \u00xx round-trips identically in JS/JSON.
    payload = (json.dumps(data, ensure_ascii=True)
               .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("/*DATA*/", payload))
    return out_path

def iter_files(d, glob_pat, recursive):
    """Yield note files under d. Recursive by default (Obsidian vaults are nested), skipping
    junk/archive dirs; set a source's "recursive": false for a flat, top-level-only scan."""
    if not recursive:
        yield from sorted(glob.glob(os.path.join(d, glob_pat)))
        return
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for f in sorted(files):
            if fnmatch(f, glob_pat):
                yield os.path.join(root, f)

def harvest_sources(cfg, cfg_path, markers):
    items = []
    for src in cfg["sources"]:
        d = xpath(src["dir"])
        if not os.path.isdir(d):
            healed = find_moved_dir(d, src.get("glob", "*.md")) if cfg.get("self_heal", True) else None
            if healed:                # the folder moved (e.g. a vault reorg) — repair automatically
                print(f"self-heal: '{src['dir']}' not found -> using moved folder '{healed}'", file=sys.stderr)
                persist_source_fix(cfg_path, src["dir"], healed)
                d = healed
            else:                     # fail loud, not a silent undercount
                print(f"WARNING: source dir not found — '{src['dir']}' (resolved: {d}). 0 items; "
                      f"did the folder move, get renamed, or split into copies?", file=sys.stderr)
                continue
        inc, exc = src.get("include_prefix"), src.get("exclude_prefix", [])
        recursive = src.get("recursive", True)
        matched = 0
        for path in iter_files(d, src.get("glob", "*.md"), recursive):
            base = os.path.basename(path)
            if inc and not any(base.startswith(p) for p in inc):
                continue
            if any(base.startswith(p) for p in exc):
                continue
            items += harvest_file(path, src.get("label", "notes"), markers)
            matched += 1
        if matched == 0:
            print(f"WARNING: source '{src['dir']}' matched 0 files "
                  f"(glob '{src.get('glob','*.md')}', recursive={recursive}).", file=sys.stderr)
    return items

def main():
    try:                    # so --brief never crashes on a non-UTF-8 console (Windows)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", action="version", version=f"backlog-cockpit {VERSION}")
    ap.add_argument("--config", default=None)
    ap.add_argument("--public-only", action="store_true")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="skip the LLM pass even if enabled (fast, for session hooks)")
    ap.add_argument("--brief", nargs="?", type=int, const=12, default=None,
                    help="print the top-N priority threads to stdout (for a session-start hook / brief)")
    args = ap.parse_args()
    cfg_path = args.config or (os.path.join(HERE, "config.local.json")
                               if os.path.exists(os.path.join(HERE, "config.local.json"))
                               else os.path.join(HERE, "config.example.json"))
    cfg = load_config(cfg_path)
    markers = compile_markers(cfg)

    items = harvest_sources(cfg, cfg_path, markers)

    print(f"config: {os.path.basename(cfg_path)}  |  harvested {len(items)} open threads")
    if cfg.get("llm", {}).get("enabled") and not args.no_llm:
        try:
            import llm
            items = llm.enrich(items, cfg)
        except Exception as e:
            print(f"llm pass skipped: {e}", file=sys.stderr)
    if not args.public_only:
        p = write_html(cfg, build_dataset(cfg, items, False, lambda s: s), cfg["output"]["local"])
        print(f"  LOCAL  (full detail)  -> {p}")
    if not args.local_only:
        # structural mode drops all prose, so the redactor (and its term-list warning) isn't needed
        redact = (lambda s: s) if cfg["redact"].get("mode") == "structural" else load_redactor(cfg)
        p = write_html(cfg, build_dataset(cfg, items, True, redact), cfg["output"]["public"])
        print(f"  PUBLIC (redacted)     -> {p}")
    if args.brief is not None:
        top = sorted(items, key=lambda x: (x.get("priority", 0), -1 if x["age"] is None else x["age"]), reverse=True)[:args.brief]
        hi = sum(1 for i in items if i.get("tier") == "high")
        ns = sum(1 for i in items if i["kind"] == "not_sent")
        st = sum(1 for i in items if i["age"] is not None and i["age"] > 10)
        print(f"\n=== TOP {len(top)} OPEN THREADS — {len(items)} total · {hi} high · {ns} not-sent · {st} stale>10d ===")
        for n, it in enumerate(top, 1):
            age = "—" if it["age"] is None else (f"{it['age']}d")
            print(f"{n:>2}. [P{it.get('priority',0)} {it.get('tier','low')}/{it['kind']}] {it['text']}  ({it['project']}, {age})")
        print("\n→ Triage: which 3-5 of these should be tackled or sorted out first today, and why? "
              "Weigh urgency (gates, not-sent, deadlines), staleness, and leverage — not just the number.")

# ------------------------------------------------------------------ template
TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Backlog Cockpit</title>
<style>
:root{--paper:#f1f2ef;--surface:#fff;--surface-2:#f7f8f5;--ink:#1b2320;--ink-soft:#576059;--ink-faint:#828b83;--line:#dde1d9;--line-soft:#e9ece5;--accent:#a2641b;--accent-soft:#c98a3a;--todo:#8b948b;--doing:#4d7488;--wait:#b98a1e;--block:#b3452f;--fsans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--fmono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;--sh:0 1px 2px rgba(20,30,25,.05),0 6px 22px rgba(20,30,25,.06);}
@media(prefers-color-scheme:dark){:root{--paper:#0f1512;--surface:#171d18;--surface-2:#1e241f;--ink:#e7ebe4;--ink-soft:#a3ac9f;--ink-faint:#79817a;--line:#28302a;--line-soft:#20271f;--accent:#d29a4d;--accent-soft:#e0ad63;--todo:#7c857e;--doing:#6f9bb0;--wait:#d0a63f;--block:#d4715c;--sh:0 1px 2px rgba(0,0,0,.3),0 8px 26px rgba(0,0,0,.34);}}
:root[data-theme=dark]{--paper:#0f1512;--surface:#171d18;--surface-2:#1e241f;--ink:#e7ebe4;--ink-soft:#a3ac9f;--ink-faint:#79817a;--line:#28302a;--line-soft:#20271f;--accent:#d29a4d;--accent-soft:#e0ad63;--todo:#7c857e;--doing:#6f9bb0;--wait:#d0a63f;--block:#d4715c;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--fsans);line-height:1.5}
h1{margin:0;font-weight:680;letter-spacing:-.01em}a{color:inherit}button{font-family:inherit;cursor:pointer}:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.top{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--paper) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line-soft)}
.top .in{max-width:1080px;margin:0 auto;padding:0 22px;height:58px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700}.mk{width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,var(--accent),var(--accent-soft));display:grid;place-items:center;color:#fff;font-family:var(--fmono);font-size:.7rem;font-weight:800}
.brand small{font-family:var(--fmono);font-weight:500;color:var(--ink-faint);font-size:.72rem}
.mode{font-family:var(--fmono);font-size:.62rem;letter-spacing:.05em;text-transform:uppercase;padding:3px 8px;border-radius:20px;border:1px solid var(--line)}
.mode.local{color:var(--block)}.mode.public{color:var(--doing)}
.ghost{border:1px solid var(--line);background:var(--surface);color:var(--ink-soft);border-radius:9px;padding:7px 11px;font-size:.76rem;font-family:var(--fmono)}.ghost:hover{border-color:var(--accent);color:var(--ink)}
.wrap{max-width:1080px;margin:0 auto;padding:22px}.hi h1{font-size:1.5rem}.hi .sub{color:var(--ink-soft);font-size:.9rem;margin-top:2px}
.focus{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0 18px}@media(max-width:820px){.focus{grid-template-columns:repeat(2,1fr)}}@media(max-width:480px){.focus{grid-template-columns:1fr}}
.ftile{background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:13px 14px;box-shadow:var(--sh);position:relative;overflow:hidden}.ftile::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,var(--accent))}
.ftile .n{font-size:1.7rem;font-weight:730;line-height:1;font-variant-numeric:tabular-nums}.ftile .k{font-family:var(--fmono);font-size:.64rem;letter-spacing:.03em;text-transform:uppercase;color:var(--ink-faint);margin-top:7px}
.filters{display:flex;flex-wrap:wrap;gap:7px;margin:6px 0 18px;align-items:center}
.chip{border:1px solid var(--line);background:var(--surface);color:var(--ink-soft);border-radius:20px;padding:5px 12px;font-size:.75rem;font-family:var(--fmono)}.chip[aria-pressed=true]{background:var(--accent);color:#fff;border-color:var(--accent)}
.lead{font-family:var(--fmono);font-size:.7rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-faint);margin:0 0 12px}
.goals{display:flex;flex-direction:column;gap:13px}
.goal{background:var(--surface);border:1px solid var(--line);border-radius:15px;box-shadow:var(--sh);overflow:hidden}
.ghead{display:grid;grid-template-columns:auto 1fr auto;gap:13px;align-items:center;padding:14px 17px;cursor:pointer}.ghead:hover{background:var(--surface-2)}
.gicon{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-size:1.05rem;background:color-mix(in srgb,var(--gc,var(--accent)) 15%,transparent)}
.gttl h3{font-size:1.02rem;margin:0}.gcount{font-family:var(--fmono);font-size:.8rem;color:var(--ink-soft)}
.chev{color:var(--ink-faint);transition:transform .2s;font-size:.8rem}.goal.collapsed .chev{transform:rotate(-90deg)}.goal.collapsed .items{display:none}
.items{border-top:1px solid var(--line-soft)}
.it{display:grid;grid-template-columns:auto auto 1fr auto auto;gap:11px;align-items:start;padding:10px 17px;border-bottom:1px solid var(--line-soft)}.it:last-child{border-bottom:0}.it:hover{background:var(--surface-2)}
.tdot{width:8px;height:8px;border-radius:50%;margin-top:6px;flex:none;background:var(--todo)}.tdot.t-high{background:var(--block);box-shadow:0 0 0 3px color-mix(in srgb,var(--block) 22%,transparent)}.tdot.t-med{background:var(--wait)}.tdot.t-low{background:var(--line)}
.pill{font-family:var(--fmono);font-size:.6rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;padding:3px 7px;border-radius:20px;white-space:nowrap;min-width:74px;text-align:center;margin-top:1px}
.pill[data-k=not_sent],.pill[data-k=gate]{color:var(--block);background:color-mix(in srgb,var(--block) 13%,transparent)}
.pill[data-k=decision]{color:var(--wait);background:color-mix(in srgb,var(--wait) 15%,transparent)}
.pill[data-k=deferred],.pill[data-k=parked]{color:var(--todo);background:color-mix(in srgb,var(--todo) 14%,transparent)}
.pill[data-k=awaiting]{color:var(--doing);background:color-mix(in srgb,var(--doing) 15%,transparent)}
.pill[data-k=next],.pill[data-k=todo]{color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,transparent)}
.itx{min-width:0;font-size:.88rem}.meta{font-family:var(--fmono);font-size:.7rem;color:var(--ink-faint);margin-top:2px}
.age{font-family:var(--fmono);font-size:.72rem;color:var(--ink-faint);white-space:nowrap;text-align:right;margin-top:1px}.age.hot{color:var(--block);font-weight:700}
.go{border:1px solid var(--line);background:var(--surface);color:var(--ink-soft);border-radius:8px;width:30px;height:28px;display:grid;place-items:center;text-decoration:none;font-size:.9rem}.go:hover{border-color:var(--accent);color:var(--accent)}
.hint{margin:20px 0 0;font-size:.82rem;color:var(--ink-soft);background:var(--surface-2);border:1px dashed var(--line);border-radius:12px;padding:13px 15px}
footer{max-width:1080px;margin:0 auto;padding:16px 22px 40px;font-family:var(--fmono);font-size:.7rem;color:var(--ink-faint);line-height:1.7}
</style></head><body>
<div class="top"><div class="in"><div class="brand"><span class="mk">BC</span> <span id="ttl">Backlog Cockpit</span> <small id="stamp"></small> <span class="mode" id="mode"></span></div>
<div style="display:flex;gap:8px"><button class="ghost" id="expand">Collapse all</button><button class="ghost" id="tbtn">Theme</button></div></div></div>
<div class="wrap">
<div class="hi"><h1>Everything that's still open.</h1><div class="sub" id="sub"></div></div>
<div class="focus" id="focus"></div><div class="filters" id="filters"></div>
<p class="lead">By goal &middot; oldest threads on top</p><div class="goals" id="goals"></div>
<div class="hint">Click an item's <b>&#8599;</b> to open a Claude session that pulls the note and works it. Re-run <code>harvest.py</code> to refresh. Wrong bucket or noisy line? Markers &amp; routing are all in your config.</div>
</div>
<footer id="foot"></footer>
<script>
const D=/*DATA*/;const L=D.labels;let kf=null,stale=false;const $=id=>document.getElementById(id);
$("ttl").textContent=D.title;$("stamp").textContent="· "+D.total+" open · "+D.generated;
$("mode").textContent=D.mode;$("mode").className="mode "+D.mode;
$("sub").textContent=D.mode==="public"?"Redacted view — safe to share. Full detail lives on your machine.":"Harvested from your notes. Stalest first. Nothing left this machine.";
$("foot").textContent=D.mode==="public"?"Redacted build · numbers, paths, emails & your term list stripped.":"Local build · full detail · never published.";
function tiles(){return[{n:D.total,k:"Open threads",c:"var(--accent)"},{n:(D.counts.high||0),k:"High priority",c:"var(--block)"},{n:D.counts.not_sent,k:"Not sent",c:"var(--wait)"},{n:D.counts.stale,k:"Stale &gt; 10 days",c:"var(--todo)"}]}
function esc(s){return(s+"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function ageTxt(a){return a===null?"—":a===0?"today":a+"d"}
function renderFocus(){$("focus").innerHTML=tiles().map(t=>`<div class="ftile" style="--c:${t.c}"><div class="n">${t.n}</div><div class="k">${t.k}</div></div>`).join("")}
function renderFilters(){const ks=Object.keys(L);$("filters").innerHTML=`<button class="chip" data-k="" aria-pressed="${kf===null}">All kinds</button>`+ks.map(k=>`<button class="chip" data-k="${k}" aria-pressed="${kf===k}">${L[k]}</button>`).join("")+`<span style="flex:1"></span><button class="chip" id="sb" aria-pressed="${stale}">Stale &gt; 10d only</button>`;
 $("filters").querySelectorAll(".chip[data-k]").forEach(b=>b.onclick=()=>{kf=b.dataset.k||null;render()});$("sb").onclick=()=>{stale=!stale;render()}}
function show(it){if(kf&&it.kind!==kf)return false;if(stale&&!(it.age!==null&&it.age>10))return false;return true}
function renderGoals(){const g=$("goals");g.innerHTML="";D.goals.forEach(goal=>{const items=goal.items.filter(show);if(!items.length)return;
 const c=document.createElement("div");c.className="goal";c.style.setProperty("--gc",goal.color);
 c.innerHTML=`<div class="ghead"><div class="gicon" style="--gc:${goal.color}">${esc(goal.icon)}</div><div><h3>${esc(goal.name)}</h3></div><div style="display:flex;gap:12px;align-items:center"><span class="gcount">${items.length}</span><span class="chev">▼</span></div></div><div class="items">${items.map(it=>`<div class="it"><span class="tdot t-${it.tier||'low'}" title="priority ${it.priority||''}"></span><span class="pill" data-k="${it.kind}">${esc(L[it.kind])}</span><div class="itx">${esc(it.text)}<div class="meta">${esc(it.project)} · ${esc(it.source)}</div></div><span class="age ${it.age!==null&&it.age>10?'hot':''}">${ageTxt(it.age)}</span><a class="go" href="${esc(it.link)}" target="bc-work" rel="noopener" title="Open in Claude (reuses one tab)">↗</a></div>`).join("")}</div>`;
 c.querySelector(".ghead").onclick=()=>c.classList.toggle("collapsed");g.appendChild(c)});
 if(!g.children.length)g.innerHTML=`<div class="hint">Nothing matches this filter.</div>`}
function render(){renderFocus();renderFilters();renderGoals()}
$("expand").onclick=e=>{const any=[...document.querySelectorAll(".goal")].some(c=>c.classList.contains("collapsed"));document.querySelectorAll(".goal").forEach(c=>c.classList.toggle("collapsed",!any));e.target.textContent=any?"Collapse all":"Expand all"};
$("tbtn").onclick=()=>{const r=document.documentElement,c=r.getAttribute("data-theme")||(matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light");r.setAttribute("data-theme",c==="dark"?"light":"dark")};
render();
</script></body></html>"""

if __name__ == "__main__":
    main()
