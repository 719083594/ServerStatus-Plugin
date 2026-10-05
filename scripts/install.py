#!/usr/bin/env python3
"""安装宿主机状态采集服务；仅显式选择时启用云崽适配。"""
import argparse,grp,importlib.util,json,os,pwd,shutil,subprocess,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parent.parent

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');path.chmod(0o640)

def quote(value):
    value=str(value)
    if any(c in value for c in '\n\r\0%'):raise ValueError('路径含有不支持的字符')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'

def main():
    parser=argparse.ArgumentParser(description=__doc__,add_help=False)
    parser.add_argument('-h','--help',action='help',help='显示帮助并退出')
    parser._optionals.title='可选参数'
    parser.add_argument('--application-root',type=Path,help='宿主机应用根目录；无需机器人框架标记文件')
    parser.add_argument('--yunzai-root',type=Path,help='旧版兼容参数，同时选择云崽适配')
    parser.add_argument('--integration',choices=['standalone','yunzai'],default='standalone',help='适配模式：standalone 独立应用 / yunzai 云崽')
    parser.add_argument('--ipc-dir',type=Path,help='宿主机通信目录')
    parser.add_argument('--bot-ipc-dir',help='机器人可访问的共享通信目录')
    parser.add_argument('--application-user','--bot-user',dest='application_user',default=pwd.getpwuid(os.getuid()).pw_name,help='应用运行用户')
    parser.add_argument('--collector-user',help='采集器运行用户；默认与应用运行用户一致')
    parser.add_argument('--font-path',type=Path,help='中文字体文件路径')
    parser.add_argument('--docker-mode',choices=['auto','selected','off'],default='auto',help='容器监测：auto 自动发现 / selected 指定容器 / off 关闭')
    parser.add_argument('--install-deps',action='store_true',help='安装 Pillow 和中文字体（Debian/Ubuntu，需 root 权限）')
    parser.add_argument('--systemd',action='store_true',help='安装并启动采集服务（需 root 权限）')
    parser.add_argument('--force-config',action='store_true',help='明确允许覆盖已有配置和服务')
    args=parser.parse_args()
    if sys.platform!='linux':raise ValueError('宿主机采集器仅支持 Linux')
    if args.application_root and args.yunzai_root:raise ValueError('只能指定一种应用根目录参数')
    selected=args.application_root or args.yunzai_root
    if selected is None:raise ValueError('请通过 --application-root 指定应用根目录')
    integration='yunzai' if args.yunzai_root else args.integration
    root=selected.expanduser().resolve()
    if not root.is_dir():raise ValueError('应用根目录（applicationRoot）不存在或不是文件夹')
    if integration=='yunzai':
        if not (root/'lib/plugins/plugin.js').is_file():raise ValueError('未找到云崽 V3 插件接口')
        if PACKAGE.parent!=root/'plugins':raise ValueError('请将完整插件目录放在应用根目录的 plugins 文件夹下')
    ipc=(args.ipc_dir or root/'data/server-status').expanduser().resolve()
    for p in [root,ipc,PACKAGE]:quote(p)
    if args.install_deps:
        if os.geteuid()!=0 or not shutil.which('apt-get'):raise ValueError('--install-deps 需要在 Debian/Ubuntu 上以 root 运行')
        subprocess.run(['apt-get','update'],check=True)
        subprocess.run(['apt-get','install','-y','--no-install-recommends','python3-pil','fonts-wqy-microhei'],check=True)
    if not importlib.util.find_spec('PIL'):raise ValueError('图片采集服务需要 Pillow；独立 JSON 命令不需要图像依赖')
    from PIL import ImageFont
    fonts=[args.font_path,'/usr/share/fonts/truetype/wqy/wqy-microhei.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    font=next((str(Path(p).resolve()) for p in fonts if p and Path(p).is_file()),None)
    if not font:raise ValueError('未找到中文字体，请安装 fonts-wqy-microhei 或通过 --font-path 指定')
    ImageFont.truetype(font,24)
    app=pwd.getpwnam(args.application_user);collector=pwd.getpwnam(args.collector_user or args.application_user)
    if collector.pw_uid not in (0,app.pw_uid):raise ValueError('采集器必须以应用运行用户或 root 运行')
    if os.geteuid()!=0 and os.getuid()!=app.pw_uid:raise ValueError('请以应用运行用户或 root 运行')
    config_file=PACKAGE/'collector/config.json';plugin_file=PACKAGE/'config/plugin.json';integration_file=PACKAGE/'config/integration.json'
    files=[config_file,integration_file]+([plugin_file] if integration=='yunzai' else [])
    if not args.force_config and any(p.exists() for p in files):raise ValueError('配置已存在；请保留原配置，明确覆盖时传 --force-config')
    target=Path('/etc/systemd/system/server-status.service')
    if args.systemd:
        if os.geteuid()!=0 or not shutil.which('systemctl'):raise ValueError('--systemd 需要 root 权限和 systemd')
        if target.exists() and not args.force_config:raise ValueError('服务已存在，未覆盖')
    if integration=='yunzai':
        if args.bot_ipc_dir:bot_ipc=args.bot_ipc_dir
        elif ipc.is_relative_to(root):bot_ipc=ipc.relative_to(root).as_posix()
        else:raise ValueError('通信目录位于应用根目录之外，请通过 --bot-ipc-dir 指定机器人侧路径')
    ipc.mkdir(parents=True,exist_ok=True)
    if os.geteuid()==0:os.chown(ipc,app.pw_uid,app.pw_gid)
    ipc.chmod(0o2770)
    write_json(config_file,{'applicationRoot':str(root),'ipcDirectory':str(ipc),'fontPath':font,'dockerMode':args.docker_mode,'containers':[],'storageDirectories':[],'storageCacheSeconds':60,'programCacheSeconds':3600})
    write_json(integration_file,{'adapter':'yunzai' if integration=='yunzai' else None})
    if integration=='yunzai':
        write_json(plugin_file,{'ipcDirectory':bot_ipc})
    if os.geteuid()==0:
        for p in files:os.chown(p,app.pw_uid,app.pw_gid)
    if args.systemd:
        unit=f'''[Unit]
Description=ServerStatus Linux host image collector
After=docker.service

[Service]
Type=simple
User={collector.pw_name}
Group={grp.getgrgid(app.pw_gid).gr_name}
ExecStart={quote(sys.executable)} {quote(PACKAGE/'collector/collector.py')} --config {quote(config_file)}
Environment=TZ=Asia/Shanghai
Restart=on-failure
RestartSec=3
UMask=0007
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths={quote(ipc)}
PrivateTmp=true
CPUQuota=30%
MemoryMax=128M
TasksMax=64

[Install]
WantedBy=multi-user.target
'''
        target.write_text(unit,encoding='utf-8');target.chmod(0o644)
        subprocess.run(['systemctl','daemon-reload'],check=True)
        subprocess.run(['systemctl','enable','--now','server-status.service'],check=True)
    print('宿主机配置已就绪。适配模式：',integration)
    print('前台启动命令：',sys.executable,str(PACKAGE/'collector/collector.py'),'--config',str(config_file))
    if integration=='yunzai':print('已启用云崽适配；请重启机器人后由主人发送 #系统。')
if __name__=='__main__':
    try:main()
    except Exception as exc:print('安装失败：',str(exc),file=sys.stderr);raise SystemExit(1)
