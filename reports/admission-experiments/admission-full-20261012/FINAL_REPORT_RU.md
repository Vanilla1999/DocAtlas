# DocAtlas: финальный отчёт по admission, reranking и pruning

> **Уточнение после повторного методического аудита:** см. `RESEARCH_METHOD_AUDIT_RU.md`. Завершена серия диагностических запусков, но единое сопоставимое end-to-end сравнение методов не завершено. Нельзя читать отсутствие доказанной пользы как доказательство бесполезности rerankers/compressors. Исходные измерения, frozen verdicts и рекомендация не включать B1 в default сохраняются.

## Решение

**Не включать экспериментальный B1 в default и не внедрять новую модель admission по этим результатам.** Причина потери найденных фактов подтверждена, изолированный B1 улучшил доставку **28/40 → 39/40**, но существенно увеличил выдачу/задержку и нарушил четыре прежних отрицательных требования. Промпт существующей модели помогает понимать контекст, однако сам по себе не обеспечил точные цитаты и полное grounding.

**Минимальное следующее направление:** bounded source-valid candidate handoff, сохранение владельца/условий источника и проверяемое извлечение точных цитат; затем один ограниченный сравнительный public-сценарий. Это предложение, не выполненное внедрение. Если нужен небольшой ranker, **mMiniLM — кандидат на дешёвое ранжирование**, но не на самостоятельный relevance/answerability veto. Измеренного основания добавлять Qwen, CRAG или compressor в production сейчас нет.

Независимый окончательный verdict: `G_FINAL_REVIEW.md`; структурированные результаты: `G_FINAL_RESULTS.json`. Проверки завершены. **Unit-тесты не добавлялись и не запускались.** Исходные corpus/questions/oracle не изменены.

Ранние NOT RUN / pending разделы A–F сохраняются как история до разрешения и запуска. Текущий итог определяется этим отчётом, `G_FINAL_REVIEW.md` и фактическими raw receipts, а не прежними checkpoint-статусами.

## 1. Что реально исполнено

- Настоящий in-process public MCP/SQLite на изолированных данных: baseline, изменённый продукт с выключенным флагом, opt-in B1, существующие положительные/отрицательные/source-isolation/stale-hash интеграции.
- Реальные checkpoint forwards: mMiniLM, Qwen3-Reranker, XProvence, официальный CRAG evaluator, LLMLingua-2, SWE-Pruner. Все модели исполнены на **CPU**, последовательно между моделями; GPU не benchmark-ился.
- **21 настоящий stateless endpoint request** существующему `openai/gpt-5.6-luna#medium`: 1 readiness, 12 generation, 4 sufficiency, 4 prompted ranking. Не использовались mock-ответы или скрытые format repairs.
- Source/span/hash, конечные факты, реальные ответы и цитаты независимо проверены агентом G по исходным документам.

Границы доказательства различаются: compact ranker positives — replay 21 сохранённого native окна; negatives — 2 настоящих публичных B1 пакета. R1/S1/LLML/SWE используют реальные public packets и client-side adapters. **Это не публичная интеграция нейросетевого selector внутри DocAtlas и не полноценное воспроизведение всех статей.** Installed stdio, production/client smoke, SWE-Bench, независимый document holdout и полный CRAG correction pipeline не исполнялись.

## 2. Доставка и контракт

| Вариант | old10 | direct40 | Q16/Q46 | Прежние 28 успехов |
|---|---:|---:|---|---|
| B0 | 10/10 | 28/40 | Факты не доставлены | База |
| Изменённый продукт, флаг выключен | 10/10 | 28/40 | Без изменений | Все сохранены; нормализованная выдача всех 40 совпала |
| Opt-in B1 | 10/10 | **39/40** | Оба полных факта доставлены | Все сохранены |

Факты Q16/Q46 уже были найдены native acquisition; baseline терял их на topical admission/read presentation **до projection**. Поэтому последующее сжатие не могло восстановить пустой пакет.

**Q31 остаётся FAIL доставки.** Факт лежит в двух соседних найденных окнах. По коду сохранённый unresolved-name guard не принимает `HumanEval` из целого термина `HumanEval/LeetCode`. Raw показывает null admission и пустую выдачу; конкретная внутренняя ветка реконструирована статически, не записана как runtime receipt. Ни вопрос, ни guard ради 40/40 не изменялись.

B1 нарушил прежний empty-source контракт в **четырёх сценариях**: OtherAPI, составные идентификаторы, Setext topical heading, нерелевантный квантовый канал. JUnit показывает 8 PASS / 2 failed items, потому что один item содержит несколько сценариев и останавливается на первом assertion. Эти четыре FAIL не скрыты и не переклассифицированы в PASS.

Numeric7/numeric7–9 и пустое acquisition сохранили пустую выдачу. Scope/module/foreign-source controls имеют реальные положительные проверки индексированных источников. Наблюдаемое состояние до/после reads не изменилось: generation, `generation_sources`, hashes каталогов/исходных файлов. Answer/edit authority осталась false. **Это ограниченное подтверждение, не доказательство всех access/consent/wrong-version правил.**

## 3. Реальные ответы хоста

| Ветка | Q16: обязательные факты | Q16: точная цитата | Q46: факты и точные цитаты |
|---|---|---|---|
| B0 | Не решено; корректный отказ при пустом контексте | Нет выдуманных цитат | Не решено; корректный отказ |
| B1 | PASS | **FAIL** | **PASS** |
| R1 selected packet | PASS | **FAIL** | **PASS** |
| LLML exact-line client view | PASS | **FAIL** | **PASS** |

Во всех трёх Q16 ответах модель заменила newline/два пробела в цитате одним пробелом. Смысл правильный, но цитата **не является дословной подстрокой** источника. Критерий не ослаблялся, ответы не исправлялись и не перегенерировались ради PASS.

Хост отказался отвечать по OtherAPI/квантовому каналу; OtherAPI explanation имеет owner caveat: дополнительная цитата относится к DeliveryEngine, а владелец не повторён в пояснении. Это не утвердительный выдуманный ответ OtherAPI, но и не идеальная source-scoped выдача.

S1 верно отметил достаточность двух positive packets и недостаточность двух negatives. R1 сохранил полезный контекст и вернул `useful_ids=[]` для обоих negatives. **Вердикт sufficiency не исправляет цитаты и не даёт authority.** Три удачных Q46 — три ветви одного известного вопроса, не три независимых задачи.

## 4. Методы и модели

Все перечисленные ниже исполнения — **ADAPTED**, с точно зафиксированными checkpoint/code revisions. Канонический paper/model/protocol reproduction не заявляется.

| Метод | Размер | Реальное испытание | Результат / ограничение |
|---|---:|---|---|
| Sufficient Context-style S1 | Существующий хост | 4 sufficiency requests | Верные labels на этом срезе; не certificate правильности/цитат |
| RankGPT-style R1 | Тот же хост | 4 ranking + 2 последующих generation | Useful selection и negative rejection; Q16 citation FAIL; дополнительный вызов увеличил суммарную стоимость |
| mMARCO mMiniLMv2 | 117.6M | 23 FP32 forwards | Полезное окно rank1 Q16/Q46; OtherAPI score выше полезного Q16; public selector не интегрирован |
| Qwen3-Reranker | 595.8M | 23 BF16 forwards | То же rank1; тот же scalar-cutoff контрпример; преимущества сверх Mini/B1 не доказаны |
| XProvence | 567.8M | 23 FP32 joint forwards | Rank1 обоих positives; pruning сохранил обязательные spans; diagnostics не доказывают public/native admission lineage или net saving |
| CRAG evaluator | 738.7M фактически загружено | 19 FP32 forwards | 17/21 positive pairs scored, 4 overflow без clipping; полезный Q16 не scored, Q46 rank2; OtherAPI ошибочно CORRECT по опубликованному порогу |
| LLMLingua-2 XLM-R | 558.9M checkpoint | 20 forwards на двух public contexts | Raw удаляет identifiers/отрицания; exact-line wrapper возвращает факты, но увеличивает host input |
| SWE-Pruner | 634.3M | 1 forward, CPU eager/FP32 | Только отдельный короткий Dart code-QA smoke; факты сохранены, owner attribution/complete grounding не сохранены |

### Почему нельзя просто поставить threshold

| Модель | Полезное Q16 native окно | Неподдерживающий OtherAPI public пакет |
|---|---:|---:|
| Mini | 1.660 | **2.750** |
| Qwen | 3.625 | **8.438** |
| XProvence | −0.995 | **1.291** |

Один глобальный ascending `score >= threshold` не может одновременно принять эти Q16 positives и отклонить этот OtherAPI negative. Positive/native и negative/public representations различаются; это **узкий наблюдаемый контрпример**, не доказательство невозможности owner-aware/query-dependent selector или иной калибровки. Threshold не подбирался по этой проверке.

CRAG web/refinement/corrective actions не запускались: web widening несовместим с project scope. Его веса зафиксированы по полученным bytes SHA-256, не по неизвестному авторскому immutable checksum. XProvence имеет отдельные лицензионные ограничения/неясности; experimental inference не означает разрешение production/redistribution.

## 5. Сжатие и полная стоимость

**B1 не экономичен:** public DTO proxy tokens **41 047 → 275 588 (6.71×)**; snippet tokens 20 896 → 184 035. Median context latency **202 → 4369 ms**; сумма сохранённых 40 reads **8.822 → 174.765 s**, около 19.8×. Это наблюдения, не стабильный p95 или контролируемый repeated benchmark.

Ранжирование R1 уменьшило выбранный Q16 JSON view **4297 → 326** proxy tokens, но сам ranking call тоже получает контекст. Суммарные submitted-prompt proxies ranking+generation:

- Q16: **5496 против 4794** без R1; endpoint wall **10.64 против 6.73 s**.
- Q46: **2510 против 1351**; wall **8.61 против 3.26 s**.

**Чистой экономии полного хода не доказано.**

LLML raw counters примерно −52%, однако raw искажает identifiers/отрицания и не является исходной цитатой. Exact-line client closure увеличил полный submitted host input примерно **+7.57% / +6.30%**; JSON views 4297→4645 и 952→1031. Добавляются compressor forwards/time. Для текущего exact-source контракта этот вариант не оправдан.

SWE сократил JSON view **273→148**, полный submitted prompt примерно **−21.74%**, но добавил 2.577s compression process. Сохранились методы/default/assignment, однако удалено видимое `class TSDTabController`; question не заменяет доказательство владельца. Оба code-host ответа дали правильные значения и короткие точные цитаты, но не объяснили/подтвердили обязательное `switchTo` → `current = type`. **Оба strict complete code answers FAIL grounding**; SWE дополнительно теряет owner support. Это не SWE-Bench или проверка выполнения/изменения Dart-приложения.

CPU positive-smoke наблюдения: Mini 21 forwards/1.142s/~0.96GiB RSS; Qwen 21/35.609s/~1.55GiB; XProvence 21/7.263s/~2.08GiB; CRAG 17/35.255s/~3.43GiB. LLML 20/13.110s/~2.08GiB; SWE 1/2.577s/~4.02GiB. Разные бюджеты/границы; часть пересекалась с API-проверками. **Не использовать как общий рейтинг производительности.**

Все o200k/cl100k/model-token counters различаются по единицам и **не равны billing**. Endpoint не раскрывает actual input/output/reasoning tokens, цену, backend immutable revision или provider transport retries. Авторское строковое “Saving $…” у compressor не является измерением нашего счёта.

## 6. Воспроизводимость, ошибки и состояние репозитория

- База: `4849b8f796d9e3e25e2c49e58562ec6859978411`, ветка `fix/main-flow-compact-evidence`.
- Изменены три domain-файла opt-in B1 и существующий eval runner для ограниченного recovery/per-call persistence. **Default не включён.** Не было commit/push/merge/release.
- Итоговый diff: `FINAL_EXPERIMENT.patch`, SHA-256 `28011c0ea70c0b96e6ca1250473979225bade1ecd1a4f5bf1fc0fd8b6752a9f8`. `git diff --check` чистый. Frozen input hashes совпадают с manifest.
- Первый B1 прогон timeout120s: сохранены 24 результата; четыре completed outputs потеряны из-за buffering, один request прерван. После изменения persistence исполнены только недостающие IDs35–50. Итого **44 completed context attempts +1 interrupted**, два prepares; 39/40 — assembly уникальных результатов, не один непрерывный run. Таймаут не скрыт, уже сохранённые 24 не повторялись.
- Initial baseline controls: шесть setup FAIL из-за group-writable storage ancestry. Guard не обходился; private runtime перенесён под sticky `/tmp`, повторены только failed шесть, все PASS. Артефакты остаются под `/tmp/opencode`.
- Preserved model assets/locks/raw requests/responses и независимые audits находятся рядом с отчётом. Models CPU-runtime изолирован, training отсутствовал. Общая серия — **109 model forwards**, отдельные границы/loads/overflow учтены в receipts.

Главные файлы: `G_FINAL_REVIEW.md`, `G_FINAL_RESULTS.json`, `FINAL_COSTS.json`, `B1_COMBINED40.json`, `CLIENT_EXCERPT_BINDINGS.json`, `DEFAULT_OFF_PARITY.json`, `A_Q31_REMAINING.md`; подробные method reports — A/B/C/D/E/F.

## Что осталось недоказанным

Генерация ответов по всем 40/50 вопросам; calibrated public-integrated neural selector; независимый holdout; стабильность хоста; полный CRAG/авторские paper metrics; production/installed/client acceptance; все access/consent/version-denial состояния. Риски соседних зависимых пунктов и mixed host_lookup остаются static/UNVERIFIED.

**Итог:** причина Q46/Q16 устранена в экспериментальной доставке, но безопасное/экономичное default-решение ещё не получено. Новая маленькая модель не требуется доказанно; naive threshold и раннее сжатие эту задачу не решают. Следующий минимальный эксперимент — semantic relation/owner selection и exact citation extraction без ослабления исходных критериев, а не дополнительная матрица моделей или повтор до PASS.
