# 固定帮助图片

`#系统帮助` 默认发送本地预先生成的 JPEG；`#系统帮助 文字` 查看文字版，两种方式都支持 `/` 前缀。原有主人权限对帮助与状态查询保持一致，非主人不会触发帮助图片读取。

公开说明定义在 `lib/help-content.mjs` 的 `helpTopics['system-help']`。离线构建使用同级 AI-Plugin 的纯 SVG 构建及原生图片服务，生成 `resources/help/system-help-1.jpg` 与 `manifest.json`。在线帮助请求只读取经过源码及图片 SHA-256 校验的固定图，不运行宿主机采集器，不启动浏览器，不调用 AI。状态看板继续使用原来的实时本机采集链路。

Yunzai 适配器按需加载 AI-Plugin 的固定图片发送模块；模块未安装、图片缺失或校验不通过时显示文字帮助，插件加载和实时状态功能仍正常。核心调用可选注入 `handleStatus(event, build, image, {helpReply})`，其中 `helpReply(event, topic)` 完成发送后返回 `true`，尚未发送返回 `false`；部分发送失败应抛出异常，防止重复发送文字说明。

修改说明后重新离线生成帮助图与 manifest。固定图仅含公开指令，服务器资源、服务列表、账号与配置不会进入固定帮助资源。
