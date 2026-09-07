# BSH001 — Hostile Filenames

实现 `/workspace/solution.sh ROOT`，使用 Bash 5.2。显式启用并保持 `set -Eeuo pipefail`。
只允许 Bash、GNU coreutils、findutils、procps、util-linux；禁止其他解释器和 eval。
递归枚举 ROOT 下普通文件，不跟随符号链接。ROOT 内容在运行中不变。
按照相对 ROOT 路径的 LC_ALL=C 字节序排序；每文件向 stdout 输出：
`relative_path NUL decimal_size NUL lowercase_sha256 NUL`，字段之间没有空格或额外换行。
Linux 文件名可能包含除 NUL 和路径分隔符之外的任意字节。文件内容可能是二进制。
空目录成功输出零字节。发现、读取、hash 等任何错误必须非零退出，不得把缺失 ROOT 当空目录成功。
有效输入退出 0。不要执行由文件名组成的 shell 代码。
公开样例：`bash /workspace/public-test.sh`。最终只提交 solution.sh，隐藏评测不会保留其他自建辅助文件。
