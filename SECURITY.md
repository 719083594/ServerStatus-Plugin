# 安全与清理边界

系统状态含主机数据、容器名和插件信息。Yunzai 适配器要求规则 `permission:master`，处理器二次验证可信 `e.isMaster === true`；通用处理器要求归一化 `isOwner === true`。CLI/Node API 是本地管理接口，没有网络认证，其他框架必须自行鉴权，不得公开无认证的状态或清理端点。

默认不删除。清理需要配置 `cleanup.enabled:true` 与 `--apply`，安装定时器还需 root 显式 `--enable`。预览不调用 Docker prune、不删除文件、不写清理报告。配置路径使用 `applicationRoot`，兼容旧 `yunzaiRoot`；拒绝文件系统根目录。通用化移除了云崽标记检查，范围仍固定在该应用根目录下的 `temp`、`data/upload_tmp` 和 `logs`，不接受消息中的任意路径或命令。

文件清理跳过隐藏文件、符号链接、硬链接、跨设备文件；验证全部路径组件，使用 Linux no-follow 目录描述符，并在删除前检查 inode/修改时间/大小未改变。只删除过期普通文件；日志仅限明确已轮转 `.log.1`/`.gz`/`.zst` 形式，当前日志保留。不会删除目录、数据库、配置、登录文件或业务历史。不要将有保留需求的业务文件存到临时缓存目录。

Docker 只使用固定参数数组执行 `docker image prune --all` 与 `docker builder prune --all`，按配置保留时间过滤。**作用于宿主机的全部 Docker 缓存**，可能删除暂未被容器引用的回滚镜像，重建/拉取会需要网络。没有运行 `system prune`、`container prune`、`volume prune`，不删除容器和数据卷。不可回收估算与实际释放简单相加。

IPC 文件每次覆盖，定时清理独占文件锁。IPC 使用应用用户组的权限，不应开放给其他用户写。Docker socket 和 root 采集器具有宿主机级权限，请根据需要最小授权。状态请求不触发清理；定时任务单独运行，错误会记录在 `cleanup.json` 与 systemd 日志中。

公开发布禁止包含本地配置、凭据、真实系统截图、QQ 登录数据、数据库、日志和 `.env`。仓库已忽略这些内容。报告问题请提供脱敏错误与版本，禁止粘贴密钥。许可维持 PolyForm Noncommercial 1.0.0。
