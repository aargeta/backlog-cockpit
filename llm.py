"""Optional LLM enrichment pass — rewrite raw harvested lines into crisp, action-first task
names and refine their priority. Off by default; the core tool never needs it.

Transport, in order of preference:
  1. the local `claude` CLI (Claude Code) — no API key, uses your existing auth. Ideal for
     Claude Code users, and keeps note text inside your own authenticated session.
  2. the Anthropic API, if ANTHROPIC_API_KEY is set.

Fails soft: on a missing transport, timeout, or unparseable reply, items pass through unchanged.
Guardrail: items whose text matches any `llm.exclude` regex are never sent to the model.
"""
import os, re, sys, json, shutil, subprocess, urllib.request

PROMPT = (
    "You are triaging a work backlog. For the numbered open items below, return ONLY a JSON array "
    "of objects like {\"n\": <number>, \"name\": \"<crisp action-first task title, <= 12 words>\", "
    "\"priority\": <1-10, higher = more urgent or blocking>}. Rewrite vague lines (e.g. \"Next Action\") "
    "into concrete tasks using the item's OWN words and kind; never invent facts you don't see. "
    "Return the array and nothing else.\n\nItems:\n"
)


def _excluded(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)


def _via_cli(prompt, model):
    exe = shutil.which("claude")
    if not exe:
        return None
    cmd = [exe, "-p", prompt]
    if model:
        cmd += ["--model", model]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240, encoding="utf-8")
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _via_api(prompt, model):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({"model": model or "claude-sonnet-5", "max_tokens": 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception:
        return None


def _extract_json(txt):
    if not txt:
        return None
    m = re.search(r"\[.*\]", txt, re.S)
    try:
        return json.loads(m.group()) if m else None
    except Exception:
        return None


def _tier(p):
    return "high" if p >= 6 else "med" if p >= 3.5 else "low"


def enrich(items, cfg, _transport=None):
    """Enrich the top-priority items in place-ish (returns the list). `_transport` overrides the
    model call for tests: a callable(prompt)->str."""
    lc = cfg.get("llm", {})
    if not lc.get("enabled") or not items:
        return items
    model = lc.get("model")
    exclude = lc.get("exclude", [])
    max_items = lc.get("max_items", 60)
    ranked = sorted(range(len(items)), key=lambda i: items[i].get("priority", 0), reverse=True)
    targets = [i for i in ranked if not _excluded(items[i]["text"], exclude)][:max_items]
    if not targets:
        return items
    listing = "\n".join(f'{n}. [{items[i]["kind"]}] {items[i]["text"]}' for n, i in enumerate(targets))
    prompt = PROMPT + listing
    raw = _transport(prompt) if _transport else (_via_cli(prompt, model) or _via_api(prompt, model))
    parsed = _extract_json(raw)
    if not parsed:
        print("llm: no transport or unparseable reply — items left unchanged.", file=sys.stderr)
        return items
    by_n = {int(o["n"]): o for o in parsed if isinstance(o, dict) and "n" in o}
    renamed = 0
    for n, i in enumerate(targets):
        o = by_n.get(n)
        if not o:
            continue
        name = (o.get("name") or "").strip()
        if name and len(name) >= 4:
            items[i]["text"] = name[:200]
            renamed += 1
        pr = o.get("priority")
        if isinstance(pr, (int, float)) and 0 <= pr <= 10:
            items[i]["priority"] = round(float(pr), 1)
            items[i]["tier"] = _tier(float(pr))
    print(f"llm: enriched {renamed}/{len(targets)} top items.", file=sys.stderr)
    return items
