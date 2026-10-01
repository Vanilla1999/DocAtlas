# P1 exact-head stacked validator

The P1 evidence stack may produce reviewed commits from GitHub Actions. Events
created by `GITHUB_TOKEN` do not recursively start ordinary pull-request
workflows, so every final head needs an explicit dispatchable validation path.

`p1-stack-exact-validation.yml` is merged before the stacked P1 evidence MRs.
For each exact branch SHA it runs:

- core tests on Python 3.11, 3.12 and 3.13;
- installed Docs MCP smoke on macOS and Windows;
- advanced, recovery, Project Docs, question-surface, Agent Developer,
  adversarial and mutation gates;
- all P1 evidence gates present on that ref;
- compile, module-size, diff and temporary-carrier checks;
- wheel/sdist build identity;
- wheel install and MCP smoke on Python 3.11, 3.12 and 3.13;
- sdist reconstruction and installer smoke.

The final `p1-stack-exact` job is the one serial merge controller requires.
This workflow never publishes to PyPI and cannot close the deferred P0 public
release rows.
