"""Score frozen artifacts separately from the process which produced them."""
import json


def error_kind(message):
    text=str(message).lower()
    for kind, needles in [
        ('tool_budget_exceeded',('tool_budget_exceeded',)),
        ('api_auth_error',('401','403','unauthorized','invalid api key')),
        ('api_quota_error',('insufficient_quota','quota exceeded','credit balance')),
        ('api_timeout',('timed out','timeout')),
        ('api_rate_limit',('429','rate limit','too many requests')),
        ('api_server_error',('500','502','503','504','overloaded','unavailable')),
        ('api_connection_error',('connection','fetch failed','econn','socket','network')),
        ('context_limit',('context length','context window','too many tokens')),
    ]:
        if any(n in text for n in needles):return kind
    return 'controller_error'


def read_events(path):
    try:
        with path.open() as stream:
            for line in stream:
                try:yield json.loads(line)
                except ValueError:continue
    except OSError:return


def summarize(result, events):
    anomalies=[]; retries=[]; tool_errors=0; last_error=None; last_stop=None; recovered=False; seen=False;transport_errors=[];shell_nonzero=0
    for event in events:
        seen=True; kind=event.get('type'); msg=event.get('message',{})
        if kind=='message_end' and msg.get('role')=='assistant':
            last_stop=msg.get('stopReason')
            if last_stop=='length':anomalies.append('output_truncated')
            if last_stop in ('error','aborted'):
                last_error=error_kind(msg.get('errorMessage','')) if last_stop=='error' else 'aborted'
                anomalies.append(last_error)
        elif kind=='controller_error':
            # The controller's generic wrapper must not overwrite the provider error.
            if msg := event.get('message'):
                if msg!='agent_failed' or not last_error:last_error=error_kind(msg)
        elif kind=='auto_retry_start':
            retries.append({k:event[k] for k in ('time','attempt','delayMs','errorMessage') if k in event})
            anomalies.append(error_kind(event.get('errorMessage','')))
        elif kind=='auto_retry_end':
            if event.get('success'):recovered=True
            else:
                anomalies.append('retry_cancelled' if 'cancel' in event.get('finalError','').lower() else 'retry_exhausted')
                last_error=error_kind(event.get('finalError',''))
        elif kind=='api_transport_error':
            detail={k:event[k] for k in ('time','request_id','elapsed_ms','error') if k in event}
            encoded=json.dumps(event.get('error',{}))
            detail['kind']='api_connect_timeout' if 'UND_ERR_CONNECT_TIMEOUT' in encoded else ('api_request_aborted' if event.get('error',{}).get('name')=='AbortError' else 'api_connection_error')
            transport_errors.append(detail)
            anomalies.append(detail['kind'])
        elif kind=='shell_command_end' and event.get('exit_code') != 0:
            shell_nonzero+=1;anomalies.append('shell_nonzero_exit')
        elif kind=='tool_execution_end' and event.get('isError'):
            tool_errors+=1; anomalies.append('tool_error')
    status=result.get('status')
    failure=result.get('generation_failure')
    if not failure and status not in ('pass','fail',None):
        failure=last_error if status=='generation_error' and last_error else status
    if failure: generation_status='failed'; anomalies.append(failure)
    elif not seen or not last_stop:generation_status='unknown'
    elif recovered:generation_status='recovered'
    elif anomalies:generation_status='completed_with_anomalies'
    else:generation_status='completed'
    cases=result.get('cases',[])
    return {'schema_version':2,
            'submission':{'status':('pass' if all(c['passed'] for c in cases) else 'fail') if cases else 'not_evaluated',
                          'passed':sum(bool(c['passed']) for c in cases),'total':len(cases)},
            'generation':{'status':generation_status,'failure':failure,'final_stop_reason':last_stop,
                          'anomalies':list(dict.fromkeys(anomalies)),'retry_count':len(retries),
                          'retries':retries,'tool_errors':tool_errors,'shell_nonzero_exits':shell_nonzero,'transport_errors':transport_errors}}
