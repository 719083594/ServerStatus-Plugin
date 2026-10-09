#!/usr/bin/env python3
"""Render README examples from fictional fixtures; never collect host metrics."""
import argparse
import importlib.util
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font', help='Optional CJK font path')
args = parser.parse_args()
candidates = [args.font, '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
              str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'),
              '/System/Library/Fonts/PingFang.ttc']
font_path = next((p for p in candidates if p and Path(p).is_file()), None)
if not font_path:
    raise SystemExit('A CJK font is required; pass --font /path/to/font.ttc')
spec = importlib.util.spec_from_file_location('readme_status_renderer', ROOT / 'collector/collector.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

# No configure(), collect(), services(), SSH, instance config, or host files are read.
renderer.FONT = font_path
GiB, MiB = 1024**3, 1024**2
fixture = {
    'cpuPercent': 18.6, 'cores': 4, 'memory': {
        'total': 8*GiB, 'available': 5*GiB, 'used': 3*GiB, 'percent': 37.5,
        'swapTotal': 2*GiB, 'swapUsed': 0, 'swapPercent': 0},
    'uptime': 1098000, 'load': [0.28, 0.34, 0.21],
    'runtime': {'nodeVersion': 'v22.0.0', 'botUptime': 275400, 'botRss': 184*MiB,
                'connected': True, 'loadedCount': 12, 'taskCount': 2},
    'services': [
        {'name': 'demo-bot', 'running': True, 'health': 'healthy', 'restarts': 0,
         'cpu': '2.4%', 'memory': '184MiB / 1GiB', 'memoryPercent': '18.0%', 'pids': '18'},
        {'name': 'demo-cache', 'running': True, 'health': 'healthy', 'restarts': 0,
         'cpu': '0.3%', 'memory': '32MiB / 256MiB', 'memoryPercent': '12.5%', 'pids': '6'},
        {'name': 'demo-worker', 'running': True, 'health': 'starting', 'restarts': 1,
         'cpu': '1.1%', 'memory': '76MiB / 512MiB', 'memoryPercent': '14.8%', 'pids': '9'},
    ],
}
class DemoTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, 8, 0, 0)

output = ROOT / 'docs/images'
output.mkdir(parents=True, exist_ok=True)
with patch.object(renderer, 'datetime', DemoTime):
    renderer.render(fixture, 'resources', output / 'resources-demo.png')
    renderer.render(fixture, 'services', output / 'services-native.png')
resources = Image.open(output / 'resources-demo.png').convert('RGB')

# Paste the native output intact into a clearly marked documentation frame.
width, height = 1280, 278 + resources.height + 166
canvas = Image.new('RGB', (width, height))
draw = ImageDraw.Draw(canvas)
for y in range(height):
    t = y / (height - 1)
    draw.line((0, y, width, y), fill=(round(235 - 14*t), round(243 - 11*t), round(253 - 7*t)))
def font(size):
    return ImageFont.truetype(font_path, size)
def text(xy, value, size=24, color='#162d49'):
    draw.text(xy, value, font=font(size), fill=color)
draw.rounded_rectangle((70, 54, 1210, 104), 25, fill='#d9e8fb')
text((92, 64), 'SERVERSTATUS  /  原生看板预览', 20, '#2e5b90')
text((1040, 64), '演示数据', 20, '#2e5b90')
text((70, 130), '服务器状态，一张图看清。', 46)
text((73, 199), 'Linux 资源 · 应用运行 · 按需生成 PNG', 25, '#59708c')
top = 264
draw.rounded_rectangle((84, top + 12, 1196, top + resources.height + 32), 25, fill='#c7d6e9')
draw.rounded_rectangle((84, top, 1196, top + resources.height + 20), 25, fill='white')
canvas.paste(resources, (100, top + 10))
y = top + resources.height + 63
for x, label in [(70, 'CPU / 内存 / Swap'), (465, 'JSON 与 PNG'), (860, '主人权限命令')]:
    draw.rounded_rectangle((x, y, x + 350, y + 56), 16, fill='#f8fbff')
    text((x + 22, y + 12), label, 23)
text((73, y + 80), '虚构主机与手工指标 · 固定演示时间 · 未采集任何真实服务器数据', 19, '#59708c')
canvas.save(output / 'showcase.png', optimize=True)

services = Image.open(output / 'services-native.png').convert('RGB')
service_canvas = Image.new('RGB', (1280, services.height + 310), '#eaf2fd')
service_draw = ImageDraw.Draw(service_canvas)
service_draw.rounded_rectangle((70, 48, 1210, 98), 25, fill='#d9e8fb')
service_draw.text((92, 58), 'SERVERSTATUS  /  服务状态 · 演示数据', font=font(20), fill='#2e5b90')
service_draw.text((70, 124), '每个容器，都有清楚的状态。', font=font(40), fill='#162d49')
service_canvas.paste(services, (100, 202))
service_draw.text((73, services.height + 240),
                  'demo-* 均为虚构服务 · 固定演示时间 · 未读取 Docker 或真实服务器',
                  font=font(19), fill='#59708c')
service_canvas.save(output / 'services-demo.png', optimize=True)
print('Generated resource/service examples and docs/images/showcase.png (fictional fixtures).')
