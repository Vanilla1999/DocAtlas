# Итог retrieval ablation: development-фаза завершена

## Проверка перед публикацией экспериментальной ветки

При сохранении результатов 2026-10-01: изменения ограничены experimental harness,
отчётами и tests; `docmancer/`, defaults и lock не изменены. Runtime `docmancer/`
не импортирует `retrieval_ablation`. Публикация ветки не означает merge или активацию.
`git diff --check` прошёл. Свежий запуск шести ablation test modules через системный
`python3` заблокирован на collection: отсутствует `pydantic` (также manifest сообщает
stale modules вследствие collection errors). Это не новый PASS и не заменяет
исторические результаты ниже. Среда и lock ради публикации не изменялись.

Следующая отдельная задача — delivery MkDocs05 и полного Pydantic03 на проверенном
delivery-checkpoint. Это не продолжение ablation и не доказательство выполнения
Evidence Sets T06: сохранённый pool replay — другой этап с тем же номером.

Дата: 2026-10-01. **Это основной итоговый отчёт текущей серии.** Поэтапные
отчёты сохраняются как доказательства; их разделы «следующий эксперимент» не
являются активным планом продолжения.

## 1. Итоговое решение

**Безопасность экспериментального harness улучшена; универсальная замена
retrieval/qualification/packing не обоснована. Production defaults оставить
прежними. Расширение этой development-серии остановить.**

Это ограниченный инженерный вывод, не подтверждение оптимальности текущего
продукта и не полная T12-приёмка исходного плана. Не все T00–T12 выполнены.
Незавершённые проверки не мешают отвергнуть неподтверждённую активацию кандидатов,
но не позволяют объявить их безопасной продуктовой заменой.

Product defaults, публичная MCP-схема, `uv.lock`, P0/frozen-v3 и MPNet threshold
не менялись. Push, merge и активация не выполнялись. Последние реализации остаются
локальными изменениями поверх HEAD `39347d29`; это не опубликованный релиз.

## 2. Решения по компонентам

| Компонент | Решение | Основание и граница |
|---|---|---|
| Source/project/version/stale/unsafe/canonical/reference/authorization защиты | **ОСТАВИТЬ** | Не являются мягкой релевантностью. Их нельзя снимать вместе с overlap/ratio правилами. |
| Исправления допуска соседей в harness | **ОСТАВИТЬ В HARNESS** | Закрыты возврат unsafe-соседа и несогласованные version/heading claims; replay повторно проверяет snapshot и admission. Это не разрешение переносить весь packer в production. |
| Текущий P и production ratio | **ОСТАВИТЬ** | Ratio removal возвращает полезный контекст, но добавляет unsupported admission. Глобальное удаление не оправдано. |
| Ошибки Markdown ownership | **ИСПРАВЛЯТЬ ОТДЕЛЬНО** | Setext и ложные headings в code/HTML/quotes имеют проверяемый структурный дефект. Исправление parser не следует объединять с новым ranking или снижением qualification thresholds. |
| Связь verified declaration с body-overlap | **ИСПРАВЛЯТЬ ОТДЕЛЬНО** | Правильный owner ещё может потерять exact identity из-за мягкого порога. Диагностическое `>= 1` не является готовой безопасной политикой. |
| Assembly/DTO budget | **ИСПРАВЛЯТЬ ОТДЕЛЬНО** | Расширение иногда вытесняет необходимое evidence. Сохранённый pool позволяет воспроизвести потерю без нового поиска. |
| B как продуктовая замена representation | **НЕ АКТИВИРОВАТЬ** | Ownership улучшен, но общий выигрыш достаточности не установлен; на синтетических controls был и проигрыш. |
| D_L как default packing | **НЕ АКТИВИРОВАТЬ** | Есть выигрыши и бюджетная потеря, а не однозначное улучшение. |
| P_MINUS_RATIO и heading hooks | **НЕ АКТИВИРОВАТЬ** | Process-local диагностические вмешательства, не concurrent-server policy и не authorization mechanism. |
| Удаление legacy ordering/packing | **НЕ АКТИВИРОВАТЬ** | Один ordering-pass дал ничью по достаточности; весь legacy package не изолирован и не проверен. Ничья не доказывает ненужность компонента. |
| Dense/hybrid и изменение answerer/skill | **НЕ АКТИВИРОВАТЬ НА ОСНОВЕ ЭТОЙ СЕРИИ** | Независимая оценка отсутствует; отсутствие измерения не означает отсутствие пользы. |

«Исправлять отдельно» — список конкретных дефектов для возможных самостоятельных
задач, а не продолжение эксперимента без конца и не разрешение менять продукт
сейчас. Любой перенос требует отдельной scoped-правки и её проверки.

## 3. Доказательства, достаточные для этих решений

### Ratio на реальном P

28 вопросов, из них 23 отвечаемых; 112 физических выполнений с повторами.
Posthoc development-review: **3 выигрыша / 0 потерь / 20 ничьих** на отвечаемых
вопросах и **одно дополнительное unsupported admission** на пяти неотвечаемых.
Это потеря селективности контекста, не измеренная hallucination модели.
См. [RATIO_REMOVE_ONE.md](RATIO_REMOVE_ONE.md).

Отдельные 168 real-P phase-запусков подтвердили, что tagging и final
requalification не взаимозаменяемы. Видимые источники изменились в 3/28 вопросах
при tagging-only, 11/28 при final-only и 15/28 при all-sites. Это **не число
улучшений качества**; контрольные P DTO совпали между фазами. Final requalification
выполняется на разных шагах projection, не только после окончательного DTO.
См. [P_RATIO_PHASES_T07.md](P_RATIO_PHASES_T07.md).

### Структура и assembly

На 28 реальных ATX Markdown-вопросах A/B DTO были одинаковыми. На setext-controls
новый B правильно разделяет владельцев, но qualification может отвергнуть полезный
body; значит, исправление структуры не решает весь путь до итогового evidence.

На 23 отвечаемых реальных вопросах D_L против того же B-пула:
**3 выигрыша / 1 потеря / 19 ничьих**. Потеря `source_changed` прослежена до
`whole_child_exceeds_dto_budget`, не до отсутствия кандидата в retrieval.
См. [STRUCTURE_T05_REPORT.md](STRUCTURE_T05_REPORT.md).

T06 **закрыт в native project scope**: сохранены 34 case snapshots и 339
кандидатов; 68 повторных snapshot-replay дали идентичные B/D DTO, **ноль новых
поисков** и максимум 796 D-токенов. Проверяются полный exposed ranked pool,
canonical bytes, eligibility, ownership, бюджет и неизменность snapshot.
«Полный pool» здесь означает все кандидаты в рамках зафиксированного cap,
не uncapped recall. См. [SAVED_POOL_T06.md](SAVED_POOL_T06.md).

### Heading, HTML и evaluator

- Heading threshold diagnostic: на шести синтетических механизмах достаточность
  B изменилась **1/6 → 6/6**, на 28 реальных вопросах DTO не изменились.
  Admission-only и final-only по отдельности восстановление не дали.
  [HEADING_CALL_SITES.md](HEADING_CALL_SITES.md).
- HTML provenance прошёл production extraction → canonical Markdown → ingestion
  → A/B/D_L: **36 запусков**, 36 привязанных цитат, идентичные повторы,
  максимум 515 токенов. Координаты относятся к canonical Markdown, не к raw HTML.
  A/B одинаковы; преимущества retrieval не заявляются.
  [HTML_PROVENANCE_T05.md](HTML_PROVENANCE_T05.md).
- Существующий evaluator переиспользован, его controls дали **42 passed**.
  Сохранены 18 текстов development-ответов и отдельная annotation/citation review.
  Их автор — текущий ассистент после просмотра packets и annotations; это **не
  blind agent benchmark**. [EVALUATOR_READER_T09_T10.md](EVALUATOR_READER_T09_T10.md).

## 4. Границы доказательств

1. Вопросы self-authored/inspected, review same-author и posthoc. Основные реальные
   панели — один репозиторий; синтетические controls учитываются отдельно.
   Независимого multi-source holdout нет. Повторы не являются новыми вопросами.
2. Canonical audit подтверждает механическую корректность, не semantic sufficiency,
   правильность ответа или полезность источника. Неизвестные семантические случаи
   остаются в review queue, не превращаются автоматически в success/failure.
3. A/B/D не являются resource-matched заменами P; прямой итог «A лучше P» не
   установлен. Исторический FTS-only B теперь называется `B_FTS`; результаты
   разных definitions нельзя объединять.
4. Для парных сравнений контролировались source identity и fixture root. Прогоны
   с другими roots сохранены как confound diagnosis, не доказательство эффекта.
   [MECHANICAL_COMPARISON.md](MECHANICAL_COMPARISON.md).
5. Development-запуски использовали обычные процессы без OS-enforced label
   isolation. Production frozen-run CLI не получил unsafe fallback.
6. Library/version scopes, полный uncapped first-loss trace, RST и ownership вне
   headings не завершены. HTML проверен как derived-canonical project path, не
   прямые raw-HTML публичные цитаты. Hybrid не запускался.
7. Нет blind agent execution, независимого free-text/citation review, доказательств
   general answer accuracy, hallucination rate, latency или экономии токенов модели.

## 5. Проверки и блокеры продуктовой приёмки

Последняя focused/adjacent suite: **176 passed**. Последний полный offline run:
**5771 passed / 28 failed / 10 skipped**. Сравнение с unchanged локальным HEAD
`39347d29` в настоящем detached worktree: **29 baseline failures, 28 общих,
ноль candidate-only failure node IDs**. Единственный baseline-only failure —
B/D-тест с разными fixture roots. Новые/переименованные тесты не следует считать
числом исправленных product bugs.

Полный run предшествует последним P phase/HTML quote-binding правкам; для них
есть focused regression evidence, а не новый полный зелёный gate. Сравнение с
локальным HEAD не заменяет полный paired acceptance against origin/main.
См. [FULL_OFFLINE_GATE.md](FULL_OFFLINE_GATE.md).

**Блокеры:**
- Восемь namespace/isolation tests: `uid_map: Operation not permitted`.
- Остальные общие failures включают frozen witness revision mismatches,
  query planning, projection и service expectations. Они не списаны на окружение
  и не waived. Locks, assertions и thresholds не ослаблялись.
- Нет независимого corpus/reader/reviewer evidence для продуктовой замены.
- Отсутствующий RST parser и неподдержанные scopes ограничивают перенос выводов.

Отсутствие новых failures — не зелёный gate и не подтверждение эквивалентности.
Merge/activation/T12 acceptance не одобрены.

## 6. Завершение серии

**Development-фаза завершена этим отчётом.** Новые hooks, corpora, повторные
прогоны и расширение T05–T12 автоматически не запускаются. Существующие
артефакты и исторические отчёты сохраняются; многие raw outputs находятся в
`/tmp/opencode/`, поэтому отчёт не обещает их постоянного хранения или новой
подписанной release-freeze.

Если позднее будет отдельно запрошено продуктовое изменение, его основанием
должны стать конкретный дефект, минимальная правка и отдельная приёмка. Если
будет отдельно запрошена универсальная замена pipeline, потребуется новый
независимый протокол. Это новые задачи, не обязательное продолжение этой серии.
