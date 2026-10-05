# 验证范围

```bash
node --test tests/*.test.mjs
python3 tests/portable_test.py
python3 tests/collector_test.py
python3 tests/cleanup_test.py
python3 tests/install_test.py
```

Node.js 测试检查纯 API 导入、默认无框架加载、适配标记加载 `apps`、主人限制、图片消息段、TRSS/经典云崽字段回退、IPC 串行请求、缓存和超时。

portable 测试主动拦截 Pillow 导入，确认 JSON 核心不需要图像依赖；Linux 另用 `python -S` 禁用 site-packages 执行真实 `/proc` JSON CLI。collector 测试检查 CPU/内存口径、Docker 回退、容器名称校验、五种 PNG、缺失运行数据、非法/过期请求。cleanup 使用独立应用临时目录，无框架标记，验证默认关闭、范围、过期、仅轮转日志、链接保护、预览和失败报告。安装器测试在独立 Linux 临时应用安装/诊断并检查拒绝重复覆盖。

PNG 与安装测试需要 Pillow/中文字体；Linux 文件清理需要 no-follow 目录描述符。Windows 会跳过 Linux 专有部分，不能替代部署验证。GitHub Actions 在 Ubuntu 安装依赖并运行全部测试。合成预览不展示任何用户系统数据。

真实 TRSS 部署用于集成验证。Yunzai V3 接口兼容不代表测试过所有框架、发行版或版本；缺少内部字段一律显示未知。

Linux IPC 集成测试只在 Linux 执行；Windows 仍检查独立导入、命令、主人限制与消息段。Windows 的文件替换锁语义不在宿主采集器支持范围内。
