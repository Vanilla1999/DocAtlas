# Все 40 вопросов: неизменная строгая оценка и отдельное ручное чтение

В positive проверяется полный контекст для вопроса; в partial — только документированная часть; в negative — прежний empty-source контракт. PASS не означает правильного сгенерированного ответа. Строгий gold и ручная оценка не объединяются в один показатель. Полные receipts и reasoning — в evaluation.json и semantic-review.json.

| ID | Тип | Исходный вопрос | Gold: budget | Gold: Mini | Ручная: budget | Ручная: Mini |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| V40-B01 | positive | What is Black's default line length? | PASS | FAIL | PASS | FAIL |
| V40-B02 | positive | How does Black determine target Python versions when --target-version is not set? | PASS | PASS | PASS | PASS |
| V40-B03 | positive | Which exit codes can Black --check return for unchanged files, files needing reformatting, and internal errors? | PASS | PASS | PASS | PASS |
| V40-B04 | positive | What does Black --no-cache do to cache reads and writes? | PASS | PASS | PASS | PASS |
| V40-B05 | positive | How does --force-exclude differ from --exclude for files passed explicitly to Black? | PASS | PASS | PASS | PASS |
| V40-B06 | partial | Where does Black search for pyproject.toml, and what TCP port does blackd listen on by default? | PASS | FAIL | PASS | FAIL |
| V40-B07 | partial | Which environment variable overrides Black's cache directory, and for exactly how many days are cache entries retained? | PASS | PASS | PASS | PASS |
| V40-B08 | negative | What guaranteed 99th-percentile formatting latency in milliseconds does Black provide? | FAIL | FAIL | FAIL | FAIL |
| V40-P01 | positive | Which file stores Poetry project-local application configuration, and is it the same file as pyproject.toml? | PASS | PASS | PASS | PASS |
| V40-P02 | positive | What is Poetry's configuration precedence from highest to lowest? | PASS | PASS | PASS | PASS |
| V40-P03 | positive | How are Poetry configuration setting names converted into environment variable names? | PASS | PASS | PASS | PASS |
| V40-P04 | positive | How do you undo an explicitly selected Poetry Python environment and return to default behavior? | PASS | PASS | PASS | PASS |
| V40-P05 | positive | What version range does the compatible release requirement ~=1.2.3 allow in Poetry? | FAIL | PASS | FAIL | PASS |
| V40-P06 | partial | What does poetry env activate print, and what process ID will the activated shell have? | FAIL | FAIL | FAIL | FAIL |
| V40-P07 | negative | What guaranteed 99th-percentile dependency resolution latency does Poetry provide? | FAIL | FAIL | FAIL | FAIL |
| V40-P08 | negative | What hard maximum number of virtual environments will Poetry retain automatically for one project? | FAIL | FAIL | FAIL | FAIL |
| V40-T01 | positive | What does the first positional argument to Textual reactive specify? | PASS | PASS | PASS | PASS |
| V40-T02 | positive | If several reactive attributes change together, how many refreshes does Textual perform? | FAIL | PASS | FAIL | PASS |
| V40-T03 | positive | Which Textual reactive helper can be used when changes should not trigger refresh or layout? | FAIL | FAIL | FAIL | FAIL |
| V40-T04 | positive | What arguments does a Textual watch method receive when it declares one positional argument versus two? | PASS | PASS | PASS | PASS |
| V40-T05 | positive | What does exclusive=True do when Textual starts a new worker? | PASS | PASS | PASS | PASS |
| V40-T06 | partial | What happens inside a coroutine when Worker.cancel is called, and what maximum cancellation latency does Textual guarantee? | PASS | PASS | PASS | PASS |
| V40-T07 | partial | How should a thread worker update the UI, and which exact OS thread scheduling policy does Textual use? | FAIL | FAIL | PASS | PASS |
| V40-T08 | negative | What guaranteed 99th-percentile keyboard-to-render latency does Textual provide? | FAIL | FAIL | FAIL | FAIL |
| V40-V01 | positive | Which env variables does Vite expose to client-side code by default, and what type are their parsed values? | PASS | PASS | PASS | PASS |
| V40-V02 | positive | What wins when the same Vite environment variable is defined by the process and by .env files? | PASS | PASS | PASS | PASS |
| V40-V03 | positive | What is Vite dev server's default port, and what happens when that port is already in use? | FAIL | PASS | FAIL | PASS |
| V40-V04 | positive | What does server.strictPort=true do when the configured Vite port is already in use? | FAIL | FAIL | FAIL | FAIL |
| V40-V05 | positive | How are files in Vite's public directory served and how should public/icon.png be referenced from source code? | PASS | PASS | PASS | PASS |
| V40-V06 | partial | What is the default value of server.fs.strict, and what HTTP status code is guaranteed for a file blocked specifically by server.fs.deny? | FAIL | FAIL | FAIL | FAIL |
| V40-V07 | negative | What guaranteed 99th-percentile HMR propagation latency does Vite provide? | FAIL | FAIL | FAIL | FAIL |
| V40-V08 | negative | What exact CDN cache TTL does Vite guarantee for production build assets? | PASS | PASS | PASS | PASS |
| V40-E01 | positive | Which filenames can ESLint use for its flat configuration file? | FAIL | FAIL | FAIL | FAIL |
| V40-E02 | positive | How does ESLint search for a configuration file for each target file when run on the command line? | PASS | PASS | PASS | PASS |
| V40-E03 | positive | How does --fix-dry-run differ from --fix, and can it be used with stdin? | PASS | PASS | PASS | PASS |
| V40-E04 | positive | What are ESLint's default globally ignored paths and default JavaScript file patterns? | FAIL | PASS | PASS | PASS |
| V40-E05 | partial | What extra dependency does Node.js need for TypeScript ESLint config files, and what exact startup overhead in milliseconds does it add? | FAIL | FAIL | FAIL | FAIL |
| V40-E06 | partial | What is the default --concurrency value and what does auto mean, and exactly how many worker threads will auto choose on an 8-core host? | PASS | PASS | PASS | PASS |
| V40-E07 | negative | What hard maximum memory usage per lint worker does ESLint guarantee? | FAIL | FAIL | FAIL | FAIL |
| V40-E08 | negative | What production uptime SLA does ESLint guarantee for local linting? | FAIL | FAIL | FAIL | FAIL |

Расхождения методик: E04 — все факты уже есть в другом допустимом разделе у budget; T07 — оба режима имеют правильные UI-инструкции из другого диапазона. Старые strict FAIL и их исходные evidence сохранены.
