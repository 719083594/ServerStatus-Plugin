#!/usr/bin/env python3
"""Independent Linux snapshot CLI. JSON mode uses only Python's standard library."""
import argparse,importlib.util,json,sys,time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config',type=Path)
parser.add_argument('--application-root',type=Path,help='Override application root; defaults to current directory')
parser.add_argument('--kind',choices=['all','resources','storage','plugins','services'],default='all')
parser.add_argument('--format',choices=['json','png','both'],default='json')
parser.add_argument('--output',type=Path,help='Required PNG output path; overwritten each run')
parser.add_argument('--runtime',type=Path,help='Optional JSON facts supplied by a framework adapter')
parser.add_argument('--runtime-stdin',action='store_true')
args=parser.parse_args()
try:
    if sys.platform!='linux':raise ValueError('Host metrics require Linux')
    if args.format!='json' and args.output is None:raise ValueError('--output is required for PNG')
    if args.runtime and args.runtime_stdin:raise ValueError('Select only one runtime source')
    config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
    if args.application_root:config['applicationRoot']=str(args.application_root)
    runtime=json.loads(args.runtime.read_text(encoding='utf-8')) if args.runtime else json.loads(sys.stdin.read(100000)) if args.runtime_stdin else {}
    if not isinstance(runtime,dict):raise ValueError('runtime must be a JSON object')
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
