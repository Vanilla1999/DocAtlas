# V40: DocAtlas prepared-parent и Grounded — сохранённые результаты
Даты прогонов: 12–13 октября 2026. Ветка: `fix/main-flow-compact-evidence`.

Этот каталог сохраняет отчёты, машинные метрики и независимый пересчёт по **одним и тем же 40 историческим вопросам и 15 исходным файлам пяти проектов** (Black, Poetry, Textual, Vite, ESLint). Исходные вопросы и эталоны лежат в [eval/prepared_model_comparison40](../../../../eval/prepared_model_comparison40/README.md). Слепым holdout тест не является.

## Что находится в каталоге

| Файл | Содержание |
|---|---|
| [RESEARCH_AND_FAILURES_RU.md](RESEARCH_AND_FAILURES_RU.md) | Что реально сделано, основания в исследованиях, карта потерь и техническое решение |
| [ARCHITECTURE_RU.md](ARCHITECTURE_RU.md) | Старая/новая архитектура: 40 пар, стоимость, разбивка по стадиям |
| [ARCHITECTURE_CASES.csv](ARCHITECTURE_CASES.csv) | Все 40 вопросов и исходы обоих режимов DocAtlas |
| [STAGE_PROOF.json](STAGE_PROOF.json) | Проверка кандидатов и золотых диапазонов по 10 ключевым случаям |
| [GROUNDED_REPORT_RU.md](GROUNDED_REPORT_RU.md) | Grounded top-2 / top-5 и сопоставление с DocAtlas |
| [GROUNDED_INITIAL_LITERAL.json](GROUNDED_INITIAL_LITERAL.json) | Исходный буквальный результат без дополнительной нормализации |
| [GROUNDED_MARKDOWN_EQUIV.json](GROUNDED_MARKDOWN_EQUIV.json) | Исследовательская оценка с нормализацией Markdown, выполненной после просмотра исходных результатов |
| [score_grounded_v40.py](score_grounded_v40.py) | Пересчёт из сырого Grounded ZIP и извлечённого DocAtlas ZIP; CLI пути параметризованы |

## Проверенные итоги

| frozen evidence delivery | DocAtlas legacy | DocAtlas prepared-parent | Grounded 2 | Grounded 5 |
|---|---:|---:|---:|---:|
| Положительные | 18/24 | 18/24 | 21/24 | 22/24 |
| Документированная часть частичных | 4/8 | 5/8 | 7/8 | 8/8 |
| Отрицательные с пустой выдачей | 1/8 | 1/8 | 0/8 | 0/8 |

Результаты Grounded 21/24 и 22/24 относятся к **экспериментальной Markdown-equivalent оценке**; буквальная исходная версия дала 15/24 и 16/24. Основной структурный вывод не изменяется: Grounded присылал существенно больше исходного текста, так что это **не fair equal-token-budget A/B**. Ни в одном сравнении генератор ответа не вызывался.

## Оригинальные сырьевые данные и исполнение

- [DocAtlas V40 CI run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38307961403), [raw artifact 11772859414](https://github.com/Vanilla1999/DocAtlas/actions/runs/38307961403/artifacts/11772859414): 80 публичных MCP JSON, selection receipts, trace и логический state SQLite. SHA-256 ZIP: `343a81cfd4380cfb081a787684f0eb39f86b5b4ee2a9b93c8c2344a866f450e0` (9,399,403 байта).
- [Grounded V40 CI run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38316181819), [raw artifact 11777480417](https://github.com/Vanilla1999/DocAtlas/actions/runs/38316181819/artifacts/11777480417): 5 локальных индексаций, 80 фактических CLI JSON, stderr и manifest. SHA-256 ZIP: `e340935ca43b6c37714392e709141ed9221872d93431a4ca3516e93e737ec273` (435,836 байт).
- Важное ограничение: GitHub Actions artifacts имеют **retention 14 дней** и здесь **ссылаются**, но ZIP не добавлены как бинарные Git blobs. Итоговые машинные оценки, таблицы, скрипт и выводы сохраняются в репозитории постоянно. При необходимости сырой runtime воспроизводится из замороженного корпуса и CI/runner.

Коммиты кодовой базы: исправление после trace [6a133805](https://github.com/Vanilla1999/DocAtlas/commit/6a133805d7b8bfc1777e35be3a8f288b3e8b3b08); сравнение двух сборщиков [7bb61ef8](https://github.com/Vanilla1999/DocAtlas/commit/7bb61ef8b72965bdbdf42cdd7c48ec59931989d0); Grounded comparator [67889012](https://github.com/Vanilla1999/DocAtlas/commit/67889012296a25ec32fea580776ccc687aab8c54).

## Повторный подсчёт

Для полного автоматического пересчёта понадобятся сохранённые сырые CI ZIP. Извлеките DocAtlas artifact в отдельный каталог, затем:

```bash
python reports/admission-experiments/prepared-retrieval/v40-comparison-20261013/score_grounded_v40.py \
  --grounded-zip grounded-v40-full-actual.zip \
  --docatlas-dir extracted-docatlas-v40 \
  --output recomputed-v40.json
```

Код исходных раннеров: [eval/structural_assembly40](../../../../eval/structural_assembly40/) и [eval/grounded_v40](../../../../eval/grounded_v40/). Сам score script не обращается к индексам или LLM и **не поставляет oracle в retrieval**.

Документация по дефектам и ограничениям не подразумевает включения нового сборщика по умолчанию; opt-in/default не изменены этой публикацией.
