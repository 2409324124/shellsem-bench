# ShellSem-Bench

Qwen 预览模型与 Qwen3.8 baseline 的 Bash agent smoke benchmark。

已发布检查点 **v0.1.0**；当前工作版本加入了有界重试和双维度评分。固定 Pi 0.85.1，五道独立题目，各有公开测试、六个隐藏 case 和 Bash 参考实现。runner、看门狗、只读观察服务是独立进程。两模型每关一次，共 10 次生成；这不是统计意义上的排行榜。

## 题目

| ID | 任务 | 检查 |
|---|---|---|
| BSH001 | Hostile Filenames | 特殊路径、NUL 分隔 manifest、size/hash、字节排序 |
| BSH002 | Pipeline Autopsy | 三阶段真实退出码、SIGPIPE、stdout/stderr 无损 |
| BSH003 | Hidden Subshell Failure | NUL 记录、计数、scanner 部分输出后失败、发布 |
| BSH004 | Ordered Concurrent Runner | 四路并发、输入顺序聚合、输入顺序失败码 |
| BSH005 | Transactional Supervisor | fail-fast、INT/TERM、进程组/后代/FD、事务性发布 |

题面、公开样例、隐藏 verifier 分别放在 `tasks/BSH00*/`。隐藏 verifier 与参考解不放入生成容器。生成后仅收集 solution.sh，在全新容器中判分。

## 本地准备

需要 Python 3.12+、Node.js 24、可用的 Docker daemon。首次部署：

```bash
cp .env.example .env
cp .env.example .env.baseline
chmod 600 .env .env.baseline
mkdir -p .runtime/pi
cp configs/pi-runtime/package*.json .runtime/pi/
npm ci --prefix .runtime/pi --ignore-scripts
```

分别填入 Base URL、API key 和精确模型 ID；不要 source env 文件。`.env` 为 preview，`.env.baseline` 为 baseline。配置读取只把内容当数据。

按用户要求**不拉镜像**。默认使用本机已有的 `wcb/ps7-sidecar:7.6.4`，已验证 Ubuntu 24.04.4 / Bash 5.2.21；其他机器需先提供兼容的本地镜像并修改 `runner/sandbox.py` 的 IMAGE。`--pull=never` 防止意外下载，不会安装或修改 Docker daemon。

容器限制：1 CPU、512 MiB 内存及相同 swap 上限、128 PID、根文件系统只读、移除 capabilities、no-new-privileges，工作区与临时文件使用限额 tmpfs。**bridge 网络开启**。API key 仅在宿主 Pi controller 中，四个工具的所有 I/O 都经 Docker adapter 进入容器，不挂载宿主家目录或 Docker socket。

## 运行与观察

```bash
# 只读模型列表 / API smoke
python3 -m runner.probe --env .env
python3 -m runner.smoke --env .env.baseline

# 实时页面及只读 JSON 接口；独立终端运行
python3 -m runner.observer --port 8765

# 两模型 × 五题 × 一次，默认串行；已有同名运行不重复生成
python3 -m runner.suite --prefix smoke-retry --concurrency 1

# 针对旧 API 超时记录另建补跑，旧记录不覆盖
python3 -m runner.suite --prefix retry-preview --labels preview --tasks BSH003 BSH004 --concurrency 1
```

页面：<http://127.0.0.1:8765/>。

- `GET /api/status`：调度、runner/guard 心跳、阶段、剩余时间、进程/资源与评分。
- `GET /api/events?run=smoke-low-baseline-BSH001`：最近 128 KiB 模型增量与工具事件。
- HTTP 只监听 loopback，没有修改/控制接口。页面每秒刷新，模型事件持续落盘。

单独运行一题：

```bash
python3 -m runner.guard --run-dir runs/manual-baseline-BSH001 \
  --deadline-seconds 600 -- \
  python3 -m runner.execute --task BSH001 --label baseline
```

当前任务 smoke 设置：`enable_thinking=false`、Pi thinking=off、每次输出请求上限 4096、客户端上下文阈值 32768、100 次工具调用、工具最长 30 秒、生成墙钟最多 300 秒。客户端 token 阈值不代表已验证的服务容量；墙钟硬期限是独立保障。`runner.smoke`/`pi_smoke` 是早期接入预检，不能代替这里的任务配置。

## 重试与双维度评分

每个失败的 API 轮次最多重试 2 次，依次退避 2 秒、4 秒。使用 Pi 会话层的恢复机制，保留已完成工具的结果；不重新跑整道题。底层 provider 自动重试设为 0，避免叠加重试。超时、连接错误、429 和暂时性服务错误可重试；鉴权与额度耗尽不重试。退避与请求耗时全部计入 300 秒生成预算，外层 guard 仍然独立生效。

默认调度并发度为 1，减少 key 并发限制的干扰；这不能证明 key 确实不支持并发，也不协调其他终端或其他机器的调用。`--concurrency 2` 可显式恢复两路调度。对旧失败的补跑使用新的 `--prefix`，分别报告，不覆盖原轨迹或挑最好分数。

`result.json` 的 `score` 使用 schema version 2，分两部分：

- `submission`：冻结脚本的隐藏用例通过数/执行数和 pass/fail。没有执行隐藏测试为 `not_evaluated`，页面显示“未验证”。
- `generation`：`completed`、`completed_with_anomalies`、`recovered`、`failed` 或证据不足的 `unknown`；另存失败原因、最终 stop reason、异常列表、重试次数与每次错误/退避记录。

例如提交 `6/6 pass` 可以同时标记 `output_truncated`，或生成 `failed / api_timeout`。API 最终失败、工具/时间预算耗尽时，只要取得了合格大小的脚本，也继续隔离验证，并用 `artifact_origin=interrupted` 标明来源；这类提交通过不算完整成功运行。正常结束仅表示没有记录到生成异常，不证明每一步都正确。

错误细分类包括 API 超时、底层建连超时、请求取消、连接、限流、鉴权、额度、服务错误、上下文限制、工具预算、时间预算、日志上限、缺失/过大的提交及未知 controller 错误。底层 fetch 记录请求开始、响应状态/延迟和异常 cause/code，避免把所有故障压成一个 `generation_error`。不记录请求体、鉴权头或 URL 查询参数。工具报错及 shell 非零退出也作为过程观察记录；预期的失败自测可能产生这些记录，不改变提交正确性分数。

旧记录由 observer 从原事件推导同一评分视图，原始 `result.json` 不改写；旧日志没有底层 transport 或 shell 退出事件时无法补造。监测页同时显示提交分数、过程状态、重试次数及完整异常/退避信息。

## 卡死与错误分类

- runner 每轮控制循环写原子心跳；模型流事件另有活动时间，不能混为一谈。
- 外层 guard 在独立进程检查 runner 心跳（默认 15 秒失联）、整轮硬期限（默认 900 秒；suite 600 秒）、进程退出。
- 超时/卡死后杀宿主 runner 进程组，并按本轮预登记清单移除容器；不会 prune 或清理其他容器。
- 观察服务独立读文件，看门狗自身心跳过期也会显示异常。
- 状态观察/清场的 Docker 调用有单次超时。`cleanup_errors` 非空时必须人工检查，不会谎报已清理。
- 生命周期题先检查本轮残留和无关 sentinel，再执行外层清场。
- 模型答案失败、生成预算耗尽、基础设施异常分别记录；不为了得到 PASS 自动重跑模型。

本地证据在未跟踪的 `runs/<run>/`：事件、配置、提交、guard/runner 状态、逐 case 结果。后续运行保存逐 case stdout/stderr；早期预检记录格式有所不同。初版验证器覆盖约定的 smoke 场景，不是针对恶意提交的安全评测平台；极短暂的发布窗口和并发峰值采用采样观测，有采样分辨率限制。

## 验证

```bash
python3 -m unittest discover -s tests -v
SHELLSEM_DOCKER_TESTS=1 python3 -m unittest discover -s tests -v
node --test tests/retry.test.mjs
```

Docker 集成检查包括五题参考解、故意错误版本、runner SIGSTOP 后容器回收；非 Docker 检查包括配置处理、硬期限、观察服务失联状态和页面脚本解析。所有集成测试只用本地镜像，不调用模型 API。

项目方案见 [agent.md](agent.md)，模型接入证据见 [reports/](reports/)。原始凭据、原始轨迹、node_modules 不进入版本控制。v0.1.0 的 10 次 smoke 已全部结束，详细记录留在本地 `runs/SMOKE-RESULTS.md`。模拟 API 验证覆盖重试恢复不重复执行已完成工具、超时恢复、重试上限、鉴权/额度错误不重试。

本机 API 的串行补跑已捕获底层 `UND_ERR_CONNECT_TIMEOUT`（10 秒连接期限），以及请求超时、502；重试可以恢复这些故障。仅凭这次 smoke 不能认定服务稳定性或 key 并发能力。

## 评测反馈材料

[新老模型对照总结](reports/model-comparison-summary-2026-09-14.md) · [表单填写内容](feedback/feedback-form.md) · [任务附件](feedback/task-attachments.zip) · [评测产物](feedback/evaluation-products.zip) · [执行过程数据](feedback/execution-data.zip)

当前计分口径：解释错误不扣正确性分；以执行结果、代码功能和代码约束为准。
