"""Replay 77 real previously recorded MCP contexts under the implicit default.

Supplementary evidence; no paid GPT or live autonomous OpenCode session.
"""
import argparse
import json
import os
from pathlib import Path
import zipfile
from docmancer.docs.application.context_assembly import assemble_context, decode_context
from docmancer.docs.application.model_context_view import canonical
from docmancer.docs.application.projection_tokenizer import projection_token_count

def tok(s):
    return projection_token_count(s.encode())

def run(archive, out):
    assert "DOCATLAS_CONTEXT_ASSEMBLY" not in os.environ
    sums = {"new20":[0,0], "historical57":[0,0]}
    formats = {}
    rows = 0
    def check(base, expected, suite):
        nonlocal rows
        assert canonical(json.loads(base)) == base
        actual = assemble_context(base)
        assert actual == assemble_context(base, policy="adaptive") == expected
        assert assemble_context(base, policy="literal") == base
        unpacked = decode_context(json.loads(actual))
        assert canonical(unpacked) == base
        assert unpacked["notice"] in json.loads(actual)["notice"]
        rows += len(unpacked["sources"])
        fmt = json.loads(actual)["context_format"]
        formats[fmt] = formats.get(fmt, 0)+1
        assert tok(actual) <= tok(base)
        sums[suite][0] += tok(base)
        sums[suite][1] += tok(actual)

    with zipfile.ZipFile(archive) as z:
        new = sorted(n for n in z.namelist() if n.startswith("original/new20/paid-inputs/") and n.endswith("-literal.json"))
        assert len(new) == 20
        for n in new:
            x = json.loads(z.read(n))
            y = json.loads(z.read(n.replace("-literal.json","-adaptive.json")))
            assert x["id"] == y["id"] and x["question"] == y["question"]
            check(x["context"], y["context"], "new20")
        old = sorted(n for n in z.namelist() if n.startswith("recorded58/replies/") and n.endswith("-literal.json"))
        assert len(old) == 57
        for n in old:
            x = canonical(json.loads(z.read(n)))
            y = canonical(json.loads(z.read(n.replace("-literal.json","-adaptive.json"))))
            check(x, y, "historical57")
        denied = canonical(json.loads(z.read("original/new20/literal/black/unavailable.json")))
        assert assemble_context(denied) == denied and not json.loads(denied).get("sources")
        grading = json.loads(z.read("original/new20/RESULT.json"))
        assert all(r["delivered_requirements"] == 43 for r in grading["policies"].values())
    assert sums == {"new20":[24644,22382],"historical57":[62560,56579]}, sums
    assert sum(formats.values()) == 77
    result = {"pass":True,"same_pinned_public_mcp_contexts":77,"roundtrip_source_rows":rows,
              "implicit_equals_explicit_adaptive":True,"literal_rollback":True,
              "denial_untouched":True,"model_view_o200k_tokens":sums,"formats":formats,
              "provider_usage":None,"answer_comprehension":"NOT_TESTED"}
    out.mkdir(parents=True,exist_ok=True)
    (out/"RECORDED.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    x=ap.parse_args()
    run(x.archive,x.out)
