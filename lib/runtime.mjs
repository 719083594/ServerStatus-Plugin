import fs from 'node:fs'
let loader
try { loader=(await import('../../../lib/plugins/loader.js')).default }catch{}

export function runtimeFrom({loader:source,bot={},files=[],processInfo=process}) {
  const priority=Array.isArray(source?.priority)?source.priority:undefined
  const counts=source?.pluginCountMap instanceof Map?source.pluginCountMap:undefined
  const loaded=new Map()
  for(const [key,count] of counts||[]) {
    const name=String(key).split('/')[0]
    loaded.set(name,(loaded.get(name)||0)+(Number(count)||0))
  }
  let connected=null
  if(bot.bots && typeof bot.bots==='object')connected=Object.keys(bot.bots).length>0
  else if(typeof bot.isOnline==='function') {
    try { const online=bot.isOnline();if(typeof online==='boolean')connected=online }catch{}
  } else if(typeof bot.isOnline==='boolean')connected=bot.isOnline
  return {
    nodeVersion:processInfo.version,botUptime:processInfo.uptime(),botRss:processInfo.memoryUsage().rss,
    connected,loadedCount:priority?.length??null,taskCount:Array.isArray(source?.task)?source.task.length:null,
    plugins:files.map(name=>({name,loaded:counts?(loaded.get(name)||0):null,active:priority?priority.filter(i=>String(i.key||'').split('/')[0]===name).length:null}))
  }
}
export function collectRuntime() {
  let files=[]
  try { files=fs.readdirSync('plugins',{withFileTypes:true}).filter(i=>i.isDirectory()).map(i=>i.name) }catch{}
  return runtimeFrom({loader,bot:globalThis.Bot||{},files})
}
