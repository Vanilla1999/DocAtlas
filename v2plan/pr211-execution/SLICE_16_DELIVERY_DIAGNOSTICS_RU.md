# PR211: наблюдать фактическую причину delivery veto

У quality observer не было вызова на раннем validated delivery veto. Поэтому отсутствие его данных могло выглядеть как отсутствие retrieval, хотя acquisition уже вернул кандидаты и qualification их отклонил.

После проверки отказного публичного DTO существующий private observer получает фактические service traces: planning/retrieval/qualification отдельно от ranking/projection/coverage, до которых выполнение не дошло. Новые stage values blocked_before_projection и not_reached описывают этот путь. Публичный ответ, отказ, число retrieval calls и доступ к данным не меняются. Ошибка observer не может преобразовать отказ в успех.

Два fixture-only original запроса через настоящий handler различают реально найденный, но отклонённый кандидат с DocAtlas и полностью отсутствующий topic. Они сравнивают public bytes с наблюдением и без него, проверяют отсутствие sources/answer/edit authority, пустой snapshot, exact call counts, сохранность source text и cleanup observer. Нет fabricated успешной projection и нет подмены missing diagnostics пустым acquisition.

Независимый review agent_fixtures_impl APPROVE; выявленный stale diagnostic node hash исправлен. Root прочитал source diff и controls. AST/compile без исполнения, JSON и node inventory PASS. Runtime ожидается в обычном PR CI. Это улучшение достоверности диагностики, не исправление semantic retrieval.
