import fs from 'node:fs/promises'
import path from 'node:path'
import {randomUUID} from 'node:crypto'

export const commands = Object.freeze({系统:'all',服务器:'all',资源:'resources',存储:'storage',插件:'plugins',服务:'services',系统帮助:'help'})
const help = '系统状态插件（仅主人）\n#系统 / #服务器：完整总览\n#资源：CPU、内存、Swap、运行时间\n#存储：磁盘、数据目录、Docker存储\n#插件：已安装插件和实际加载情况\n#服务：服务运行及占用\n#系统帮助：本说明\n所有命令也支持 / 开头。无需 @，不调用 AI、不画图。'
export function commandKind(msg) { return commands[String(msg).trim().replace(/^[#\/]/,'')] }
export async function handleStatus(e, build, image) {
  // The trusted adapter derives isOwner from framework configuration, never user text.
  if (e.isOwner !== true) return true
  const kind = commandKind(e.msg)
  if (!kind) return false
  if (kind === 'help') { await e.reply(help); return true }
  try {
    const report = await build(kind)
    const result = await e.reply(image(report.png))
    if (result === false || result?.error) throw new Error('QQ图片发送失败')
  } catch (err) {
    globalThis.logger?.error('[服务器状态] '+err.message)
    await e.reply('系统状态图暂时无法发送，请稍后重试。')
  }
  return true
}

export function createDashboard({directory, runtime=()=>({}), timeoutMs=12000, cacheMs=5000}) {
  let pending, cached
  return async kind => {
    if (!Object.values(commands).includes(kind) || kind==='help') throw new Error('未知面板')
    if (cached?.kind===kind && Date.now()-cached.at < cacheMs) return cached.report
    while (pending) {
      await pending.catch(()=>{})
      if (cached?.kind===kind && Date.now()-cached.at < cacheMs) return cached.report
    }
    const task=(async()=>{
      await fs.mkdir(directory,{recursive:true,mode:0o2770})
      const id=randomUUID(), started=Date.now()
      const request={id,kind,requestedAt:started,runtime:runtime()}
      const temp=path.join(directory,'request.tmp')
      await fs.writeFile(temp,JSON.stringify(request),{mode:0o660})
      await fs.rename(temp,path.join(directory,'request.json'))
      while(Date.now()-started < timeoutMs) {
        try {
          const response=JSON.parse(await fs.readFile(path.join(directory,'response.json'),'utf8'))
          if(response.id===id) {
            if(response.error) throw new Error('宿主机采集失败')
            if(response.kind!==kind || Date.now()-response.generatedAt>timeoutMs) throw new Error('采集结果过期')
            const png=await fs.readFile(path.join(directory,'dashboard.png'))
            if(png.length>6*1024*1024 || !png.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex'))) throw new Error('状态图格式错误')
            const report={png,details:response.details,generatedAt:response.generatedAt}
            cached={kind,at:Date.now(),report};return report
          }
        } catch(err) {
          if(err.code!=='ENOENT' && !(err instanceof SyntaxError)) throw err
        }
        await new Promise(resolve=>setTimeout(resolve,120))
      }
      throw new Error('宿主机采集超时')
    })()
    pending=task
    try{return await task}finally{if(pending===task)pending=undefined}
  }
}
