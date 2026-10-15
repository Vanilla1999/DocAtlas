# Slice 20: три ActionPacket v4 fidelity controls

База поведения: ActionPacket v4 на `0049c6d`. Старые три cases останавливались
на удалённом `max_tokens`; ожидания v3 не исполнялись.
[Task 33C evidence 118e5d1](https://github.com/Vanilla1999/DocAtlas/actions/runs/37968004995/job/113947140389).

Сохранены исходные вопросы, authored text, source paths, stable/parent IDs
и display hashes. Fixtures получили current whole-window coordinates.
Все 20 имён функций модуля сохранены; три cases мигрированы:

- обязательный OpaqueContractValue-739: сначала complete data с точным текстом,
  затем подмена реального rendered source;
- RareExactSymbol: сначала точный witness, затем потеря символа;
- обязательный permission contract: сначала complete data, затем удаление
  assignments; честный partial с точными missing IDs остаётся допустимым.

Подмены обновляют SHA, coordinates и token estimate, чтобы отказ приходился
на связь с исходным source window, а не на случайно сломанную schema.
Ожидаются конкретные guards `source differs from bound retrieval window`
и `complete data is missing mandatory assignments`. В positives и honest
partial `edit_ready=false`; prose не превращается в mutation permission.
Фиксированный output ceiling не восстанавливается.

Независимый question_recovery_impl review: APPROVE к CI; прочитаны schema,
реальный validator и exact diff blob `0ac6cb909fc32fe8afe2fe2dc12c838b6ca4c25f`
против `9d55f6b2ce918597f3fa414e2cbf6c710ea1997c`.
Local AST/runtime **NOT RUN** вследствие exec transport outage. PASS до нового CI
не заявляется.
