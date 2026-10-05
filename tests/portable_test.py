"""Generic import/config checks, intentionally block Pillow imports."""
import builtins,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
class PortableTests(unittest.TestCase):
    def test_standard_library_core_and_legacy_root(self):
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='PIL' or name.startswith('PIL.'):raise AssertionError('Pillow imported in JSON core')
            return original(name,*args,**kwargs)
        with patch.object(builtins,'__import__',guarded),tempfile.TemporaryDirectory() as temp:
            spec=importlib.util.spec_from_file_location('portable_collector',ROOT/'collector/collector.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            for key in ['applicationRoot','yunzaiRoot']:
                module.configure({key:temp,'dockerMode':'off'},require_font=False)
                self.assertEqual(module.ROOT,Path(temp).resolve())
            self.assertEqual(module.duration(None),'未知')
            self.assertEqual(module.size(None),'未知')
    @unittest.skipUnless(sys.platform=='linux','Linux host metrics')
    def test_json_cli_without_site_packages(self):
        result=subprocess.run([sys.executable,'-S',str(ROOT/'scripts/status.py'),'--kind','resources','--format','json'],check=True,capture_output=True,text=True)
        data=json.loads(result.stdout);self.assertGreater(data['details']['memory']['total'],0)
        self.assertEqual(data['details']['runtime'],{})
if __name__=='__main__':unittest.main()
