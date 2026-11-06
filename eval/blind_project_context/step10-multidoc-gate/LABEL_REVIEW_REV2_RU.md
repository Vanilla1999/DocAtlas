# Draft rev2: semantic review ДО любого inference

Parent review выявил ошибочные hard-negative labels для правдивых ограничений.
Rev1 сохранён в history/draft-rev1/. Документы, вопросы и81 fact quotes не менялись.
Это новое предложение разметки, не frozen gate и не реакция на scores.

## Контракт

Required direct/structural facts и complete obligation units обязательны.
Optional_support — допустимые дополнительные свидетели: отсутствие не снижает
recall, доставка не false positive; tokens учитываются в50% reduction criterion.
Ancestor bodies для optional witnesses — optional_context, не новые obligations.
True hard negative — похожая, но другая операция/condition, не evidence для
данного вопроса; это не обязательно ложный текст в исходном документе.

Для эквивалентных witnesses допускается явно размеченная any-of группа полных
source-backed witnesses на один required fact. В текущих дополнительных текстах
полные эквиваленты ВСЕХ частей canonical obligations не установлены: например,
запрет прогноза не заменяет interlock+operator conjunction. Фиктивные equivalences
не добавлены. Настоящая альтернатива заменяет all-of witness requirement на any-of,
не создаёт новое обязательное тело. Требовать все полезные alternatives запрещено.

## Ручной review исходного содержания

| Case | Почему optional_support необязательны | True hard negatives rev2 |
|---|---|---|
| C-T1 | Survey imports: новые IDs/offline heartbeat не live repair; Recovery simulation: immediate restart не live policy; Historical default: двухдневное удаление отменено; Display hiding не pause; Refresh не replay. Это подтверждает canonical checkpoint/IDs/heartbeat/retention, не добавляет действия. | Journal design: station/day layout не recovery/deletion conditions. |
| C-T2 | Preview ограничен sandbox; Display hiding не меняет export membership. Canonical checksum/missing/revision уже обязательны. | Journal design: физическая группировка не public manifest requirement. |
| C-T3 | Historical default отвергает старое удаление; Refresh отделяет browser expiry от originals. Retention/Capacity уже содержит deletion conditions. | Survey imports: IDs/heartbeat offline ingestion не разрешают удаление при low-space. |
| C-L1 | Display preference запрещает заменять capture profile; Legacy demonstration запрещает guessing в production. Это supporting ограничения, не отдельные стадии. | Validate: checksum recovery не определяет profile/monochrome conversion. |
| C-L2 | Preview reset/Legacy demonstration отвергают shortcuts; все обязательные шаги полной Recovery procedure уже размечены. | Нет hard negative ради количества; unrelated bodies остаются noise. |
| C-L3 | Preview links только review group; Draft cleanup отличает unpublished delete от withdrawal. Approval/embargo/identity/retention уже обязательны. | Resume: worker lease после recovery не publication approval/recall. |
| V-M1 | Training slots не night observation; Colours refresh не clear lock; Indoor instrument поясняет категорию, когда Suspension уже ограничен outdoor; Forecast не interlock. | Clock offset: drift recovery не регулирует transfer при maintenance/wind. |
| V-M2 | Forecast display запрещает restart по прогнозу; Colours отделяет display от execution; Transfer не отменяет suspension. Не требовать их как дубли обязательного interlock+operator. | Simulation clock: ручное ускорение времени не evidence о wind/indoor exemption. |
| V-M3 | Simulation clock не real gateway; Prototype recovery отвергает local sample restart; Timezones display не меняет stored reservations. Не новые mandatory steps. | Transfer: ownership consent не clock recovery. |
| V-C1 | Training archive: unsigned не production; Demonstration mode: partial publication не policy. Canonical signed+scan/hold уже обязательны. | Preview pointer не устанавливает snapshot eligibility/hold release. |
| V-C2 | Sandbox reset/Training archive не production; Demonstration mode не разрешает delete previous pointer; Object store: replication не approval. Полная procedure уже задаёт obligations. | Нет hard negative ради количества. |
| V-C3 | Preview pointer/Abandoned preview отделяют preview от public switch/rollback; Demonstration mode не policy; Object store: replication не approval. | Нет hard negative ради количества. |

No-answer C-T4/C-L4/V-M4/V-C4: прежние hard negatives сохранены после чтения.
Retention/refresh intervals не calibration fixed sensors; profile/display не
cleaning reagent; indoor/wind не cooling temperature; checksum/snapshot не
maintenance interval. Module temptations всегда excluded.

## Scope interpretation C-L1

Root «production derivatives of colour camera originals» задаёт обычную ветвь
colour conversion. Monochrome originals задаёт special case для явно помеченных
monochrome originals. Preserve-marker и запрет вывода из filename обязательны:
вопрос прямо спрашивает этот случай. Root не запрещает читать авторское исключение.
Это явная authored-scope интерпретация на parent review; source text не переписан.

Navigation в Display/Colours может доставить optional support вместо hard-negative
FAIL. Это не делает все anchors полезными: считать added tokens/reasons и
unrelated bodies обязательно. Calibration сохраняет REQUIRED obligations,
не все optional support; optional не понижает tau. Требуется review rev2 до freeze.
