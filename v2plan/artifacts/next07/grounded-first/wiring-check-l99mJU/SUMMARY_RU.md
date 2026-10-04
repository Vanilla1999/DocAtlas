# I.4 VALIDATED_LOCAL; I.5 / I.6 REJECTED на frozen N10

## Baseline и исполнения

Branch `next07-feasibility-audit`; HEAD `ed3ec41b` поверх `0f4b5847`.
Полный dirty patch — `baseline.patch`, HEAD — `commit.txt`. Посторонняя работа
сохранена. Candidate `b6e890b6` не менялся; prepared/first_fit и runtime не менялись.
Новый research runner `v2plan/next07_grounded_public_controls.py` исполняет
существующий N10, не новый evaluator. Его protocol записан до public calls.
53-PASS evidence ранее проверено; повтор не выполнялся.

Новые wiring tests: 26 PASS, `unit.log` / `unit.xml`, exit 0.
Команда: `DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q
v2plan/test_next07_grounded_public_wiring.py --junitxml=<OUT>/unit.xml`.

Native команда: `DOCATLAS_OFFLINE=1 .venv/bin/python -m
v2plan.next07_grounded_final_run --out <OUT>/native`.
Exit 0, stdout `native.log`, exact verdict `native/result.json`.
OUT — этот каталог. Для каждого case сохранены свежие N/C public captures,
snapshot/projection attempts и actual-call trace. Temporary state DB не включаются
в коммит. G не перезапускался: reference artifact hashes совпали (`integrity.json`).

## I.4: настоящий MCP final packet

| Case | Фактически доставленные factual snippets | Final whole-DTO cost | Sources |
|---|---|---:|---:|
| P1 | `# LeaseClient\n\nAn expired operation raises \`LeaseExpired\`.` и `# LeaseClient\n\nThe default timeout is 17 seconds.` | 589 | 3 |
| P2 | `# LeaseClient\n\nAn expired operation raises \`WaitExpired\`.` и `# LeaseClient\n\nThe default timeout is 29 seconds.` | 613 | 3 |
| P3 | `# LeaseClient\n\nThe default timeout is 17 seconds.`; exception отсутствует | 443 | 2 |

P1/P2 также включают original overview. Handler validator и packer validator
без ошибок; exact original bytes, owner/condition и binding проверены runner.
`answer_supported=False`, `answer_available=False`, `edit_ready=False`,
retrieval_only. Hooks восстановлены. Это local I.4, не общая приёмка всех routes.

## I.5: первый содержательный failure

Command: `DOCATLAS_OFFLINE=1 .venv/bin/python -m
v2plan.next07_grounded_public_controls --out <OUT>/controls-N10`.
Exit **1**, stdout `controls-N10.log`, protocol/results и N/C traces в
`controls-N10/`. Expectation заимствовано без изменения из существующего
`test_local_topic_witness_rejects_heading_echo_and_scattered_terms`:
heading-only topic с unrelated prose должен дать empty sources.
Working positive и negative используют один исходный root-only QUESTION
из этого module; expected answers не передаются selection.

Working positive delivered:

```text
# Guide

storage retention behavior is documented in this current guide.
```

Фактически возвращённый negative source:

```text
# Guide

# storage retention behavior

Unrelated network details.
```

Negative public вызов выполнен, real projection reached, handler validator чист,
hooks restored. Packet содержит правильно bound source, но не фактический ответ
на topic. Классификация: **irrelevant context / frozen abstention-policy violation**,
не source forgery и не false applicability credit. Не переименовывается в PASS.
Exact node не входит в frozen policy-delta allowlist (`integrity.json`).

## Итог и NOT_RUN

- I.4 **VALIDATED_LOCAL_I4**.
- I.5 **REJECTED** на mandatory N10.
- I.6 конечный verdict замера **REJECTED**, не READY.
- P1/P2/P3 passed; P4/P5 и остальные N controls NOT_RUN после STOP.
- Fresh retained/lost/gained IDs NOT_RUN; historical 49 retained/lost IDs NOT_RUN;
  ранее полезные partial facts NOT_RUN. P3 target partial — не historical retention.
- Paired 80 replay, focused/gates/full regression NOT_RUN: mandatory control failed.
- Предсуществующие 06 failures не измерены заново и не исправлены; новый
  substantive failure — frozen N10 forbidden packet.
- Candidate/read/retrieval/first_fit/guards/expectations не менялись после failure.
- Unseen/reader и часть II NOT_RUN. Production/main/defaults не менялись.
- Rollout: **NOT_AUTHORIZED**.
