# API 接入预检（2026-09-07）

这是接入烟雾测试，不是正式 Bash benchmark 成绩。

- 用户指定 Base URL：`https://mdataplus-open.alibaba-inc.com/v1`
- 请求模型：`qwen-latest-series-invite-2608`
- `/models`：HTTP 200，列出上述模型。
- 对话响应 model：`qwen-latest-series-invite-202608-w4`。这是响应字段，不能据此推断其他正式版对应关系。
- 普通对话：返回 `API_OK`，finish_reason 为 `stop`。
- 工具调用：`tool_choice=auto` 返回正确的 `benchmark_echo({"text":"TOOL_OK"})`，finish_reason 为 `tool_calls`。
- 工具结果回传：模型最终返回 `TOOL_OK`。
- 兼容性：思考模式下强制 function 对象返回 HTTP 400，服务明确不支持 required/object；auto 成功。没有关闭思考模式。
- 成功轮三次请求 total_tokens 分别为 79、380、449；均为服务报告值。
- 本次使用非流式 Chat Completions、max_tokens=1024；未配置 temperature、top_p 或推理预算，不能视作已冻结正式实验参数。

复现：`python3 -m runner.probe`，`python3 -m runner.smoke`。凭据从未跟踪的 `.env` 读取。

尚待核验：流式工具调用、Pi 接入、模型实际上下文上限、正式 token/推理预算、四工具沙箱隔离、隐藏 verifier。

## Pi 预检

- 已本地安装 `@earendil-works/pi-coding-agent@0.85.1`，精确依赖锁保存在 `configs/pi-runtime/`。
- 禁用工具、扩展、skills、模板、主题和上下文文件加载，使用独立配置与工作目录。
- 流式对话成功，返回 `PI_OK`，stopReason 为 stop，保留了 thinking 内容和 responseModel 字段。
- Pi 报告 totalTokens=513、reasoning=12；其默认 cost=0 只是未配置价格，不能作为真实免费成本。
- 本次 contextWindow=8192、maxTokens=1024 仅为小型烟雾测试的客户端限制，不代表服务端容量。
- Docker 客户端与 daemon 均为 29.2.1，可通过有权限的执行环境访问。
- 复现：`python3 -m runner.pi_smoke`；原始事件位于未跟踪的 `runs/pi-api-preflight/`。
- 本轮未启用 Pi shell/filesystem 工具，四工具隔离与正式题目评测仍待实现。
