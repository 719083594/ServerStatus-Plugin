#!/usr/bin/env python3
"""显式启用每日缓存清理定时器，保留已有采集器配置。"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('status_cleanup', PACKAGE / 'collector/cleanup.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def quote(path):
    value = str(path)
    if any(char in value for char in '\r\n\0%'):
        raise ValueError('路径含有不支持的字符')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__,add_help=False)
    parser.add_argument('-h','--help',action='help',help='显示帮助并退出')
    parser._optionals.title='可选参数'
    parser.add_argument('--config', type=Path, required=True, help='已有宿主机采集器配置文件')
    parser.add_argument('--enable', action='store_true', help='明确启用定时清理')
    parser.add_argument('--time', default='03:30', help='每日执行时间（北京时间）')
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('请在 Linux 宿主机以 root 安装定时器')
    if not args.enable:
        raise ValueError('请传 --enable 明确启用定时清理')
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['cleanup'] = {**cleanup.DEFAULTS, **config.get('cleanup', {}), 'enabled': True, 'scheduleTime': args.time}
    value = cleanup.settings(config)
    root = cleanup.checked_directory(config.get('applicationRoot') or config.get('yunzaiRoot'))
    ipc = cleanup.checked_directory(config['ipcDirectory'])
    if root == Path(root.anchor):
        raise ValueError('禁止将文件系统根目录作为清理范围')
    paths = [ipc, root / 'temp', root / 'data/upload_tmp', root / 'logs']
    for path in paths:
        if path.exists() or path.is_symlink():
            cleanup.checked_directory(path)
    service = f'''[Unit]
Description=ServerStatus expired application cache cleanup
After=docker.service

[Service]
Type=oneshot
ExecStart={quote(sys.executable)} {quote(PACKAGE / 'collector/cleanup.py')} --config {quote(config_path)} --apply
User=root
Environment=TZ=Asia/Shanghai
Environment={quote('DOCKER_CONFIG=' + str(ipc / 'docker-client'))}
UMask=0007
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths={' '.join(('-' if not path.exists() else '') + quote(path) for path in paths)}
CPUQuota=20%
MemoryMax=256M
TasksMax=64
TimeoutStartSec=300
'''
    timer = f'''[Unit]
Description=Daily ServerStatus cache cleanup

[Timer]
OnCalendar=*-*-* {value['scheduleTime']}:00 Asia/Shanghai
Persistent=true
RandomizedDelaySec=300
Unit=server-status-cleanup.service

[Install]
WantedBy=timers.target
'''
    subprocess.run(['systemd-analyze', 'calendar', f"*-*-* {value['scheduleTime']}:00 Asia/Shanghai"], check=True)
    temporary = config_path.with_name(config_path.name + '.cleanup.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    original = config_path.stat()
    temporary.chmod(original.st_mode & 0o777)
    os.chown(temporary, original.st_uid, original.st_gid)
    temporary.replace(config_path)
    for name, text in [('service', service), ('timer', timer)]:
        target = Path('/etc/systemd/system/server-status-cleanup.' + name)
        target.write_text(text, encoding='utf-8')
        target.chmod(0o644)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'server-status-cleanup.timer'], check=True)
    print('定时清理已启用，每日 ' + value['scheduleTime'] + '（北京时间，最多延迟 5 分钟）。')


if __name__ == '__main__':
    main()
