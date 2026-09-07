# BSH002 — Pipeline Autopsy

实现 `/workspace/solution.sh OUTDIR`。Bash 5.2，显式启用并保持 `set -Eeuo pipefail`。
只能使用 Bash、GNU coreutils、findutils、procps、util-linux，不使用其他解释器或 eval。
OUTDIR 为已有可写空目录。必须以真正的管道执行以下三个黑盒程序，且各执行恰好一次：
`/usr/local/bin/source-stage | /usr/local/bin/filter-stage | /usr/local/bin/sink-stage`。
保存 sink stdout 到 OUTDIR/stdout.bin，三个 stage 的 stderr 分别到 source.stderr、filter.stderr、sink.stderr，全部逐字节无损。
stdout 严格输出四行：source_rc=N、filter_rc=N、sink_rc=N、pipeline_rc=N（此顺序，每行结尾换行）。
必须报告各 stage 的实际退出状态，SIGPIPE 按 Bash 的 141 记录。pipeline_rc 是 pipefail 语义下从右向左第一个非零值，全零则为 0。
脚本最终退出码按优先级选择第一个非零：filter、source、sink；全部成功返回 0。
下游可能提前退出，上游可能收到 SIGPIPE，不要为报告状态而丢弃输出、强制串行或重复运行 stage。
公开测试：`bash /workspace/public-test.sh`。仅提交 solution.sh。
