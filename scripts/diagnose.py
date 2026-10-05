#!/usr/bin/env python3
"""Read-only generic local preflight. Configuration contents are never printed."""
import argparse,importlib.util,json,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);parser.add_argument('--json-only',action='store_true');args=parser.parse_args()
checks={'linux':sys.platform=='linux','pillow':importlib.util.find_spec('PIL') is not None,'du':shutil.which('du') is not None,'dockerInstalled':shutil.which('docker') is not None}
try:
    config=json.loads(args.config.read_text());root=Path(config.get('applicationRoot') or config.get('yunzaiRoot') or Path.cwd());ipc=Path(config.get('ipcDirectory') or root/'data/server-status')
    checks.update(applicationRoot=root.is_dir(),ipcExists=ipc.is_dir())
    spec=importlib.util.spec_from_file_location('status_collector',Path(__file__).resolve().parent.parent/'collector/collector.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.configure(config,require_font=not args.json_only)
    checks['font']=args.json_only or bool(module.FONT);checks['configValid']=True
except Exception as exc:checks.update(configValid=False,errorType=type(exc).__name__)
required=['linux','du','applicationRoot','configValid']+([] if args.json_only else ['pillow','ipcExists','font'])
checks['ready']=all(checks.get(k) for k in required)
print(json.dumps(checks,ensure_ascii=False,indent=2));raise SystemExit(0 if checks['ready'] else 1)
