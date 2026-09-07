// No request bodies, credentials, query strings, or arbitrary response headers in traces.
export function installNetworkTrace(emit) {
  const original=globalThis.fetch; let sequence=0;
  const causes=(error,depth=0)=>{
    if(!error||depth>4)return undefined;
    return {name:error.name,code:error.code,message:error.message,
      cause:causes(error.cause,depth+1),errors:Array.isArray(error.errors)?error.errors.slice(0,4).map(e=>causes(e,depth+1)):undefined};
  };
  globalThis.fetch=async function(input,init){
    const id=++sequence,start=performance.now();
    const url=new URL(typeof input==='string'||input instanceof URL?input:input.url);
    emit({type:'api_request_start',request_id:id,endpoint:url.origin+url.pathname});
    try{
      const response=await original.call(globalThis,input,init);
      emit({type:'api_response_headers',request_id:id,status:response.status,elapsed_ms:Math.round(performance.now()-start),provider_request_id:response.headers.get('x-request-id')});
      return response;
    }catch(error){
      emit({type:'api_transport_error',request_id:id,elapsed_ms:Math.round(performance.now()-start),error:causes(error)});
      throw error;
    }
  };
  return ()=>{globalThis.fetch=original;};
}
