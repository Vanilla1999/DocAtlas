# I.4: ремонт typed wiring после 0f4b5847

Дата: 2026-10-04. Ветка: next07-feasibility-audit.
База: 0f4b5847b2e2a7d7509c33ca39865ffa8706e0f7.
Статус: исправлена воспроизводимая ошибка контракта wiring; новый native C NOT_RUN.
Исторический BLOCKED не переписан. Это технический ремонт wiring, не подбор
нового retrieval/read алгоритма после содержательного failure.

## Причина

В next07_grounded_public.installed.context результат get_project_context
преобразовывался через asdict и возвращался как dict. Но следующий consumer
_UnifiedDocsContextServicePart02._normalize_project_context обращается к
result.context_pack; следующие consumers читают также .status/.project_docs.
Сериализация исправляла попытку индексировать dataclass, но нарушала контракт
возвращаемого объекта. На старом wiring воспроизведено:
AttributeError: 'dict' object has no attribute 'context_pack'.
Старый native capture не содержит traceback; это воспроизведение найденного
дефекта контракта, не новый native traceback исторического запуска.

## Правка

1. Возвращается dataclasses.replace(result, context_pack=rows). Тип dataclass и
   вложенные canonical decisions сохраняются. asdict используется только в log.
2. Проектор получает actual retrieval.context_pack после штатной нормализации,
   source filtering и trust annotations. Старый cached rows больше не может
   воскресить удалённый источник или проигнорировать новую risk annotation.
3. Обёрнут настоящий service.unified_context.get_docs_context: исключение
   сохраняется с traceback до санитаризации MCP, затем пробрасывается без замены.
   Projection exceptions записываются аналогично. Traceback не попадает в public DTO.
4. Реальный handler validator наблюдается без изменения его verdict. Все hooks
   восстанавливаются в finally, включая выход через exception. State очищается
   между запросами, исключая повторное использование previous request identity.
5. Runner проверяет возвращённый public payload: факты в своих источниках,
   subject/condition, flags, whole-DTO cost, source cap, вызов final handler
   validator и его результат. Pre-handler budget больше не заменяет final cost.
   Непустой traceback означает invalid execution; содержательный отказ/пустая
   выдача после projection не объявляются автоматически environment blocker.
   Exit: 0=локальная I.4, 1=REJECTED, 2=BLOCKED_INVALID. Автоповторов нет.

Неизменны: весь next07_grounded_candidate.py (SHA-256
5ac8e2600a12d216070087a50c9ddc64c8efaaff2f399d70e2b345db0bf71ff7),
prepared и first_fit (AST), splitter/FTS/BM25/read_decision/source guards,
production, прежние 53 tests и все historical artifacts.

## Не скрывать оставшуюся границу

Existing prepared() жестко задаёт scope=project. Новый entry check запрещает
незаметно применять этот harness к module/all, assisted lookups, historical
intent или change. Такие вызовы получают явный unsupported wiring, НЕ guard
acceptance PASS. Сейчас entry рассчитан только на explicit root-only current
project read — в частности P1/P2/P3. Это не реализация остальных маршрутов.

Исходная prepared() и схема получения inventory пока сохранены: native context
и отдельная preparation могут выполнять дополнительную внутреннюю работу.
Resource/call parity, полнота inventory и 80-case retention этим ремонтом НЕ
проверены. При дальнейшей I.5 их нельзя объявлять пройденными из unit tests.
Не ослаблять owner-preservation ради результата; его recall-цена остаётся
отдельным измеряемым риском candidate.

## Выполненная проверка

В доступном контейнере нет checkout и DNS к GitHub. Через connector получены
исходники. Два исходных wiring/runner файла сверены по полным Git blob SHA.
Исполнены точные новые определения wiring; DTO и normalizer взяты из pinned
исходных определений. Неиспользуемые здесь application imports изолированы;
prepared/first_fit в unit tests — spies. Ни один guard не объявляется проверенным
на этом основании. Полный приложение/handler в контейнере не запускались.

- RED на исходном wiring: 2 FAIL / 24 deselected, обе позиционные формы вызова
  воспроизводят dict.context_pack AttributeError.
- GREEN на исправленном wiring: 26 PASS.
- Python compile: PASS; AST prepared/first_fit: unchanged.

Это 26 новых contract/runner tests, НЕ повтор 53 PASS, НЕ 79 native checks и
НЕ подтверждение доставки. В обычном окружении проекта новый test module
импортирует настоящие модели/normalizer; архив содержит отдельный loader,
явно описывающий использованную здесь dependency isolation.

Native C/P1/P2/P3, final budget/source validation, прочие public controls,
49-ID/partial retention, required gates/full suite и reader/unseen: NOT_RUN.

## Следующий запуск в существующем окружении

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q \
  v2plan/test_next07_grounded_public_wiring.py

# Только если unit-команда прошла; output должен ещё не существовать.
DOCATLAS_OFFLINE=1 .venv/bin/python -m v2plan.next07_grounded_final_run \
  --out v2plan/artifacts/next07/grounded-first/<новый-run-id>
```

Runner сам выполняет paired N/C для 17, 29 и partial, прекращая замер при первом
failure. При успехе I.4 продолжить I.5/I.6 текущего плана, не часть II.
При исключении точная причина ожидается в <case>/trace.json → exceptions;
никаких ещё TypeError/AttributeError без traceback как достаточного диагноза.
Rollout NOT_AUTHORIZED. Старые результаты и чужие dirty files сохранены.
