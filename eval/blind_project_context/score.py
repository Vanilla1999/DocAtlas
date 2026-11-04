"""Score a run.py output directory; write score.json, report.md, holdout-details.md.

    python eval/blind_project_context/score.py OUT

Per case: which gold facts the delivered rows contain, whether every fact was
delivered, the rank of the first row with a fact, how many distinct words of
the question (and of search_question) also occur in the gold quotes and in the
drawn section, and which limits were reached.

A fact counts as delivered when the character span of one of its audited
occurrences (witness-audit.json) is covered by the union of the delivered
rows' spans in that document. Every row is placed by locating its exact text
inside its own cited lines; long lines arrive as several windows, so a quote
may straddle two adjacent rows. A row whose text occurs more than once inside
its cited lines has no unique place: it only counts when the verdict does not
depend on where it sits, otherwise the case gets an anomaly. Rows with equal
path and lines are ordered by generation-bound refs, which differ between
preparations, so a row's rank is the first position of its equal-lines block.

Limits:

* delivery: ``source_selection.budget_limited`` / ``reference_limited``, rows
  omitted by the output budget, payload status;
* acquisition (observer): an SQL lane returned the 256-candidate ceiling, or
  rows were skipped by the token/byte ceilings;
* discovery (observer): a catalog read was truncated (wall clock or bytes);
  that is an environment failure and makes the run invalid.

Where a missed fact was lost (only when the observer ran with this gold): no
acquired candidate contained the quote, or a candidate did and the fact was
dropped later (joint selection under the output budget, or later checks).

Words are ``\\w+`` runs after casefold: no stopword list, stemming or other
dictionary, so function words count too and are listed explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from corpus import build, documents  # noqa: E402
from docmancer.docs.application.context_assembly import decode_context  # noqa: E402
from docmancer.docs.application.section_compression import expand_sections  # noqa: E402

SPLITS = ("dev", "holdout")
CORPORA = ("L0", "L2")
LANGS = ("ru", "en")
WORD = re.compile(r"\w+")


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def words(text: str) -> set[str]:
    return set(WORD.findall(text.casefold()))


def overlap(question: str | None, answer: str, section: str) -> dict | None:
    if not question:
        return None
    terms = words(question)
    shared = sorted(terms & words(answer))
    return {"question_words": len(terms), "answer_overlap": len(shared), "answer_words": shared,
            "section_overlap": len(terms & words(section))}


def placements(text: str | None, line_start: int, line_end: int, needle: str) -> list[tuple[int, int]]:
    """Every character span of ``needle`` inside lines line_start..line_end (1-based, inclusive)."""
    if text is None or not needle:
        return []
    lines = text.splitlines(keepends=True)
    if not 1 <= line_start <= line_end <= len(lines):
        return []
    low = sum(len(line) for line in lines[:line_start - 1])
    region = "".join(lines[line_start - 1:line_end])
    spans, at = [], region.find(needle)
    while at >= 0:
        spans.append((low + at, low + at + len(needle)))
        at = region.find(needle, at + 1)
    return spans


def covers(intervals: list[tuple[int, int]], span: tuple[int, int]) -> bool:
    """True when the union of half-open ``intervals`` contains all of ``span``."""
    reach = span[0]
    for start, end in sorted(intervals):
        if start > reach:
            break
        reach = max(reach, end)
        if reach >= span[1]:
            return True
    return False


def rows_of(payload: dict) -> list[dict]:
    if not payload.get("sources"):
        return []
    if payload.get("context_format"):
        return [{"path": row["path"], "line_start": row["line_start"], "line_end": row["line_end"],
                 "text": row["text"]} for row in decode_context(payload).get("sources", [])]
    return [{"path": row.get("path_or_url"), "line_start": row.get("line_start"),
             "line_end": row.get("line_end"), "text": row.get("snippet") or row.get("text") or ""}
            for row in expand_sections(payload).get("sources", [])]


def limits(payload: dict, events: list[dict], documents_expected: int) -> dict:
    selection = payload.get("source_selection") or {}
    acquisitions = [event for event in events if event.get("event") == "acquisition"]
    reads = [event for event in events if event.get("event") == "catalog_read"]
    delivery = {key: selection.get(key) for key in ("budget_limited", "reference_limited", "candidate_rows",
                                                    "eligible_rows", "selected_rows", "omitted_rows")}
    delivery["status"] = payload.get("status")
    acquisition = {
        "lanes": len(acquisitions),
        "sql_rows": [event.get("sql_rows", 0) for event in acquisitions],
        "ceiling_lanes": sum(1 for event in acquisitions
                             if event.get("sql_rows", 0) >= event.get("candidate_ceiling", 256)),
        "resource_skipped_rows": sum(int(event.get("resource_skipped_rows") or 0) for event in acquisitions),
    }
    discovery = {"catalog_reads": len(reads),
                 "truncated": any(event["truncation_warnings"] or event["candidates"] < documents_expected
                                  for event in reads)}
    reached = []
    if delivery["budget_limited"]:
        reached.append("output_budget")
    if delivery["reference_limited"]:
        reached.append("reference_limit")
    if acquisition["ceiling_lanes"]:
        reached.append("candidate_ceiling")
    if acquisition["resource_skipped_rows"]:
        reached.append("acquisition_resource_ceiling")
    if discovery["truncated"]:
        reached.append("discovery_truncated")
    return {"reached": reached, "delivery": delivery, "acquisition": acquisition, "discovery": discovery}


def score_case(case: dict, record: dict | None, out: Path, topic: dict, gold: dict, audit: dict,
               docs: dict[str, str], observed: bool, ranked: bool = False) -> dict:
    section = "\n".join(docs[topic["path"]].splitlines()[topic["line_start"] - 1:topic["line_end"]])
    answer = "\n".join(fact["quote"] for fact in gold["facts"])
    result = {"case_id": case["id"], "topic_id": case["topic_id"], "split": case["split"], "lang": case["lang"],
              "question": case["question"], "search_question": case.get("search_question"),
              "overlap": {"question": overlap(case["question"], answer, section),
                          "search_question": overlap(case.get("search_question"), answer, section)},
              "anomalies": []}
    if record is None:
        result.update(facts=[], facts_found=0, facts_total=len(gold["facts"]), all_found=False)
        result["anomalies"].append("missing_record")
        return result
    text = (out / record["payload"]).read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
        rows = rows_of(payload)
    except (ValueError, KeyError, TypeError):
        payload, rows = {}, []
        result["anomalies"].append("unparsable_payload")
    if record["is_error"]:
        result["anomalies"].append("mcp_is_error")
    sure: dict[str, list[tuple[int, int]]] = defaultdict(list)
    maybe: dict[str, list[tuple[int, int]]] = defaultdict(list)
    placed: list[list[tuple[int, int]]] = []
    block: dict[tuple, int] = {}
    for index, row in enumerate(rows, start=1):
        block.setdefault((row["path"], row["line_start"], row["line_end"]), index)
        spots = placements(docs.get(row["path"]), row["line_start"], row["line_end"], row["text"])
        placed.append(spots)
        if not spots:
            result["anomalies"].append(f"row_not_verbatim:{row['path']}:{row['line_start']}-{row['line_end']}")
        elif len(spots) == 1:
            sure[row["path"]].append(spots[0])
        maybe[row["path"]].extend(spots)
    facts = []
    for fact in gold["facts"]:
        spans = []
        for place in audit[fact["fact_id"]]:
            found_here = placements(docs.get(place["path"]), place["line_start"], place["line_end"], fact["quote"])
            if not found_here:
                result["anomalies"].append(f"audit_occurrence_missing:{fact['fact_id']}")
            spans += [(place["path"], span) for span in found_here]
        covered = [(path, span) for path, span in spans if covers(sure[path], span)]
        if bool(covered) != any(covers(maybe[path], span) for path, span in spans):
            result["anomalies"].append(f"ambiguous_row_placement:{fact['fact_id']}")
        first = min((block[(row["path"], row["line_start"], row["line_end"])]
                     for path, span in covered for row, spots in zip(rows, placed)
                     if row["path"] == path and any(a < span[1] and span[0] < b for a, b in spots)), default=None)
        whole = any(row["path"] == path and any(a <= span[0] and span[1] <= b for a, b in spots)
                    for path, span in covered for row, spots in zip(rows, placed))
        facts.append({"fact_id": fact["fact_id"], "found": bool(covered), "first_row": first,
                      "in_one_row": whole if covered else None})
    acquisitions = [event for event in record["observer_events"] if event.get("event") == "acquisition"]
    for fact in facts:
        ranks = [event["fact_ranks"][fact["fact_id"]] for event in acquisitions
                 if fact["fact_id"] in (event.get("fact_ranks") or {})] if ranked else []
        fact["candidate_rank"] = min(ranks, default=None) if ranked else None
        fact["in_candidates"] = bool(ranks) if ranked else None
    result["lost"] = {"not_acquired": [fact["fact_id"] for fact in facts
                                       if not fact["found"] and fact["in_candidates"] is False],
                      "dropped_after_acquisition": [fact["fact_id"] for fact in facts
                                                    if not fact["found"] and fact["in_candidates"]]
                      } if ranked else None
    found = sum(fact["found"] for fact in facts)
    result.update(facts=facts, facts_found=found, facts_total=len(facts), all_found=found == len(facts),
                  first_fact_row=min((fact["first_row"] for fact in facts if fact["found"]), default=None),
                  rows=len(rows), paths=len({row["path"] for row in rows}),
                  rows_sha256=hashlib.sha256(json.dumps(sorted(
                      (row["path"], row["line_start"], row["line_end"], row["text"]) for row in rows),
                      ensure_ascii=False).encode("utf-8")).hexdigest(),
                  drawn_section_rows=sum(1 for row in rows if row["path"] == topic["path"]
                                         and row["line_start"] <= topic["line_end"]
                                         and topic["line_start"] <= row["line_end"]),
                  utf8_bytes=record["utf8_bytes"], seconds=record["seconds"])
    if observed:
        result["limits"] = limits(payload, record["observer_events"], len(docs))
        if result["limits"]["discovery"]["truncated"]:
            result["anomalies"].append("discovery_truncated")
    else:
        result["limits"] = limits(payload, [], len(docs))
    return result


def summarize(cases: list[dict]) -> dict:
    lost = [case.get("lost") for case in cases]
    known = all(item is not None for item in lost)
    return {"cases": len(cases), "facts_found": sum(case["facts_found"] for case in cases),
            "lost_not_acquired": sum(len(item["not_acquired"]) for item in lost) if known else None,
            "lost_after_acquisition": sum(len(item["dropped_after_acquisition"]) for item in lost) if known else None,
            "facts_total": sum(case["facts_total"] for case in cases),
            "all_found": sum(case["all_found"] for case in cases),
            "limit_reached": sum(bool(case.get("limits", {}).get("reached")) for case in cases),
            "output_budget": sum("output_budget" in case.get("limits", {}).get("reached", ()) for case in cases),
            "candidate_ceiling": sum("candidate_ceiling" in case.get("limits", {}).get("reached", ()) for case in cases),
            "seconds": round(sum(case.get("seconds") or 0 for case in cases), 1)}


def score(out: Path) -> dict:
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    questions = load("questions.json")["cases"]
    topics = {topic["topic_id"]: topic for topic in load("topics.json")["topics"]}
    oracle = {topic["topic_id"]: topic for topic in load("oracle.json")["topics"]}
    audit_doc = load("witness-audit.json")
    if run["questions_sha256"] != hashlib.sha256((HERE / "questions.json").read_bytes()).hexdigest():
        raise RuntimeError("run used different questions")
    # Payloads never depend on the gold; the gold is bound here, at scoring.
    oracle_sha256 = hashlib.sha256((HERE / "oracle.json").read_bytes()).hexdigest()
    if oracle_sha256 != audit_doc["oracle_sha256"]:
        raise RuntimeError("witness-audit.json is stale: run audit.py")
    records = {(record["corpus"], record["case_id"]): record for record in run["records"]}
    # Candidate ranks of gold quotes exist only when the observer had this gold.
    ranked = bool(run["observer"]) and run.get("observer_oracle_sha256") == oracle_sha256 and all(
        "fact_ranks" in event for record in run["records"] for event in record["observer_events"]
        if event.get("event") == "acquisition")
    selected = set(run["selected_cases"])
    with TemporaryDirectory() as tmp:
        corpora = {name: documents(project) for name, project in build(Path(tmp)).items()}
    results = []
    for corpus in run["corpora"]:
        audit = {fact["fact_id"]: fact["occurrences"][corpus] for fact in audit_doc["facts"]}
        for case in questions:
            if case["id"] not in selected:
                continue
            item = score_case(case, records.get((corpus, case["id"])), out, topics[case["topic_id"]],
                              oracle[case["topic_id"]], audit, corpora[corpus], run["observer"], ranked)
            results.append({"corpus": corpus, **item})
    slices = defaultdict(list)
    for item in results:
        slices[f"{item['split']}/{item['corpus']}/{item['lang']}"].append(item)
    return {"schema_version": 2, "questions_sha256": run["questions_sha256"], "oracle_sha256": oracle_sha256,
            "source_tree": run["source_tree"], "server_environment": run["server_environment"],
            "observer": run["observer"], "candidate_ranks": ranked, "wall_seconds": run["wall_seconds"],
            "run": {key: run.get(key) for key in ("started_at_utc", "eval_tree", "python", "platform", "cpus", "jobs",
                                                  "work_root", "project_config", "units")},
            "anomalies": sorted({f"{item['corpus']}/{item['case_id']}:{anomaly}"
                                 for item in results for anomaly in item["anomalies"]}),
            "slices": {key: summarize(value) for key, value in sorted(slices.items())},
            "cases": results}


def _words(item: dict | None) -> str:
    if not item:
        return "—"
    shown = ", ".join(item["answer_words"]) if item["answer_words"] else ""
    return f"{item['answer_overlap']}/{item['question_words']} (раздел {item['section_overlap']})" + (f": {shown}" if shown else "")


def _limits(item: dict) -> str:
    limit = item.get("limits") or {}
    delivery, acquisition = limit.get("delivery", {}), limit.get("acquisition", {})
    parts = []
    if "output_budget" in limit.get("reached", ()):
        parts.append(f"бюджет выдачи (отброшено {delivery.get('omitted_rows')} из {delivery.get('eligible_rows')})")
    if "candidate_ceiling" in limit.get("reached", ()):
        parts.append(f"потолок 256 в {acquisition.get('ceiling_lanes')}/{acquisition.get('lanes')} SQL-запросах")
    if "acquisition_resource_ceiling" in limit.get("reached", ()):
        parts.append(f"ресурсный потолок ({acquisition.get('resource_skipped_rows')} строк)")
    if "reference_limit" in limit.get("reached", ()):
        parts.append("лимит ссылок")
    if "discovery_truncated" in limit.get("reached", ()):
        parts.append("ОБРЕЗАНО обнаружение каталога")
    return "; ".join(parts) or "нет"


def _facts(item: dict) -> str:
    split = sum(1 for fact in item.get("facts", ()) if fact["found"] and not fact["in_one_row"])
    return f"{item['facts_found']}/{item['facts_total']}" + (f" ({split} по частям)" if split else "")


def _lost(item: dict) -> str:
    lost = item.get("lost")
    if lost is None:
        return "н/д" if item["facts_found"] < item["facts_total"] else "—"
    short = lambda ids: ",".join(fact_id.split(".", 1)[1] for fact_id in ids)
    parts = []
    if lost["not_acquired"]:
        parts.append(f"нет в кандидатах: {short(lost['not_acquired'])}")
    if lost["dropped_after_acquisition"]:
        parts.append(f"отброшены после выборки: {short(lost['dropped_after_acquisition'])}")
    return "; ".join(parts) or "—"


def _case_table(cases: list[dict]) -> list[str]:
    lines = ["| Случай | Корпус | Факты | Где потеряны | 1-я строка с фактом | Слова вопроса в ответе | Слова search_question в ответе | Лимиты | Строк | Сек |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for item in cases:
        lines.append(f"| {item['case_id']} | {item['corpus']} | {_facts(item)} | {_lost(item)} | "
                     f"{item.get('first_fact_row') or '—'} | {_words(item['overlap']['question'])} | "
                     f"{_words(item['overlap']['search_question'])} | {_limits(item)} | {item.get('rows', 0)} | "
                     f"{item.get('seconds', 0):.0f} |")
    return lines


def _slice_table(slices: dict) -> list[str]:
    lines = ["| Срез | Случаев | Факты | Все факты | Потеряно: нет в кандидатах | Потеряно: после выборки | Упёрлись в лимит | Бюджет выдачи | Потолок 256 |",
             "|---|---|---|---|---|---|---|---|---|"]
    shown = lambda value: "н/д" if value is None else value
    for key, value in slices.items():
        lines.append(f"| {key} | {value['cases']} | {value['facts_found']}/{value['facts_total']} | "
                     f"{value['all_found']}/{value['cases']} | {shown(value['lost_not_acquired'])} | "
                     f"{shown(value['lost_after_acquisition'])} | {value['limit_reached']} | {value['output_budget']} | "
                     f"{value['candidate_ceiling']} |")
    return lines


def _machine(run: dict) -> str:
    prepare = {}
    for unit in run.get("units") or ():
        prepare.setdefault(unit["corpus"], []).append(unit["prepare_seconds"])
    config = ((run.get("project_config") or {}).get("docatlas.yaml") or {}).get("project") or {}
    return (f"Машина: {run.get('cpus')} CPU, серверов параллельно: {run.get('jobs')}; подготовка "
            + ", ".join(f"{corpus} {max(values):.1f} с" for corpus, values in sorted(prepare.items()))
            + f"; scan_deadline_seconds: {config.get('scan_deadline_seconds', 'по умолчанию')}.")


def write_reports(result: dict, out: Path) -> None:
    head = ["# Слепой тест контекста проекта", "",
            f"Дерево: `{result['source_tree']['commit']}`" + (" (есть незакоммиченные изменения)" if result['source_tree']['dirty_paths'] else ""),
            f"Время прогона: {result['wall_seconds']} с. Наблюдатель: {'да' if result['observer'] else 'нет'}.",
            _machine(result.get("run") or {}),
            "", "Слова — различные `\\w+` после casefold, без словарей; служебные слова тоже считаются.",
            "«Раздел» — сколько слов вопроса есть во всём разыгранном разделе (с заголовком).", ""]
    if result["anomalies"]:
        head += ["**Аномалии (прогон недействителен для сравнения):**", ""] + [f"- {item}" for item in result["anomalies"]] + [""]
    dev = [item for item in result["cases"] if item["split"] == "dev"]
    report = head + ["## Срезы", ""] + _slice_table(result["slices"]) + ["", "## Dev: по вопросам", ""] + _case_table(dev)
    report += ["", "Подробности holdout — в `holdout-details.md`; их не используют для подбора изменений."]
    (out / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    holdout = [item for item in result["cases"] if item["split"] == "holdout"]
    details = ["# Holdout: по вопросам", "", "Не использовать для подбора изменений: только для проверки уже готового изменения.", ""]
    (out / "holdout-details.md").write_text("\n".join(details + _case_table(holdout)) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    result = score(args.out.resolve())
    (args.out / "score.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_reports(result, args.out)
    for key, value in result["slices"].items():
        print(key, f"facts {value['facts_found']}/{value['facts_total']}", f"all {value['all_found']}/{value['cases']}",
              f"limit {value['limit_reached']}")
    if result["anomalies"]:
        print("ANOMALIES:", *result["anomalies"][:20], sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
