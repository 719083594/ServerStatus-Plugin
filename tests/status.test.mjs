import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import {commands,commandKind,handleStatus,createDashboard} from '../lib/status.mjs'
for(const name of Object.keys(commands))for(const prefix of ['#','/'])assert.equal(commandKind(prefix+name),commands[name])
let builds=0,replies=[]
await handleStatus({isMaster:false,msg:'#系统',reply:async m=>replies.push(m)},async()=>{builds++},()=>{})
assert.equal(builds,0);assert.equal(replies.length,0)
const png=Buffer.from('89504e470d0a1a0a0001','hex')
await handleStatus({isMaster:true,msg:'/系统',reply:async m=>{replies.push(m);return {message_id:1}}},async kind=>{assert.equal(kind,'all');return {png}},buffer=>({type:'image',file:buffer}))
assert.equal(replies[0].type,'image');assert.equal(replies[0].file,png)
const directory=await fs.mkdtemp(path.join(os.tmpdir(),'qqbot-status-test-'))
let observed=[]
const timer=setInterval(async()=>{
 try{
  const req=JSON.parse(await fs.readFile(path.join(directory,'request.json')))
  if(observed.includes(req.id))return
  observed.push(req.id)
  await fs.writeFile(path.join(directory,'dashboard.png'),png)
  const temp=path.join(directory,'test-response.tmp')
  await fs.writeFile(temp,JSON.stringify({id:req.id,kind:req.kind,generatedAt:Date.now(),details:{kind:req.kind}}))
  await fs.rename(temp,path.join(directory,'response.json'))
 }catch{}
},20)
try{
 const dashboard=createDashboard({directory,runtime:()=>({}),timeoutMs:2000,cacheMs:5000})
 const values=await Promise.all(['all','storage','plugins','services','resources'].map(kind=>dashboard(kind)))
 assert.deepEqual(values.map(v=>v.details.kind),['all','storage','plugins','services','resources'])
 assert.equal(observed.length,5)
 await dashboard('resources');assert.equal(observed.length,5)
 clearInterval(timer)
 const timeout=createDashboard({directory,runtime:()=>({}),timeoutMs:180,cacheMs:0})
 await assert.rejects(timeout('all'),/超时/)
 console.log(JSON.stringify({ok:true,checks:['both_command_prefixes','non_owner_no_collection','owner_image_segment','concurrent_request_serialization','cache','timeout']}))
}finally{clearInterval(timer);await fs.rm(directory,{recursive:true,force:true})}
