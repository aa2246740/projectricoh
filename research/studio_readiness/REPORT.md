Level 5，95.7%（67 通过 / 3 失败 / 14 跳过，共 84 项）。

基线是 Level 2，21.9%（14 通过 / 50 失败 / 20 跳过）。最终是 Level 5，95.7%。两次都按同一套 0.240.0 rubric 对当时的工作树完整评过 84 项。

`studio/` 现在是一个没有 remote 的嵌套仓库，外层 projectricoh 仍只显示未跟踪的 `studio/`。本地提交是 `e4fe1be`（导入当时的树）、`3f64665`（检查和本机运维设施）、`027369c`（由 git 历史生成的 CHANGELOG）。没有 push。

改动按用途分：

检查和入口。`pyproject.toml` 里钉了 ruff、mypy、pytest-cov、deptry、vulture、import-linter、bandit、pylint、pytest-rerunfailures，并写进 `uv.lock`。这些是让 lint、类型、覆盖率、无用依赖、死代码、包边界、重复代码和失败重跑真能跑起来，原来的运行时依赖没有换版本。`make setup` / `make dev` / `make check` 是从克隆到启动、到全套检查的入口。`.githooks/pre-commit` 在提交时跑 ruff、秘密扫描、大文件和死开关；这次两个新提交都跑过。`engine/` 和 `lut/spaces.py` 不进 ruff format，因为来源一致性测试要求那些字节保持原样。

测试。原有 391 个用例都还在。新增 `tests/test_ops.py`（开关、告警、打码、请求号、schema 对照、列表查询次数）和 `tests/integration/test_studio_flow.py`（健康检查和设置）。`list_shots` 改成按批取 files 和 edits，`dates()` 收成一条 SQL，返回的字段和以前一样。覆盖率门槛是 85%，这次实测 89.40%。CI 和 `make test` 使用 `--durations=20` 和 `--reruns 1`。

本机可观察性。请求经过访问控制之后带 `X-Request-ID`，日志是一行一个 JSON，Bearer、`token=` 和 GitHub 令牌形状会被打掉。`/api/metrics` 和 `/api/usage` 只在这个进程里计数，不联网。后台任务失败会进 `on_job_failed`，由 `StudioNotifier` 记下并可从 `/api/alerts` 读。`library_rebuild` 默认开着，只有应用数据目录里的 `flags.json` 把它关掉时，重建接口才返回 403。页面行为没有改。

文档和协作文件。`AGENTS.md`、`CONTRIBUTING.md`、`docs/architecture.md`、`docs/privacy.md`、`docs/observability.md`、三份 runbook、`docs/openapi.json`（运行中的服务仍然不打开 OpenAPI 页面）、`docs/feature-flags.md`、`docs/dependencies.md`（含 7 天依赖等待）。`.github` 里有 issue/PR 模板、标签表、CODEOWNERS（`@aa2246740`）、CI、发版和 CI 失败建 issue 的工作流。`.devcontainer/devcontainer.json` 写了，本机没有 devcontainer CLI，所以「容器能跑起来」按规则跳过。`.claude/skills/gxr-studio/SKILL.md` 是给以后改这个仓库的 agent 用的。`.gitignore` 补了 `.env`、编辑器、缓存、图库、导出和 DNG/`GXRCE.DAT`。

还没通过的三项：

- `strict_typing`。mypy 已经能过，但没有开 strict。单独用 strict 跑，缺注解的错误大约有 800 条，这次没有为了分数去改那批签名。
- `dependency_update_automation`。`renovate.json` 和 `dependabot.yml` 都在，但规则要求能指出一条更新机器人真正开过的 pull request。这个仓库没有 remote，不能编一条。
- `error_tracking_contextualized`。失败会记在本机告警里。规则点名的是 Sentry、Bugsnag 或 Rollbar，而这个工具约定不联网，所以没有接。

另外 14 项按规则跳过：单包仓库（monorepo、版本漂移）、不是基础设施仓库（金丝雀、回滚）、没有打包步骤、没有外部服务（本地依赖、熔断）、没有 devcontainer CLI、以及 gh 已登录但这个仓库没有 remote，因此读不到分支保护、发布频率、CI 时长、自动评审和 issue 积压。隐私合规也跳过：没有账号，也没有向外采集数据。

基线报告：

- `/Volumes/Workspace/Scratch/tmp/projectricoh/readiness/state/597b52574f176c8d041edb67/20261030T063201Z-65c407ede0cb.json`
- `/Volumes/Workspace/Scratch/tmp/projectricoh/readiness/state/597b52574f176c8d041edb67/20261030T063201Z-65c407ede0cb.md`

最终报告：

- `/Volumes/Workspace/Scratch/tmp/projectricoh/readiness/state/597b52574f176c8d041edb67/20261030T070204Z-f53e099e20b6.json`
- `/Volumes/Workspace/Scratch/tmp/projectricoh/readiness/state/597b52574f176c8d041edb67/20261030T070204Z-f53e099e20b6.md`

最终测试：在 `studio/` 里跑 `uv run --frozen pytest -q --durations=15 --reruns 1 --cov=gxr_studio --cov-report=term --cov-fail-under=85`，398 passed，1 条 ResourceWarning（sqlite 连接，用例本身通过），覆盖率 89.40%，用时 6 分 1 秒。临时目录在 Scratch 上，跑完已删。
