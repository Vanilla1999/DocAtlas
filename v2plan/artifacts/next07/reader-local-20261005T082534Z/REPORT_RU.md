# PARTIAL — READY_NATIVE (исторический CI) / MODEL_NOT_RUN

- Ветка: `next07-feasibility-audit`; HEAD: `f8805a5d696e4ed023fb96f2f7af5f23ccc3e480`.
- Проверенная revision: `1c326db1106998b84bb3b53eeda44c073dddfdff`.
- Все 11 опубликованных reviewed hashes совпадают. Полные SHA-256 рабочей копии и проверенной revision: `tracked-hashes.json`; сравнение reviewed hashes: `reviewed-hash-comparison.json`.
- HEAD отличается от проверенной revision только добавленным SUMMARY_RU.md. Незакоммиченные пользовательские изменения сохранены в `dirty.patch`; перечень, включая untracked: `git-status.txt`. Чужие файлы не изменены.
- Техническое evidence переиспользовано: Actions 37282546116, 72 PASS, native 10/10, FastAPI scripted reachability. SHA-256 исходного artifact ZIP: `83ab3d7782fde300a1465cf9ba75d29f72ba6d7156272178e1c05618a00539e6`. Здесь ZIP заново не скачивался; основание — опубликованный отчёт, копия `prior-technical-evidence-summary.md`. Это не новый PASS грязной рабочей копии.
- Точная модель не выбрана пользователем. Адаптер: OpenAI Chat Completions. OPENAI_API_KEY отсутствует в текущем environment; ключи не печатались. IDE-подписка не использовалась.
- `.venv/bin/python` — Python 3.13.12, не требуемый Python 3.12. Системный `/usr/bin/python3.12` — 3.12.3, но project environment с действующими зависимостями для него не подтверждён. Окружение не заменялось.
- `pip freeze` завершился с exit 1; пакеты текущего окружения отдельно сохранены через importlib.metadata в `installed-distributions.json`. Основные команды и exit codes: `commands.json`. Дополнительная команда проверки `/usr/bin/python3.12` и сохранения metadata завершилась с exit 0.
- Локальные tests/native/live не запускались. A: 0/10, B: 0/10; model calls: 0; объём и latency модели: не измерены.
- Модельные/provider ошибки, помощь навигации, лишние чтения, неправильные subject/conditions, honest unknown и вопросы пользователю: не измерены, ответов модели нет.
- Независимая проверка: REVIEW_PENDING, blind queue не создана; reviewer не запускался без ответов. Автоматического semantic PASS нет.
- Продолжение требует точного выбора модели, OpenAI API credential в environment и готового Python 3.12 project environment. Разрешённый объём остаётся 20 независимых сессий / максимум 40 calls, без повторов до успеха.
- Production, tests, prompts, cases, caps, corpus и evaluator не менялись. N10 не запускался. Исторические 48/49 не переоценивались.
- Rollout: NOT_AUTHORIZED.
