# 安装与升级

## 独立应用

JSON 单次采集：Linux + Python 3.10+ + coreutils `du` 即可。PNG 另需 Pillow 和中文字体，可用 `--config` 中的 `fontPath` 指定自备字体。`scripts/status.py --help` 列出参数。无需 Node.js、机器人或运行守护服务。

若需要 IPC 看板守护服务：

```bash
sudo python3 scripts/install.py --application-root /srv/my-application \
  --application-user myapp --install-deps --systemd --docker-mode off
```

应用根目录必须已存在；不检查任何框架标记。默认安装 `standalone`，不加载 Yunzai。采集器用户默认应用用户；需要 Docker 监测时自行提供 Docker 权限或显式使用 `--collector-user root`。Docker socket 权限等价于宿主机管理权限。配置为本地文件，不提交 Git。

非 systemd：去掉 `--systemd`，按安装器输出的 Python 前台命令启动，或交给自己的进程管理器。依赖不会隐式安装；`--install-deps` 仅支持 Debian/Ubuntu。其他 Linux 自行安装 Pillow、中文字体和 coreutils。诊断：

```bash
python3 scripts/diagnose.py --config collector/config.json
python3 scripts/diagnose.py --config collector/config.json --json-only
```

## Yunzai 原生部署

整包必须位于 `<框架根>/plugins/ServerStatus-Plugin`，执行 README 安装命令。安装器只在 `--integration yunzai`（或兼容参数 `--yunzai-root`）时检查 Yunzai 接口。它写入 `config/plugin.json` 的 IPC 路径、`config/integration.json` 的适配器标记和 `collector/config.json` 的宿主机设置。通用 `index.js` 的 `apps` 默认空，在本地选定 Yunzai 后才加载适配器。

安装器拒绝覆盖现有配置和服务；`--force-config` 明确允许替换，但会写默认采集设置，**升级保留已有 cleanup 参数时不要使用它**。升级用 `git pull`，保持所有本地配置不变，重启采集器与机器人即可。

## Docker 部署

假设宿主机 `/srv/bot` 映射到机器人 `/app`，宿主机插件在 `/srv/bot/plugins/ServerStatus-Plugin`：

```bash
sudo python3 /srv/bot/plugins/ServerStatus-Plugin/scripts/install.py \
  --application-root /srv/bot --integration yunzai \
  --application-user bot --collector-user root --docker-mode auto \
  --install-deps --systemd
```

默认 IPC 宿主机 `/srv/bot/data/server-status`，机器人相对路径 `data/server-status`。若共享挂载不同，显式提供 `--ipc-dir /host/shared/status --bot-ipc-dir /container/shared/status`。目录必须是同一实际挂载；容器用户 UID/GID 要能读写 IPC。采集器在宿主机运行，不能装在容器内冒充宿主机指标。

## 旧版迁移

1. 保留旧 `collector/config.json`、`config/plugin.json`、共享 IPC 及 cleanup 参数，停止旧采集器/定时器。
2. 整包目录改为 `ServerStatus-Plugin`，不要重复加载旧目录。
3. 配置中的 `yunzaiRoot` 仍可用，也可改为 `applicationRoot`；保留原 IPC 路径即可，新增适配标记 `{"adapter":"yunzai"}`。
4. 更新新采集服务 `ExecStart` 路径到 `ServerStatus-Plugin/collector/collector.py`；配置路径也更新。采用新服务名 `server-status.service`。
5. 已授权定时清理时，用 `scripts/install-cleanup.py --config ... --enable` 创建新通用定时器。确认只有一个清理定时器启用；旧 `yunzai-server-status-cleanup.*` 不会自动被卸载。
6. 诊断通过后重启机器人，用主人命令检查五种面板。

安装脚本不修改 bot 网络、QQ 登录、业务数据或其他插件，不负责云端凭据和远程发布。
