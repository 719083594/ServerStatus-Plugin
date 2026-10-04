import test from 'node:test'
import assert from 'node:assert/strict'
import {runtimeFrom} from '../lib/runtime.mjs'
test('TRSS loader counters and connected bots without hardcoded accounts',()=>{
 const r=runtimeFrom({loader:{pluginCountMap:new Map([['foo/a.js',2]]),priority:[{key:'foo/a.js'}],task:[{}]},bot:{bots:{demo:{}}},files:['foo','bar']})
 assert.equal(r.connected,true);assert.equal(r.loadedCount,1);assert.equal(r.plugins[0].active,1)
 assert.equal(r.plugins[1].active,0)
})
test('classic Yunzai online client and absent internal counters degrade honestly',()=>{
 const r=runtimeFrom({bot:{isOnline:()=>true},files:['foo']})
 assert.equal(r.connected,true);assert.equal(r.loadedCount,null);assert.equal(r.plugins[0].active,null)
})
test('unknown connection state is not reported as disconnected',()=>assert.equal(runtimeFrom({}).connected,null))
