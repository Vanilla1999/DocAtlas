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

Пользователь уточнил: старая БД не нужна, никто ей не пользуется; её можно
очистить. Сохранение legacy rows и identity migration больше не нужны.
План — новая пустая БД без migration/alias. Пока ничего не удалено: точный
target path ещё не определён. Это не снимает безопасное initialization/write
требование и не разрешает broad storage deletion или live MCP replacement.

## Конкретный review packing R

R проверил исходники на `ffc11a6a` (без исполнения). Post-acquisition retention
допустим для независимо квалифицированных eligible windows, не всех acquired
rows. `SourceReferenceContext.prepare()` выполняется до merge caps; блок
service part03:687–785 не читает source content напрямую с filesystem.

Настоящий no-extra-I/O blocker: action packet authority validation читает
project catalog для каждого canonical item; build/validation повторяют путь.
Path resolution также требует отдельного учёта. Простой bypass packing caps
не может заявлять неизменный I/O. B проектирует request-local root/catalog-bound
provenance snapshot/cache; точный интерфейс и дополнительные файлы требуют
review до реализации. Global cache, metadata-issued authority, пропуск проверок
или downgrade authority не допускаются.

Unresolved admission остаётся bounded и неизменным. Acquisition calls,
fallback triggers и operational control view сохраняются. Telemetry validators
остаются bounded diagnostic, не completeness certificate. >32 KB по-прежнему
условны: unchanged acquisition должен реально вернуть достаточные окна.
