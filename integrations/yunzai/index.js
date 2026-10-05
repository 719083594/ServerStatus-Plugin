import plugin from '../../../../lib/plugins/plugin.js'
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {createDashboard,handleStatus} from '../../lib/status.mjs'
import {collectRuntime} from './runtime.mjs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
let config={}
try {config=JSON.parse(fs.readFileSync(path.join(root,'config/plugin.json'),'utf8'))}
catch(err){if(err.code!=='ENOENT')throw new Error('服务器状态插件配置文件不是有效JSON')}
const directory=path.resolve(config.ipcDirectory||'data/server-status')
const dashboard=createDashboard({directory,runtime:()=>collectRuntime(),timeoutMs:12000,cacheMs:5000})
export class ServerStatus extends plugin {
  constructor(){super({name:'服务器状态',dsc:'主人专用宿主机状态图片',event:'message',priority:5,rule:[{reg:/^[#\/](?:系统|服务器|资源|存储|插件|服务|系统帮助)\s*$/,fnc:'status',permission:'master'}]})}
  async status(e){return handleStatus({isOwner:e.isMaster===true,msg:e.msg,reply:value=>e.reply(value)},dashboard,buffer=>globalThis.segment.image(buffer))}
}
