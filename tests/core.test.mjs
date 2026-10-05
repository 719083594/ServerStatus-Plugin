import test from 'node:test'
import assert from 'node:assert/strict'
import {apps,commands,collectSnapshot,createDashboard,handleStatus} from '../index.js'
test('plain checkout imports API without Yunzai installed',()=>{
  assert.deepEqual(apps,{})
  assert.equal(commands.系统,'all')
  assert.equal(typeof collectSnapshot,'function')
  assert.equal(typeof createDashboard,'function')
})
test('owner proof must be a trusted boolean',async()=>{
  let calls=0
  for(const isOwner of [undefined,false,'true',1])await handleStatus({isOwner,msg:'#系统',reply:()=>calls++},()=>calls++,()=>{})
  assert.equal(calls,0)
})
test('direct snapshot rejects malformed arguments before starting a process',async()=>{
  await assert.rejects(collectSnapshot({kind:'shell'}),/Unknown panel/)
  await assert.rejects(collectSnapshot({format:'png'}),/output path required/)
})
