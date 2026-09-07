import {createAgentSession, createExtensionRuntime, SessionManager, SettingsManager} from '../.runtime/pi/node_modules/@earendil-works/pi-coding-agent/dist/index.js';

export function createBenchSession({modelRuntime,model,configDir,tools,defs,retryDelayMs=2000,timeoutMs=60000}) {
  const loader={getExtensions:()=>({extensions:[],errors:[],runtime:createExtensionRuntime()}),getSkills:()=>({skills:[],diagnostics:[]}),getPrompts:()=>({prompts:[],diagnostics:[]}),getThemes:()=>({themes:[],diagnostics:[]}),getAgentsFiles:()=>({agentsFiles:[]}),getSystemPrompt:()=>undefined,getSystemPromptSource:()=>undefined,getAppendSystemPrompt:()=>[],getAppendSystemPromptSources:()=>[],extendResources:()=>{},reload:async()=>{}};
  return createAgentSession({cwd:'/workspace',agentDir:configDir,model,thinkingLevel:'off',modelRuntime,resourceLoader:loader,
    tools,customTools:defs,sessionManager:SessionManager.inMemory('/workspace'),
    settingsManager:SettingsManager.inMemory({compaction:{enabled:false},retry:{enabled:true,maxRetries:2,baseDelayMs:retryDelayMs,provider:{maxRetries:0,timeoutMs}}})});
}
