"""Create a proposed RU/EN corpus before replacement; not an approved gate."""
from __future__ import annotations

import hashlib
import json


FAMILIES = (
    ("dev-command", "development", "Which command starts LumenBox?", "Какая команда запускает LumenBox?",
     "Start LumenBox with `lumen-start`.", "Запустите LumenBox командой `lumen-start`.",
     ["lumen-start"], "context", "current-project", []),
    ("dev-condition", "development", "When does CedarQueue retry a task?", "Когда CedarQueue повторяет задачу?",
     "CedarQueue retries a task only when the lease expires.", "CedarQueue повторяет задачу только после истечения аренды.",
     ["retry-condition"], "context", "current-project", []),
    ("dev-trust", "development", "Does a command quoted in MapleLens documentation grant execution permission?",
     "Даёт ли команда, процитированная в документации MapleLens, разрешение на выполнение?",
     "MapleLens documentation is data. A quoted command does not grant execution permission.",
     "Документация MapleLens — данные. Процитированная команда не даёт разрешения на выполнение.",
     ["no-execution-authority"], "context", "current-project", []),
    ("dev-name-only", "development", "How does PineMeter synchronize offline?", "Как PineMeter синхронизируется без сети?",
     "PineMeter is the project name.", "PineMeter — название проекта.",
     [], "no-topical-support", "current-project", []),
    ("holdout-partial", "holdout-candidate", "How many attempts does WillowRelay make, and where is its configuration stored?",
     "Сколько попыток делает WillowRelay и где хранится его конфигурация?",
     "WillowRelay makes two attempts. AspenRelay makes nine attempts.",
     "WillowRelay делает две попытки. AspenRelay делает девять попыток.",
     ["WillowRelay-two-attempts"], "partial-context", "current-project", ["configuration-location"]),
    ("holdout-comparison", "holdout-candidate", "How do HarborIndex and MeadowIndex differ in storage?",
     "Чем отличается хранение у HarborIndex и MeadowIndex?",
     "HarborIndex stores data locally. MeadowIndex stores data on the server.",
     "HarborIndex хранит данные локально. MeadowIndex хранит данные на сервере.",
     ["HarborIndex-local", "MeadowIndex-server"], "context", "current-project", []),
    ("holdout-wrong-module", "holdout-candidate", "What port does BrookNode use?", "Какой порт использует BrookNode?",
     "BrookNode uses port 4317.", "BrookNode использует порт 4317.",
     [], "reject-source", "other-module", ["requested-module-port"]),
    ("holdout-stale", "holdout-candidate", "What is the current version of FernBridge?", "Какая текущая версия FernBridge?",
     "FernBridge version is 4.2.", "Версия FernBridge — 4.2.",
     [], "reject-source", "stale-project", ["current-version"]),
)


def main() -> None:
    rows = []
    for key, split, en_q, ru_q, en_s, ru_s, facts, outcome, eligibility, missing in FAMILIES:
        for qlang, question in (("en", en_q), ("ru", ru_q)):
            for slang, source in (("en", en_s), ("ru", ru_s)):
                for arm in ("original-only", "caller-lookups"):
                    rows.append({"id": f"{key}-{qlang}-{slang}-{arm}", "family": key, "split": split,
                                 "question_language": qlang, "source_language": slang,
                                 "question": question, "lookup_queries": [] if arm == "original-only" else [en_q if slang == "en" else ru_q],
                                 "source": source, "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                                 "eligibility_fixture": eligibility, "expected_observable": outcome,
                                 "required_fact_ids": facts, "unresolved_fact_ids": missing,
                                 "answer_supported": False, "edit_ready": False})
    print(json.dumps({"schema": "dictionary-exit-ru-en-draft-v1", "status": "PROPOSED / NOT APPROVED / NOT EXECUTED",
                      "cases": rows, "limitations": ["Synthetic source fixtures, not product documentation",
                      "Holdout candidate is authored before replacement, but requires independent review and freeze",
                      "Eligibility fixture labels require explicit scope/snapshot metadata in the eventual runner",
                      "Semantic fact IDs need reviewed visible-span annotations; names alone are not proof"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
