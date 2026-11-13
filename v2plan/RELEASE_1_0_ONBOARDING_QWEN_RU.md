# Релиз 1.0: first-run опыт и путь Qwen-реранкера (анализ, 2026-11-13)

Цель: после установки пользователь сразу может пользоваться продуктом, а желающие
включить Qwen-отбор могли это сделать за минимальное число понятных шагов.

## 1. Что пользователь получает сегодня сразу после установки

`scripts/install.sh` ставит `uv` + `doc-atlas` из PyPI и регистрирует docs-MCP
(`doc-atlas mcp docs-serve`) в Claude Code / OpenCode / Codex. Базовый путь
(лексический отбор, `get_docs_context` → `prepare_docs` → ответ с источниками)
работает из коробки: это контракт `docatlas-agent-contract-v1`, он документирован.

Вывод: **дефолтный путь к 1.0 готов**. Проблема — «Qwen-путь».

## 2. Текущее состояние Qwen-пути (no_redundancy)

### 2.1 Что нужно включить (ничего из этого не задокументировано публично)

| Переменная | Значение | Назначение |
|---|---|---|
| `DOCATLAS_EXPERIMENT_PAIRED_QWEN` | `1` | включает paired-скоринг (checked pool) |
| `DOCATLAS_EXPERIMENT_QWEN_STUDY` | `1` | включает study-слой отборочных режимов |
| `DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE` | `no_redundancy` | режим отбора (control/no_stop/no_redundancy/relative) |
| `DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH` | абс. путь к каталогу | подготовленные веса, `verify_assets` на каждом вызове |
| `DOCATLAS_EXPERIMENT_PAIRED_CACHE` | абс. каталог (опц.) | кеш оценок; иначе каждый вызов считает заново |

Защитные ограничения: `DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1` запрещён;
требуется нативный контекстный token budget; pool-настройки pruning/units
должны быть `control` (не задавать `*_PRUNING`/`*_UNITS` env). Один механизм
за раз: `QWEN_STUDY=1` + mode != control запрещён (`experimental_qwen_ablation.py`).

### 2.2 Модель

- Пин: `Qwen/Qwen3-Reranker-0.6B` @ `e61197ed45024b0ed8a2d74b80b4d909f1255473`,
  9 файлов с точными SHA-256 + `provenance.json` (`context_evidence_scoring.py`).
- Каталог строго с этими файлами: любой лишний файл → `evidence_model_unpinned_extra_asset`.
- Скрипт подготовки есть **только в eval**:
  `eval/blind_project_context/step10-open-scorer/prepare_assets.py`. Он не входит
  в пакет, не документирован и жёстко требует CUDA уже на этапе подготовки.
- Веса ≈ 1.2 ГБ (`model.safetensors`).

### 2.3 Жёсткий пин рантайма

`_load()` сверяет фактический рантайм с `RUNTIME` дословно
(`evidence_model_runtime_mismatch`, без деталей «что ожидалось / что реально»):

- `torch 2.10.0+cu128`, CUDA 12.8, **capability `[12, 0]` — только Blackwell (RTX 50xx)**;
- `transformers 4.57.1`, `tokenizers 0.22.2`, `safetensors 0.8.0`, bfloat16, sdpa, batch 1.

То есть сегодня Qwen-режим физически работает только на RTX 50-й серии
с cu128-сборкой torch. На любой другой GPU — молчаливый отказ вызова.

### 2.4 Несостыковка в packaging

`pyproject.toml`: extra `reranker-mini` ставит `torch==2.10.0` — это CPU-колесо,
которое заведомо не совпадает с пином `2.10.0+cu128`. Пользователь, следующий
логичному пути «поставь extra», получит `evidence_model_runtime_mismatch`.

### 2.5 Политика отказа

Скоринг не имеет лексического fallback (осознанно, `score_rows`: «No lexical
fallback»). Любая ошибка (нет каталога, другой GPU, нет CUDA, кривой кеш) роняет
весь `get_docs_context` с непрозрачной строкой ошибки. Для эксперимента это
правильно; для «пользователь включил и оно просто работает» — главный UX-риск.

### 2.6 doctor не знает о реранкере

`doc-atlas doctor` не проверяет ни env-комбинацию, ни assets, ни совместимость
GPU/рантайма. Единственный способ диагностики — читать traceback.

## 3. Варианты для 1.0

### Вариант A: Qwen остаётся документированной экспериментальной опцией (минимум)

1. Перенести/адаптировать `prepare_assets.py` в продукт: команда
   `doc-atlas reranker prepare --out DIR` — скачивает запиненный ревизион,
   проверяет SHA-256 (в т.ч. LFS), пишет `provenance.json`; CUDA на этапе
   подготовки не требуется.
2. `doc-atlas reranker check DIR` — проверяет assets + рантайм и печатает
   понятную таблицу «ожидалось / фактически» (torch, CUDA, capability, env).
3. В `doctor` добавить группу `reranker`: env, deps, assets, GPU.
4. Понятные ошибки: `evidence_model_runtime_mismatch` включает diff пина;
   подсказку «какая GPU поддерживается».
5. Документация: `wiki/Reranker.md` + раздел в README: требования, шаги,
   точные env, оговорка «экспериментально, метрика = доставка свидетельств».

Оценка: 1–2 дня работы, не меняет продуктовых контрактов.

### Вариант B: перевести no_redundancy в поддерживаемый режим (дорого)

Дополнительно к A: установка cu128-torch (installer-флаг `--with-reranker`
или отдельный uv-инструмент), возможно ослабление пина capability (минимальный
порог вместо точного списка), graceful degradation (фолбэк на лексику с явным
receipt). Требует: решения о пинах (они были зафиксированы под эксперимент),
повторных прогонов на поддерживаемых конфигурациях, изменения контракта
«no fallback». Отдельное решение владельца; в 1.0 по умолчанию НЕ рекомендую.

## 4. Мелкие first-run улучшения (независимо от варианта)

- В выводе install.sh после регистрации MCP — одна строка «далее: открой агент
  и спроси что-нибудь; при `prepare_docs` следуй возвращённому действию».
- `doctor` по умолчанию в человеческом выводе (сейчас JSON-only) с итогом OK/FAIL.
- CHANGELOG + bump версии, прогон `scripts/release_gate.py`.

## 5. Что не меняем (фиксируем ограничения контракта)

- Пин модели и SHA-256 ассетов; локальность (`local_files_only`), доверие только
  подготовленному каталогу.
- «Отбор не отвечает на вопрос»: метрика остаётся доставкой свидетельств;
  semantic correctness не заявляется.
- Никаких скрытых фолбэков и авто-скачиваний без явного consent.

## 6. Чек-лист релиза 1.0

- [x] Решение A/B по Qwen-пути — владелец выбрал **A** (2026-11-13).
- [x] (A) `reranker prepare` + `reranker check` в CLI (`docmancer/cli/reranker_commands.py`,
      логика `docmancer/docs/application/reranker_setup.py`), doctor-группа `reranker`
      (только при `DOCATLAS_EXPERIMENT_PAIRED_QWEN=1`).
- [x] Понятные ошибки пина рантайма: `evidence_model_runtime_mismatch` включает
      diff «ожидалось/фактически» и подсказку про supported GPU.
- [x] `wiki/Reranker.md` + README-раздел + индекс wiki; комментарий в pyproject
      про `reranker-mini` (CPU-колесо, не удовлетворяет пину).
- [ ] Прогон установочного сценария с нуля (чистый uv-кеш) на Linux + macOS.
- [ ] release_gate + публикация.

### Валидация 2026-11-13 (репо-venv, Linux)

- `reranker check` на реальных подготовленных ассетах (`~/.local/share/docatlas-eval/step14/assets`):
  assets [ok], все несовпадения пина показаны с expected/actual, exit 1 + подсказка установки cu128.
- `reranker check` без аргументов и env: «path not set», exit 1.
- Гарды `prepare`: относительный путь и непустой каталог отклоняются понятной ошибкой.
- Полное скачивание `prepare` из этой сети невозможно: Hugging Face API и `resolve`
  малых файлов доступны, но редирект весов на CDN `us.aws.cdn.hf.co` блокируется
  (TLS handshake обрывается; подтверждено curl). Ограничение окружения, не кода;
  в wiki добавлено примечание про подготовку на другой машине.
- `doctor --check reranker` при `PAIRED_QWEN=1` даёт BLOCKER `RERANKER_NOT_READY`
  с командой исправления; без env — группа молчит, статус дефолтного пути не меняется.
- Полный прогон `prepare` end-to-end с проверкой хэшей не выполнялся (см. пункт
  про CDN); логика верификации повторяет проверенный eval-скрипт и та же
  сверка SHA-256 проходит через `check` на реальных ассетах.
