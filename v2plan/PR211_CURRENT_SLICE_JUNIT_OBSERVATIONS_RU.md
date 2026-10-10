# PR #211: наблюдения из того же JUnit

Обновление `scripts/summarize_pytest_acceptance.py` печатает из уже созданных core JUnit artifacts результаты узких семей текущего пакета: Context7 после retirement, пять read fixtures в docs_service_part03, новый mixed contract и два существующих quality controls.

Причина: на eb2c4f3b aggregate модуля docs_service_part03 улучшился с 6 PASS / 18 FAIL до 10 PASS / 14 FAIL, но такая разница не доказывает индивидуальный результат каждой из пяти миграций. Для следующего SHA нужны реальные node outcomes, а не вывод из счётчика. Новый mixed contract и мигрированный Legacy oracle также должны иметь наблюдаемый исходный traceback при отказе.

Reader по-прежнему не запускает тесты и не импортирует runtime приложения. Workflow, pytest selection, assertions, thresholds, return policy и обязательные aggregates неизменны. Полный artifact сохраняет все случаи. Ограничение объёма консоли и явный `omitted_rows` остаются; это транспорт диагностики, не output ceiling продукта. Новых jobs, reruns или duplicated tests нет.

Base blob `3de25fe8481ccd8ac13d2deeb215d73610ca59fd`; proposed `5b98d9d29364413966c334f43383d44a0f0f20aa`, mode `100644`. Root проверил пять точных замен и обратное побайтное восстановление исходника. Обычный запуск reader на существующих JUnit следующего CI остаётся PENDING; добавление диагностических строк не означает PASS тестов.
