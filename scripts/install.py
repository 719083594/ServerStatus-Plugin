#!/usr/bin/env python3
"""Install local collector support. No server credentials, downloads, or shell eval."""
import argparse,importlib.util,json,os,pwd,shutil,subprocess,sys
from pathlib import Path

PACKAGE=Path(__file__).resolve().parent.parent
def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    path.chmod(0o640)
def quote(value):
    value=str(value)
    if any(c in value for c in '\n\r\0%'):raise ValueError('Unsupported path character')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
def dependencies(install):
    if install:
        if os.geteuid()!=0:raise ValueError('--install-deps requires root')
        if not shutil.which('apt-get'):raise ValueError('Automatic dependencies only support Debian/Ubuntu; see docs/INSTALL.md')
        subprocess.run(['apt-get','update'],check=True)
        subprocess.run(['apt-get','install','-y','--no-install-recommends','python3-pil','fonts-wqy-microhei'],check=True)
    if not importlib.util.find_spec('PIL'):raise ValueError('Pillow missing: sudo apt-get install python3-pil fonts-wqy-microhei')
    fonts=['/usr/share/fonts/truetype/wqy/wqy-microhei.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    return next((p for p in fonts if Path(p).is_file()),None)
def main():
    parser=argparse.ArgumentParser(description='Install host-side support for yunzai-server-status')
    parser.add_argument('--yunzai-root',type=Path,required=True,help='HOST path to the Yunzai checkout')
    parser.add_argument('--ipc-dir',type=Path,help='HOST path to the shared IPC directory')
    parser.add_argument('--bot-ipc-dir',help='Path inside bot, only needed with a custom shared mount')
    parser.add_argument('--bot-user',default=pwd.getpwuid(os.getuid()).pw_name)
    parser.add_argument('--collector-user',help='Collector Unix user; default: bot-user')
    parser.add_argument('--font-path',type=Path)
    parser.add_argument('--docker-mode',choices=['auto','selected','off'],default='auto')
    parser.add_argument('--install-deps',action='store_true',help='Explicitly install distro Pillow/CJK font dependencies')
    parser.add_argument('--systemd',action='store_true',help='Explicitly install and start a systemd service (requires root)')
    parser.add_argument('--force-config',action='store_true',help='Explicitly replace existing local config')
    args=parser.parse_args()
    if sys.platform!='linux':raise ValueError('Host collector currently supports Linux only')
    root=args.yunzai_root.expanduser().resolve()
    if not (root/'package.json').is_file() or not (root/'lib/plugins/plugin.js').is_file():raise ValueError('Not a Yunzai-compatible framework root')
    ipc=(args.ipc_dir or root/'data/yunzai-server-status').expanduser().resolve()
    if args.bot_ipc_dir:bot_ipc=args.bot_ipc_dir
    elif ipc.is_relative_to(root):bot_ipc=ipc.relative_to(root).as_posix()
    else:raise ValueError('IPC is outside framework root; pass its bot-side --bot-ipc-dir explicitly')
    for p in [root,ipc,PACKAGE]:quote(p)
    default_font=dependencies(args.install_deps)
    font=str(args.font_path.resolve()) if args.font_path else default_font
    if not font or not Path(font).is_file():raise ValueError('CJK font missing; install fonts-wqy-microhei or pass --font-path')
    from PIL import ImageFont
    ImageFont.truetype(font,24)
    bot=pwd.getpwnam(args.bot_user);collector=pwd.getpwnam(args.collector_user or args.bot_user)
    if collector.pw_uid not in (0,bot.pw_uid):raise ValueError('Collector must run as the bot user or root to read its requests')
    if os.geteuid()!=0 and os.getuid()!=bot.pw_uid:raise ValueError('Run as bot-user, or use sudo')
    config_file=PACKAGE/'collector/config.json';plugin_file=PACKAGE/'config/plugin.json'
    if not args.force_config and (config_file.exists() or plugin_file.exists()):raise ValueError('Local config exists; preserve it or explicitly pass --force-config')
    target=Path('/etc/systemd/system/yunzai-server-status.service')
    if args.systemd:
        if os.geteuid()!=0 or not shutil.which('systemctl'):raise ValueError('--systemd requires root and systemd')
        if target.exists() and not args.force_config:raise ValueError('Service already exists; not overwritten')
    ipc.mkdir(parents=True,exist_ok=True)
    if os.geteuid()==0:os.chown(ipc,bot.pw_uid,bot.pw_gid)
    ipc.chmod(0o2770)
    config={'yunzaiRoot':str(root),'ipcDirectory':str(ipc),'fontPath':font,'dockerMode':args.docker_mode,'containers':[],'storageDirectories':[],'storageCacheSeconds':60,'programCacheSeconds':3600}
    write_json(config_file,config)
    write_json(plugin_file,{'ipcDirectory':bot_ipc})
    if os.geteuid()==0:
        for p in [config_file,plugin_file]:os.chown(p,bot.pw_uid,bot.pw_gid)
    collector_path=PACKAGE/'collector/collector.py'
    if args.systemd:
        if os.geteuid()!=0 or not shutil.which('systemctl'):raise ValueError('--systemd requires root and systemd')
        unit=f'''[Unit]
Description=Yunzai host status image collector
After=docker.service

[Service]
Type=simple
User={collector.pw_name}
Group={pwd.getpwuid(bot.pw_uid).pw_name}
ExecStart={quote(sys.executable)} {quote(collector_path)} --config {quote(config_file)}
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
        # Group is derived from gid (a username need not match its primary group).
        import grp
        unit=unit.replace('Group='+bot.pw_name,'Group='+grp.getgrgid(bot.pw_gid).gr_name)
        target.write_text(unit,encoding='utf-8');target.chmod(0o644)
        subprocess.run(['systemctl','daemon-reload'],check=True)
        subprocess.run(['systemctl','enable','--now','yunzai-server-status.service'],check=True)
    print('Collector config and shared IPC directory ready.')
    print('Foreground command:',sys.executable,str(collector_path),'--config',str(config_file))
    print('Next: restart your bot, then send #系统 as the configured owner.')
if __name__=='__main__':
    try:main()
    except Exception as exc:print('Setup failed:',str(exc),file=sys.stderr);raise SystemExit(1)
