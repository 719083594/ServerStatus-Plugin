"""On-demand host metrics; optional cleanup runs in a separate host timer."""
import json, os, re, subprocess, sys, time, threading
from datetime import datetime
from pathlib import Path

CONFIG={}
ROOT=Path.cwd()
DIRECTORY=ROOT/'data/server-status'
FONT=None
CONTAINERS={}
KINDS={'all','resources','storage','plugins','services'}


def configure(config, require_font=True):
    global CONFIG,ROOT,DIRECTORY,FONT,CONTAINERS,storage_cache
    CONFIG=config
    ROOT=Path(config.get('applicationRoot') or config.get('yunzaiRoot') or Path.cwd()).expanduser().resolve()
    DIRECTORY=Path(config.get('ipcDirectory') or ROOT/'data/server-status').expanduser().resolve()
    if not ROOT.is_dir():raise ValueError('应用根目录（applicationRoot）不存在或不是文件夹')
    candidates=[config.get('fontPath'),'/usr/share/fonts/truetype/wqy/wqy-microhei.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc']
    FONT=next((str(p) for p in candidates if p and Path(p).is_file()),None)
    if require_font:
        from PIL import ImageFont
        if not FONT:raise ValueError('未找到中文字体，请安装 fonts-wqy-microhei 或配置字体路径（fontPath）')
        ImageFont.truetype(FONT,24)
    mode=config.get('dockerMode','auto')
    if mode not in ('auto','selected','off'):raise ValueError('容器监测模式（dockerMode）无效')
    CONTAINERS={}
    for item in config.get('containers',[])[:30]:
        name=item.get('name','')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',name):raise ValueError('容器名称无效')
        CONTAINERS[name]=str(item.get('label',name))[:40]
    storage_cache=None
storage_cache=None
program_lock=threading.Lock()

def program_size():
    # Large dependency trees must not block a status command under the CPU cap.
    p=DIRECTORY/'program-cache.json';cached={}
    try:cached=json.loads(p.read_text())
    except (OSError,ValueError):pass
    if time.time()-cached.get('at',0)>max(60,int(CONFIG.get('programCacheSeconds',3600))) and program_lock.acquire(blocking=False):
        def refresh():
            try:
                n=int(run(['du','-sx','-B1','--',str(ROOT)],20).split()[0])
                write_json('program-cache.json',{'at':time.time(),'bytes':n})
            except Exception:pass
            finally:program_lock.release()
        threading.Thread(target=refresh,daemon=True).start()
    return cached.get('bytes')

def run(args, timeout=4):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=True)
    return result.stdout.strip()

def connection(value):return '未知' if value is None else '已连接' if value else '未连接'
def count_text(value):return '未知' if value is None else value
def percent(used,total):return round(used/total*100,1) if total else 0
def size(n):
    if n is None:return '未知'
    for unit in ['B','KiB','MiB','GiB','TiB']:
        if abs(n)<1024 or unit=='TiB':return f'{n:.1f} {unit}'
        n/=1024
def duration(seconds):
    if seconds is None:return '未知'
    days,rest=divmod(int(seconds),86400);hours,rest=divmod(rest,3600);minutes=rest//60
    return f'{days}天 {hours}小时 {minutes}分' if days else f'{hours}小时 {minutes}分'
def cpu_ticks():
    values=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
    return sum(values[:8]),sum(values[3:5])
def cpu_percent(first,second):
    total=second[0]-first[0];idle=second[1]-first[1]
    return round(max(0,min(100,(total-idle)/total*100)),1) if total>0 else 0
def memory():
    fields={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
    total=fields['MemTotal'];available=fields.get('MemAvailable',fields['MemFree']);used=total-available
    swap=fields['SwapTotal'];swap_used=swap-fields['SwapFree']
    return {'total':total,'available':available,'used':used,'percent':percent(used,total),'swapTotal':swap,'swapUsed':swap_used,'swapPercent':percent(swap_used,swap)}

def storage():
    global storage_cache
    if storage_cache and time.time()-storage_cache['at']<max(5,int(CONFIG.get('storageCacheSeconds',60))):return storage_cache
    mounts=[];seen=set()
    for line in Path('/proc/mounts').read_text().splitlines():
        source,mount,kind,*_=line.split()
        if kind not in {'ext4','xfs','btrfs','zfs','ext3','ext2'}:continue
        mount=mount.replace('\\040',' ')
        try:
            dev=os.stat(mount).st_dev
            if dev in seen:continue
            seen.add(dev);v=os.statvfs(mount);total=v.f_blocks*v.f_frsize;used=(v.f_blocks-v.f_bfree)*v.f_frsize;available=v.f_bavail*v.f_frsize
            mounts.append({'mount':mount,'type':kind,'total':total,'used':used,'available':available,'percent':percent(used,used+available),'inodePercent':percent(v.f_files-v.f_ffree,v.f_files)})
        except OSError:continue
    dirs=[]
    dirs.append({'label':'应用目录（后台缓存）','bytes':program_size()})
    configured=CONFIG.get('storageDirectories',[])
    defaults=[{'label':'应用运行数据','path':str(ROOT/'data')}]
    for item in (configured or defaults)[:20]:
        label=str(item.get('label','数据目录'))[:30]
        directory=Path(item['path']).expanduser().resolve()
        try:dirs.append({'label':label,'bytes':int(run(['du','-sx','-B1','--',str(directory)],3).split()[0])})
        except Exception:dirs.append({'label':label,'bytes':None})
    try:
        if CONFIG.get('dockerMode','auto')=='off':raise ValueError('未启用容器监测')
        docker=[json.loads(s) for s in run(['docker','system','df','--format','{{json .}}'],4).splitlines()]
    except Exception:docker=[]
    cleanup={'enabled':CONFIG.get('cleanup',{}).get('enabled',False),'scheduleTime':CONFIG.get('cleanup',{}).get('scheduleTime','03:30')}
    try:
        report=DIRECTORY/'cleanup.json'
        if report.stat().st_size<100000:cleanup['last']=json.loads(report.read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    storage_cache={'at':time.time(),'mounts':mounts,'directories':dirs,'docker':docker,'cleanup':cleanup}
    return storage_cache

def services():
    result=[]
    if CONFIG.get('dockerMode','auto')=='off':return [{'name':'原生部署','error':'未启用 Docker 监测；程序内存见资源页'}]
    try:
        names=dict(CONTAINERS)
        if CONFIG.get('dockerMode','auto')=='auto' and not names:
            discovered=run(['docker','ps','-a','--format','{{.Names}}'],3).splitlines()[:30]
            names={name:name for name in discovered if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}',name)}
        if not names:return [{'name':'Docker','error':'没有可监测的容器'}]
        info=json.loads(run(['docker','inspect',*names],3))
        stats={s['Name']:s for s in (json.loads(line) for line in run(['docker','stats','--no-stream','--format','{{json .}}',*names],4).splitlines())}
        for c in info:
            name=c['Name'].lstrip('/');s=stats.get(name,{})
            result.append({'name':names[name],'running':c['State']['Running'],'health':c['State'].get('Health',{}).get('Status','无健康探针'),'restarts':c['RestartCount'],'cpu':s.get('CPUPerc','--'),'memory':s.get('MemUsage','--'),'memoryPercent':s.get('MemPerc','--'),'pids':s.get('PIDs','--')})
    except Exception:result.append({'name':'Docker监测','error':'Docker 不可用或权限不足；宿主机资源仍可查看'})
    return result

def plugins(runtime):
    rows=[]
    names={'system':'TRSS 系统功能','adapter':'OneBot 适配器','other':'TRSS 辅助功能','example':'示例插件','chatgpt-plugin':'GPT 聊天插件','Guoba-Plugin':'锅巴管理面板','ServerStatus-Plugin':'服务器状态','WebSearch-Plugin':'联网搜索','OrangeJuice-Plugin':'橙汁管理平台','AI-Plugin':'AI 聊天'}
    for item in runtime.get('plugins',[])[:50]:
        name=str(item.get('name',''))
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',name):continue
        version=str(item.get('version',''))[:40]
        p=ROOT/'plugins'/name/'package.json'
        if p.is_file():
            try:version=str(json.loads(p.read_text()).get('version',''))[:40]
            except Exception:pass
        rows.append({'name':name,'label':str(item.get('label',names.get(name,name)))[:40],'version':version,'loaded':item.get('loaded'),'active':item.get('active')})
    return rows

def collect(request):
    if sys.platform!='linux':raise ValueError('宿主机状态采集仅支持 Linux')
    start=cpu_ticks();time.sleep(0.65);cpu=cpu_percent(start,cpu_ticks())
    runtime=request.get('runtime',{});kind=request['kind']
    if kind not in KINDS:raise ValueError('未知面板')
    if not isinstance(runtime,dict):raise ValueError('应用运行信息（runtime）必须是对象')
    uptime=float(Path('/proc/uptime').read_text().split()[0]);loads=os.getloadavg()
    data={'cpuPercent':cpu,'cores':os.cpu_count(),'memory':memory(),'uptime':uptime,'load':list(loads),'runtime':runtime}
    if kind in {'all','storage'}:data['storage']=storage()
    if kind in {'all','services'}:data['services']=services()
    if kind in {'all','plugins'}:data['plugins']=plugins(runtime)
    return data

class Dashboard:
    def __init__(self,title,generated):
        self.width=1080;self.y=196;self.items=[];self.title=title;self.generated=generated
    def section(self,title,height):
        y=self.y;self.items.append(('section',(y,title,height)));self.y+=height+20;return y
    def text(self,xy,content,px=24,color='#35465a'):
        self.items.append(('text',(xy,str(content),px,color)))
    def gauge(self,xy,label,value,subtitle):
        self.items.append(('gauge',(xy,label,value,subtitle)))
    def finish(self,target):
        from PIL import Image, ImageDraw, ImageFont
        im=Image.new('RGB',(self.width,self.y+100),'#eef3f9');draw=ImageDraw.Draw(im)
        def font(px):return ImageFont.truetype(FONT,px)
        def text(xy,value,px=24,fill='#35465a'):draw.text(xy,value,font=font(px),fill=fill)
        draw.rounded_rectangle((28,28,1052,172),radius=24,fill='#162d49')
        text((60,47),self.title,40,'#ffffff');text((62,110),'Linux 宿主机 · 服务器状态',24,'#a4c7ec')
        text((710,116),self.generated,21,'#a4c7ec')
        for typ,args in self.items:
            if typ=='section':
                y,title,height=args;draw.rounded_rectangle((28,y,1052,y+height),radius=22,fill='white');text((56,y+18),title,28,'#162d49')
            elif typ=='text':text(*args)
            elif typ=='gauge':
                (x,y),label,value,subtitle=args;color='#1985e4' if value<75 else '#e5a02b' if value<90 else '#e15353'
                text((x,y),label,24);text((x,y+36),f'{value:.1f}%',43,color)
                draw.rounded_rectangle((x,y+99,x+290,y+113),radius=7,fill='#e9eff6')
                if value>0:draw.rounded_rectangle((x,y+99,x+max(14,290*min(value,100)/100),y+113),radius=7,fill=color)
                text((x,y+130),subtitle,20,'#758399')
        text((56,self.y+5),'数据按需采集；5秒图片缓存；存储目录大小最多缓存60秒。',20,'#758399')
        text((56,self.y+38),'#系统  #资源  #存储  #插件  #服务  #系统帮助（也支持 /）',20,'#758399')
        tmp=target.with_suffix('.tmp');im.save(tmp,format='PNG',optimize=True);os.chmod(tmp,0o660);tmp.replace(target)
        return im.size

def render(data,kind,target):
    title={'all':'服务器运行总览','resources':'CPU 与内存资源','storage':'磁盘与存储情况','plugins':'机器人插件情况','services':'服务运行与占用'}[kind]
    now=datetime.now().strftime('%Y-%m-%d %H:%M:%S');d=Dashboard(title,now);m=data['memory'];r=data['runtime']
    if kind in {'all','resources'}:
        y=d.section('核心资源 · CPU 为全部核心平均占用',260)
        d.gauge((56,y+65),'CPU',data['cpuPercent'],f"{data['cores']} 核 · 0.65秒采样")
        d.gauge((386,y+65),'物理内存',m['percent'],f"{size(m['used'])} / {size(m['total'])}")
        d.gauge((716,y+65),'交换内存',m['swapPercent'],f"{size(m['swapUsed'])} / {size(m['swapTotal'])}")
        y=d.section('运行信息',215)
        d.text((56,y+68),f"服务器已运行：{duration(data['uptime'])}       应用：{duration(r.get('botUptime'))}")
        d.text((56,y+110),f"连接：{connection(r.get('connected'))}    Node {r.get('nodeVersion','未知')}    系统负载：{' / '.join(f'{n:.2f}' for n in data['load'])}",23)
        d.text((56,y+146),f"应用进程内存：{size(r.get('botRss'))}",20,'#758399')
        d.text((56,y+180),'内存已用 = 总量 - MemAvailable；包含系统和全部服务，不含可回收缓存。',18,'#758399')
    if kind in {'all','storage'}:
        s=data['storage'];height=80+len(s['mounts'])*108+len(s['directories'])*36+len(s['docker'])*32+160
        y=d.section('硬盘与存储',height);yy=y+65
        for row in s['mounts']:
            d.text((56,yy),f"磁盘 {row['mount']} ({row['type']})    {row['percent']:.1f}% 已用",26)
            d.text((56,yy+39),f"已用 {size(row['used'])} / 总量 {size(row['total'])}    可用 {size(row['available'])}    inode {row['inodePercent']}%",22);yy+=108
        for row in s['directories']:
            d.text((56,yy),row['label'][:25],22);d.text((680,yy),size(row['bytes']) if row['bytes'] is not None else '统计中或无法读取',22);yy+=36
        yy+=15
        labels={'Images':'Docker镜像','Containers':'容器可写层','Local Volumes':'Docker数据卷','Build Cache':'构建缓存'}
        for row in s['docker']:
            d.text((56,yy),f"{labels.get(row['Type'],row['Type'])}：{row['Size']}    估算可回收 {row['Reclaimable']}",20);yy+=32
        d.text((56,yy+8),'Docker 估算含共享层；实际释放以清理结果为准，目录与 Docker 容量勿相加。',18,'#758399');yy+=38
        cleanup=s.get('cleanup',{});last=cleanup.get('last')
        schedule=f"每天 {cleanup.get('scheduleTime','03:30')}（北京时间，最多延迟5分）" if cleanup.get('enabled') else '未启用'
        d.text((56,yy),'定时清理：'+schedule,20);yy+=34
        if last:
            at=datetime.fromtimestamp(last['finishedAt']/1000).strftime('%m-%d %H:%M')
            state='完成' if last.get('success') else '部分失败，查看清理日志'
            reclaimed=' / '.join(item.get('reclaimed','失败') for item in last.get('docker',[]))
            d.text((56,yy),f"最近 {at} {state} · 临时文件 {last.get('filesDeleted',0)} 个",20);yy+=30
            d.text((56,yy),'Docker 实际释放（镜像 / 构建缓存）：'+(reclaimed or '未清理'),18,'#758399')
        else:d.text((56,yy),'仅清理过期缓存；保留容器、数据卷、聊天记录、登录和配置。',18,'#758399')
    if kind in {'all','services'}:
        rows=data['services'];y=d.section('服务状态 · 容器 CPU 以单核100%计，多核可超过100%',125+len(rows)*78)
        yy=y+70
        for row in rows:
            if 'error' in row:d.text((56,yy),row['error']);yy+=78;continue
            good=row['running'] and row['health'] in {'healthy','无健康探针'}
            health={'healthy':'健康','unhealthy':'异常','starting':'启动中'}.get(row['health'],row['health']) if row['running'] else '已停止'
            d.text((56,yy),row['name'][:14],24);d.text((430,yy),health,22,'#219271' if good else '#db4d54');d.text((715,yy),f"CPU {row['cpu']}",22)
            d.text((56,yy+35),f"内存 {row['memory']} ({row['memoryPercent']})   进程 {row['pids']}   重启 {row['restarts']}次",20,'#758399');yy+=78
        d.text((56,yy+8),'内存数字为 Docker 统计口径；不能和宿主机占用直接相加。',18,'#758399')
    if kind in {'all','plugins'}:
        rows=data['plugins'];y=d.section(f"插件 · 已加载 {count_text(r.get('loadedCount'))} 个功能 / {count_text(r.get('taskCount'))} 个定时任务",135+len(rows)*63)
        yy=y+65
        for row in rows:
            label=('连接 '+connection(r.get('connected'))+' · 适配器不注册命令') if row['name']=='adapter' else (f"{row['active']} 个已注册功能" if row['active'] is not None else '框架未提供功能数量')
            d.text((56,yy),row['label'][:22],24);d.text((610,yy),label,22,'#219271' if row['active'] or (row['name']=='adapter' and r.get('connected')) else '#a0772a')
            d.text((56,yy+30),row['name']+(' · v'+row['version'] if row['version'] else ''),19,'#758399');yy+=63
        d.text((56,yy+12),'功能已注册不代表每项外部API可用；上游额度、禁言等由对应服务决定。',18,'#758399')
    return d.finish(target)

def write_json(name,data):
    tmp=DIRECTORY/(name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');os.chmod(tmp,0o660);tmp.replace(DIRECTORY/name)
def process(request):
    identifier=request.get('id','');kind=request.get('kind')
    if not re.fullmatch(r'[0-9a-f-]{36}',identifier) or kind not in KINDS:raise ValueError('状态采集请求无效')
    if abs(time.time()*1000-request.get('requestedAt',0))>15000:return
    try:
        data=collect(request);dimensions=render(data,kind,DIRECTORY/'dashboard.png')
        write_json('response.json',{'id':identifier,'kind':kind,'generatedAt':int(time.time()*1000),'dimensions':dimensions,'details':data})
    except Exception as exc:
        print('状态采集器：',type(exc).__name__,flush=True)
        write_json('response.json',{'id':identifier,'kind':kind,'error':type(exc).__name__})
def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True,mode=0o2770)
    last=None
    while True:
        try:
            p=DIRECTORY/'request.json'
            if p.exists() and p.stat().st_size<100000:
                request=json.loads(p.read_text());identifier=request.get('id')
                if identifier!=last:last=identifier;process(request)
        except Exception as exc:print('状态采集器：',type(exc).__name__,flush=True)
        time.sleep(0.3)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='按需采集 Linux 宿主机状态并生成图片',add_help=False)
    parser.add_argument('-h','--help',action='help',help='显示帮助并退出')
    parser._optionals.title='可选参数'
    parser.add_argument('--config',type=Path,required=True,help='采集器配置文件')
    parser.add_argument('--once',action='store_true',help='处理一次请求后退出')
    args=parser.parse_args()
    configure(json.loads(args.config.read_text(encoding='utf-8')))
    DIRECTORY.mkdir(parents=True,exist_ok=True,mode=0o2770)
    if args.once:process(json.loads((DIRECTORY/'request.json').read_text()))
    else:main()
