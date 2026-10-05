import {spawn} from 'node:child_process'
import fs from 'node:fs/promises'
import {fileURLToPath} from 'node:url'

/** Collect Linux host facts directly, with no daemon or bot framework. */
export async function collectSnapshot({configPath,kind='all',format='json',output,runtime={},python='python3',timeoutMs=30000}={}) {
  if (!['all','resources','storage','plugins','services'].includes(kind)) throw new Error('未知面板')
  if (!['json','png','both'].includes(format)) throw new Error('未知输出格式')
  if (format!=='json'&&!output) throw new Error('生成 PNG 图片需要指定输出路径')
  const args=[fileURLToPath(new URL('../scripts/status.py',import.meta.url)),'--kind',kind,'--format',format,'--runtime-stdin']
  if(configPath)args.push('--config',configPath)
  if(output)args.push('--output',output)
  const raw=await new Promise((resolve,reject)=>{
    const child=spawn(python,args,{stdio:['pipe','pipe','pipe'],shell:false})
    let stdout='',stderr='',done=false
    const finish=(err,value)=>{if(done)return;done=true;clearTimeout(timer);err?reject(err):resolve(value)}
    const timer=setTimeout(()=>{child.kill();finish(new Error('宿主机状态采集超时'))},timeoutMs)
    child.on('error',err=>finish(err))
    child.stdout.on('data',buf=>{stdout+=buf;if(stdout.length>2*1024*1024){child.kill();finish(new Error('状态采集结果过大'))}})
    child.stderr.on('data',buf=>{if(stderr.length<4000)stderr+=buf})
    child.on('close',code=>finish(code===0?null:new Error('宿主机状态采集失败：'+stderr.trim()),stdout))
    child.stdin.on('error',()=>{})
    child.stdin.end(JSON.stringify(runtime))
  })
  const report=JSON.parse(raw)
  if(format!=='json')report.png=await fs.readFile(output)
  return report
}
