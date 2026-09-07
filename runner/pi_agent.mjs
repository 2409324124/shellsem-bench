import {installNetworkTrace} from './network_trace.mjs';
import {createBenchSession} from './session.mjs';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {ModelRuntime} from '../.runtime/pi/node_modules/@earendil-works/pi-coding-agent/dist/index.js';
import {createReadToolDefinition,createWriteToolDefinition,createEditToolDefinition,createBashToolDefinition} from '../.runtime/pi/node_modules/@earendil-works/pi-coding-agent/dist/core/tools/index.js';

export function dockerOps(container,emit=()=>{}) {
  function exec(argv, {input, onData, signal, timeout=30}={}) {
    return new Promise((resolve,reject)=>{
      const p=spawn('docker',['exec','-i','--user','1001:1001','--workdir','/workspace',container,...argv],{stdio:['pipe','pipe','pipe']});
      let chunks=[],size=0,settled=false;
      const stop=()=>p.kill('SIGKILL');
      const timer=setTimeout(stop,(timeout+3)*1000);
      signal?.addEventListener('abort',stop,{once:true});
      p.stdin.on('error',()=>{});
      const collect=b=>{size+=b.length;if(onData)onData(b);else if(size<=16777216)chunks.push(b);else stop();};
      p.stdout.on('data',collect); p.stderr.on('data',collect);
      p.on('error',e=>{if(!settled){settled=true;clearTimeout(timer);reject(e);}});
      p.on('close',code=>{clearTimeout(timer);signal?.removeEventListener('abort',stop);if(!settled){settled=true;resolve({code,data:Buffer.concat(chunks)});}});
      p.stdin.end(input);
    });
  }
  async function checked(argv, options) {const r=await exec(argv,options);if(r.code!==0)throw new Error(`Sandbox operation failed (${r.code}): ${r.data.toString().slice(0,1000)}`);return r.data;}
  const readFile=p=>checked(['bash','-c','n=$(stat -Lc %s -- "$1") && ((n <= 16777216)) && cat -- "$1"','_',p]);
  const writeFile=(p,content)=>checked(['bash','-c','cat > "$1"','_',p],{input:content});
  return {readFile,writeFile,
    readAccess:p=>checked(['test','-r',p]),
    editAccess:p=>checked(['bash','-c','test -r "$1" && test -w "$1"','_',p]),
    mkdir:p=>checked(['mkdir','-p','--',p]),
    bash:async(command,cwd,opts)=>{const start=performance.now();const seconds=Math.min(opts.timeout||30,30);const r=await exec(['timeout','-k','2',String(seconds),'bash','--noprofile','--norc','-c',command],{onData:opts.onData,signal:opts.signal,timeout:seconds});emit({type:'shell_command_end',exit_code:r.code,elapsed_ms:Math.round(performance.now()-start)});return {exitCode:r.code};}
  };
}

async function main(){
  const [mode,container,configDir,promptFile]=process.argv.slice(2);
  const emit=e=>process.stdout.write(JSON.stringify({time:Date.now()/1000,...e})+'\n');
  const ops=dockerOps(container,emit);
  const defs=[createReadToolDefinition('/workspace',{operations:{readFile:ops.readFile,access:ops.readAccess,detectImageMimeType:async()=>undefined}}),
    createWriteToolDefinition('/workspace',{operations:{writeFile:ops.writeFile,mkdir:ops.mkdir}}),
    createEditToolDefinition('/workspace',{operations:{readFile:ops.readFile,writeFile:ops.writeFile,access:ops.editAccess}}),
    createBashToolDefinition('/workspace',{operations:{exec:ops.bash},exposeSessionEnvironment:false})];
  if(mode==='selftest'){
    await defs[1].execute('write',{path:'/workspace/adapter-check',content:'before\n'});
    await defs[2].execute('edit',{path:'/workspace/adapter-check',edits:[{oldText:'before',newText:'after'}]});
    const r=await defs[0].execute('read',{path:'/workspace/adapter-check'});
    if(!JSON.stringify(r).includes('after'))throw Error('read/edit mismatch');
    let output=''; const b=await ops.bash('printf SANDBOX_OK; test -z "$QWEN_API_KEY"; test ! -e /var/run/docker.sock; test ! -e /home/miku',{},{onData:x=>output+=x.toString()});
    if(b.exitCode!==0||output!=='SANDBOX_OK')throw Error('isolation failed');
    let denied=false;try{await ops.readFile('/home/miku/projects/bench/repo/.env');}catch{denied=true;}
    if(!denied)throw Error('host file visible');
    console.log(JSON.stringify({type:'adapter_selftest',passed:true}));return;
  }
  const restoreFetch=installNetworkTrace(emit);
  const runtime=await ModelRuntime.create({authPath:path.join(configDir,'auth.json'),modelsPath:path.join(configDir,'models.json'),allowModelNetwork:false});
  const model=runtime.getModel('qwen-bench',process.env.QWEN_MODEL_ID);
  if(!model)throw Error('Model not loaded');
  const {session}=await createBenchSession({modelRuntime:runtime,model,configDir,tools:['read','write','edit','bash'],defs});
  let count=0, exceeded=false; const toolIds=new Set();
  session.subscribe(e=>{
    if(e.type==='message_update'){const a=e.assistantMessageEvent;emit({type:e.type,deltaType:a.type,delta:a.delta});}
    else emit(e);
    if(e.type==='tool_execution_start'&&!toolIds.has(e.toolCallId)){toolIds.add(e.toolCallId);if(++count>100){exceeded=true;void session.abort();}}
  });
  emit({type:'effective_configuration',model:model.id,systemPrompt:session.systemPrompt,toolNames:session.getActiveToolNames(),toolAdapter:'docker-operations',maxToolSeconds:30,retry:{maxRetries:2,baseDelayMs:2000,providerRetries:0,requestTimeoutMs:60000}});
  try{await session.prompt(fs.readFileSync(promptFile,'utf8'));if(exceeded)throw Error('tool_budget_exceeded');
    const last=session.state.messages.filter(m=>m.role==='assistant').at(-1);
    if(!last||['error','aborted'].includes(last.stopReason))throw Error('agent_failed');
    emit({type:'generation_complete',toolCalls:count});
  }finally{session.dispose();restoreFetch();}
}
if(process.argv[1]===fileURLToPath(import.meta.url))main().catch(e=>{console.error(JSON.stringify({type:'controller_error',message:e.message}));process.exitCode=1;});
