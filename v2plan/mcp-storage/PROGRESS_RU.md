# Storage continuation — состояние

Интегрированы ready-index диагностики C: `f4db3e95` (`b81e942a`).
Это не public preparation и не parity с живым индексом.

## Installed artifact C

- 31 normal-gated tests PASS в C worktree.
- Structured/text: project complete/partial, module и all scope доставляют
  source-bound evidence; missing module/version дают unavailable.
- Large protocol: 50 113 bytes оригинала, 2 435 bytes уникальных доставленных
  окон; >32 KB не доказаны. Metadata и повторные окна не засчитываются.
- Library v1/v2: unavailable; lineage blocker не обходился.
- Preparation blocked; fixture DB bytes/rows неизменны.
- Evidence generations ready-index fixtures неизменны. Whole DB bytes менялись
  при initialization registry/jobs: byte-for-byte read-only claim отсутствует.
- Full smoke и ready-index: exit 1, не release acceptance.

Wheel SHA256:
`34c5bf0a8312580d59f8b9bbf6f4e563be2c84adcafa107746a1de7ee66627bb`.
Лог: `/tmp/opencode/mcp-storage-c-validation/ready-index-final.log`.
Это C artifact, не exact integrated-SHA/deployed parity.

После интеграции: 95 focused tests PASS; общий Python line-budget PASS.
Scope checker расширен только двумя точными coordinator report paths этого
разрешённого этапа; runtime allowlist и protected-history guards не расширены.

## Дальнейшие границы

Пользователь разрешил пересмотреть packing найденных окон для explicit
patch_context; discovery/I/O/scope/network guards остаются прежними.
B готовит точный контракт до implementation/review.

Snapshot backend не принят: он меняет storage product и имеет открытые
restart/CAS obligations. Native extension/VFS — пока предложение под review R,
не разрешение ослабить alias, crash или ownership guarantees. Новые зависимости,
live replacement, index migration/rebuild, publish и merge не выполнялись.

R concept review: native путь правдоподобен, но `xSetSystemCall` — optional
testing API, не доказанная полная confinement boundary. Пользователь разрешил
изолированный research spike; A получил только experimental C/worker/headers
и новые tests. Production integration не разрешена. Strict hardlink semantics,
crash recovery после hostile journal removal и direct same-UID modification
этим разрешением не ослаблены.

B закончил read-only inventory packing: финальные merge/ranking caps отделены
от acquisition stops, которые могут запускать дополнительные reads. Контракт
проходит review R, включая риск дополнительных current-source rebinding reads.
Library lineage остаётся отдельным нерешённым срезом.
