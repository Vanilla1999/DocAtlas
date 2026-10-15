# Основной source-native путь: изменения и интеграционная проверка

Продолжение по новому запросу владельца после остановленного эксперимента.
Старые freeze manifests, wheels и результаты в `heuristic-removal/` относятся к
предыдущему коду. На текущий код их PASS/FAIL и hashes не переносятся.

## Изменения

- Удалён `experimental_heuristic_removal.py`; `DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL`
  больше не переключает продуктовый путь. Lexical acquisition использует native
  equal-field FTS5 BM25 OR. Удалены старое ручное ранжирование из `query` и
  weighted/AND-first/fallback SQL из `_search_rows`.
- Source-only admission теперь основной контракт оригинального вопроса:
  source-valid не означает qualified или answer-supported. Удалены phrase,
  technical-anchor, scalar-label и unresolved-name fallback реализации из
  `ordinary_body_context.py`; сохраняются raw/window/hash/owner/live-receipt проверки.
- Native-rank selection и whole-window finalization включаются внутри настоящего
  request-bound чтения без флага. Финальный лимит по умолчанию 12000; acquisition
  имеет отдельные ограничители. Membership/permission не выводятся из флага.
- Расширена привязка discovery receipts на module и all. Для module требуется
  точное совпадение scope/module_path; для all сохраняются принадлежность проекту,
  допустимый scope, module metadata, generation и hashes.
- Исправлена потеря version в local-project routing. Локальные документы без
  версии не удовлетворяют explicit-version запрос: такой запрос явно отклоняется.
- Исправлен measurement helper: повторный keyword scope; относительные resource
  paths; `complete` с последним snippet проверяется как содержимое, а не как
  пустой end-of-source. Исходные факты и вопросы не изменены.

## Проверки

Только публичные integration с реальными storage/indexing/projection/resource
компонентами. Последний запуск: **6 passed in 3.13s**:

```
tests/test_heuristic_removal_public_integration.py
tests/test_prepared_retrieval_integration.py
```

Первый файл явно удаляет removal/cap env vars перед вызовами. Проверены delivery
обязательных исходных фактов, source hashes/spans, scope/module/all, foreign
locator, недоступная версия, false answer/edit authority, stale→confirmed sync,
source resource, отсутствие записи при read, trace off/on/off parity. Второй
файл дополнительно проверяет prepared-parent parity, restart и конечный бюджет.
Unit не добавлялись и не запускались. Финальные integration и
`git diff --check` прошли после продуктовых изменений.

## Анализ логов, сохранённые FAIL

- `guards.log`: setup FAIL до контекстных вызовов — `/tmp/opencode` является
  writable ancestor. Storage policy сохранена; runtime перемещён в отдельный
  private каталог `/tmp/docatlas-default-HXV8YAxA`.
- `guards02.log`: trace off/on/off доставил одинаковые факты; resource matcher
  ошибочно требовал reason_code у terminal snippet. Module выдача была пустой:
  discovery scope ограничивался project. Исправлены matcher и продуктовая scope
  привязка раздельно.
- `guards03.log`: scope/version/foreign сценарий PASS; lifecycle упёрся в
  ошибочное требование absolute resource path. Проверка исправлена на нормализацию
  пути с сохранением сравнения исходного текста/hash/span.
- `guards04.log`, `guards05.log`: оба guard сценария PASS.
- `prepared.log`: 3 PASS, 1 FAIL — all scope оставался вне discovery scope.
  Исправлено сохранением per-member scope в рамках того же project identity.
- `final.log`, `final.xml`: все 6 PASS после исправления all scope. Лог содержит
  request start, один включённый query trace, request end. В трассе исходного
  optics вопроса: 4 доставленных источника, false answer/edit authority,
  `trace_incomplete=false`. Доказательство фактов и trace parity — assertions
  конечных payload, а не наличие этих логов.

## Точная граница результата

Это default source-native путь оригинального local-project/module/all чтения,
а не утверждение об удалении всех правил во всех API. Отдельные explicit lookup,
library, mutation и hybrid пути и общие policy/qualification реализации ещё
существуют. Для них полный отказ от эвристик этим набором не доказан.
Старые S fallback ветки вне live source-bound scope остаются. Поэтому полное
физическое удаление всех эвристик из продукта ещё не закрыто.

6 PASS — source-tree public integration, не установленный новый wheel/stdio,
не независимое review и не benchmark качества ответа. Commit/push/deploy не было.
Все логи, включая красные, сохранены; `RECEIPTS.json` содержит их SHA-256.
