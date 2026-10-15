# Inventory: начальный scope удаления

Источники: ../HEURISTICS_AND_RESEARCH_RU.md в основном проекте; actual code91dd2b4e. Детальные подтверждения/параметры добавляются после A–C, до runtime.

| Механизм | Тип | Цель candidate | Владелец |
|---|---|---|---|
| BM25 | Исследованный lexical метод | Сохранить, документировать SQLite реализацию и deviations | A |
| title/leading phrase/length/authority score adjustments | Локальное ручное ранжирование | Убрать; source policy не заменять score | A |
| dispatcher/acquisition caps и estimated-token packing | Ресурсные policies | Разделить acquisition и final delivery, конечные bounds явны | A/C |
| lexical qualification ratio и inferred whole-query обязательства | Relevance proxy | Не использовать для допуска/приоритета candidate | B |
| phrase/clause/числовые partial rescue | Локальные синтаксические эвристики | Не переносить в source-only candidate | B |
| qualification-first | Локальная priority policy | Сохранить acquisition rank | C |
| Budget top2 child | First-k baseline, не семантическая оптимизация | Отбор под явным финальным бюджетом, без обещания полноты | C |
| parent/neighbor expansion по смысловым предположениям | Structural/relevance policy | Минимальные native source-bound units | C |
| exact occurrence dedupe | Точная идентичность | Допустим, не semantic novelty | C |
| source hash/span/project/member/scope/version/freshness | Контракт источника | Сохранить | Все |
| output token counting | Учёт ресурса | Один fixed accounting/packing для сравнения | E/координатор |

Не считаем engineering resource bound научно оптимальным. Не называем BM25-only baseline воспроизведением Anthropic reranking/SetR/RAPTOR.
