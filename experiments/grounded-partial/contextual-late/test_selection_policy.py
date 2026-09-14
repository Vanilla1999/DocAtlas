"""Synthetic counterexamples; no benchmark answers or library-specific rules."""
from copy import deepcopy
from itertools import permutations
import unittest

from selection_policy import (compatible, make_item, prefer_signature,
                              retain_extend, retains, signature_features,
                              signature_subjects)


def item(text, start=0, path="api.md", rank=0, **origin_flags):
    origin = dict(content=text, char_start=start, path=path, source_class="project_doc",
                  project_identity="p", authority="source_of_truth", **origin_flags)
    source = dict(snippet=text, path_or_url=path, evidence_id=f"ev-{path}-{start}",
                  project_identity="p", authority="source_of_truth")
    return make_item(source, origin, rank=rank)


def cost(items):
    # Stub cost for unit tests only. The replay uses the actual full-DTO counter.
    return 20 + sum(10 + len(part["source"]["snippet"]) for part in items)


def extend(before, pool, **kwargs):
    return retain_extend(before, pool, question="Describe Widget", lookup_texts=(),
                         tokens=cost, **kwargs)


class SignatureTests(unittest.TestCase):
    def test_both_orders_prefer_definition(self):
        intro = {"content": "Widget performs work after sending a response."}
        definition = {"content": "Signature: `Widget(function, *args)`"}
        for order in permutations([intro, definition]):
            self.assertIs(prefer_signature(list(order), "What is the signature of Widget?")[0], definition)

    def test_russian_intent(self):
        self.assertEqual(signature_subjects("Какая сигнатура WorkItem добавляет задачу?"), ("WorkItem",))
        self.assertTrue(signature_features("Какая сигнатура WorkItem?", "Signature: `WorkItem(func)`"))

    def test_lowercase_explicit_name(self):
        self.assertTrue(signature_features("What is the signature of do_work?", "def do_work(a, b):\n    pass"))

    def test_neighbour_symbol_and_prefix_are_not_target(self):
        for text in ("Signature: `WidgetExtra(value)`", "Signature: `OtherWidget(value)`"):
            self.assertFalse(signature_features("Signature of Widget?", text))

    def test_call_is_not_definition(self):
        for text in ("result = Widget(value)", "Widget(value)", "`Widget(value)`", "class Widget(Base):"):
            self.assertFalse(signature_features("Signature of Widget?", text))

    def test_no_signature_request_is_exact_noop(self):
        values = [{"content": "Intro"}, {"content": "Signature: `Widget(value)`"}]
        self.assertEqual(prefer_signature(values, "When does Widget run?"), values)

    def test_visible_snippet_beats_hidden_content(self):
        c = {"snippet": "Intro", "content": "Signature: `Widget(value)`"}
        good = {"snippet": "Signature: `Widget(value)`"}
        self.assertEqual(prefer_signature([c, good], "Signature of Widget?"), [good, c])

    def test_ambiguous_unbound_symbols_not_guessed(self):
        self.assertEqual(signature_subjects("Which signature adds FooBar and BazQux?"), ())

    def test_missing_subject_is_noop(self):
        self.assertFalse(signature_subjects("Which signature?"))


class RetentionTests(unittest.TestCase):
    def test_empty_is_not_rescued(self):
        self.assertEqual(extend([], [item("Widget provides a signature")]), [])

    def test_append_complement_from_same_query(self):
        old = item("Widget introduction.")
        other = item("Signature: `Widget(function)`", start=100)
        result = extend([old], [other])
        self.assertEqual(len(result), 2)
        self.assertTrue(retains([old], result))

    def test_genuine_duplicate_does_not_spend_budget(self):
        old = item("Widget text.")
        duplicate = item("Widget text.", start=100)
        self.assertEqual(extend([old], [duplicate]), [old])

    def test_overlap_without_containment_rejected(self):
        old = item("Widget text.", start=20)
        overlapping = item("Another long Widget text that overlaps.", start=25)
        self.assertEqual(extend([old], [overlapping]), [old])

    def test_larger_quote_can_retain_small_one(self):
        old = item("Widget text.", start=10)
        larger = item("1234567890Widget text. More details.")
        result = extend([old], [larger])
        self.assertEqual(len(result), 1)
        self.assertTrue(retains([old], result))
        self.assertEqual(result[0]["source"]["snippet"], larger["source"]["snippet"])

    def test_source_ceiling(self):
        old = [item("One", path="1"), item("Two", path="2"), item("Three", path="3")]
        self.assertEqual(extend(old, [item("Fourth", path="4")]), old)

    def test_full_budget(self):
        old = [item("One")]
        self.assertEqual(extend(old, [item("More", path="2")], max_tokens=cost(old)), old)

    def test_over_budget_baseline_is_error(self):
        with self.assertRaises(ValueError):
            extend([item("One")], [], max_tokens=1)

    def test_foreign_project(self):
        old, other = item("One"), item("More", path="2")
        other["origin"]["project_identity"] = "foreign"
        self.assertEqual(extend([old], [other]), [old])

    def test_stale_risky_and_unqualified_rejected(self):
        for key, value in (("stale", True), ("freshness", "stale"),
                           ("index_freshness", "outdated"), ("risk_flags", ["risk"]),
                           ("instruction_risk_flags", ["instruction"])):
            self.assertEqual(extend([item("One")], [item("More", path="2", **{key: value})]), [item("One")])
        other = item("More", path="2")
        other["qualified"] = False
        self.assertEqual(extend([item("One")], [other]), [item("One")])

    def test_lower_authority_does_not_displace_authoritative(self):
        other = item("More", path="2")
        other["source"]["authority"] = "supporting"
        self.assertEqual(extend([item("One")], [other]), [item("One")])

    def test_no_input_mutation(self):
        old, pool = [item("One")], [item("More", path="2")]
        saved = deepcopy((old, pool))
        extend(old, pool)
        self.assertEqual((old, pool), saved)

    def test_distinct_spans_get_distinct_evidence_ids(self):
        old, other = item("One"), item("More", start=100)
        other["source"]["evidence_id"] = old["source"]["evidence_id"]
        result = extend([old], [other])
        self.assertEqual(len({r["source"]["evidence_id"] for r in result}), 2)

    def test_binding_rejects_unlocatable_and_repeated_quote(self):
        origin = item("One")["origin"]
        self.assertIsNone(make_item({"snippet": "Other"}, origin, rank=0))
        origin["content"] = "One One"
        self.assertIsNone(make_item({"snippet": "One"}, origin, rank=0))

    def test_synthetic_permutations_always_retain_baseline(self):
        old = [item("Widget runs.")]
        pool = [item("Signature: `Widget(work)`", start=100),
                item("Widget stores a result.", start=200), item("Widget runs.", start=300)]
        for order in permutations(pool):
            result = extend(old, list(order), max_tokens=110)
            self.assertTrue(retains(old, result))
            self.assertTrue(compatible(result))
            self.assertLessEqual(cost(result), 110)
            self.assertLessEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
