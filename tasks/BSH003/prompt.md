# BSH003 — Hidden Subshell Failure

实现 `/workspace/solution.sh ROOT OUTPUT`。Bash 5.2，显式启用并保持 `set -Eeuo pipefail`。
允许 Bash、GNU coreutils、findutils、procps、util-linux；禁用其他解释器和 eval。
调用 `/usr/local/bin/scanner ROOT` 恰好一次。scanner 向 stdout 写 NUL 分隔、以 NUL 结尾的记录，记录可为空，也可包含任意非 NUL 字节和换行。scanner 可能写出部分合法记录后非零退出。
只有 scanner 成功时，发布 OUTPUT 目录，包含：
- manifest.bin：对每条记录顺序输出 `十进制字节长度 NUL 原始记录 NUL`。
- count.txt：十进制记录数和一个换行。
OUTPUT 初始不存在、父目录可写，位于同一文件系统；成功前 OUTPUT 不可见。空扫描成功发布空 manifest 和 `0\n`。
scanner 非零时返回其实际退出码，不发布 OUTPUT，不保留临时文件。基础设施错误返回 125。
不能把输出计数成功当作 scanner 成功；不能因管道子 shell 丢失计数。允许使用临时文件。
公开测试：`bash /workspace/public-test.sh`。仅提交 solution.sh。
