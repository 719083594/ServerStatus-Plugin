import test from 'node:test';
import assert from 'node:assert/strict';
import {commandKind,handleStatus} from '../lib/status.mjs';
import {helpTopics} from '../lib/help-content.mjs';

test('owner check happens before a fixed help callback',async()=>{
  let calls=0;for(const isOwner of [false,undefined,1,'true'])await handleStatus({isOwner,msg:'#系统帮助',reply:()=>{calls++}},()=>{assert.fail('help must not collect')},()=>{assert.fail('help must not render')},{helpReply:()=>{calls++;return true}});
  assert.equal(calls,0);
});
test('owner fixed help uses the declared topic and needs no collector',async()=>{
  const replies=[],topics=[];const event={isOwner:true,msg:'#系统帮助',reply:value=>replies.push(value)};
  assert.equal(await handleStatus(event,()=>{assert.fail('help must not collect')},()=>{assert.fail('help must not render')},{helpReply:async(e,topic)=>{assert.equal(e,event);topics.push(topic);return true}}),true);
  assert.deepEqual(topics,['system-help']);assert.deepEqual(replies,[]);
});
test('text help remains available and missing JPEG fallback is explicit',async()=>{
  const replies=[];let callbacks=0;
  assert.equal(commandKind('/系统帮助 文字'),'help');assert.equal(commandKind('#资源 文字'),undefined);
  for(const msg of ['#系统帮助 文字','/系统帮助 文字'])await handleStatus({isOwner:true,msg,reply:value=>replies.push(value)},null,null,{helpReply:()=>{callbacks++;return true}});
  assert.equal(callbacks,0);assert.equal(replies.length,2);assert.match(replies[0],/系统状态插件/);
  await handleStatus({isOwner:true,msg:'#系统帮助',reply:value=>replies.push(value)},null,null,{helpReply:async()=>false});assert.equal(replies.length,3);
});
test('partial fixed image delivery errors do not append duplicate text',async()=>{
  const replies=[];await assert.rejects(handleStatus({isOwner:true,msg:'#系统帮助',reply:value=>replies.push(value)},null,null,{helpReply:async()=>{throw Error('PARTIAL_FIXED_HELP_DELIVERY')}}),/PARTIAL_FIXED_HELP_DELIVERY/);assert.deepEqual(replies,[]);
});
test('fixed system source contains command descriptions and no live host details',()=>{
  const topic=helpTopics['system-help'],text=JSON.stringify(topic);for(const command of ['#系统 / #服务器','#资源','#存储','#插件','#服务','#系统帮助 文字'])assert.ok(text.includes(command));
  assert.doesNotMatch(text,/47\.112|hostAddress|isOwner|token|cookie|ipcDirectory/);
});
