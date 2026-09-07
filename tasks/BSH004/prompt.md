# BSH004 — Ordered Concurrent Runner

实现 `/workspace/solution.sh TASKS OUTPUT`。Bash 5.2，保持 `set -Eeuo pipefail`。只允许 Bash、GNU coreutils、findutils、procps、util-linux，禁止其他解释器和 eval。
TASKS 是 NUL 分隔且以 NUL 结尾的任务列表，任务字符串非空、可包含换行，不重复。按输入顺序对每条任务调用 `/usr/local/bin/worker -- "$task"` 恰好一次。
最多同时运行 4 个 worker；至少 4 个待处理任务时必须实际重叠运行 4 个，不能串行规避。允许按四个一批调度。
worker stdout/stderr 是任意二进制，包括 NUL、大输出和尾部换行，必须无损保存。
全部成功：发布 OUTPUT/aggregate.bin，按输入顺序拼接 stdout；stderr 按输入顺序存入 OUTPUT/stderr/000000.log 等六位从零编号文件。
某任务失败：继续运行并等待全部任务，以输入顺序第一个失败任务的退出码退出，不发布 OUTPUT。
OUTPUT 初始不存在且父目录可写。成功前不能看到部分 OUTPUT，空列表成功发布空 aggregate 和空 stderr 目录；清理临时目录。
worker 不创建后代且最终会结束。生命周期和取消不在本关范围。
公开测试：`bash /workspace/public-test.sh`。仅提交 solution.sh。
