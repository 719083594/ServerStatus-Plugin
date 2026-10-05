#!/usr/bin/env python3
"""Install ServerStatus host support; Yunzai is an explicitly selected integration."""
import argparse,grp,importlib.util,json,os,pwd,shutil,subprocess,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parent.parent

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');path.chmod(0o640)

def quote(value):
    value=str(value)
    if any(c in value for c in '\n\r\0%'):raise ValueError('Unsupported path character')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application-root',type=Path,help='HOST application data root; no framework marker required')
    parser.add_argument('--yunzai-root',type=Path,help='Legacy alias: selects the Yunzai integration')
    parser.add_argument('--integration',choices=['standalone','yunzai'],default='standalone')
    parser.add_argument('--ipc-dir',type=Path)
    parser.add_argument('--bot-ipc-dir',help='Integration-visible shared mount path')
    parser.add_argument('--application-user','--bot-user',dest='application_user',default=pwd.getpwuid(os.getuid()).pw_name)
    parser.add_argument('--collector-user',help='Collector Unix user; default: application-user')
    parser.add_argument('--font-path',type=Path)
    parser.add_argument('--docker-mode',choices=['auto','selected','off'],default='auto')
    parser.add_argument('--install-deps',action='store_true',help='Install distro Pillow/CJK font (Debian/Ubuntu, root)')
    parser.add_argument('--systemd',action='store_true',help='Install/start server-status.service (root)')
    parser.add_argument('--force-config',action='store_true',help='Explicitly replace existing config/service')
    args=parser.parse_args()
    if sys.platform!='linux':raise ValueError('Host collector supports Linux only')
    if args.application_root and args.yunzai_root:raise ValueError('Select only one root argument')
    selected=args.application_root or args.yunzai_root
    if selected is None:raise ValueError('--application-root is required')
    integration='yunzai' if args.yunzai_root else args.integration
    root=selected.expanduser().resolve()
    if not root.is_dir():raise ValueError('applicationRoot is not a directory')
    if integration=='yunzai':
        if not (root/'lib/plugins/plugin.js').is_file():raise ValueError('Missing Yunzai V3 integration interface')
        if PACKAGE.parent!=root/'plugins':raise ValueError('Put the whole package directly under applicationRoot/plugins')
    ipc=(args.ipc_dir or root/'data/server-status').expanduser().resolve()
    for p in [root,ipc,PACKAGE]:quote(p)
    if args.install_deps:
        if os.geteuid()!=0 or not shutil.which('apt-get'):raise ValueError('--install-deps requires root on Debian/Ubuntu')
        subprocess.run(['apt-get','update'],check=True)
        subprocess.run(['apt-get','install','-y','--no-install-recommends','python3-pil','fonts-wqy-microhei'],check=True)
    if not importlib.util.find_spec('PIL'):raise ValueError('Pillow required for daemon PNG; JSON CLI needs no Pillow')
    from PIL import ImageFont
    fonts=[args.font_path,'/usr/share/fonts/truetype/wqy/wqy-microhei.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    font=next((str(Path(p).resolve()) for p in fonts if p and Path(p).is_file()),None)
    if not font:raise ValueError('Chinese font missing; install fonts-wqy-microhei or pass --font-path')
    ImageFont.truetype(font,24)
    app=pwd.getpwnam(args.application_user);collector=pwd.getpwnam(args.collector_user or args.application_user)
    if collector.pw_uid not in (0,app.pw_uid):raise ValueError('Collector must run as application-user or root')
    if os.geteuid()!=0 and os.getuid()!=app.pw_uid:raise ValueError('Run as application-user or root')
    config_file=PACKAGE/'collector/config.json';plugin_file=PACKAGE/'config/plugin.json';integration_file=PACKAGE/'config/integration.json'
    files=[config_file,integration_file]+([plugin_file] if integration=='yunzai' else [])
    if not args.force_config and any(p.exists() for p in files):raise ValueError('Config exists; preserve it or pass --force-config')
    target=Path('/etc/systemd/system/server-status.service')
    if args.systemd:
        if os.geteuid()!=0 or not shutil.which('systemctl'):raise ValueError('--systemd requires root and systemd')
        if target.exists() and not args.force_config:raise ValueError('Service exists; not overwritten')
    if integration=='yunzai':
        if args.bot_ipc_dir:bot_ipc=args.bot_ipc_dir
        elif ipc.is_relative_to(root):bot_ipc=ipc.relative_to(root).as_posix()
        else:raise ValueError('External IPC requires explicit --bot-ipc-dir')
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
    print('Host configuration ready. Integration:',integration)
    print('Foreground:',sys.executable,str(PACKAGE/'collector/collector.py'),'--config',str(config_file))
    if integration=='yunzai':print('Integration marker selects Yunzai; code is unchanged. Restart bot, then send #系统 as owner.')
if __name__=='__main__':
    try:main()
    except Exception as exc:print('Setup failed:',str(exc),file=sys.stderr);raise SystemExit(1)
