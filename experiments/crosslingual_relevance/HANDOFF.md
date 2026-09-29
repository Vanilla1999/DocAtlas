# Handoff: Cross-lingual retrieval — запрос на дальнейшее исследование

## Контекст

Репозиторий: `git@github.com:Vanilla1999/DocAtlas.git`
Ветка: `task-44-cross-lingual-retrieval` (от `main` @ `58c7f37c`)
План: `roadmap/44_CROSS_LINGUAL_RETRIEVAL_AND_BOUNDED_RELEVANCE.md`

## Проблема

DocAtlas (docs-as-code assistant) теряет релевантные блоки для русскоязычных и
смешанных RU+EN вопросов к англоязычной документации. Два дефекта:

1. **Лексический фильтр** `qualify_evidence` отклоняет блоки, где RU-термины
   не совпадают с EN-текстом (`insufficient_visible_match`).
2. **Полностью русские вопросы** дают ноль кандидатов через lexical retrieval
   (нет общих токенов ≥4 символов).

## Что сделано (M0–M6)

### Доказано

- **Dense retrieval (MPNet)** находит gold-блоки для всех языковых групп
  (M4: rank #1 для 7/7 задач, Recall@5=1.0).
- **Rescue механизм** безопасно допускает блоки: 22 теста, все негативные
  контроли intact (wrong project, stale, forged score, degraded, K-limit).
- **BoundedScorer** исправлен: cache проверяется до limit, минимальная длина
  80 chars, K=60.
- **Stub-scorer M5** доказывает механизм доставки (rescue → packet), но не
  качество модели.

### Отрицательный результат (главный)

Реальный MPNet scorer с замороженным порогом `0.7453` **не работает для Typer**:

| Task | MPNet score | Threshold | Result |
|---|---|---|---|
| typer-mixed-ru | 0.5227 | 0.7453 | FAIL |
| typer-pure-ru | 0.5187 | 0.7453 | FAIL |
| typer-en | 0.4372 | 0.7453 | PASS (lexical) |
| m15-dev-01 (httpx) | 0.8409 | 0.7453 | FAIL (different chunk in pipeline) |
| m15-dev-02 (ruff) | 0.7241 | 0.7453 | PASS (lexical) |

Порог 0.7453 заморожен на M1.5 calibration split (httpx, ruff, starlette, pydantic).
Gold-блоки Typer оцениваются в 0.50–0.54 — далеко ниже порога.
План **запрещает** подстраивать порог под Typer.

### Архитектура

```
get_docs_context (MCP handler)
  → query_project_docs
    → dispatcher.run(mode="dense")
      → dense retrieval (MPNet, sqlite-vec)
      → qualification (qualify_evidence)
        → rescue patch (context_rescue.installed)
          → apply_rescue: insufficient_visible_match + score ≥ threshold → admit
      → projection (_requalify_visible_source)
        → повторная квалификация (rescue применяется повторно)
    → selection, dedup, budget ≤ 800
  → first packet (sources)
```

Rescue патчит `qualify_evidence` в 5 модулях через `unittest.mock.patch`:
- `docmancer.docs.domain.evidence_qualification`
- `docmancer.docs.application.context_query_probes`
- `docmancer.docs.application.reference_query_tagging`
- `docmancer.docs.application._docs_context_projection_core`
- `docmancer.docs.domain.context_hint_policy`

## Ключевые файлы

| Файл | Назначение |
|---|---|
| `experiments/crosslingual_relevance/context_rescue.py` | Rescue механизм (BoundedScorer, apply_rescue, installed) |
| `experiments/crosslingual_relevance/mpnet_scorer.py` | Реальный MPNet cosine similarity scorer |
| `experiments/crosslingual_relevance/m5_real_scorer.py` | E2E тест с реальным scorer |
| `experiments/crosslingual_relevance/m4_dense_candidates.py` | M4 dispatcher test |
| `experiments/crosslingual_relevance/m6_holdout.py` | M6 holdout (метрики не валидны) |
| `experiments/crosslingual_relevance/m15_evaluation_manifest.json` | Замороженный eval набор |
| `experiments/crosslingual_relevance/pool.json` | M2 pool (29 блоков) |
| `experiments/crosslingual_relevance/results.json` | M2 scores |
| `experiments/crosslingual_relevance/evidence/` | Все логи |
| `tests/docs/test_bounded_contextual_relevance.py` | 22 защитных теста |
| `tests/docs/test_m5_first_packet_green.py` | 7 пакетных тестов (stub scorer) |
| `tests/docs/test_multilingual_first_packet.py` | M0 RED тесты |
| `tests/docs/test_multilingual_query_integrity.py` | M1 инварианты |
| `roadmap/44_CROSS_LINGUAL_RETRIEVAL_AND_BOUNDED_RELEVANCE.md` | TDD план + evidence |

## Ограничения среды

- Qdrant недоступен → sqlite-vec (dense-only, no sparse/SPLADE)
- `DOCATLAS_AUTO_VECTORS='1'`, `DOCATLAS_FASTEMBED_CACHE_DIR=/tmp/fastembed_cache`
- `max_sections_per_source=20` (pilot, production default=2)
- P0 freeze: продакшн-активация — отдельное решение мейнтейнера
- `protocol_v3.lock.json` заморожен, не менять

## Что исследовать дальше

### Направление 1: Multilingual reranker вместо порогового допуска

Проблема: MPNet cosine similarity даёт 0.50 для Typer gold vs 0.75+ для M1.5.
Пороговой фильтрации недостаточно — нужен reranker, оценивающий пару
(вопрос, фрагмент) как бинарную классификацию.

Вопросы:
- Какой reranker работает cross-lingual без дообучения?
- Можно ли использовать cross-encoder из sentence-transformers?
- Как калибровать порог reranker отдельно от dense retrieval?
- Сохраняет ли reranker source-policy проверки?

### Направление 2: Расширение калибровки (M2c)

Порог 0.7453 калиброван на 4 документах (httpx, ruff, starlette, pydantic).
Typer не входит. Возможен новый M2c на расширенном корпусе.

Вопросы:
- Сколько документов нужно для стабильного порога?
- Сохраняется ли zero-FPR на расширенном корпусе?
- Не нарушает ли это план (M1.5 frozen, не подстраивать под Typer)?

### Направление 3: Причина различия scores

Почему MPNet даёт 0.84 для httpx gold, но 0.52 для Typer gold?
Разница в длине? В структуре? В семантической близости?

Вопросы:
- Зависит ли score от длины фрагмента?
- Влияет ли markdown-разметка на embedding?
- Отличается ли распределение scores для разных доменов?

## Как воспроизвести

```bash
# M0 RED
.venv/bin/python -m pytest tests/docs/test_multilingual_first_packet.py -v

# M3 + M5 (stub scorer)
.venv/bin/python -m pytest tests/docs/test_bounded_contextual_relevance.py tests/docs/test_m5_first_packet_green.py -v

# M4 dispatcher
.venv/bin/python -m experiments.crosslingual_relevance.m4_dense_candidates

# M5 real scorer
.venv/bin/python -m experiments.crosslingual_relevance.m5_real_scorer

# M6 holdout
.venv/bin/python -m experiments.crosslingual_relevance.m6_holdout
```
