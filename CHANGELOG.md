# Changelog

## 1.0.0 — 2026-07-12

First stable release.

### Added
- Harvest open threads from Markdown/Obsidian notes and a Claude Code `~/.claude` memory dir —
  markers (`NEXT`/`TODO`/`Deferred`/`Parked`/`Not sent`/`Awaiting`/gate) plus Markdown checkboxes,
  with multiline sub-bullet capture.
- Priority ranking (kind urgency + staleness) with tier dots and a "high priority" focus tile.
- Two hosted builds — **structural** (provably safe: no prose) and **denylist** (redacted) — plus a
  local full-detail build. Self-contained HTML, no server, no dependencies.
- Optional LLM naming/ranking pass (`llm.py`) via the local `claude` CLI or the Anthropic API — off
  by default, fails soft, honours an exclude list.
- React frontend under `web/`; click-to-Claude links that reuse a single tab.
- **Self-healing source paths** — if a folder moves (a vault reorg), locate it by name and repair
  the config automatically.
- `--brief`, `--no-llm`, `--version`; a `SessionStart`-hook automation recipe.
- Zero-dependency test suite (49 tests) + CI on Python 3.8 and 3.12.

### Fixed (hardening pass, post-review)
- **Recursive source scanning** — nested Obsidian vaults were silently undercounted (`*.md` no longer
  stops at the top level); junk/archive dirs are skipped.
- **CRLF frontmatter** — Windows-authored notes kept their `name:`/`last_worked:` (was returning `{}`).
- **Self-heal safety** — validates a candidate (must contain matching files), bounds how far it climbs,
  skips junk dirs, never mutates the tracked `config.example.json`, and persists backslash-path configs
  correctly (was a silent no-op).
- **`clean()`** no longer eats leading identifiers (e.g. `2607-491 …`).
- **Dedup** compares full text (no 80-character-prefix collisions).
- **Escaping** extended to config-sourced template fields (defence-in-depth).
