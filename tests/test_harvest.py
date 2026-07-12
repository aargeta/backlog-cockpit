"""Test suite for the Backlog Cockpit engine. Zero dependencies — run with:  python -m unittest -v
Focuses on the security-critical paths (redaction, script-injection) and the extraction core."""
import os, sys, json, tempfile, importlib.util, unittest, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("harvest", os.path.join(ROOT, "harvest.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

MK = h.compile_markers(h.DEFAULTS)


def harvest_text(text, label="notes"):
    p = os.path.join(tempfile.gettempdir(), "bc_test_note.md")
    open(p, "w", encoding="utf-8").write(text)
    return h.harvest_file(p, label, MK)


class TestClassify(unittest.TestCase):
    def test_markers_hit(self):
        for line, kind in [("NEXT: build it", "next"), ("Deferred: later", "deferred"),
                           ("Awaiting the client", "awaiting"), ("Open decision: which db", "decision"),
                           ("TODO: write docs", "todo"), ("Parked for now", "parked")]:
            self.assertEqual(h.classify(line, MK), kind, line)

    def test_not_sent_is_case_insensitive(self):   # regression guard
        for s in ("NOT SENT", "not sent", "Not Sent yet"):
            self.assertEqual(h.classify(s + " proposal", MK), "not_sent", s)

    def test_gate_noun_not_matched(self):          # "signature block" must NOT be a gate
        self.assertIsNone(h.classify("update the signature block", MK))
        self.assertIsNone(h.classify("the intake gate design", MK))   # lowercase 'gate' noun
    def test_gate_real(self):
        self.assertEqual(h.classify("GATE: needs sign-off", MK), "gate")
        self.assertEqual(h.classify("this is Blocked on legal", MK), "gate")

    def test_non_marker_returns_none(self):
        self.assertIsNone(h.classify("just a normal sentence about work", MK))


class TestExtraction(unittest.TestCase):
    def test_checkbox_open_is_task(self):
        items = harvest_text("- [ ] wire the export button\n")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "todo")
        self.assertTrue(items[0]["checkbox"])
        self.assertNotIn("[", items[0]["text"])       # checkbox syntax stripped

    def test_checkbox_done_excluded(self):
        self.assertEqual(harvest_text("- [x] finished this\n- [X] and this\n"), [])

    def test_strikethrough_excluded(self):
        self.assertEqual(harvest_text("~~dropped this idea~~\n"), [])

    def test_prose_done_excluded_but_open_kept(self):
        items = harvest_text("Next: rotate key — DONE, resolved\nNext: build the parser\n")
        texts = " ".join(i["text"] for i in items)
        self.assertIn("build the parser", texts)
        self.assertNotIn("rotate key", texts)          # excluded: done + no still-open word

    def test_still_open_word_survives_done(self):
        items = harvest_text("Awaiting Amy, the prep work is done\n")
        self.assertEqual(len(items), 1)                # 'awaiting' keeps it despite 'done'

    def test_multiline_continuation_joined(self):
        items = harvest_text("Next: build the parser\n    handle the wide geometry\n    and the bands\n")
        self.assertEqual(len(items), 1)
        self.assertIn("wide geometry", items[0]["text"])
        self.assertIn("bands", items[0]["text"])

    def test_multiline_stops_at_new_marker(self):
        items = harvest_text("Next: first task\n    detail line\nTODO: second task\n")
        self.assertEqual(len(items), 2)

    def test_headings_and_blanks_ignored(self):
        self.assertEqual(harvest_text("# A heading\n\n## Another\n"), [])

    def test_dedup_within_file(self):
        items = harvest_text("TODO: same thing\nTODO: same thing\n")
        self.assertEqual(len(items), 1)


class TestPriority(unittest.TestCase):
    def test_kind_weight_ordering(self):
        self.assertGreater(h.score("not_sent", 0), h.score("todo", 0))
        self.assertGreater(h.score("gate", 0), h.score("deferred", 0))

    def test_staleness_raises_priority(self):
        self.assertGreater(h.score("todo", 40), h.score("todo", 0))

    def test_staleness_capped(self):
        self.assertLessEqual(h.score("todo", 10000) - h.score("todo", 0), 5.01)

    def test_tiers(self):
        self.assertEqual(h.tier(7), "high")
        self.assertEqual(h.tier(4), "med")
        self.assertEqual(h.tier(1), "low")

    def test_items_carry_priority_and_tier(self):
        it = harvest_text("NOT SENT: the proposal\n")[0]
        self.assertIn("priority", it)
        self.assertIn(it["tier"], ("high", "med", "low"))


class TestRedaction(unittest.TestCase):
    def redactor(self, terms=None):
        cfg = {"redact": {"patterns": h.DEFAULTS["redact"]["patterns"], "terms_file": None, "mask": "#"}}
        r = h.load_redactor(cfg)
        if terms:
            # emulate a terms file
            import re
            pat = __import__("re").compile("|".join(__import__("re").escape(t) for t in terms), __import__("re").I)
            base = r
            return lambda s: pat.sub("#" * 4, base(s))
        return r

    def test_masks_multisegment_and_permit_ids(self):
        r = self.redactor()
        for probe in ("1234-56-789", "450000-1", "12-345678-X", "2999-499"):
            self.assertNotIn(probe, r(f"item {probe} here"), probe)

    def test_masks_paths_and_emails(self):
        r = self.redactor()
        self.assertNotIn("secret.md", r("see notes in secret.md"))
        self.assertNotIn("@", r("email me at a@b.com"))
        self.assertNotIn("Users", r(r"C:\Users\bob\notes"))

    def test_terms_masked(self):
        r = self.redactor(terms=["Acme"])
        self.assertNotIn("Acme", r("proposal for Acme Corp"))

    def test_structural_drops_all_prose(self):
        items = [{"kind": "not_sent", "text": "secret client Acme proposal 1234-56-789",
                  "checkbox": False, "project": "Acme deal", "source": "notes", "file": "acme.md",
                  "path": "/x/acme.md", "age": 5, "priority": 6.0, "tier": "high"}]
        cfg = h.deep_merge(h.DEFAULTS, {"redact": {"mode": "structural"}})
        data = h.build_dataset(cfg, items, public=True, redact=lambda s: s)
        blob = json.dumps(data)
        for probe in ("Acme", "secret", "1234", "acme.md"):
            self.assertNotIn(probe, blob, probe)

    def test_link_uses_redacted_text_not_raw(self):
        # denylist: the claude link must be built from redacted text, never the raw item
        items = [{"kind": "todo", "text": "call Acme about 1234-56-789", "checkbox": False,
                  "project": "p", "source": "notes", "file": "p.md", "path": "/x/p.md", "age": 1, "priority": 2, "tier": "low"}]
        cfg = h.deep_merge(h.DEFAULTS, {"redact": {"mode": "denylist"}})
        data = h.build_dataset(cfg, items, public=True, redact=lambda s: s.replace("Acme", "####").replace("1234-56-789", "####"))
        link = data["goals"][0]["items"][0]["link"]
        self.assertNotIn("Acme", link)
        self.assertNotIn("1234-56-789", link)


class TestInjection(unittest.TestCase):
    def test_script_breakout_escaped(self):
        data = {"generated": "2026-01-01", "title": "T", "mode": "public", "total": 1,
                "labels": h.DEFAULTS["kind_labels"], "counts": {"not_sent": 0, "decision": 0, "high": 0, "stale": 0},
                "goals": [{"id": "x", "name": "G", "icon": "x", "color": "#000", "items": [
                    {"kind": "todo", "text": "evil</script><script>alert(1)</script>", "project": "p",
                     "source": "s", "age": 1, "priority": 1, "tier": "low", "link": "https://claude.ai/new?q=x"}]}]}
        out = os.path.join(tempfile.gettempdir(), "bc_xss.html")
        h.write_html({"title": "T"}, data, out)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        self.assertEqual(html.count("</script>"), 1, "only the real closing tag should remain")
        self.assertIn("\\u003c/script", html)


class TestConfig(unittest.TestCase):
    def test_deep_merge_overrides_scalars_keeps_others(self):
        merged = h.deep_merge({"a": 1, "b": {"x": 1, "y": 2}}, {"b": {"y": 9}})
        self.assertEqual(merged["a"], 1)
        self.assertEqual(merged["b"], {"x": 1, "y": 9})

    def test_route_catchall(self):
        g = h.route(h.DEFAULTS, "totally unmatched name")
        self.assertEqual(g["id"], "other")

    def test_frontmatter_parse(self):
        fm = h.parse_frontmatter("---\nname: Demo\nlast_worked: 2026-07-01\n---\nbody\n")
        self.assertEqual(fm["name"], "Demo")
        self.assertEqual(fm["last_worked"], "2026-07-01")

    def test_days_old_from_frontmatter(self):
        fm = {"last_worked": "2000-01-01"}
        self.assertGreater(h.days_old(fm, "/nonexistent"), 9000)


class TestLLM(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("llm", os.path.join(ROOT, "llm.py"))
        self.llm = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.llm)

    def test_disabled_is_noop(self):
        items = [{"kind": "todo", "text": "raw line", "priority": 2, "tier": "low"}]
        self.assertEqual(self.llm.enrich(items, {"llm": {"enabled": False}}), items)

    def test_extract_json_from_prose(self):
        self.assertEqual(self.llm._extract_json('sure!\n[{"n":0,"name":"x"}]\ndone'), [{"n": 0, "name": "x"}])
        self.assertIsNone(self.llm._extract_json("no json here"))

    def test_excluded(self):
        self.assertTrue(self.llm._excluded("touch salary numbers", ["salary"]))
        self.assertFalse(self.llm._excluded("normal task", ["salary"]))

    def test_enrich_renames_and_reprioritizes(self):
        items = [{"kind": "next", "text": "Next Action", "priority": 3.0, "tier": "low"},
                 {"kind": "todo", "text": "touch salary", "priority": 2.0, "tier": "low"}]
        fake = lambda prompt: '[{"n":0,"name":"Rewrite the export button handler","priority":7}]'
        out = self.llm.enrich(items, {"llm": {"enabled": True, "exclude": ["salary"]}}, _transport=fake)
        self.assertEqual(out[0]["text"], "Rewrite the export button handler")
        self.assertEqual(out[0]["priority"], 7.0)
        self.assertEqual(out[0]["tier"], "high")
        self.assertEqual(out[1]["text"], "touch salary")   # excluded item never sent, unchanged

    def test_enrich_fails_soft_on_bad_reply(self):
        items = [{"kind": "todo", "text": "keep me", "priority": 2, "tier": "low"}]
        out = self.llm.enrich(items, {"llm": {"enabled": True}}, _transport=lambda p: "garbage, no json")
        self.assertEqual(out[0]["text"], "keep me")


class TestSelfHeal(unittest.TestCase):
    def test_finds_uniquely_moved_folder(self):
        root = tempfile.mkdtemp()
        moved = os.path.join(root, "new-area", "my-notes"); os.makedirs(moved)
        missing = os.path.join(root, "old-area", "my-notes")   # gone; nearest existing ancestor is root
        self.assertEqual(os.path.normpath(h.find_moved_dir(missing)), os.path.normpath(moved))

    def test_ambiguous_match_returns_none(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "a", "dup")); os.makedirs(os.path.join(root, "b", "dup"))
        self.assertIsNone(h.find_moved_dir(os.path.join(root, "gone", "dup")))   # 2 matches -> refuse to guess

    def test_no_match_returns_none(self):
        root = tempfile.mkdtemp()
        self.assertIsNone(h.find_moved_dir(os.path.join(root, "gone", "nothing-like-this")))

    def test_to_config_path_tildes_home(self):
        p = h.to_config_path(os.path.join(os.path.expanduser("~"), "x", "y"))
        self.assertTrue(p.startswith("~/"))
        self.assertNotIn("\\", p)

    def test_persist_rewrites_config_surgically(self):
        d = tempfile.mkdtemp(); cfgp = os.path.join(d, "c.json")
        with open(cfgp, "w", encoding="utf-8") as f:
            f.write('{\n  "sources": [ { "dir": "~/old/place" } ]\n}\n')
        h.persist_source_fix(cfgp, "~/old/place", os.path.join(os.path.expanduser("~"), "new", "place"))
        txt = open(cfgp, encoding="utf-8").read()
        self.assertIn("~/new/place", txt)
        self.assertNotIn("~/old/place", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
