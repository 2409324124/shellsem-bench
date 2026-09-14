# 裸模型与 Pi 工具版对照

两道 Bash 语义题，模型为 `qwen-latest-series-invite-2608` 和 `qwen3.8-max-0902`。用户于 2026-09-14 明确允许使用已配置 API；早先“绕过 API”的网页方案已被替代。不采用 TDD，实现后验证。

## 裸模型

```bash
python3 -m single_shot.api --output runs/single-shot/2026-09-14-first
```

每模型每题一个独立请求，只有用户题面消息，无工具、无 Pi、无历史回复、无评测反馈。关闭思考，输出上限 8192，网络操作超时 120 秒，串行调用。首次网络失败后若未收到答案，可以按用户已授权的故障重试规则在新的输出目录补请求；不得覆盖失败记录，不重发已有答案的任务。脚本自身不自动重试。

原始请求、完整响应、首答文本、请求/响应模型 ID、usage、finish_reason、时间、题面及答案哈希均保存到对应目录。首答文件设为只读，拒绝复用输出目录。首答中模型自行推翻、改写的内容仍属于同一份首答，全部保留；不会截取最优片段替换原文。

`prompts/` 是原始题面正文，哈希见 manifest.json。`capture.py` 是保留的手工网页原文采集工具，本轮不使用。

## 本地判分

单独编译的 `.runtime/bash-5.2.37/bin/bash` 已核对版本；来源与哈希见 environment.json。系统 Bash 未替换，Docker 镜像不拉取。模型代码只在本地现有镜像创建的新鲜受限容器执行，向 tmpfs 注入该 Bash 二进制，不挂载仓库、参考解或宿主秘密。

- Q1：使用指定版本执行两个原始脚本各 50 次确认稳定输出；对照完整 stdout、stderr 和 exit code。首答中每个 JSON 版本都保留、逐个比较；格式、解释和语义错误另记。
- Q2：从整份首答中提取最后一个完整 collect 函数代码块，作为其最终声明的提交；不修改函数。独立构造 16 组功能数据，分别直接调用和放进 if 条件，共 32 次检查。独立参考实现先通过全部用例，再判模型。不是用户提到但未提供的原始参考包。
- Q2 覆盖空记录、特殊字节、8192 字节记录、二进制输出、失败优先级、未终止尾片段、输入/描述符隔离、流式握手、并发及调用者后台作业等待。源码限制、精确 wait、选项/trap 修改、解释是否符合字数和真实代码，另行审阅；功能通过不替代约束审查。

任何后续纠错回答须另存，不能混入本轮首答评分。

## Pi 工具版

裸模型判分完成后再开始。使用同样两道题、相同模型、关闭思考、每次回复最多 8192 token。`prompts_pi/` 仅放开验证工具，并说明工具工作目录/Bash 版本；Q2 增加 collect.sh 保存位置，语义要求不变。未向模型暴露隐藏 verifier 或参考解。

```bash
python3 -m runner.guard --run-dir runs/pi-compare-preview-Q1 --deadline-seconds 600 -- \
  python3 -m single_shot.pi --task Q1 --label preview
```

Pi 固定 0.85.1，read/write/edit/bash 四工具在 Docker 内执行。每题生成限 300 秒、100 次工具调用，工具最长 30 秒；每次失败 API 轮次最多重试两次、退避 2/4 秒，计入总时间。独立 guard 检测卡死并清理容器。保存 `events.jsonl`、`requests/*.json`（仅 JSON 请求体，无鉴权头）、最终 assistant 消息、collect.sh、有效提示词和配置、guard/runner 状态。

比较答案得分、生成是否完整、工具接口错误、Shell 非零退出、API 故障/重试、调用数、token 与耗时。Shell 非零可能来自故意构造的失败测试，不能自动当作工具使用错误。对照估计的是工具访问与 Pi harness 的联合影响；没有相同工具条件下的其他 harness 对照，不能单独识别 harness 的因果效果。

凭据、二进制不提交 Git。原始轨迹本地保留，并在结束后经凭据扫描压缩归档到 evidence/，与报告和代码一起推送GitHub 仓库。

## 第二题不限总时间的补齐轮

用户允许超出原 300 秒限制后，新旧模型均用以下参数重新取得完整最终函数并判分：

```bash
python3 -m runner.guard --run-dir runs/NEW_UNIQUE_RUN --deadline-seconds 0 -- \
  python3 -m single_shot.pi --task Q2 --label preview --generation-seconds 0 --max-tokens 32768 --context-window 131072 --max-tool-calls 0
```

旧模型将 label 改为 baseline。0 关闭总时长截止；独立 guard 的心跳失联检测继续生效。32768 是模型配置的输出上限，SDK 可能根据当前上下文剩余额度调低实际请求值，原始请求体保留实际值。默认参数仍为原来的 300 秒和 8192 token，不改写历史配置。该补齐轮与原轮分开报告，不把不同预算的结果混为同条件比较。

补齐轮同时把 Pi 本地 contextWindow 声明改为 131072，防止原 32768 声明将后期请求 max_tokens 压到 1。它是本轮 harness 配置，不据此声称供应商公布的模型窗口大小；实际请求与服务器接受情况另留证据。新旧模型同配置重跑。

完整交付轮 `--max-tool-calls 0` 关闭总调用次数限制，默认仍为 100；单次工具超时、失联检测和日志大小限制仍生效。此前命中 100 次的独立运行保留，不伪装成模型自然结束。

容器现启用 Docker `--init` 回收退出的孤儿子进程。原 sleep PID 1 在长工具会话中曾积累 126 个僵尸进程，耗尽 128 PID 配额。验证使用五批共 200 个后台任务，结束后僵尸数为 0。资源上限不变；失效会话和进程证据保留，后续新旧模型均在该修正环境重跑。

## 最终完整评测配置

扩大窗口的诊断轮仍会在历史用尽时截断，因此最终新旧模型配对使用原 32768 上下文 / 8192 输出预算并启用 Pi 自动压缩恢复：

```bash
python3 -m runner.guard --run-dir runs/NEW_UNIQUE_RUN --deadline-seconds 0 -- \
  python3 -m single_shot.pi --task Q2 --label preview --generation-seconds 0 \
  --max-tokens 8192 --context-window 32768 --max-tool-calls 0 --auto-compact
```

旧模型改为 baseline。自动压缩是 Pi 自带的历史总结/恢复机制，事件及请求全部留档；评测者不提供隐藏测试反馈。原默认 compaction=false 保留，只有显式参数开启，以便复现旧记录。

最终压缩配置保留最近 4096 个估算 token；默认 20000 对该轨迹可能无可压缩区段。评分器支持 `--source collect.artifact.sh`，用于模型声明完成但正文漏贴函数的情况，来源与格式错误单独记录；无完成声明的中间文件仍仅作诊断。
