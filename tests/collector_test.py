import importlib.util,json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('collector',ROOT/'collector/collector.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def demo():
    return {'cpuPercent':12.5,'cores':4,'memory':{'total':4*1024**3,'available':3*1024**3,'used':1024**3,'percent':25,'swapTotal':2*1024**3,'swapUsed':0,'swapPercent':0},'uptime':95000,'load':[0.15,0.2,0.1],
      'runtime':{'nodeVersion':'v22.0.0','botUptime':7200,'botRss':96*1024**2,'connected':True,'loadedCount':12,'taskCount':2},
      'storage':{'at':time.time(),'mounts':[{'mount':'/','type':'ext4','total':40*1024**3,'used':8*1024**3,'available':32*1024**3,'percent':20,'inodePercent':3}],
         'directories':[{'label':'云崽程序和全部插件（后台缓存）','bytes':300*1024**2},{'label':'机器人数据','bytes':20*1024**2}],'docker':[]},
      'services':[{'name':'示例机器人','running':True,'health':'healthy','restarts':0,'cpu':'2.0%','memory':'96MiB / 512MiB','memoryPercent':'18.75%','pids':'12'}],
      'plugins':[{'name':'yunzai-server-status','label':'服务器状态图片','version':'1.0.0','loaded':1,'active':1},{'name':'example-plugin','label':'示例插件','version':'1.0.0','loaded':3,'active':3}]}

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.ipc=self.base/'ipc';self.ipc.mkdir()
        c.configure({'yunzaiRoot':str(self.base),'ipcDirectory':str(self.ipc),'dockerMode':'off'})
    def tearDown(self):self.temp.cleanup()
    def test_cpu_math(self):
        self.assertEqual(c.cpu_percent((100,40),(200,100)),40)
        self.assertEqual(c.cpu_percent((100,40),(100,40)),0)
    def test_memory_consistency(self):
        m=c.memory();self.assertEqual(m['used']+m['available'],m['total']);self.assertTrue(0<=m['percent']<=100)
    def test_no_docker_keeps_services_available(self):self.assertIn('未启用',c.services()[0]['error'])
    def test_invalid_container_name(self):
        with self.assertRaises(ValueError):c.configure({'yunzaiRoot':str(self.base),'ipcDirectory':str(self.ipc),'containers':[{'name':'bad;command'}]})
    def test_all_images(self):
        for kind in sorted(c.KINDS):
            p=self.ipc/(kind+'.png');w,h=c.render(demo(),kind,p)
            self.assertEqual(w,1080);self.assertGreater(h,300);self.assertTrue(p.read_bytes().startswith(bytes.fromhex('89504e470d0a1a0a')))
    def test_unknown_framework_fields_render(self):
        data=demo();data['runtime'].update(connected=None,loadedCount=None,taskCount=None);data['plugins'][0]['active']=None
        c.render(data,'plugins',self.ipc/'unknown.png')
    def test_invalid_request_never_processed(self):
        with self.assertRaises(ValueError):c.process({'id':'../../escape','kind':'all'})
    def test_stale_request_does_not_return_old_image(self):
        c.process({'id':'11111111-1111-1111-1111-111111111111','kind':'all','requestedAt':0});self.assertFalse((self.ipc/'response.json').exists())

if __name__=='__main__':
    if '--preview' in sys.argv:
        c.configure({'yunzaiRoot':str(ROOT),'ipcDirectory':str(ROOT/'data'),'dockerMode':'off'})
        c.render(demo(),'all',ROOT/'docs/preview.png');print('Synthetic preview generated')
    else:unittest.main()
