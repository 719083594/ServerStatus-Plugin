# 安装与支持组件

## 环境清单

需要 Linux、Python 3.10+、Pillow、中文字体、`du`，以及具有云崽 V3 插件接口的机器人。机器人自身必须能收取主人命令和发送普通图片。插件不用 npm 第三方依赖、不用 AI 模型、不用浏览器。

支持组件均在包内：`collector/collector.py`、`scripts/install.py`、`scripts/diagnose.py`。**采集器必须在宿主机运行**；它处理固定的采集请求，不提供执行任意系统命令的接口。

## Docker 部署

以下都是示例路径和用户；请替换成你的实际部署值。在宿主机运行，不在容器中运行。

假设宿主机 `/srv/yunzai` 挂载到机器人内 `/app`，包放在 `/srv/yunzai/plugins/yunzai-server-status`：

```bash
cd /srv/yunzai
git clone https://github.com/719083594/yunzai-server-status.git plugins/yunzai-server-status
sudo python3 plugins/yunzai-server-status/scripts/install.py \
  --yunzai-root /srv/yunzai \
  --bot-user root --collector-user root \
  --docker-mode auto --install-deps --systemd
```

该例仅适用于机器人容器也以 root 运行的情况。非 root 容器必须使用对应宿主机 UID/GID 的本地用户或等效的共享目录权限映射，不能照抄 `--bot-user root` 后让普通用户读取失败。安装器把 IPC 目录设为该机器人用户的 setgid 共享目录，采集器输出供机器人组读取。

机器人只需要已有的 `/srv/yunzai:/app` 挂载，无需把 Docker socket 挂载进机器人容器。IPC 默认是宿主机 `/srv/yunzai/data/yunzai-server-status`，机器人中的 `data/yunzai-server-status`，二者必须对应。

若 IPC 放在另一共享挂载，明确配置两侧路径：

```bash
sudo python3 plugins/yunzai-server-status/scripts/install.py \
  --yunzai-root /srv/yunzai \
  --ipc-dir /srv/shared/status --bot-ipc-dir /shared/status \
  --bot-user root --collector-user root --docker-mode auto --systemd
```

前提是已有 `/srv/shared:/shared` 挂载。安装器不会修改你的 Compose，不会重启 QQ 或网关；配置后自行重启机器人加载插件。

## 原生 Linux 部署

在云崽根目录，使用运行机器人的 Unix 用户调用安装器，或通过 `sudo` 配合 `--bot-user` 明确指定该用户。原生默认 `--docker-mode off` 只看宿主机和机器人插件，不要求 Docker 权限。

如不用 systemd，省略 `--systemd`，然后用安装器提示的命令启动：

```bash
python3 plugins/yunzai-server-status/collector/collector.py \
  --config plugins/yunzai-server-status/collector/config.json
```

请用现有进程管理器保持它运行。关闭终端会使前台采集器停止。

## 其他 Linux 发行版

`--install-deps` 仅支持 apt 的 Debian/Ubuntu。其他发行版从本机包管理器安装 Python、Pillow、中文字体和 coreutils；然后省略此选项，必要时传 `--font-path /path/to/cjk-font.ttc`。不要安装在另一个 Python 环境里，再用未安装 Pillow 的 Python 执行采集器。

## 本地配置

安装器生成两份配置，Git 默认忽略它们，不会随着公开仓库更新上传：

- `config/plugin.json`：机器人视角的 `ipcDirectory`。
- `collector/config.json`：宿主机的云崽目录、IPC 目录、字体、监测容器和数据目录。

安装器会拒绝覆盖既有配置；确实需要重新配置时才使用 `--force-config`。升级代码通常无需再次运行安装器，只需重启采集器和机器人。

容器支持 `dockerMode: off / auto / selected`。`auto` 未指定列表时监测本机最多 30 个容器；`selected` 配合 `containers` 白名单：

```json
{
  "dockerMode": "selected",
  "containers": [{ "name": "my-bot", "label": "QQ机器人" }],
  "storageDirectories": [{ "label": "机器人数据", "path": "/srv/yunzai/data" }]
}
```

这些字段加入完整的 `collector/config.json`，不要删掉 `yunzaiRoot` 等必需字段。目录统计只读取你在本地配置中指定的路径；聊天消息不能传路径。

## 故障排查

| 现象 | 检查 |
| --- | --- |
| 没有命令响应 | 是否重启机器人、是否主人账号、框架群内是否限制必须 @、是否禁言、是否被功能黑名单阻止 |
| 提示采集超时 | 采集器进程/服务是否运行、`plugin.json` 和 `collector/config.json` 的 IPC 是否对应 |
| 图片读取失败 | 共享挂载、机器人 UID/GID、IPC 目录与输出文件权限 |
| 缺少 Pillow | 用同一个 Python 安装/运行，Debian/Ubuntu 安装 `python3-pil` |
| 中文字体检查失败 | 安装 `fonts-wqy-microhei` 或指定 CJK 字体；普通英文字体不能替代 |
| Docker 不可用 | 不使用容器监测可设 `off`；需要时检查 Docker CLI 与采集服务的权限 |
| 插件计数未知 | 该框架没有公开对应 loader 字段；插件目录和版本仍显示 |
| 大目录正在统计 | 后台缓存正在刷新，稍后再查；不阻塞 CPU、内存等状态 |

读取 Docker socket 的权限在安全上相当于管理宿主机。只在可信的宿主机采集服务中使用，不把它开放给普通群友或挂入机器人。服务不开放网络监听端口。

## 停用

```bash
sudo systemctl disable --now yunzai-server-status
```

将插件目录移出 `plugins` 后重启机器人。保留或移走本地配置和状态目录，按需卸载依赖；插件不会自动删除文件或清理磁盘。
