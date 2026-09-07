# BSH005 — Transactional Supervisor

实现 `/workspace/solution.sh TASKS OUTPUT`。Bash 5.2，显式启用并保持 `set -Eeuo pipefail`。
只允许 Bash、GNU coreutils、findutils、procps、util-linux，不使用其他解释器或 eval。
TASKS 是 NUL 分隔且以 NUL 结尾的非空任务字符串列表。对每项调用 `/usr/local/bin/worker -- "$task"`，最多四路并发；四项待处理时必须实际重叠运行四个。
成功时按输入顺序把 worker 的二进制 stdout 拼到 OUTPUT/aggregate.bin，stderr 分别保存为 OUTPUT/stderr/000000.log 等从零编号文件。空列表产生空结果。
OUTPUT 初始不存在、父目录可写、同一文件系统；发布前不可见，发布时必须完整。成功、失败和中断都不能留下工作临时目录。
本关采用 fail-fast：观察到任一 worker 非零后，停止调度并取消本次其他 worker 及后代，返回该次观察到的非零退出码，不发布 OUTPUT。隐藏失败场景只安排一个主动失败任务，因此不存在多失败优先级歧义。
收到 SIGTERM/SIGINT 时清理本次全部 worker 及后代，分别返回 143/130，不发布 OUTPUT。清理应在 2 秒内完成。可 TERM 后 KILL；不能杀死无关进程。
worker 可能产生 child/grandchild，忽略 TERM，或主进程先退出而后代持有 stdout/stderr FD。它们不主动 setsid/改变进程组来逃逸。成功返回前也必须清理本次存活后代；主进程成功退出后的后代只持有 FD，不再产生有用输出，允许终止这些后代。
不能仅依赖直接 worker PID 是否退出；不能用 pkill worker 杀死无关同名任务。需要自己管理进程组和等待；外层评测清场不会替你取得通过。
信号只在提交 OUTPUT 之前注入。公开测试：`bash /workspace/public-test.sh`。仅提交 solution.sh。
