# Gate R — предлагаемый resource contract

Статус: **принят для isolated implementation** ответом пользователя «давай дальше
след шаг» после предложения согласовать профиль. Production defaults/index не изменены.
Это один консервативный профиль, не подбор параметров по benchmark.

## Что действительно есть сейчас

- `core/structured_chunking.py`: child target 160, hard 512 в единицах
  `utf8-bytes-div4-v1` (ceil UTF-8 bytes / 4), не provider tokens.
- `core/config.py`: query default budget 2400, default limit 8;
  retrieval max_sections_per_source 2.
- `_project_context_service_part01.py:89`: project candidate request
  `min(20, max(12, (limit or 4)*3))`, по умолчанию 12.
- `_sqlite_store_part03.py:198`: внутренний FTS pool `limit*4`; это не
  returned candidate cap. Поиск уже материализует строки до downstream packing.
- Store budget допускает oversized first candidate (`if selected ...`, стр. 252).
  Поэтому 2400 нельзя честно назвать действующим строгим upper bound hydration.
- `docs/domain/context_blocks.py`: MAX_BLOCKS/MAX_ALTERNATIVES по 4096 на extent.
- `docs/domain/context_windows.py`: rolling windows 160/320/520 **characters**;
  short complete source до 704 characters. Это не passage/index limits.
- DTO boundary: 800 admission tokens и не более 3 public sources.

Пути `context_blocks.py`/`context_windows.py` в шаге 06 исходного плана ошибочно
указаны как application; реальные модули находятся в **domain**. До шага 06
нужно явно согласовать корректировку allowed paths, не создавать дубликаты.

## Один предлагаемый профиль

| Ресурс | Значение / правило | Основание |
|---|---|---|
| Passage target | 512 estimate units | Использовать существующий hard envelope как contextual target; не расширять максимальный размер блока |
| Passage hard max | 512 estimate units / 2048 UTF-8 bytes | Тот же byte estimator и существующий hard bound |
| Passage overlap | 0 | Не вводить multiplicative overlap; grouping contiguous atoms вместо child enlargement |
| Candidate request cap | `min(20, max(12, (limit or 4)*3))` | Наследовать project caller; default 12, absolute max 20 |
| FTS ranking result cap | равен candidate request cap | Новый single-order path не нуждается в `*4` pool для ручного rerank |
| Суммарный admitted passage payload | ≤2400 estimate units **и** ≤9600 UTF-8 bytes на request | 2400 наследуется из query budget; byte cap — новый строгий envelope, не утверждение о старом hydration limit |
| При меньшем caller budget | `min(2400, caller budget)`, byte cap ≤4× этого значения | Нельзя повысить caller budget; giant first hit не получает исключения |
| Окна на весь request | максимум 4096 уникальных exact spans | Наследовать численный work cap, но сделать его общим, не умножать на candidates |
| Atom enumeration | ≤4096 atoms на extent; overflow = explicit deferred | Существующий parser work bound, не silent truncation как complete |
| Per-source admitted passage cap | 2 | Наследовать RetrievalConfig default; не parent novelty reorder |
| Per-module cap | общий request cap; не отдельный дополнительный pool | Scope=all не умножает budget на modules |
| Public packet | ≤800 whole-DTO tokens / ≤3 sources | Без изменений |
| Ranking ties | BM25 ascending, затем full stable passage identity ascending | Не insertion order, score rounding или synthetic score |

Passage ID включает source identity, snapshot/content identity, exact offsets и
profile identity. Одинаковые bytes в разных sources/projects не дедуплицируются.
Caps применяются в одном BM25 order; skipped oversized/capped candidates
фиксируются в trace. Это resource exclusion, не semantic abstention.

## Не скрывать расходы

9600 bytes ограничивают **passage text**, не raw documents, metadata, FTS index
size или весь process RSS. Existing reference evidence содержит raw_document;
перенос этого целиком на каждый passage не доказан bounded по этому контракту.

До index/query integration измерить отдельно: FTS fetched text bytes, hydrated
passage bytes, unique raw snapshot bytes, metadata bytes, alternatives count.
SQL retrieval должен ограничить oversized rows до Python text hydration;
нельзя прочитать все giant sources и назвать их «отфильтрованными бесплатно».
Raw snapshots использовать request-local shared inventory, не новые source I/O
на каждую alternative. Если это требует увеличения прежнего snapshot/read budget,
STOP и отдельное согласование; passage-byte cap не покрывает такое увеличение.

Oversized structural atom нельзя разрезать с потерей conditions и назвать
complete. Для этого профиля он deferred; нужно учитывать recall loss в paired
tests. Принятый профиль — не доказательство MkDocs delivery или non-regression.

## Решение, необходимое до шага 02

Принять этот профиль как **один экспериментальный implementation contract**
для isolated state, не пользовательские defaults; либо указать изменяемые limits.
Gate A остаётся независимым и открытым. Если после принятия обнаружена потеря
fact, не подбирать новые значения по exposed case: показать failure и пересмотреть
контракт отдельно.
