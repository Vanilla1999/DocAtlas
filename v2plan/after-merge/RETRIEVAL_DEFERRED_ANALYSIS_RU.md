# Отложенный разбор retrieval после релиза

Дата: 2026-10-08.

## Решение владельца

Пользователь попросил пока НЕ запускать исправления трёх направлений:
original-only paraphrase, upstream multi-section/long selection и admission
полезных partial facts. Сначала требуется дополнительный разбор в будущем.
Эти работы исключены из текущей implementation wave и записаны в backlog
после релиза. Это не означает, что сценарии исправлены или acceptance пройден.
Не менять gold/thresholds/gates и не объявлять release-ready автоматически:
согласование обещаний выпуска и обязательных acceptance criteria остаётся отдельным.

## Текущее evidence

Исследованная production база: `edf1ced699aea1f8ae28a514bc12962de6aa5d18`.
Диагностика на неизменных исходных EN/RU вопросах и fixture-owned SQLite корпусе.
Отчёт: `/tmp/opencode/docatlas-next-8e38eet1/A-report.md`.
Полные вопросы, fixture hashes, SHA runner и stage traces:
`A-scenario-evidence.json` в той же папке.

| Сценарий EN / RU | Наблюдение | Первая подтверждённая граница потери |
|---|---|---|
| Basic | 4→2 / 4→2 chunks, все 3 required markers сохранены | До final delivery явной потери фактов не найдено; один qualified chunk |
| Original-only paraphrase | 0→0 / 0→0 chunks | Пустое lexical acquisition |
| Multi-section | 4→2 / 4→2 chunks; markers 4→3 / 4→1 | Post-acquisition diversity selection; surviving fragments также unqualified |
| Partial + неизвестный deployment region | 5→3 / 4→2 chunks; известные retry markers 2→2 | Qualification/ranking исключает полезные acquired facts |
| Absent encryption | 3→2 / 0→0 chunks, нет qualified retained result | Final negative delivery не подтверждена |
| Long validation | 36→8 / 28→3 chunks; 120 markers→18 / 7 | Post-acquisition selection, затем qualification |

Explicit lookup отдельно получил EN 44 / RU 4 chunks, но ranking не сохранил
результат. Это не исправление original-only paraphrase и не original credit.

## Граница доказательств

Все 15 diagnostic calls закончились handler_exception на запрещённом private-fixture
Git probe (`git rev-parse --is-inside-work-tree` из impact path). До этой границы
сняты stage traces; успешная доставка и реальные MCP stdio/client сценарии NOT RUN.
Source-change/CAS/revocation final scenarios также не проверены этим run.
Нельзя выдавать stage evidence за доказанное end-to-end качество.

Агент A добавил только guard tests, commit
`b8c589bda7571e2a6ba65fc1a22c49debdfd377d`: 8 новых behavioral controls +
6 прежних bootstrap/confirmation/CAS controls, 14 PASS. Production fixes нет.
Tests подтверждают сохранение уже-qualified windows и отказ forged/unqualified
carriers, а не решение трёх отложенных проблем. Commit ещё требует independent review.

## Что исследовать перед будущей реализацией

1. Paraphrase: существующий FastEmbed/dense backend, cold member configuration,
   offline readiness и подходящий RU/EN model artifact. Векторы не объявлены
   обязательным решением; downloads/provisioning требуют отдельного разрешения.
2. Multi-section/long: классификация `_limit_sections_per_source`, source diversity
   и global acquisition/work bounds. Backfill уже-acquired overflow — только
   гипотеза, не согласованный fix и не гарантия полноты при exhausted global limit.
3. Partial: общий явный relevance/admission контракт для полезных source-bound
   fragments без qualification/answer/edit promotion. Dormant `need_context`
   fallback остаётся отключённым; его прежнее proposal было rejected.
4. Настоящий transport: разрешённые конкретные server/Git descendants, private
   storage, verified imports и отсутствие provider/download/user-index effects.

Будущие критерии: неизменные RU/EN original-only вопросы; несколько необходимых
разделов, точный длинный хвост, честные missing facts; unrelated/absent negatives;
source/catalog/hash/span/current/consent integrity; no answer/edit authority.
Не добавлять словари, скрытые aliases/переводы, case-specific rewrites, scoring
tuning или снижение qualification thresholds ради PASS.

## Статус

DEFERRED — анализ и реализация после релиза по новому разрешению владельца.
Не запускать fixes или новые retrieval pilots автоматически в текущей волне.
Output-cap removal, test successors и schema/client work продолжаются отдельно.
