# Точный учёт активных acceptance cases в существующих JUnit

## Почему нужен этот вывод

На `067dd56044fb1fe292af2d17783154c8a4b7c092` все три core lanes завершились:
**6000 PASS / 1837 FAIL / 0 ERROR / 10 SKIP** в каждой версии Python.
[Diagnostics 114029489614](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321138/job/114029489614)
проверил XML counts, уникальность concrete node IDs и hashes; integrity issues пусты.

Прежняя консоль печатала только failing modules и часть failure traces.
Отсутствие модуля в таком списке не доказывает, сколько его tests были collected.
Поэтому точный PASS новых member-reader guards нельзя было заявить по отсутствию failures.

## Что меняется

В том же reader, из тех же уже скачанных core JUnit, добавлен `JUNIT_TRACKED`:

- отдельные observed counts и collected count по восьми изменяемым модулям для каждой Python lane;
- artifact filename и SHA256 самого XML;
- concrete outcomes новых reader invalid-storage cases, реальных service fixtures,
  generated-artifact fixture, alias contract и нового intent contract;
- отсутствующий модуль явно имеет collected=0, а не предполагаемый PASS.

Все тесты по-прежнему исполняет существующий core job. Reader не импортирует project code,
не запускает pytest и не переписывает результат. Полный JSON artifact и полный список
JUnit cases сохраняются; прежняя проверка integrity и required-ci verdict не меняются.
Консоль остаётся ограниченным транспортом с явным omitted_rows; это не output ceiling продукта.

Новый output предназначен для проверки следующего общего SHA. Это не заявление о
положительном результате новых intent/tests до их фактического CI.
