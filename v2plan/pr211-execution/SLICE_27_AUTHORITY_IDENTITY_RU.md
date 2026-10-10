# Slice 27: одинаковая identity для текущих authority aliases

На ec85a49 Task33 показывает 53 PASS / 11 FAIL. Положительный NativeVoice SDK
сохраняет полные исходные документы и create-parent binding, но валидатор отвергает
mutation binding. Причина в production: evidence_identity_for_item для raw
`authority=official` вычисляет supporting identity, тогда как build_action_packet
нормализует тот же источник в canonical через _effective_authority.

`_authority` теперь признаёт `official`
и `project_owned` теми же canonical aliases. Это согласование двух текущих
нормализаторов, а не замена fixture authority ради зелёного теста. Explicit
_packet_authority продолжает иметь приоритет. Demotion по catalog, module scope
и explicit_agent_policy остаётся в _effective_authority без изменения; supporting
identity после demotion сохраняется. Authority остаётся частью evidence hash.

Изменена только эта set literal в _action_packet_part01.py. Код вне функции и
42 определения сохранены. Не добавлен fallback, принимающий оба evidence ID.
General helper по-прежнему не вычисляет contextual demotion без контекста.

Root source review c68719868910b3d3a1b8d0660bcb62e52875bedb: APPROVE;
independent investigation: question_recovery_impl. Существующий NativeVoice
positive и неизменённые binding negatives проверят изменение в обычном CI.
Local AST/runtime NOT RUN: exec transport недоступен. Runtime PASS пока не заявлен.
