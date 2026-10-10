"""Unit controls for the isolated prototype, not product/release acceptance."""
import hashlib
import unittest

from p2_retrieval_prototype import Index, eligibility, features, project


def source():
    text = "UnknownUnit keeps a local excerpt."
    meta = dict(project="p", module="m", version="v", generation="g", synchronized=True,
                body_sha256=hashlib.sha256(text.encode()).hexdigest(), offset_unit="unicode-code-point",
                start=0, end=len(text))
    return dict(id="test-source", text=text, metadata=meta)


class Controls(unittest.TestCase):
    def test_each_scope_boundary(self):
        row = source()
        scope = {k: row["metadata"][k] for k in ("project", "module", "version", "generation")}
        self.assertTrue(eligibility(row, scope)[0])
        for field in scope:
            with self.subTest(field=field):
                self.assertFalse(eligibility(row, dict(scope, **{field: "foreign"}))[0])

    def test_integrity_faults(self):
        row = source()
        scope = {k: row["metadata"][k] for k in ("project", "module", "version", "generation")}
        for fault in (dict(body_sha256="0" * 64), dict(end=len(row["text"]) + 1),
                      dict(start=-1), dict(synchronized=False), dict(offset_unit="bytes")):
            with self.subTest(fault=fault):
                self.assertFalse(eligibility(dict(row, metadata=dict(row["metadata"], **fault)), scope)[0])

    def test_fallback_retains_local_excerpt(self):
        row = source()
        scope = {k: row["metadata"][k] for k in ("project", "module", "version", "generation")}
        result = Index([row], "char-tfidf").search(["UnknownUnit"], scope, 1, backend_available=False)
        self.assertEqual(result["status"], "local-lexical-degraded")
        self.assertEqual(result["prefit"][0]["source"], row)
        self.assertEqual(result["extra_query_calls"], 0)

    def test_projection_does_not_invent_proof_or_truncate_quotes(self):
        row = source()
        rows = [dict(source=row)]
        self.assertEqual(project(rows, 1000)["sources"][0]["text"], row["text"])
        self.assertEqual(project(rows, 100)["sources"], [])
        self.assertEqual(project(rows, 1000)["proof_status"], "not-evaluated")
        with self.assertRaises(ValueError):
            project(rows, 1)

    def test_unicode_features_without_alias_expansion(self):
        self.assertEqual(features("НезнакомыйИдентификатор", "lexical"), {"незнакомыйидентификатор": 1})
        with self.assertRaises(ValueError):
            features("text", "unknown-backend")


if __name__ == "__main__":
    unittest.main()
