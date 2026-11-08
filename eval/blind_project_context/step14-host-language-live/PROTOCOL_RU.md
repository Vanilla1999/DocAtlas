# Step14 live A/B/C: подготовка, НЕ ГОТОВО К ЗАПУСКУ

Это seen diagnostic, не blind gate. Исходные четыре вопроса и 19 фактов находятся в точной копии `tasks.json`; модель не должна видеть этот файл и аннотации. Никаких результатов новых сессий здесь нет.

## Состав

* A: MCP, `concise-v1`, `language_preflight=model`, настоящий Qwen minimal-context и `one-hop-v1`.
* B: идентично A, кроме `language_preflight=host-v1` и необходимого отдельного workspace binding.
* C: native files, те же шесть оригинальных project-документов, без private module; `concise-v1` как аргумент builder, не превращающий files-инструкцию в MCP-инструкцию.

Одинаковы вопросы, corpus, policy, recipe, common/source-to-draft инструкция, модель `openai/gpt-6.1-terra#low`, 12 шагов и 900 секунд на сессию. Рандомизации нет: сохранить порядок V-M1..V-M4 и A/B/C; всего 12 свежих сессий. Отличия backend-specific инструкций и схем фиксировать отдельно. Внешний отвечающий provider не подменяется. Не использовать прежние ответы как новые результаты.

## Блокеры до запуска

1. Точные локальные Qwen assets и совместимый установленный Python/CLI отсутствовали по сообщению родителя; их ищет родитель. Не скачивать и не устанавливать здесь. Проверить их по `step10-open-scorer/assets-provenance.json`, `verify_assets` и runtime против `step12-live-comparison/runtime.json`; сохранить вывод и hashes, не выполнять inference при проверке.
2. Нужно независимо подтвердить установленный DocAtlas с нужными Qwen/one-hop возможностями и hash wheel/исходников, пригодность GPU/runtime, OpenCode и доступность разрешённого provider. Прошлый receipt не доказывает текущую среду. Если не совпадает — остановиться, не менять рецепт/эталон.
3. Предстоит отдельная реализация/проверка runner и public `prepare_docs` на новом изолированном состоянии; прошлый `step12-live-comparison/run.py` непригоден без переработки: использует старые абсолютные пути, `standard`, старые имена arms и writes в старые артефакты. `account.py`/`audit.py` также жёстко привязаны к старым путям и не являются готовым анализатором этого прогона.
4. Для измерения host status, включая завершение до первого provider request, нужен проверенный capture actual MCP request/response и monotonic timestamps, не только observer provider hooks. Ограничения capture следует записать явно. Разработать и проверить instrumentation до запуска, не утверждать timing без неё.

## Предварительные команды после предоставления точных assets

В корне worktree (ни одна команда ниже не запускает модель или установку):

```sh
python3 eval/blind_project_context/step14-host-language-live/verify_inputs.py
```

После того как родитель предоставит проверенные пути к установленному интерпретатору и локальным assets, можно без inference выполнить:

```sh
QWEN_PY=/absolute/path/to/installed/python
QWEN_ASSETS=/absolute/path/to/local/assets
"$QWEN_PY" -c 'import sys; from docmancer.docs.application import context_evidence_scoring as s; s.verify_assets(sys.argv[1]); print("asset verification passed; expected runtime:", s.RUNTIME)' "$QWEN_ASSETS"
```

Это не проверка установленного GPU/runtime и не доказательство установленного wheel: их сверить отдельно с `step12-live-comparison/runtime.json`, provenance и текущим commit. Затем построить отдельный corpus, public active snapshot и 12 новых configs через `documentation_profile.build_profile` (см. `profiles.json`). Генератор требует реальные существующие executable, python, project и workspace; заполнители нельзя выдавать за готовые configs. Использовать отдельные новые каталоги вне checkout и вне corpus, без наследования посторонних AGENTS/config, отдельный `DOCATLAS_HOME`; сервер должен видеть один и тот же подготовленный snapshot. Перед созданием сравнить источники с `manifest.json`. На каждый config добавить observer из Step12 с отдельным capture path; не переиспользовать его старые файлы.

Запуск возможен только после завершения вышеуказанных блокеров и проверки runner родителем. Нет безопасной готовой команды запуска до создания и проверки runner: `run.py setup/run` из Step12 не применять. Заранее фиксировать все session IDs и started markers, сохранять первые raw events, stderr, запросы/ответы и receipt, не перезапускать неуспешные сессии автоматически. После каждой сессии проверять hashes corpus и active snapshot, обеспечить cleanup только собственных процессов.

## Оценка

Сохранить raw данные до независимой семантической оценки каждого итогового ответа и отдельно оценить delivered source facts по оригинальным 19 фактам, допустимым путям, точному тексту/hash/span, scope/version и состоянию; V-M4 имеет ноль фактов и проверяет корректное признание отсутствия доказательства, не доступ к private module. Считать реальные provider requests, status/context/source/file calls, Qwen pairs, ошибки/retries, время, provider usage/cache и локальные оценки отдельно; неизвестное — null. Для A/B проверять порядок настоящего status относительно первого provider request и одинаковость retrieval-условий; не считать отсутствие model-вызова status отсутствием host-вызова. Нельзя делать вывод о стоимости, качестве или PASS до настоящего измерения. Транспортная диагностика Step14 — другой уровень доказательств.
