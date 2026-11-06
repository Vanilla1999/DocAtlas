# Rev3 — remaining-label review before freeze/inference

Rev2 сохранён в history/draft-rev2/. Ни один source/question/required fact или
direct/structural unit не изменён. True hard negatives rev2 сохранены буквально.
Этот review не основан на scores; gate inference не было.

## Новые optional supporting witnesses

- C-L3 Queue ownership прямо отделяет lease от review approval, Raster pipeline
  прямо сохраняет approval/embargo несмотря на tile parallelism. Оба поддерживают
  обязательные approval/embargo условия, но не заменяют canonical conjunction
  curator+checksum и explicit embargo release. Необязательны как дубли.
- C-L3 Data flow: публикация только approved derivatives и preserved camera
  files не меняются при re-render. Поддерживает publication/recall traceability.
- V-M1/V-M2/V-M3 Planner: computed plan не permission обойти weather interlock
  или clock check. Это поддерживающее ограничение для suspension/restart,
  не требование запустить planner как дополнительный recovery step.
- V-M1/V-M2/V-M3 Services: calendar cannot authorize execution, gateway executes
  approved schedules; поддерживает разделение дисплея и operational approval.
- C-T1 Components: dashboard cannot acknowledge observations; checkpoint
  acknowledgement должен прийти от exporter, не display. Подтверждение authority.
- TideGauge intro для C-T1/C-T2/C-T3: fixed live observations отделены от survey
  imports. Дополнительный scope witness, не повод включить все navigation targets.
- Loom intro для C-L1/C-L2/C-L3: production queue отделена от interactive preview,
  camera originals preserved. Поддерживает уже обязательную production scope.
- Meridian intro для V-M1: confirmed night-time reservations отличаются от
  daytime training. Для V-M2/V-M3 не объявляем этот intro обязательным/полезным
  только из-за темы проекта; ancestor context для Services всё равно допустим.
- Cairn intro для V-C1/V-C2/V-C3: production immutable snapshot recovery отдельно
  от training. Identity: snapshot manifests bind stable IDs to checksums; staging
  path не новая identity. Поддерживает выбранный snapshot/его reconciliation и
  сохранение old/new identifiers, но не заменяет signed scan/approval условия.
- Cairn Components для V-C2/V-C3: publication switches pointer after review,
  не мутирует snapshot. Поддерживает previous-pointer preservation/rollback.

## Неполная разметка названа явно

Не делаем все overview/architecture bodies optional. Например, generic component
boundaries, documentation navigation и implementation layout не становятся
supporting evidence автоматически. Все остаточные bodies, не имеющие required,
optional или явно reviewed hard-negative label, теперь **unlabelled**, а не
доказанный noise. Exhaustive false-positive rate не заявляется. Отдельно считаются
доставленные true hard negatives, optional bodies и unlabelled bodies/tokens.

Этот компромисс не ослабляет recall, no-answer, source validity или true-hard-
negative gates. Все source tokens, включая optional/unlabelled/ancestor bodies,
по-прежнему входят в неизменный50% reduction criterion. No-answer требует пустой
полный successful scan независимо от того, как размечены нерелевантные тела.
Any-of equivalent witnesses не выдумываются:81 canonical fact quotes и complete
required obligations прежние. Новых обязательных alternatives нет.
