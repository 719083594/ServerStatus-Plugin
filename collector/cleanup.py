"""Opt-in host cleanup. Fixed Docker commands and narrowly scoped cache files."""
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

DEFAULTS = {
    'enabled': False, 'scheduleTime': '03:30',
    'pruneUnusedImages': True, 'imageAgeHours': 168,
    'pruneBuildCache': True, 'buildCacheAgeHours': 24, 'buildCacheKeepGB': 1,
    'cleanTemporaryFiles': True, 'temporaryMaxAgeHours': 168,
    'cleanRotatedLogs': True, 'rotatedLogMaxAgeHours': 336,
}


def settings(config):
    value = {**DEFAULTS, **config.get('cleanup', {})}
    for key in ('enabled', 'pruneUnusedImages', 'pruneBuildCache', 'cleanTemporaryFiles', 'cleanRotatedLogs'):
        if type(value[key]) is not bool:
            raise ValueError('Invalid cleanup boolean: ' + key)
    for key in ('imageAgeHours', 'buildCacheAgeHours', 'temporaryMaxAgeHours', 'rotatedLogMaxAgeHours'):
        if type(value[key]) is not int or not 24 <= value[key] <= 87600:
            raise ValueError('Cleanup retention must be 24..87600 hours: ' + key)
    if type(value['buildCacheKeepGB']) is not int or not 0 <= value['buildCacheKeepGB'] <= 100:
        raise ValueError('Invalid buildCacheKeepGB')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value['scheduleTime']):
        raise ValueError('Invalid cleanup scheduleTime')
    return value


def docker_commands(value):
    commands = []
    if value['pruneUnusedImages']:
        commands.append(('images', ['docker', 'image', 'prune', '--all', '--force', '--filter', f"until={value['imageAgeHours']}h"]))
    if value['pruneBuildCache']:
        commands.append(('buildCache', ['docker', 'builder', 'prune', '--all', '--force', '--filter',
                                      f"until={value['buildCacheAgeHours']}h", '--keep-storage', f"{value['buildCacheKeepGB']}GB"]))
    return commands


def checked_directory(path):
    """Check every path component, then use no-follow directory descriptors below."""
    path = Path(os.path.abspath(path))
    for component in reversed([path, *path.parents]):
        if component.is_symlink():
            raise ValueError('Cleanup directory contains a symlink')
    if not path.is_dir():
        raise ValueError('Cleanup directory missing')
    return path


def clean_tree(directory, cutoff, apply=False, rotated=False):
    result = {'files': 0, 'bytes': 0}
    if not directory.exists() and not directory.is_symlink():
        return result
    directory = checked_directory(directory)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(directory, flags)
    device = os.fstat(root_fd).st_dev

    def visit(fd):
        for name in os.listdir(fd):
            if name.startswith('.'):
                continue
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if info.st_dev != device or stat.S_ISLNK(info.st_mode):
                continue
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, flags, dir_fd=fd)
                try:
                    visit(child)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_mtime < cutoff:
                if rotated and not re.search(r'\.log\.(?:gz|zst|[1-9]\d*)(?:\.gz|\.zst)?$', name):
                    continue
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if (current.st_ino, current.st_mtime_ns, current.st_size) != (info.st_ino, info.st_mtime_ns, info.st_size):
                    continue
                if apply:
                    os.unlink(name, dir_fd=fd)
                result['files'] += 1
                result['bytes'] += info.st_size
    try:
        visit(root_fd)
    finally:
        os.close(root_fd)
    return result


def execute(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=120).stdout


def run_cleanup(config, apply=False, runner=execute, now=None):
    if sys.platform != 'linux':
        raise ValueError('Cleanup requires the Linux host')
    value = settings(config)
    root = checked_directory(config.get('applicationRoot') or config.get('yunzaiRoot'))
    ipc = checked_directory(config['ipcDirectory'])
    if root == Path(root.anchor):
        raise ValueError('Refusing cleanup at the filesystem root')
    if apply and not value['enabled']:
        raise ValueError('Cleanup is not enabled in local configuration')
    now = time.time() if now is None else now
    report = {'startedAt': int(now * 1000), 'dryRun': not apply, 'filesDeleted': 0,
              'fileBytes': 0, 'docker': [], 'errors': [], 'scheduleTime': value['scheduleTime']}
    before = shutil.disk_usage(root).free
    for kind, command in docker_commands(value):
        item = {'kind': kind, 'command': command}
        if apply:
            try:
                if kind == 'buildCache':
                    options = runner(['docker', 'builder', 'prune', '--help'])
                    if '--keep-storage' not in options:
                        if '--max-used-space' not in options:
                            raise ValueError('Unsupported Docker build cache retention options')
                        command = ['--max-used-space' if arg == '--keep-storage' else arg for arg in command]
                        item['command'] = command
                output = runner(command)
                match = re.search(r'(?:Total reclaimed space|Total):\s*([^\r\n]+)', output)
                item['reclaimed'] = match.group(1).strip() if match else '未报告'
            except Exception as error:
                item['error'] = type(error).__name__
                item['errorDetail'] = str(getattr(error, 'stderr', '') or str(error))[:500]
                report['errors'].append(kind + ': ' + type(error).__name__)
        report['docker'].append(item)
    targets = []
    if value['cleanTemporaryFiles']:
        targets.extend([(root / 'temp', value['temporaryMaxAgeHours'], False),
                        (root / 'data/upload_tmp', value['temporaryMaxAgeHours'], False)])
    if value['cleanRotatedLogs']:
        targets.append((root / 'logs', value['rotatedLogMaxAgeHours'], True))
    for directory, hours, rotated in targets:
        try:
            result = clean_tree(directory, now - hours * 3600, apply, rotated)
            report['filesDeleted'] += result['files']
            report['fileBytes'] += result['bytes']
        except Exception as error:
            report['errors'].append(directory.name + ': ' + type(error).__name__)
    report.update(finishedAt=int(time.time() * 1000), success=not report['errors'],
                  diskFreedBytes=max(0, shutil.disk_usage(root).free - before) if apply else 0)
    if apply:
        temporary = ipc / 'cleanup.json.tmp'
        temporary.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
        temporary.chmod(0o660)
        temporary.replace(ipc / 'cleanup.json')
        for name in ('program-cache.json',):
            (ipc / name).unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Apply configured cleanup; default only previews')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    ipc = checked_directory(config['ipcDirectory'])
    import fcntl
    with (ipc / 'cleanup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another cleanup is already running.')
            return
        report = run_cleanup(config, args.apply)
        print(json.dumps(report, ensure_ascii=False))
        if not report['success']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
