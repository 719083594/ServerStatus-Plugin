import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {pathToFileURL} from 'node:url'
test('standard V3 plugin export, master rule, and nonowner fail-closed',async()=>{
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'yunzai-contract-'))
 try{
  await fs.mkdir(path.join(temp,'lib/plugins'),{recursive:true})
  await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}')
  await fs.writeFile(path.join(temp,'lib/plugins/plugin.js'),'export default class Plugin {constructor(options){Object.assign(this,options)}}')
  await fs.writeFile(path.join(temp,'lib/plugins/loader.js'),'export default {priority:[],task:[]}')
  const root=new URL('../',import.meta.url)
  const target=path.join(temp,'plugins/ServerStatus-Plugin')
  await fs.cp(root,target,{recursive:true,filter:src=>!/[\\/](\.git|node_modules|__pycache__|data|dist)([\\/]|$)/.test(src)})
  await fs.writeFile(path.join(target,'config/integration.json'),JSON.stringify({adapter:'yunzai'}))
  const {apps:{ServerStatus}}=await import(pathToFileURL(path.join(target,'index.js')))
  const core=await import(pathToFileURL(path.join(target,'lib/api.mjs')))
  assert.equal(typeof core.collectSnapshot,'function')
  const instance=new ServerStatus();assert.equal(instance.rule[0].permission,'master')
  for(const cmd of ['系统','服务器','资源','插件','存储','服务','系统帮助'])for(const prefix of ['#','/'])assert.ok(instance.rule[0].reg.test(prefix+cmd))
  assert.equal(instance.init,undefined) // public build adds no management endpoints
  let replies=0;await instance.status({isMaster:false,msg:'#系统',reply:()=>{replies++}});assert.equal(replies,0)
 }finally{await fs.rm(temp,{recursive:true,force:true})}
})
