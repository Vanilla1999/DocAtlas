"""Read-only evidence check; production PR is restricted to two lock files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(sys.argv[1]).resolve()
BASE = "d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c"
PROVENANCE = [
    ("README.md", "be4e9c7e5aa2dfa3a99aabb06078ac7015f8a295", "4bc778b1dfaf72dcd1058427a8477841fea62e500b20913471ae05e74e9be2d9"),
    ("docs/project-docs-mcp-workflow.md", "2facdba3b84c1c5e4a396b4e0d06b2a5e32aacd4", "8900b87204a72862432f11f1f9433c6646d55663330c590044a947a5050c0f36"),
]


def historical(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


cases_path = "eval/project_context_quality_v2/cases.json"
assert (ROOT / cases_path).read_bytes() == historical(BASE, cases_path)
corpus = json.loads((ROOT / cases_path).read_bytes())
protocol_path = "eval/project_context_quality_v2/protocol.lock.json"
acceptance_path = "eval/project_context_quality_v2/acceptance.lock.json"
before = historical(BASE, protocol_path)
expected = before
rows = []
for path, commit, old_hash in PROVENANCE:
    old = historical(commit, path)
    current = (ROOT / path).read_bytes()
    assert digest(old) == old_hash
    assert current == historical(BASE, path)
    new_hash = digest(current)
    assert expected.count(old_hash.encode()) == 1
    expected = expected.replace(old_hash.encode(), new_hash.encode(), 1)
    witnesses = []
    for obligation_id, obligation in corpus["obligations"].items():
        for witness in obligation["accepted_witnesses"]:
            if witness["path"] != path:
                continue
            old_lines = [line for line in old.decode().splitlines() if witness["text"] in line]
            new_lines = current.decode().splitlines()
            assert old_lines, (path, obligation_id, "missing frozen witness")
            assert all(line in new_lines for line in old_lines), (path, obligation_id, "changed witness statement")
            affected = [case for case in corpus["cases"] if any(o["obligation_id"] == obligation_id for o in case["obligations"])]
            witnesses.append({"obligation": obligation, "frozen_statement_lines": old_lines, "affected_cases": affected, "statement_lines_unchanged": True})
    rows.append({"path":path,"historical_commit":commit,"historical_blob":subprocess.check_output(["git","rev-parse",f"{commit}:{path}"],cwd=ROOT,text=True).strip(),"expected_sha256":old_hash,"current_sha256":new_hash,"witness_checks":witnesses,"note":"Statement checks accompany manual full-diff semantic review; substring equality alone does not certify semantics."})
actual = (ROOT / protocol_path).read_bytes()
assert actual == expected, "Only two fixed-length identity substitutions are permitted"
assert len(actual) == len(before)
old_acceptance = historical(BASE, acceptance_path)
assert old_acceptance.count(digest(before).encode()) == 1
assert (ROOT / acceptance_path).read_bytes() == old_acceptance.replace(digest(before).encode(), digest(actual).encode(), 1)
changed = subprocess.check_output(["git","diff","--name-only",BASE],cwd=ROOT,text=True).splitlines()
assert set(changed) == {protocol_path, acceptance_path}, changed
print(json.dumps({"identity_only_byte_proof":"PASS","base":BASE,"protocol_sha256":digest(actual),"documents":rows},ensure_ascii=False,indent=2))
