#!/usr/bin/env python3
"""独立的 Linux 状态采集命令。JSON 模式仅使用 Python 标准库。"""
import argparse,importlib.util,json,sys,time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__,add_help=False)
parser.add_argument('-h','--help',action='help',help='显示帮助并退出')
parser._optionals.title='可选参数'
parser.add_argument('--config',type=Path,help='采集器配置文件')
parser.add_argument('--application-root',type=Path,help='指定应用根目录；默认当前目录')
parser.add_argument('--kind',choices=['all','resources','storage','plugins','services'],default='all',help='面板：all 全部 / resources 资源 / storage 存储 / plugins 插件 / services 服务')
parser.add_argument('--format',choices=['json','png','both'],default='json',help='输出：json 数据 / png 图片 / both 数据与图片')
parser.add_argument('--output',type=Path,help='PNG 图片输出路径；每次覆盖旧文件')
parser.add_argument('--runtime',type=Path,help='可选的应用运行信息 JSON 文件')
parser.add_argument('--runtime-stdin',action='store_true',help='从标准输入读取应用运行信息')
args=parser.parse_args()
try:
    if sys.platform!='linux':raise ValueError('宿主机状态采集仅支持 Linux')
    if args.format!='json' and args.output is None:raise ValueError('生成 PNG 图片必须通过 --output 指定输出路径')
    if args.runtime and args.runtime_stdin:raise ValueError('只能选择一种运行信息输入方式')
    config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
    if args.application_root:config['applicationRoot']=str(args.application_root)
    runtime=json.loads(args.runtime.read_text(encoding='utf-8')) if args.runtime else json.loads(sys.stdin.read(100000)) if args.runtime_stdin else {}
    if not isinstance(runtime,dict):raise ValueError('应用运行信息（runtime）必须是 JSON 对象')
    spec=importlib.util.spec_from_file_location('server_status_collector',Path(__file__).resolve().parent.parent/'collector/collector.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.configure(config,require_font=args.format!='json')
    data=module.collect({'kind':args.kind,'runtime':runtime})
    result={'kind':args.kind,'generatedAt':int(time.time()*1000),'details':data}
    if args.format!='json':
        args.output.parent.mkdir(parents=True,exist_ok=True)
        result['dimensions']=module.render(data,args.kind,args.output)
        result['pngPath']=str(args.output)
    print(json.dumps(result,ensure_ascii=False))
except Exception as exc:
    print(type(exc).__name__+': '+str(exc),file=sys.stderr);raise SystemExit(1)
