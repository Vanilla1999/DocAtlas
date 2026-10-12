"""Read-only historical V40 source-span scoring; model and selection code are never imported."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median

HERE=Path(__file__).resolve().parents[1]/"prepared_model_comparison40"
MODES=("legacy","prepared_parent_v1")

def get(path): return json.loads(path.read_text(encoding="utf-8"))

def returned_spans(payload,root,docs):
    spans={};errors=[]
    for row in payload.get("sources") or ():
        try:
            supplied = Path(row["path_or_url"])
            if ".." in supplied.parts:
                raise ValueError("source path traversal")
            path = (supplied.relative_to(root).as_posix() if supplied.is_absolute()
                    else supplied.as_posix())
        except (KeyError, ValueError):
            errors.append("source_path_not_bound")
            continue
        raw=docs.get(path);text=row.get("snippet") or ""
        if raw is None or not text: errors.append("source_or_text_missing");continue
        lines=raw.splitlines(keepends=True); offsets=[0]
        for line in lines: offsets.append(offsets[-1]+len(line))
        a,b=row.get("line_start"),row.get("line_end")
        if type(a)!=int or type(b)!=int or not 1<=a<=b<=len(lines):
            errors.append("invalid_line_range");continue
        begin,finish=offsets[a-1],offsets[b]
        hits=[];pos=begin
        while pos<=finish-len(text):
            found=raw.find(text,pos,finish)
            if found<0: break
            hits.append((found,found+len(text)));pos=found+1
        if len(hits)!=1:
            errors.append("ambiguous_or_missing_exact_source_occurrence");continue
        spans.setdefault(path,[]).append(hits[0])
    return spans,errors

def claim_delivered(claim,spans,docs):
    for witness in claim.get("witness_sets") or ():
        parts=witness.get("parts") or ()
        if not parts:continue
        all_parts=True
        for part in parts:
            raw=docs.get(part["path"])
            if raw is None: all_parts=False;break
            lines=raw.splitlines(keepends=True);offsets=[0]
            for line in lines:offsets.append(offsets[-1]+len(line))
            a,b=part["line_start"],part["line_end"]
            if not 1<=a<=b<=len(lines):all_parts=False;break
            start,end=offsets[a-1],offsets[b]
            while start<end and raw[start].isspace():start+=1
            while end>start and raw[end-1].isspace():end-=1
            cursor=start
            for left,right in sorted(spans.get(part["path"],[])):
                if left>cursor:break
                cursor=max(cursor,right)
            if cursor<end:all_parts=False;break
        if all_parts:return True
    return False

def trace_summary(path):
    reasons=Counter();stages=Counter()
    for line in path.read_text(encoding="utf-8",errors="replace").splitlines():
        try: obj=json.loads(line)
        except ValueError: continue
        todo=[obj]
        while todo:
            value=todo.pop()
            if isinstance(value,list):todo.extend(value)
            elif isinstance(value,dict):
                if isinstance(value.get("stage"),str):stages[value["stage"]]+=1
                if isinstance(value.get("reason"),str):reasons[value["reason"]]+=1
                todo.extend(x for x in value.values() if isinstance(x,(dict,list)))
    return dict(reasons.most_common(8)),dict(stages.most_common(12))

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run-dir",type=Path,required=True)
    run=parser.parse_args().run_dir
    cases=get(HERE/"questions.json")["cases"]
    gold={row["id"]:row for row in get(HERE/"gold_spans.json")["cases"]}
    families=get(HERE/"source_plan.json")["families"]
    docs={f["id"]:{name:(HERE/"sources"/f["id"]/name).read_text(encoding="utf-8")
                   for name in f["paths"]} for f in families}
    roots={f["id"]:Path(get(run/"preparation"/(f["id"]+".json"))["root"]) for f in families}
    stats={m:Counter() for m in MODES};times={m:[] for m in MODES};records=[]
    for case in cases:
        item={"id":case["id"],"question":case["question"],
              "family":case["project_group"],"answerability":case["answerability"],
              "expected_response":gold[case["id"]]["expected_response"],"arms":{}}
        for mode in MODES:
            location=run/"calls"/case["id"]/mode
            payload=get(location/"public-payload.json");meta=get(location/"metadata.json")
            spans,errors=returned_spans(payload,roots[case["project_group"]],docs[case["project_group"]])
            required=[c for c in gold[case["id"]]["required_claims"] if c.get("witness_sets")]
            missing=[c["id"] for c in required if not claim_delivered(c,spans,docs[case["project_group"]])]
            cls=gold[case["id"]]["expected_response"]
            success=not payload.get("sources") if cls=="abstention_or_clarification" else not missing
            reasons,stages=trace_summary(location/"trace.jsonl")
            item["arms"][mode]={
                "pass":success,"missing_claims":missing,
                "source_count":len(payload.get("sources") or ()),
                "source_integrity_observations":errors,
                "elapsed_seconds":meta["elapsed_seconds"],
                "within_cap":meta.get("within_wire_budget"),
                "trace_reasons":reasons,"trace_stages":stages}
            stats[mode][cls+"_total"]+=1;stats[mode][cls+"_pass"]+=int(success)
            stats[mode]["source_rows"]+=len(payload.get("sources") or ())
            stats[mode]["ambiguous_or_invalid_citations"]+=len(errors)
            times[mode].append(meta["elapsed_seconds"])
        a=item["arms"][MODES[0]]["pass"];b=item["arms"][MODES[1]]["pass"]
        item["change"]="gain" if b and not a else "loss" if a and not b else "both_pass" if a else "both_fail"
        records.append(item)
    totals={m:{**dict(stats[m]),"median_latency_seconds":median(times[m])} for m in MODES}
    changes=dict(Counter(r["change"] for r in records))
    result={"schema_version":1,"comparison":"historical V40, pre-generator raw evidence delivery",
            "model_calls":0,"total_questions":40,"totals":totals,"paired":changes,"cases":records}
    (run/"ANALYSIS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# V40: legacy vs prepared-parent assembly","",
           "Historical exposed questions. A PASS is delivery of all frozen witness spans,",
           "not a correct generated answer. The baseline and new arm use the same native top-2.",
           "","## Totals",""]
    for mode in MODES:lines.append(f"- {mode}: {totals[mode]}")
    lines+=["",f"Paired changes: {changes}","","## All failures or differences",""]
    for row in records:
        if row["change"]=="both_pass":continue
        lines.append(f"### {row['id']} — {row['change']}")
        lines.append(row["question"])
        for m in MODES:
            z=row["arms"][m]
            lines.append(f"- {m}: {'PASS' if z['pass'] else 'FAIL'}, missing={z['missing_claims']}, sources={z['source_count']}, reasons={z['trace_reasons']}")
        lines.append("")
    lines+=["## Limits","",
            "Strict source-span coverage does not certify semantic entailment or generated answers.",
            "The diagnostic reason histogram is not itself a causal attribution.",
            "The corpus is historical/exposed and is not an independent holdout.",""]
    (run/"REPORT_RU.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"totals":totals,"paired":changes},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
