import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createWorker} from './worker.mjs';
const value={message:'test feedback',contact:'',category:'bug',version:'1.5',request_id:'a'.repeat(24)};
const env=()=>({DISCORD_BOT_TOKEN:'test-only-token',DISCORD_FORUM_CHANNEL_ID:'123456789012345678',FEEDBACK_LIMITER:{limit:async()=>({success:true})},TOTAL_LIMITER:{limit:async()=>({success:true})}});
const request=(data=value)=>new Request('https://test.workers.dev/feedback',{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.1'},body:JSON.stringify(data)});

test('creates a forum post only in the configured channel; mentions disabled and category tagged',async()=>{
  const calls=[];const worker=createWorker(async(url,options)=>{
    calls.push({url,method:options.method,body:options.body ? JSON.parse(options.body):undefined});
    return Response.json(options.method==='GET' ? {id:'123456789012345678',type:15,available_tags:[{id:'456',name:'버그'}]} : {id:'123456789012345679',message:{id:'123456789012345680'}});
  });
  const response=await worker.fetch(request({...value,message:'@everyone test',channel_id:'999'}),env());
  assert.equal(response.status,200);assert.equal((await response.json()).ok,true);
  assert.equal(calls[0].method,'GET');assert.ok(calls[1].url.endsWith('/channels/123456789012345678/threads'));
  assert.deepEqual(calls[1].body.message.allowed_mentions,{parse:[]});
  assert.deepEqual(calls[1].body.applied_tags,['456']);
  assert.ok(calls[1].body.name.startsWith('[오류 제보]'));assert.ok(calls[1].body.message.content.includes(value.request_id));
});
test('rejects a non-forum destination, missing required tag and incomplete delivery',async()=>{
  for (const channel of [{id:'123456789012345678',type:0},{id:'123456789012345678',type:15,flags:16,available_tags:[]}]) {
    let calls=0;const worker=createWorker(async()=>{calls++;return Response.json(channel);});
    assert.equal((await worker.fetch(request(),env())).status,503);assert.equal(calls,1);
  }
  const worker=createWorker(async(url,options)=>Response.json(options.method==='GET' ? {id:'123456789012345678',type:15}: {id:'123456789012345679'}));
  assert.equal((await worker.fetch(request(),env())).status,502);
});
test('rejects oversized, empty and malformed submissions before Discord',async()=>{
  const worker=createWorker(()=>{throw new Error('must not call');});
  for(const data of [{...value,message:''},{...value,message:'x'.repeat(1501)},{...value,request_id:'wrong'},{...value,contact:'x'.repeat(9000)}])
    assert.equal((await worker.fetch(request(data),env())).status,400);
});
test('missing secrets and missing rate limit bindings fail closed',async()=>{
  const worker=createWorker(()=>{throw new Error('must not call');});
  assert.equal((await worker.fetch(request(),{})).status,503);
  const e=env();delete e.FEEDBACK_LIMITER;assert.equal((await worker.fetch(request(),e)).status,503);
});
test('rate limiting and Discord errors are not reported as delivered',async()=>{
  const e=env();e.FEEDBACK_LIMITER.limit=async()=>({success:false});
  const worker=createWorker(async()=>new Response('not allowed',{status:403}));
  assert.equal((await worker.fetch(request(),e)).status,429);
  const response=await worker.fetch(request(),env());assert.equal(response.status,502);
  assert.equal((await response.json()).error,'delivery_failed');
});
test('Discord throttling becomes a retryable response',async()=>{
  const worker=createWorker(async()=>new Response('{}',{status:429}));
  const response=await worker.fetch(request(),env());assert.equal(response.status,429);assert.equal(response.headers.get('retry-after'),'60');
});
test('Discord DM configuration errors expose only safe status codes',async()=>{
  const worker=createWorker(async()=>Response.json({code:50278,message:'not forwarded'}, {status:403}));
  const response=await worker.fetch(request(),env());
  assert.deepEqual(await response.json(),{error:'no_mutual_server',provider_status:403,provider_code:50278});
});
