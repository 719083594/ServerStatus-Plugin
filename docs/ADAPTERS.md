# 适配协议

## 无守护服务的接入

任何语言可执行 `python3 scripts/status.py --kind resources --format json`，解析标准输出 JSON。Node.js 可导入 `collectSnapshot()`，传 `runtime` 和可选 PNG 输出路径。**执行命令时使用参数数组，不能拼接用户文本到 shell 命令。** `kind` 是固定枚举，不能成为任意系统命令。

纯 API 文件为 `lib/api.mjs`（npm exports: `server-status-plugin/core`）；即使部署实例已经选择 Yunzai，导入这个入口也不会加载框架。仓库根 `index.js` 额外提供 `apps` 给兼容框架，仅在本地显式选择适配器时加载集成。

HTTP/机器人适配器负责鉴权：系统指标、容器名和插件信息属于管理信息，必须限制主人/管理员。CLI 不提供身份认证和网络服务，遵循调用者的 Unix 文件权限。图片通过各框架自己的消息段发送。

## IPC 接入

以固定目录通信，采集器一次处理一个请求。Node `createDashboard({directory,runtime})` 提供串行请求、5 秒图片缓存和超时。固定文件每次覆盖：`request.json`、`response.json`、`dashboard.png`。请求 `id` 是 UUID，`kind` 为五种面板之一，`requestedAt` 为毫秒时间戳，`runtime` 是框架提供的 JSON 对象。响应检查匹配 UUID、面板类型、时间戳、PNG 签名和 6MiB 上限。共享目录只授权采集器和应用用户，不可供其他不可信进程写入。

`handleStatus({isOwner,msg,reply},build,image)` 接受归一化事件。`isOwner` 必须是框架基于主人配置计算出的布尔 `true`；不得相信用户消息、客户端参数或任意用户 ID 声明。`reply(value)` 与 `image(Buffer)` 由适配器提供。`build(kind)` 返回 `{png, details?, generatedAt?}`。

## Runtime JSON

可选字段：`nodeVersion`、`botUptime`（秒）、`botRss`（字节）、`connected`（布尔或 null）、`loadedCount`、`taskCount`，以及 `plugins:[{name,label?,version?,loaded?,active?}]`。为兼容旧协议保留 `bot*` 字段名；适用于当前应用进程。缺少字段意味着未知。不能从插件文件夹存在推断运行成功，也不能猜测在线状态。

`runtimeFrom({loader,bot,files,processInfo})` 是可选的 Node.js 结构转换工具，不会导入框架。Yunzai 的实际字段采集只在 `integrations/yunzai/runtime.mjs`。其他框架可以直接构造 runtime JSON，不必实现 Yunzai 的 loader。

## 当前支持情况

- Linux CLI、Python 采集核心与 Node.js API：无需 Yunzai。
- Yunzai V3：现成适配器位于 `integrations/yunzai`，需本地配置选择。
- NoneBot、AstrBot、其他语言/机器人框架：可使用通用协议，未提供或宣称测试过现成适配器。
- Windows/macOS：不能运行 Linux `/proc` 宿主机采集；仅可远程调用你自己部署的受控服务，项目没有内置公开 HTTP 服务。
