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

## Request-local provenance: ещё не implementation approval

B предложил immutable observations, созданные существующими trusted readers,
с request-local owner; consumers пересчитывают проверки по observations, а не
доверяют cached «validation passed». Wire/metadata/global cache не дают authority.

Однако текущий catalog reader не обеспечивает coherent root/catalog object
binding. Capture без дополнительных операций пока не доказан. Кроме того,
same-request snapshot semantics не должны молча заменить требование current
filesystem state. R проверяет минимальный producer substitution и совместимость
с действующим контрактом. Ни expanded allowlist, ни изменение актуальности,
ни дополнительные reads пока не одобрены; packing/cache код не реализован.

R interface review: zero-extra-capture-I/O object binding невозможен с текущими
producer observations. Observation-only cache меняет late pathname freshness
checks; этот вариант пользователь не выбрал. Пользователь разрешил только
конкретный проект descriptor capture: конечный список дополнительных операций,
точный интерфейс и следующий independent review до implementation. B готовит
план с late revalidation/I/O accounting; atomic multi-file snapshot не обещаем.

B представил concrete capture protocol: pinned root/catalog/member descriptors,
точный finite namespace-edge set, before/after fences и accounting через число
объектов/рёбер/retained items. Это увеличивает validation I/O, не устраняет его:
свежие проверки сохраняются на каждом authority-validation occurrence.
Изменившийся binding предлагается reject, а не silently adopt; поведение также
требует review. Production allowlist ещё не одобрен.

R сравнивает этот план с меньшим вариантом: оставить existing validators/fresh
reads неизменными и отдельно согласовать больше validation catalog/path checks
для qualified retained windows, без дополнительного acquisition/hydration.
Ни один вариант дополнительных I/O implementation пока не разрешён.

Пользователь затем разрешил дополнительные existing validation catalog/path
checks для retained eligible windows. Выбран минимальный packing patch без
capture/cache: B начал реализацию в точном allowlist. Acquisition/source-content
I/O и validators/freshness не меняются; validation I/O учитывается отдельно.

A spike `a7a41ac5` воспроизведён independent R: 25 tests PASS, но integration
HELD. R отдельно воспроизвёл false-green при реальной close syscall error;
обнаружены exact-runtime ordinary-CI conflict и whitespace gate failure upstream
header. A исправляет outcomes, provenance и explicit research selection; gates
не отключаются. Hook coverage не объявляется complete OS confinement. R1 OPEN.

B завершил minimal retention commit `74494b47a5249b6b6c62ce2ef5387f0705e25a22`:
ровно семь allowlisted files, clean worktree, 15 новых tests / 280 focused PASS
по отчёту B. Fixture retention >64 KiB — не installed >32 KiB acceptance.
R independently проверяет implementation, acquisition/control/fallback traces,
qualification и неизменность live validators. Commit пока не интегрирован.

A followup `a537e18a`: по отчёту A real-close errno/outcome исправлен,
write attempts/results разделены, три header whitespace lines нормализованы
с provenance hashes. 16 portable и 27 explicit native checks PASS; unsupported
positive profile reject до compilation. Directory-discovery inventory conflict
ещё BLOCKED, без обхода gates/CI/conftest. Independent native R повторно
проверяет исправления и минимальный способ закрыть inventory conflict.
Ни исходный spike, ни followup пока не интегрированы; R1 остаётся OPEN.

R retention audit: 280 focused tests independently PASS, но integration HELD.
Два medium findings: generic `**kwargs` facade может silently drop retention
flag (независимо воспроизведено: 4 sources вместо 32); текущие mocked-store
tests не доказывают неизменность actual stored-generation/fallback reads.
B исправляет explicit delegation support и добавляет реальные temporary stored
generation / nonempty fallback traces, duplicate lookup и unresolved admission
regressions. Source audit иных acquisition/freshness нарушений не обнаружил;
validators untouched, но это не closure двух findings или installed acceptance.

Native independent reaudit `a537e18a`: 43 requested-runtime pytest checks PASS
(16 portable + 27 explicit); portable Python 3.12: 16 PASS; unsupported positive
setup fails до compile. Real close EIO independently reproduced: теперь error /
unknown после commit, не false-green. Header diff/provenance PASS. Однако
directory inventory conflict остаётся blocking; исходные 27 gated positives не
являются ordinary CI compatibility.

Coordinator принял standalone runner correction: все 27 research scenarios
сохраняются, скрытый pytest-модуль преобразуется в настоящий finite script,
удаляются только его новые labels/hash. Portable pytest gates остаются. Future
evidence: 16 normal-gated checks + 27 standalone checks, не CI certification.
A реализует correction; native integration всё ещё HELD, R1 OPEN.
