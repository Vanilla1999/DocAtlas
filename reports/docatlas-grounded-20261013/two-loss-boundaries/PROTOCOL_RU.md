# Диагностика E01 / P03, до исправления продукта

Разрешение: текущий запрос владельца — установить причину двух потерь исходных
фрагментов. Только исходные V40-P03 и V40-E01; corpus/questions/gold/evaluator
не менять. Два public in-process get_docs_context и две confirmed preparations,
installed8605cbdb wheel Python -I, real SQLite; не stdio/client/production.
Default без legacy experiment arms, прежний full-public-DTO cap12000.
Нет моделей, новых методов selection или исправлений retrieval.

Пассивный sys.setprofile observer в отдельном runner копирует ВСЕ rows на
search→acquisition→admission→selection→core→recheck→budget границах. Не подменяет
production функции, не изменяет объекты, не передаёт gold/целевые spans продукту.
Отдельно сохраняет реально выполненные budget.cost branches и полный omission list.
Ошибки observer и лимит4096 events/1024 source rows явны, absence при ошибке не
доказательство потери. Timing с profiler не сравнительный performance benchmark.
Источники и конечные результаты проверяет прежний независимый evaluator.
Результаты сравниваются офлайн с прежней выдачей по path/snippet/line spans:
различия isolated root/generation ожидаемы; equivalence не доказывает все свойства.

Лимиты:2 context attempts,2 prepare, context60s, prepare180s, wall600s;
без runtime retries, без запуска остальных38 вопросов. Остановиться при integrity
или read-only нарушении. Все исходники/wheel/runner/oracle/config pinning до calls.
После результатов проверить frozen inputs. Продукт на этапе диагностики не менять.
