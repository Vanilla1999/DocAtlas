# ActionPacket part02: миграция восьми узлов на v4

## Область и состояние

- База review: `067dd56044fb1fe292af2d17783154c8a4b7c092`.
- Только `tests/docs/test_action_packet_part02.py`: blob `2a7484614e857bf22a4663fd1b78cd624a951fc5` → `e41278478ea356e917e9c7e5c680f4f4e12aa612`.
- Все восемь имён тестов и 23 различных исходных выражения вопроса сохранены. Исходные paths, body/snippet strings, metadata, длинные и отрицательные fixtures сохранены.
- Три локальных assertion helpers, 762 физические строки; новых collected test nodes нет. Production, shared façade и retrieval не изменены.
- Это статически проверенная миграция. pytest/import/server/provider локально не выполнялись; runtime результат требует прогона на конечном commit SHA.

## Контракт, по которому переписаны ожидания

Публичный `build_action_packet` возвращает v4 evidence data с `edit_ready=False`. Он не принимает `max_tokens` и не выводит из текста mutation plan, команды, invariants или нормативные разрешения. Полное окно остаётся `untrusted_data`; literal assignment удостоверяет только точную цитату и её binding.

Это следует из текущих `_action_packet_part03.py`, `_action_packet_part04.py`, `_evidence_selection_part01.py`–`part03.py`, `evidence_requirements.py`, `evidence_candidates.py` и `trust_contract.py` на базе выше. Public import `refresh_action_packet_estimate` проверен через `action_packet.py`.

| Сохраняемый test node | Что проверяет миграция |
|---|---|
| `test_action_packet_is_deterministic_deduplicated_authority_filtered_and_cited` | Перестановки; точный duplicate; четыре исходных nonstale окна; authority/scope; snippets A/B; оба code chunks; все 101 ranked окна без потери; отсутствие доказательства metadata-only symbol; две версии без явного запроса, exact-only и отказ fallback-only при `exact_version=1.0`; distinct symbol identities; host rejection по path/library; risk diagnostics и явное отклонение. |
| `test_safe_project_docs_preserve_cannot_and_phase_scope_as_source_backed_guidance` | Обе исходные полные цитаты заданы explicit `required_fact/document_statement` и ограничены точным evidence path. Полный body, включая curl, остаётся untrusted. Hash/character/line spans свидетелей проверены. Неправильный scope и роль `project_rule` не закрывают behavioral guard. |
| `test_strict_behavioral_packet_fails_closed_when_only_target_surface_remains` | Код с PermissionService даёт буквальный content witness, но не снимает `behavioral_contract_required`. |
| `test_strict_behavioral_packet_rejects_credential_exfiltration_in_project_docs` | Исходный hostile README полностью процитирован как untrusted data; ни команды, ни behavioral grant, ни edit permission не возникают. |
| `test_strict_behavioral_packet_fails_closed_when_budget_removes_contract` | Историческое имя оставлено. Длинная исходная цитата сохраняется полностью, её explicit scoped literal witness закрывает contract; два required paths и spans остаются. Стоимость измеряется без потолка. |
| `test_action_packet_truncates_whole_items_and_fails_closed_without_evidence` | Все 100 строк и остальные исходные длинные/polarity/risk/prose cases сохранены. Empty и forged complete запрещены. Сохранены семь legacy malformed variants, добавлены current v4 invalid field types. Поддельная команда с обновлённым hash отвергается по настоящему source binding; поддельный requirement — по literal witness и canonical caller inputs. Metadata acceptance_conditions не заменяют отсутствующие body facts. |
| `test_required_evidence_and_targets_survive_packet_budget` | Все 11 display windows, включая восемь полных snippets, сохраняются; evidence/target identity assignments проверены. Claim `explicit_agent_policy` не повышает authority и не создаёт validation commands; identity-only packet остаётся partial. |
| `test_constraints_only_requires_canonical_source_backed_constraints` | Canonical/supporting provenance сохраняется. Ни один вариант не превращает prose в constraints-only mutation или content proof; оба остаются partial и non-authorizing. |

## Почему это не механическая замена старого status

1. **Identity и конфликт.** Одинаковые path/heading с разными байтами — два разных окна. Они не обязаны исчезнуть как duplicate и не дают семантического решения о совместимости правил. Отдельный отрицательный контроль задаёт двум исходным AGENTS окнам одинаковый stable_id: обе несовместимые bindings отклоняются с `stable_identity_collision:ambiguous-agents`. Структурно корректный failure проверяется отдельно от проверки повреждённых bound inputs; последняя обязана сообщить collision.
2. **Версия и trust.** Запрос «Use API» не задаёт версию. Exact 1.0 и latest сохранены как данные; явная версия добавляет обязательство и исключает fallback-only. Активный deny DTO — `sources.rejected` с нормализованной identity. Старое top-level risky и текущее `sources.risky` — не разрешения и не автоматическое отклонение.
3. **Behavioral guard.** Он остаётся живым. `document_statement` принимается только в явно перечисленном evidence path и при точном полном literal witness. `project_rule` сейчас не принимается даже с таким текстом. Полнота evidence не разрешает редактирование.
4. **Fidelity вместо ceilings.** Все прежние budget случаи больше не отбрасывают данные ради численного потолка. Проверяются полные окна, уникальные IDs, hashes, имеющиеся spans и точность наблюдаемой стоимости. Это не утверждение о минимально возможном размере.
5. **Подделки.** Новые отрицательные проверки меняют настоящий v4 payload. Ошибка witness/source binding проверяется после пересчёта hash/estimate, чтобы тест не проходил лишь из-за устаревшего имени поля или случайной ошибки сериализации.

## Приёмка

До publish — независимый review этого exact blob и сверка текущего base file SHA. После publish — восемь узлов на конечном SHA, затем общий acceptance/required gates. Ни статический подсчёт, ни отсутствие локального исполнения не являются CI PASS. Reduction этих восьми узлов здесь не выполняется.
