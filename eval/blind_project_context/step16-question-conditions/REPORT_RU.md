# Step16: завершённый парный опыт сохранения необходимых условий

2026-11-08. Четыре frozen вопроса × current / aspect-conditions-v1 = **8 ответов**.
**Общий выигрыш не установлен:** без спорного M7 кандидат покрывает на одну
позицию больше; с M7 оба варианта имеют по 12 full / 1 partial, но теряют разные
условия. Результат — небольшой диагностический опыт, не основание менять production.

## Исполнение и границы сравнения

Родитель выполнил 8 прямых `functions.subagent`: agent `general`, model
`openai/gpt-6.1-terra`, без variant и sessionID, свежая сессия на каждый ответ.
Два параллельных batch по 4, без повторов и выбора лучшего — по сообщению родителя.
Порядок заданий и wrapper: `launch-handoff.json`; IDs: `sessions.json`.
Экспорты подтверждают 8 разных сессий с outcome=succeeded и один user task в каждой.

Все сессии сообщают одну модель: provider `openai`, id `gpt-6.1-terra`, variant
**`default`**. Это не подтверждение Low и не доказательство конкретного effective
reasoning effort. Astra — исполнитель исследования. Старые effective defaults
неизвестны; новый прогон — парный в текущем harness, не точный historical replay.

`candidate.txt` заменяет только один проверочный абзац текущей инструкции:
определить аспекты вопроса, сохранить необходимые условия и их связь с действием,
отделить известные обстоятельства, фон и follow-up. Все остальные части prompt,
вопросы и evidence одинаковы в паре. Hash исходных восьми входов не изменён.
Источник: `manifest.json` и `generator-inputs/`; изолированные копии:
`/tmp/opencode/step16-generator-inputs/`. Rubric/gold туда не передавались.
Это изоляция пакета, не OS sandbox; по экспортам других чтений или tools не было.
Qwen/retrieval не запускались; нового редактора, доменных словарей или новых
генераций после получения ответов не было.

## Доставка: что именно доказано

В каждой экспортированной сессии:

1. Один вызов `read` с точным ожидаемым path, status=completed, truncated=false.
2. Полный tool result с последовательными номерами строк. После удаления только
   служебной нумерации каждая строка совпадает с frozen input; evidence JSON
   совпадает целиком, включая question/source text/ref/path/span/hash.
3. Второе assistant message — финальный ответ, созданный после завершения read.

**8/8 exact harness read results**, 16 assistant messages: по одному load-turn
и answer-turn на сессию. Это свидетельство доставки по harness transcript.
Raw provider request bodies и весь скрытый system context не экспортированы;
server-to-provider byte equality не заявляется. Повторный экспорт чужих сессий
не выполнялся. Нужные read inputs/outputs, response/message IDs и metadata
сохранены в `live/exports/` и извлечены в `live/results.json`.

Все предлагаемые необходимые утверждения присутствуют в прочитанном evidence:
12/12 групп без M7 и 13/13 с M7 в обоих плечах. Семантическая достаточность
опирается на независимые исходные документы и draft rubric; exact matching здесь
проверяет передачу пакета, **не оценивает правильность ответа**.

## Семантический review и sensitivity

`live/review.json` — неслепая оценка исполнителя: 42 позиции, 38 точных цитат
ответов, отдельные обоснования целых утверждений. Источники каждой позиции заданы
в `rubric-v2.json`, сами неизменные тексты/ref/hash/span — в `historical/cases.json`.
Предварительное независимое review requiredness получено до генераций; все
решения остаются draft, не owner-approved gold.

- M6 (начало уже действующей остановки) не обязательно для данного вопроса.
- M8 — допустимый follow-up о возобновлении наблюдений, не prerequisite передачи.
- P6: optionality проверяется, если upload упомянут; отсутствие не дефект.
- M3/M5 объединены в одну scoring group: различие ownership/execution и
  неизменность остановки могут быть выражены одной фразой, отдельные буквальные
  формулировки не требуются. В review сохраняются обе семантические позиции.
- M7 (ID на протяжении suspension) остаётся спорным и показан в двух вариантах.
- J1 (корректное воздержание) оценивается отдельно от положительных фактов.

| Draft denominator | Current | Кандидат |
|---|---:|---:|
| Без M7: 12 необходимых групп | 11 full, 1 partial | 12 full |
| С M7: 13 необходимых групп | 12 full, 1 partial | 12 full, 1 partial |
| Ошибочно добавленные ограничения, 4 ответа | 0 | 0 |
| Корректное воздержание | 1/1 | 1/1 |

Partial не засчитывается как full. Поскольку все группы присутствуют в read
result, эти показатели одновременно описывают draft конечное покрытие и
сохранение доставленных групп **на уровне harness transcript**. При отсутствии
raw provider capture нельзя отдельно подтвердить внутренний provider input.

Главное различие — V-M1:

- Current пишет «Для передачи подтверждённого ночного бронирования», но опускает
  **shared instrument** (M9 partial). Данное условие не задано самим вопросом.
  Кандидат: «Для подтверждённого ночного наблюдения на общем инструменте» — full.
- Current явно сохраняет «идентификатор бронирования при приостановке» — M7 full.
  Кандидат сохраняет ID при передаче, но не проговаривает временную область
  suspension — M7 partial. Неизменность остановки не объявляется автоматически
  эквивалентом явного ID-инварианта; обязательность отдельного утверждения спорна.
- Оба удерживают lock/pending даже после обоих approvals и снятие lock командой
  инструмента. Оба связывают restart prerequisites с наблюдениями, не передачей.
  Кандидат делает это явно: «не дополнительные условия передачи».
- Отсутствие stop-duty M6 у current и неполное его изложение у кандидата не
  считаются пропуском необходимого условия для уже действующей остановки.

RillPrint: необходимые scope, AND для purge, held blocker, export-before-purge,
successful verification-before-resume и неизменность receipts сохранены обоими.
В кандидате порядок purge→verify выражен последовательностью шагов 2→3.
Attachment limit и bounded abstention корректны в обоих плечах.

**Вторичное наблюдение после просмотра, не новая метрика победы:** кандидат
RillPrint пишет «does not ... give the purge and verification commands», хотя
`spool-verify` назван в source и самом ответе. Это неточное широкое описание
evidence gap; конкретная командная строка и аргументы действительно не описаны.
Оно отмечено отдельно, не превращено задним числом в ошибочное ограничение или
изменённый conditional-coverage criterion. Длина ответа не критерий победы.

## Реальный учёт токенов

**Harness-reported provider usage** из `opencode session export`: сумма
`assistant.tokens` точно равна `info.tokens` для каждой из восьми сессий.
Учитываются оба assistant turns, включая загрузку входа, не только final answer.
Индивидуальные значения и message provenance — `live/results.json`;
агрегаты — `live/summary.json`.

| Токены, сумма четырёх сессий | Current | Кандидат |
|---|---:|---:|
| `input` | 16 794 | 5 646 |
| `cache.read` | 49 408 | 60 928 |
| input + cache.read | **66 202** | **66 574** |
| `output` | 873 | 806 |
| отдельно reported reasoning | 0 | 0 |
| cache.write | 0 | 0 |

Общий учтённый вход: 132 776, выход: 1 679. Здесь input+cache.read следует
прежней конвенции OpenCode accounting; сырые поля сохранены отдельно. Это не
подсчёт tokenizer или слов. Нулевой reported reasoning не доказывает отсутствия
внутреннего reasoning. Export сообщает cost=0, но бесплатность не установлена.
Cache warm-up и параллельный порядок не контролировались; существенная разница
некешированного input не доказывает экономию кандидата. Общий вход почти одинаков,
у кандидата на 372 токена больше. Денежная стоимость не рассчитана.

## История, первичный блокер и неизменность

Исходный опыт: branch `work/step15-answer-condition-variants-20261108`, commit
`420e21924e486a7ebca8f4aa891cc176e07280f6`,
`eval/blind_project_context/step15-answer-conditions/terra-small`.
Его результаты 14/2, 15/1, 15/1, 14/2 относятся к прежним 16 требованиям.
Побайтные копии находятся в `historical/`. Исторический gold/ответы не менялись.
Новый знаменатель отличается: добавлены релевантные M3/M5, объединено lock-правило,
вынесены background/follow-up. Поэтому численное сравнение со старым 14/16
не является оценкой улучшения модели.

`pre-review/` хранит первую версию receipt/report с ошибочным выводом из Code Mode
search. `pre-live/` хранит исправленную версию до запуска. Ограничение было
**дочерней capability**: прямого launcher в списке инструментов исполнителя нет,
но он доступен родителю. Code Mode search не перечисляет прямые tools. Неизвестные
исторические defaults мешают точному replay, но не новому парному сравнению.
Родитель снял capability-блокер, выполнив все восемь запусков. Новых блокеров нет.

## Проверки и воспроизведение

Выполнялись только stdlib artifact tooling и поддерживаемый CLI export; никаких
product runtime/import/pytest/AST/install, изменения credentials/config или
commit/push. Существующие чужие изменения сохранены.

```sh
# Только первоначальная выгрузка восьми разрешённых IDs; существующие файлы не перезаписывает:
python3 eval/blind_project_context/step16-question-conditions/collect_live.py --export
# Полностью offline повторная проверка сохранённых exports:
python3 eval/blind_project_context/step16-question-conditions/collect_live.py
python3 eval/blind_project_context/step16-question-conditions/summarize_live.py
python3 eval/blind_project_context/step16-question-conditions/prepare.py
python3 eval/blind_project_context/step16-question-conditions/verify_artifacts.py
```

Результат: 8 exact reads, 8 финальных ответов, 16 assistant messages, usage
reconciliation 8/8; 42 review positions и 38 exact answer quotes. Проверки
source spans/hash и 16 исторических цитат также PASS. `checks.json` — общий receipt.
Скрипт не является независимым semantic judge: он проверяет комплектность,
цитаты, идентичность и арифметику сохранённой ручной оценки. Raw captures не выдумывает.

`sha256sum -c package.sha256` из каталога пакета проверяет финальные файлы;
исторические seals в подкаталогах проверяются относительно их исторической версии,
не относительно текущего пакета. `git diff --check` относится к tracked diff,
новые untracked файлы этой командой не проверяются.

## Исследовательская основа и ограничения

- [ConditionalQA, ACL 2022](https://aclanthology.org/2022.acl-long.253/): условия
  применимости ответа; адаптация оценки, не воспроизведение benchmark.
- [RAGChecker, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html):
  раздельная диагностика retrieval/generation; пакет RAGChecker не запускался.
- [Do RAG Systems Cover What Matters?, NAACL 2025](https://aclanthology.org/2025.naacl-long.301/):
  core/background/follow-up и гипотеза покрытия аспектов; retrieval не изменялся.
- [Sufficient Context, ICLR 2025](https://arxiv.org/abs/2411.06037): мотивация
  fixed-evidence контроля; достаточный контекст не гарантирует полный ответ.

Эти работы не доказывают эффективность на Terra. Один ответ на вариант,
четыре известных случая (три synthetic), неслепой review, спорная requiredness,
неизмеренная вариативность, неполная видимость системного/provider входа.
Кандидат остаётся экспериментальным файлом; глобальная production инструкция
не изменена. Финальное ревью родителя завершено: [REVIEW_RU.md](REVIEW_RU.md).
Пакет принят как ограниченный опыт; устойчивое преимущество не доказано.
