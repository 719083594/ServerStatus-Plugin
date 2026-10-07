"""Public component declarations must not conceal active or uncertain plugins."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('component_collector',ROOT/'collector/collector.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        c.configure({'applicationRoot':str(self.root),'dockerMode':'off'},require_font=False)

    def tearDown(self):self.temp.cleanup()

    def declaration(self,parent,components):
        directory=self.root/'plugins'/parent;directory.mkdir(parents=True,exist_ok=True)
        (directory/'orangejuice.plugin.json').write_text(json.dumps({'components':components}),encoding='utf-8')

    def row(self,name,active=0):return {'name':name,'active':active,'loaded':active}

    def names(self,rows):return [row['name'] for row in rows]

    def test_display_label_prefers_runtime_then_public_manifest_then_builtin_or_name(self):
        self.declaration('Guide-Plugin',[])
        manifest=self.root/'plugins/Guide-Plugin/orangejuice.plugin.json'
        manifest.write_text(json.dumps({'title':'  公开\n 助手  '}),encoding='utf-8')
        def label(runtime_label=None):
            item=self.row('Guide-Plugin',2)
            if runtime_label is not None:item['label']=runtime_label
            return c.plugins({'plugins':[item]})[0]['label']
        self.assertEqual(label(),'公开 助手')
        self.assertEqual(label('  运行时\n 标题  '),'运行时 标题')
        self.assertEqual(label('   '),'公开 助手')
        self.assertEqual(label(123),'公开 助手')
        self.assertEqual(label('a'*80),'a'*40)
        manifest.write_text(json.dumps({'title':{'invalid':'title'}}),encoding='utf-8')
        self.assertEqual(label(),'Guide-Plugin')
        self.assertEqual(c.plugins({'plugins':[self.row('system',2)]})[0]['label'],'TRSS 系统功能')

    def test_only_explicit_idle_components_group_under_running_parent(self):
        self.declaration('Guide-Plugin',[{'directory':'guide-assets','title':'资料图片','description':'  公共\n 图片素材  '}])
        child=self.root/'plugins/guide-assets';child.mkdir()
        (child/'package.json').write_text(json.dumps({'version':'1.2.3'}),encoding='utf-8')
        runtime={'loadedCount':7,'taskCount':2,'plugins':[self.row('Guide-Plugin',7),self.row('guide-assets'),self.row('unused')]+[self.row(name) for name in sorted(c.BUILTIN_PLUGINS)]}
        rows=c.plugins(runtime)
        self.assertEqual(self.names(rows),['Guide-Plugin','unused']+sorted(c.BUILTIN_PLUGINS))
        self.assertEqual(rows[0]['active'],7)
        self.assertEqual(rows[0]['components'],[{'name':'guide-assets','label':'资料图片','description':'公共 图片素材','version':'1.2.3'}])
        self.assertEqual(runtime['loadedCount'],7);self.assertEqual(runtime['taskCount'],2)
        self.assertEqual(len(runtime['plugins']),7)

    def test_inactive_or_unknown_parent_never_groups_children(self):
        self.declaration('Guide-Plugin',[{'directory':'guide-assets'}])
        for active in [0,None,False,'1',-1,float('nan'),float('inf')]:
            with self.subTest(active=active):
                self.assertEqual(self.names(c.plugins({'plugins':[self.row('Guide-Plugin',active),self.row('guide-assets')]})),['Guide-Plugin','guide-assets'])

    def test_active_unknown_and_non_numeric_children_remain_visible(self):
        self.declaration('Guide-Plugin',[{'directory':'guide-assets'}])
        for active in [1,None,False,'0',-1,float('nan')]:
            with self.subTest(active=active):
                self.assertEqual(self.names(c.plugins({'plugins':[self.row('Guide-Plugin',3),self.row('guide-assets',active)]})),['Guide-Plugin','guide-assets'])

    def test_duplicate_claims_remain_visible_even_when_other_parent_is_inactive(self):
        for name in ['Guide-Plugin','Other-Plugin']:self.declaration(name,[{'directory':'guide-assets'}])
        rows=c.plugins({'plugins':[self.row('Guide-Plugin',3),self.row('Other-Plugin'),self.row('guide-assets')]})
        self.assertEqual(self.names(rows),['Guide-Plugin','Other-Plugin','guide-assets'])
        self.declaration('Other-Plugin',[])
        self.declaration('Guide-Plugin',[{'directory':'guide-assets'},{'directory':'guide-assets'}])
        self.assertIn('guide-assets',self.names(c.plugins({'plugins':[self.row('Guide-Plugin',3),self.row('guide-assets')]})))

    def test_duplicate_runtime_rows_cannot_establish_unique_ownership(self):
        self.declaration('Guide-Plugin',[{'directory':'guide-assets'}])
        for entries in [[self.row('Guide-Plugin',2),self.row('Guide-Plugin',2),self.row('guide-assets')],
                        [self.row('Guide-Plugin',2),self.row('guide-assets'),self.row('guide-assets')]]:
            self.assertEqual(len(c.plugins({'plugins':entries})),3)

    def test_unsafe_names_self_claims_and_framework_components_cannot_group(self):
        self.declaration('Guide-Plugin',[{'directory':name} for name in ['..','../guide-assets','/guide-assets','C:guide-assets','Guide-Plugin',*c.BUILTIN_PLUGINS]])
        entries=[self.row('Guide-Plugin',3),self.row('guide-assets'),self.row('../escape')]+[self.row(name) for name in sorted(c.BUILTIN_PLUGINS)]
        self.assertEqual(self.names(c.plugins({'plugins':entries})),['Guide-Plugin','guide-assets']+sorted(c.BUILTIN_PLUGINS))

    def test_absent_child_or_invalid_declaration_does_not_create_hidden_rows(self):
        for components in [{'directory':'guide-assets'},None,'guide-assets',[],[{'directory':'guide-assets'}]*51]:
            self.declaration('Guide-Plugin',components)
            rows=c.plugins({'plugins':[self.row('Guide-Plugin',3),self.row('guide-assets')]})
            self.assertEqual(self.names(rows),['Guide-Plugin','guide-assets'])
        self.declaration('Guide-Plugin',[{'directory':'absent-assets'}])
        rows=c.plugins({'plugins':[self.row('Guide-Plugin',3)]})
        self.assertNotIn('components',rows[0])

    def test_invalid_and_oversized_public_metadata_does_not_group(self):
        self.declaration('Guide-Plugin',[])
        file=self.root/'plugins/Guide-Plugin/orangejuice.plugin.json'
        for raw in ['not json','[]',' '*300000]:
            file.write_text(raw,encoding='utf-8')
            self.assertEqual(self.names(c.plugins({'plugins':[self.row('Guide-Plugin',3),self.row('guide-assets')]})),['Guide-Plugin','guide-assets'])

    def test_truncated_runtime_cannot_prove_unique_component_ownership(self):
        self.declaration('Guide-Plugin',[{'directory':'guide-assets'}])
        self.declaration('Other-Plugin',[{'directory':'guide-assets'}])
        entries=[self.row('Guide-Plugin',3),self.row('guide-assets')]+[self.row('unused-'+str(index)) for index in range(48)]+[self.row('Other-Plugin',2)]
        self.assertIn('guide-assets',self.names(c.plugins({'plugins':entries})))

    def test_symlinked_declaration_never_reads_external_metadata(self):
        directory=self.root/'plugins/Guide-Plugin';directory.mkdir(parents=True)
        external=self.root/'outside.json';external.write_text(json.dumps({'components':[{'directory':'guide-assets'}]}),encoding='utf-8')
        try:(directory/'orangejuice.plugin.json').symlink_to(external)
        except OSError:self.skipTest('Symlink creation unavailable on this host')
        self.assertEqual(self.names(c.plugins({'plugins':[self.row('Guide-Plugin',3),self.row('guide-assets')]})),['Guide-Plugin','guide-assets'])

    def test_long_component_details_wrap_within_actual_font_width(self):
        try:from PIL import ImageFont
        except ImportError:self.skipTest('Pillow is optional for metadata-only tests')
        candidates=['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/truetype/wqy/wqy-microhei.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
        font_path=next((path for path in candidates if Path(path).is_file()),None)
        if not font_path:self.skipTest('No test font available')
        row={'components':[{'name':'very-long-component-'+str(index)*50,'label':'很长的公共图片组件说明'*4,'version':'1.'+'2'*35} for index in range(4)]}
        with patch.object(c,'FONT',font_path):lines=c.plugin_component_lines(row)
        font=ImageFont.truetype(font_path,18)
        self.assertGreater(len(lines),1)
        self.assertTrue(all(font.getlength(line)<=968 for line in lines))
        self.assertEqual(''.join(lines),'依赖组件：'+'；'.join(item['label']+'（'+item['name']+' · v'+item['version']+'）' for item in row['components']))


if __name__=='__main__':unittest.main()
