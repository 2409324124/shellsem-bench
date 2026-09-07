import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createBenchSession} from '../runner/session.mjs';
import {ModelRuntime} from '../.runtime/pi/node_modules/@earendil-works/pi-coding-agent/dist/index.js';

function reply(res,tool=false){
  res.writeHead(200,{'Content-Type':'text/event-stream'});
  const delta=tool?{role:'assistant',tool_calls:[{index:0,id:'call_once',type:'function',function:{name:'counter',arguments:'{}'}}]}:{role:'assistant',content:'done'};
  for(const chunk of [{choices:[{index:0,delta,finish_reason:null}]},{choices:[{index:0,delta:{},finish_reason:tool?'tool_calls':'stop'}]}])
    res.write('data: '+JSON.stringify({id:'test',object:'chat.completion.chunk',created:1,model:'test',...chunk})+'\n\n');
  res.end('data: [DONE]\n\n');
}

test('retry resumes the failed API turn without executing a completed tool twice',async()=>{
  let calls=0,executions=0;
  const server=http.createServer(async(req,res)=>{
    let body='';for await(const part of req)body+=part;
    const messages=JSON.parse(body).messages;
    calls++;
    if(calls===1)return reply(res,true);
    assert.equal(messages.filter(m=>m.role==='tool').length,1);
    if(calls===2){res.writeHead(503);return res.end(JSON.stringify({error:{message:'Service unavailable',type:'server_error'}}));}
    reply(res);
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'shellsem-retry-'));
  let session;
  try{
    await fs.writeFile(path.join(dir,'models.json'),JSON.stringify({providers:{test:{baseUrl:`http://127.0.0.1:${server.address().port}/v1`,api:'openai-completions',apiKey:'fake-test-key',models:[{id:'test',reasoning:false,input:['text'],contextWindow:32768,maxTokens:256}]}}}));
    const runtime=await ModelRuntime.create({modelsPath:path.join(dir,'models.json'),authPath:path.join(dir,'auth.json'),allowModelNetwork:false});
    ({session}=await createBenchSession({modelRuntime:runtime,model:runtime.getModel('test','test'),configDir:dir,tools:['counter'],defs:[{name:'counter',label:'counter',description:'increment counter once',parameters:{type:'object',properties:{}},execute:async()=>{executions++;return {content:[{type:'text',text:'done'}]};}}],retryDelayMs:1}));
    const events=[];session.subscribe(e=>events.push(e));
    await session.prompt('Call counter exactly once, then finish.');
    assert.equal(calls,3);assert.equal(executions,1);
    assert.equal(events.filter(e=>e.type==='auto_retry_start').length,1);
    assert.equal(events.find(e=>e.type==='auto_retry_end').success,true);
    assert.equal(session.state.messages.at(-1).stopReason,'stop');
  }finally{session?.dispose();server.closeAllConnections();await new Promise(r=>server.close(r));await fs.rm(dir,{recursive:true,force:true});}
});

for(const scenario of [
  {name:'timeouts recover within the same session',status:'timeout',expectedCalls:2,retries:1,final:'stop'},
  {name:'persistent 503 stops after two retries',status:503,expectedCalls:3,retries:2,final:'error'},
  {name:'401 authentication failure is not retried',status:401,expectedCalls:1,retries:0,final:'error'},
  {name:'quota exhaustion is not retried',status:429,message:'insufficient_quota',expectedCalls:1,retries:0,final:'error'},
])test(scenario.name,async()=>{
  let calls=0;
  const server=http.createServer(async(req,res)=>{
    for await(const ignored of req){}
    calls++;
    if(scenario.status==='timeout'){
      if(calls===1)return; // No response: exercise the actual SDK timeout.
      return reply(res);
    }
    res.writeHead(scenario.status,{'Content-Type':'application/json'});
    res.end(JSON.stringify({error:{message:scenario.message||(scenario.status===401?'Unauthorized':'Service unavailable')}}));
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'shellsem-retry-'));let session;
  try{
    await fs.writeFile(path.join(dir,'models.json'),JSON.stringify({providers:{test:{baseUrl:`http://127.0.0.1:${server.address().port}/v1`,api:'openai-completions',apiKey:'fake-test-key',models:[{id:'test',reasoning:false,input:['text'],contextWindow:32768,maxTokens:256}]}}}));
    const runtime=await ModelRuntime.create({modelsPath:path.join(dir,'models.json'),authPath:path.join(dir,'auth.json'),allowModelNetwork:false});
    ({session}=await createBenchSession({modelRuntime:runtime,model:runtime.getModel('test','test'),configDir:dir,tools:[],defs:[],retryDelayMs:1,timeoutMs:100}));
    const events=[];session.subscribe(e=>events.push(e));await session.prompt('Say done.');
    assert.equal(calls,scenario.expectedCalls);
    assert.equal(events.filter(e=>e.type==='auto_retry_start').length,scenario.retries);
    assert.equal(session.state.messages.at(-1).stopReason,scenario.final);
  }finally{session?.dispose();server.closeAllConnections();await new Promise(r=>server.close(r));await fs.rm(dir,{recursive:true,force:true});}
});
