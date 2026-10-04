# Авторское review до native run

Code revision: 4b37ba3a6fc1b5314f25f7ea26a55e5ea3341581.
Это авторская проверка, не независимый внешний аудит.

## Проверенные границы

- call_docs_tool_payload заканчивается compact_mcp_payload; _mcp_tool_result
  вызывает тот же compactor повторно. Исправление общего consumer покрывает обе
  точки без monkeypatch handler/SDK. _run_async использует asyncio.to_thread;
  caller policy должна охватывать весь вызов, включая упаковку SDK.
- Для canonical kind ни include_sections, ни page/page_size не могут обрезать
  поля уже согласованного DTO. Все поля сохраняются, а не только snippet:
  estimates/coverage/source_uri/support decisions также связаны с payload.
- При finite transport cap failure новый и самостоятельный; источники, hashes
  и прежнее answer/edit разрешение не копируются. Tiny-cap ValueError явный.
- Источник не задаёт policy: читается ContextVar, и только для docs_context.
  В отсутствие trusted policy docs_context остаётся под32KB; docs_answer,
  patch_context и administrative output не получают unlimited от read policy.
- Explicit positive integer max_bytes всегда приоритетнее caller policy.
- None — отсутствие предела в policy, не большое sentinel-число. Default None
  аргумент функции означает выбор trusted/default policy, а не автоматическую отмену.
- Закрытые source guards, parser/owner, read_decision, first_fit, SDK/dispatcher,
  evaluator/corpus/labels и scope wiring не изменены. Сравнение git подтвердило
  только два runtime файла. По AST в output_contract изменён только
  compact_mcp_payload; остальные функции generic compaction совпадают.
- В прежнем compact test изменены ровно2 строки: перечень валидируемых полей
  internal dataclass и asdict expected shape. Прежние semantic checks сохранены.
- Copy mismatch промежуточной неприкреплённой tree исправлен до code commit;
  committed test blob f1da670910317048d035f84cff76d2c14a8d69b5 совпадает с локальным.

## Локальное исполнение

29 transport unit PASS,6 SDK/native cases пока deselected из-за отсутствия
полного local checkout. Настоящие transport/policy definitions без read spies.
Старый compactor на неизменном12-source packet сохранял8 sources и менял8 цитат.
Новый default даёт transport_size_limit; COMPACT сохраняет весь packet.
Это не evidence по80 native вопросам, не gate source eligibility.

## Freeze SHA-256 для следующего workflow

- docmancer/docs/interfaces/mcp/output_contract.py:
  e2849ce892175fc0237126d623a9a144a92ddeee6a1964d3fb9eed27f9f41432
- docmancer/docs/domain/read_delivery_limits.py:
  f65b1f8faff06f29f654d381acef04b26d7ed44cf6307c707ea96dad304f9bf1
- v2plan/test_next07_compact_delivery.py:
  38d3cc35d1adf20f5c3ff0ba1df9f13426eaf89d1973068f41fe97b0bc1e134b
- v2plan/test_next07_transport_integrity.py:
  21752376fa7a81c1c57ada41177ac3a58343be23caf72e4f58b7349ed2119347

## Оставшиеся риски и предел вывода

Выдача может стать длинной. Не вводим новый quality threshold, не обещаем
минимальность контекста. Resource/read caps не повышены. Внешний реальный SDK,
host/context-window или network limit может привести к explicit failure;
универсальная способность отправить любой объём не заявляется.
Transport не доказывает применимость цитаты, он не должен её менять.
SDK JSON roundtrip не называется live stdio/network session. Настоящий replay
через handler плюс terminal SDK-аудит нужен до TRANSPORT_VALIDATED.
N10 не правится/не запускается. Historical partial retention без отдельного
ledger не считается проверенной. Полный rollout и product acceptance вне этапа.

Review result: READY_FOR_DECLARED_NATIVE_RUN, не DONE.
