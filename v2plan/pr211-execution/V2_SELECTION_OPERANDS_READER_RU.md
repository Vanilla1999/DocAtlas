# Existing V2 selection operands в acceptance reader

Этот report-only slice следует за reviewed131–135. Production и source acquisition
не меняются; собственное исполнение нового reader пока PENDING.

## Причина

В [CI130 reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38024963940/job/114135542071)
существуют все три V2_DELIVERY_OPERANDS: cache-reset, architecture, request-flow.
Из полных V2_FOCUSED_STAGE в console поместился только cache-reset.
Request-flow delivery summary сохраняет31 member windows/28 downstream windows,
но не содержит final source hashes и selection decisions.
Наличие qualified passage в Project/Unified и его отсутствие среди полных
публичных фактов не доказывает конкретный first veto.

Owning reader131 уже читает эти поля из того же сохранённого V2 report и создаёт
все три bounded records. Новый helper показывает их отдельным компактным видом.

## Изменение

Три `V2_SELECTION_OPERANDS` содержат:

- case/artifact identity и hash, исходный вопрос и observed record counts;
- public status/authority flags, source count и существующие source identity,
  line bindings и snippet hashes;
- stage status/observer counts, pre-projection/selected IDs, considered variants,
  projection rejections и final visible IDs.

Body text и source files не читаются дополнительно. Вопросы, pipeline, oracle,
thresholds, score, input corpus, mutation executor и workflow не изменяются.
Reader не восстанавливает пропущенные события и не называет отсутствие строки
доказанным first loss. Hash source record сам по себе не является proof факта.

Используются уже bounded значения из `print_focused_stage_records`.
Их original count/omission envelopes сохраняются без повторного ограничения.
Новые строки идут после critical baseline/operands и recovery operands, перед
literal receipts. Это добавляет три private diagnostic records и может уменьшить
число более поздних строк в console; для нового типа добавлен отдельный omission
counter. Прежние384000-byte console budget,512-byte reserve и полные persisted
artifacts сохраняются. Этот размер не является потолком пользовательского output.

## Source review

- `scripts/summarize_acceptance_artifacts.py`, mode100644:
  `1fa3deb9b90200f634daca29efd6dc5359823173` →
  `5b4f0388f5f828f8f7c259ff8b3deb755323d636`.
- Proposed838physical lines; SHA-256
  `64c0f4c008b64993d64e185b74b04b9b36bf5971ab057e5c719dbcab1860311c`.
- Exact inverse удаляет один pure helper, одну record insertion, один counter
  и одну already-bounded registration; получается previous source побайтно.
- Полные старые delivery/full-stage/literal records сохраняются.
  Нового import, filesystem read, runtime launch или evaluation нет.

Это отдельный diagnostic follow-up до planned V2 product change.
Joint targets остаются critical61healthy/39kills и recovery12healthy/43kills;
индивидуальные literal receipts и новые selection records ещё требуется получить
в существующем PR CI на собственном SHA. Actual source/client/quality PASS не заявляется.
