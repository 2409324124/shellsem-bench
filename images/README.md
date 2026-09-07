# 本地镜像模式

按用户要求不拉取镜像、不构建新镜像。runner 使用已存在的 `wcb/ps7-sidecar:7.6.4`，启动明确设置 `--pull=never`，覆盖其 entrypoint。

已检查该镜像是 Ubuntu 24.04.4、Bash 5.2.21，包含所需 GNU 工具。实际 image ID 将随运行记录。镜像中的额外工具不是题目允许集合。

每容器：1 CPU、512 MiB 内存及相同 swap 上限、128 PID、只读根文件系统、bridge 网络开启、drop ALL capabilities、no-new-privileges。工作区/临时目录/fixture 分别使用有大小限制的 tmpfs。模型命令使用 UID/GID 1001，不挂载宿主文件或 Docker socket。

早期远程拉取因 TLS 超时失败；用户要求停止拉取后，不再尝试。一次本地派生构建因 UID 冲突失败，没有生成最终镜像；当前完全不依赖该构建。

用户明确要求网络开启；API 凭据仍仅由宿主 controller 持有，不注入容器。网络开启意味着可联网行为属于本次 smoke 环境条件，不能将其报告为离线主榜。
