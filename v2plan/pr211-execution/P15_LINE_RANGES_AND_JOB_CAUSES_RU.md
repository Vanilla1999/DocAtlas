# P1.5: точные переводы строк и причины реальной подготовки

На `841e770e644dba369ab441ba2ec9f2a8807cac7f` фактически выполнен [P1.5 run 37989905374 / job 114021107539](https://github.com/Vanilla1999/DocAtlas/actions/runs/37989905374/job/114021107539).

Результат: 1/7 cases, 0/6 полных обязательных фактов, пять runtime errors при partial public preparation. Отдельный project-document case воспроизводит изменение только index SHA при первом чтении. Независимые self-controls остановились на advisory-only negative с infrastructure member, заканчивающимся переводом строки. Syntax и always-upload выполнены успешно.

## Исправление oracle

Исходный line-range check нормализовал raw строки через splitlines и join, теряя финальный LF/CRLF. Из-за этого точные char/byte ranges и hashes могли быть верны, но строковое окно ошибочно считалось неверным. Теперь окно собирается из splitlines(keepends=True), сохраняя исходные байты. Все прочие coordinate, source/display hash, member roster и полный факт guards остаются прежними.

В существующем assignment-source control проверяются LF, CRLF и terminal blank line; подделанный line_end по-прежнему отвергается. Все шесть имён self-tests сохранены. Вопросы, candidate bytes, gold facts, source roles и frozen protocol не меняются.

## Наблюдаемость подготовки

Требование реального succeeded job не ослаблено. При partial/failure дополнительно читаются target_results/errors/warnings из фактического job tracker по тому же job_id. Именно этот producer сохраняет terminal target summaries в DocsPrefetchService. Эти данные только объясняют failure, не подменяют registry, preparation или retrieval.

Сообщение исключения сохраняется полностью в отчёте и fixture diagnostic, чтобы действительная target cause не пропала при обрезке. Исторический отчёт не перезаписывается.

Root и отдельный reviewer прочитали все три exact diff и producer. Локальные imports/pytest/AST не выполнялись. Runtime и quality PASS для этого изменения ещё не получены; они требуют следующего CI.
