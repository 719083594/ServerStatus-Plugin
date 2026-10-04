#!/usr/bin/env python3
"""Read-only local preflight. Config paths and secrets are never printed."""
import argparse,importlib.util,json,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);args=parser.parse_args()
checks={'linux':sys.platform=='linux','pillow':importlib.util.find_spec('PIL') is not None,'du':shutil.which('du') is not None,'dockerInstalled':shutil.which('docker') is not None}
try:
    config=json.loads(args.config.read_text());root=Path(config['yunzaiRoot']);ipc=Path(config['ipcDirectory'])
    checks.update(frameworkRoot=(root/'lib/plugins/plugin.js').is_file(),ipcExists=ipc.is_dir())
    spec=importlib.util.spec_from_file_location('status_collector',Path(__file__).resolve().parent.parent/'collector/collector.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.configure(config)
    checks['font']=True
    checks['configValid']=True
except Exception as exc:checks.update(configValid=False,errorType=type(exc).__name__)
required=['linux','pillow','du','frameworkRoot','ipcExists','font','configValid']
checks['ready']=all(checks.get(k) for k in required)
print(json.dumps(checks,ensure_ascii=False,indent=2));raise SystemExit(0 if checks['ready'] else 1)
