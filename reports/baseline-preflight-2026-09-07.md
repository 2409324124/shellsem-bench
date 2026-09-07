# Baseline 接入预检

日期：2026-09-07。接入测试，不是正式评测结果。

- 用户指定凭据源：`/home/miku/projects/bench/repo/.env`；未修改源文件。
- 本项目使用未跟踪的 `.env.baseline`，权限 0600；preview 仍使用独立 `.env`。
- Base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`。
- 请求及普通对话响应 model：`qwen3.8-max-0902`。
- 普通对话返回 API_OK，工具调用参数正确，工具回传后返回 TOOL_OK，三项通过。
- 使用与 preview 相同的非流式请求形式、max_tokens=1024、tool_choice=auto；未指定采样与推理预算。
- 三次成功请求 total_tokens：99、386、424，均取服务返回值。
- Pi 0.85.1 无工具流式测试通过，返回 PI_OK，stopReason=stop，totalTokens=538。
- 一次 Pi 测试在 API 调用后因本地参数变量重名导致记录失败；修复后重跑成功。该次不进入实验统计。
- Pi 轨迹：`runs/pi-api-preflight-baseline/events.jsonl`（未跟踪）。

复现：

```bash
python3 -m runner.smoke --env .env.baseline
python3 -m runner.pi_smoke --env .env.baseline --label baseline
```

正式配置仍未冻结。接入默认值不保证两模型实际推理预算一致；后续记录并核验可控参数，不将烟雾测试 token 数视为能力比较。
