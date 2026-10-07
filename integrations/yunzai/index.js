import plugin from '../../../../lib/plugins/plugin.js'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {createDashboard,handleStatus} from '../../lib/status.mjs'
import {collectRuntime} from './runtime.mjs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
let fixedHelpPromise
async function helpReply(event,topic){
  let send
  try{
    if(!fixedHelpPromise)fixedHelpPromise=import('../../../AI-Plugin/src/rendering/static-help-reply.mjs').then(module=>module.createFixedHelpDelivery({root}))
    send=await fixedHelpPromise
  }catch{fixedHelpPromise=undefined;return false}
  return send(event,topic,{image:buffer=>{
    if(!globalThis.segment?.image)throw new Error('图片消息接口不可用')
    return globalThis.segment.image(buffer)
  }})
}
let config={}
try {config=JSON.parse(fs.readFileSync(path.join(root,'config/plugin.json'),'utf8'))}
catch(err){if(err.code!=='ENOENT')throw new Error('服务器状态插件配置文件不是有效JSON')}
const directory=path.resolve(config.ipcDirectory||'data/server-status')
const dashboard=createDashboard({directory,runtime:()=>collectRuntime(),timeoutMs:12000,cacheMs:5000})
export class ServerStatus extends plugin {
  constructor(){super({name:'服务器状态',dsc:'主人专用宿主机状态图片',event:'message',priority:5,rule:[{reg:/^[#\/](?:(?:系统|服务器|资源|存储|插件|服务)\s*|系统帮助(?:\s+文字)?\s*)$/,fnc:'status',permission:'master'}]})}
  async status(e){return handleStatus({isOwner:e.isMaster===true,msg:e.msg,reply:value=>e.reply(value)},dashboard,buffer=>globalThis.segment.image(buffer),{helpReply})}
}
