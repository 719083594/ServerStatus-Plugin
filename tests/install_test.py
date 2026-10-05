import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
@unittest.skipUnless(sys.platform=='linux','Linux installer')
class InstallerTests(unittest.TestCase):
    def test_standalone_install_without_framework_and_prevent_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);package=base/'ServerStatus-Plugin';app=base/'application';app.mkdir()
            shutil.copytree(ROOT,package,ignore=shutil.ignore_patterns('.git','dist','data','__pycache__','config.json','plugin.json','integration.json'))
            command=[sys.executable,str(package/'scripts/install.py'),'--application-root',str(app),'--docker-mode','off']
            result=subprocess.run(command,check=True,capture_output=True,text=True)
            self.assertIn('standalone',result.stdout)
            config=json.loads((package/'collector/config.json').read_text())
            self.assertEqual(config['applicationRoot'],str(app));self.assertNotIn('yunzaiRoot',config)
            self.assertEqual((package/'index.js').read_bytes(),(ROOT/'index.js').read_bytes())
            repeat=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(repeat.returncode,0);self.assertIn('Config exists',repeat.stderr)
            diagnostic=subprocess.run([sys.executable,str(package/'scripts/diagnose.py'),'--config',str(package/'collector/config.json')],check=True,capture_output=True,text=True)
            self.assertTrue(json.loads(diagnostic.stdout)['ready'])
if __name__=='__main__':unittest.main()
