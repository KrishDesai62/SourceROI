"""Installed headless Chrome, real loopback app, authored accounts/data only.

No downloads, live models, external URLs or real reviewers. Browser observations
are recorded separately from API setup and fixture-worker execution.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from examples.knowledge_change.demo import workspace
from sourceroi.live.api import create_app
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live import assurance as a
from sourceroi.live.security import SecurityStore
from sourceroi.live.durable_jobs import Jobs
from tools.browser_support.cdp import CDP

CHROME=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
PASSWORD='Authored browser fixture password'


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    if not CHROME.is_file():raise RuntimeError('Installed Chrome executable unavailable; no download authorized')
    chrome=None;server=None;thread=None;client=None;results=[]
    with tempfile.TemporaryDirectory(prefix='sourceroi-browser-fixture-') as directory:
        temp=Path(directory);cfg=workspace(temp/'project');store=SecurityStore(cfg['_root'],initialize=True)
        for role in ('viewer','operator','reviewer','admin'):store.add_user(role,PASSWORD,role)
        op=store.login('operator',PASSWORD)['user'];reviewer=store.login('reviewer',PASSWORD)['user']
        sid='a'*32;snapshot=Path(cfg['_root'])/'.sourceroi/snapshots'/sid;freeze(cfg,snapshot)
        (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"returns_days":14}')
        cfg=read_config(cfg['_root']);spec=a.propose(read_config(snapshot),cfg);store.register_plan(spec,sid)
        review=a.review(spec,reviewer='reviewer',rationale='Authored browser fixture, no independent human',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
        approval=store.bind_approval(review,reviewer);jobs=Jobs(store)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.listen()
        app=create_app(cfg['_root'])
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='critical',proxy_headers=False))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:time.sleep(.02)
        if not server.started:raise RuntimeError('Fixture service did not start')
        url=f'http://127.0.0.1:{port}'
        profile=temp/'chrome';profile.mkdir()
        log=(args.output/'chrome-startup.txt').open('wb')
        chrome=subprocess.Popen([str(CHROME),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--disable-quic','--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication','--proxy-server=http://127.0.0.1:9','--proxy-bypass-list=127.0.0.1;localhost','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],stdout=log,stderr=log,start_new_session=True)
        try:
            active=profile/'DevToolsActivePort';deadline=time.monotonic()+15
            while not active.exists() and chrome.poll() is None and time.monotonic()<deadline:time.sleep(.05)
            if not active.exists():raise RuntimeError('Installed headless Chrome failed to expose loopback CDP; see startup log')
            cdpport=int(active.read_text().splitlines()[0]);version=httpx.get(f'http://127.0.0.1:{cdpport}/json/version',trust_env=False).json()
            page=httpx.put(f'http://127.0.0.1:{cdpport}/json/new?{url}',trust_env=False).json();client=CDP(page['webSocketDebuggerUrl'])
            def wait(expression,seconds=10):
                end=time.monotonic()+seconds
                while time.monotonic()<end:
                    try:
                        value=client.evaluate(expression)
                        if value:return value
                    except RuntimeError:pass
                    time.sleep(.05)
                raise AssertionError('Browser condition timed out: '+expression)
            wait("document.readyState==='complete' && !!document.getElementById('login-form')")
            def record(name,condition):
                if not condition:raise AssertionError(name)
                results.append({'check':name,'status':'VERIFIED_BROWSER'})
            def signin(role):
                client.evaluate("document.getElementById('login-user').value="+json.dumps(role)+";document.getElementById('login-password').value="+json.dumps(PASSWORD)+";document.getElementById('login-form').requestSubmit();true")
                wait("document.getElementById('auth-status').textContent.includes('Signed in as '+"+json.dumps(role)+")")
            def logout():
                client.evaluate("document.getElementById('logout').click();true")
                wait("document.readyState==='complete' && document.getElementById('login-form') && !document.getElementById('login-form').classList.contains('hidden')")
            record('unauthenticated login visible',client.evaluate("!document.getElementById('login-form').classList.contains('hidden')"))
            signin('viewer');wait("document.getElementById('workspace-name').textContent==='Knowledge demo'")
            record('viewer inventory loaded',client.evaluate("document.getElementById('sources').textContent.includes('Policy')"))
            forbidden=client.evaluate("(async()=>{const r=await fetch('/api/v2/data-ci/freeze',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:'{}'});return r.status})()")
            record('viewer mutation denied in real browser',forbidden==403)
            forbidden_decision=client.evaluate("(async()=>{const r=await fetch('/api/v2/knowledge/decisions',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:'{}'});return r.status})()")
            record('viewer cannot submit knowledge decision',forbidden_decision==403)
            logout();record('logout returns login',True)
            signin('operator')
            denied=client.evaluate("(async()=>{const r=await fetch('/api/v2/runs',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:JSON.stringify({acknowledge_model_calls:true})});return r.status})()")
            record('real generation still denied after login',denied==403)
            client.evaluate("document.getElementById('decision-snapshot').value="+json.dumps(sid)+";document.getElementById('decision-run').click();true")
            wait("document.getElementById('decision-output').textContent.includes('knowledge_decision')")
            record('actual knowledge decision form renders persisted evidence',client.evaluate("document.getElementById('decision-output').textContent.includes('retrieved_evidence') && document.getElementById('decision-status').textContent.includes('0 generations')"))
            record('knowledge review shows unknown model quality and no release approval',client.evaluate("document.getElementById('decision-summary').textContent.includes('UNKNOWN') && document.getElementById('decision-status').textContent.includes('release not authorized')"))
            # Reviewed plan is seeded through trusted fixture API setup above;
            # browser drives the actual submission controls, not a fake UI.
            client.evaluate('knowledgeSpec='+json.dumps(spec)+';knowledgeApproval='+json.dumps(approval)+';true')
            values={'baseline':{'returns':'30','warranty':'365'},'candidate':{'returns':'14','warranty':'365'}}
            client.evaluate("document.getElementById('fixture-answers').value="+json.dumps(json.dumps(values))+";document.getElementById('fixture-submit').click();true")
            jid=wait("document.getElementById('durable-job-id').value")
            wait("document.getElementById('durable-output').textContent.includes('QUEUED')")
            record('fixture queued and polling real backend',True)
            # Explicit test-harness foreground worker. The browser does not launch
            # hidden generation or a background worker.
            outcome=jobs.run_one('browser-fixture-worker');assert outcome['id']==jid
            wait("document.getElementById('durable-output').textContent.includes('COMPLETED')",15)
            record('completed fixture/evidence rendered',client.evaluate("document.getElementById('durable-output').textContent.includes('REVIEW')"))
            def queue_setup(key,mode='valid'):
                from sourceroi.live.fixture_execution import authorize
                fresh=a.review(spec,reviewer='reviewer',rationale='Authored browser fixture '+key,expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
                receipt=store.bind_approval(fresh,reviewer);permit=authorize(jobs,op,spec,max_attempts=8,max_seconds=60)
                return jobs.submit(op,key,spec,receipt,operation='fixture_release',fixture_authorization=permit['id'],fixture_responses=values,fixture_mode=mode)
            cancelled=queue_setup('browser-cancellation-fixture')
            client.evaluate("document.getElementById('durable-job-id').value="+json.dumps(cancelled['id'])+";document.getElementById('durable-cancel').click();true")
            wait("document.getElementById('durable-output').textContent.includes('CANCELLED')")
            record('actual browser cancellation acknowledged',True)
            uncertain=queue_setup('browser-unknown-usage-fixture','missing_usage');jobs.run_one('browser-unknown-worker')
            client.evaluate("document.getElementById('durable-job-id').value="+json.dumps(uncertain['id'])+";document.getElementById('durable-inspect').click();true")
            wait("document.getElementById('durable-output').textContent.includes('INCONCLUSIVE')")
            record('unknown fixture outcome rendered as INCONCLUSIVE',True)
            client.evaluate("document.getElementById('durable-job-id').value='unknown-job';document.getElementById('durable-inspect').click();true")
            wait("document.getElementById('error').textContent.includes('not found')")
            record('unknown job actionable error',True)
            logout();signin('reviewer')
            client.evaluate("document.getElementById('durable-job-id').value="+json.dumps(jid)+";document.getElementById('semantic-task').value='warranty';document.getElementById('semantic-load').click();true")
            wait("document.getElementById('semantic-packet').textContent.includes('binding')")
            record('assigned review loads frozen source quotations',client.evaluate("document.getElementById('semantic-packet').textContent.includes('365')"))
            # Record uncertainty, not invented positive independent review.
            client.evaluate("document.getElementById('semantic-decision').value='uncertain';document.getElementById('semantic-claims').value='[]';document.getElementById('semantic-rationale').value='Automated browser fixture uncertainty, not a human adjudication';document.getElementById('semantic-basis').value='Authored test assignment; independence not verified';document.getElementById('semantic-submit').click();true")
            wait("document.getElementById('semantic-status').textContent.includes('recorded by authenticated reviewer')")
            record('actual semantic form records uncertainty without independence',client.evaluate("document.getElementById('semantic-status').textContent.includes('REVIEW') && document.getElementById('semantic-status').textContent.includes('false')"))
            accessibility=client.evaluate("(()=>{const ids=['login-user','login-password','semantic-task','semantic-decision','semantic-rationale','semantic-basis'];return ids.every(id=>document.getElementById(id).closest('label')) && document.getElementById('semantic-status').getAttribute('role')==='status'})()")
            record('basic form labels and live status',accessibility)
            client.call('Input.dispatchKeyEvent',{'type':'keyDown','key':'Tab','code':'Tab','windowsVirtualKeyCode':9});client.call('Input.dispatchKeyEvent',{'type':'keyUp','key':'Tab','code':'Tab','windowsVirtualKeyCode':9})
            record('keyboard Tab reaches focusable DOM element',client.evaluate("document.activeElement.tagName!=='BODY'"))
            ax=client.call('Accessibility.getFullAXTree')['nodes']
            names={node.get('name',{}).get('value') for node in ax if node.get('role',{}).get('value') in ('textbox','combobox','button')}
            record('Chrome accessibility tree exposes named review controls','Evaluated task ID' in names and 'Record immutable judgment' in names)
            store.revoke_user('reviewer');client.evaluate("document.getElementById('refresh').click();true")
            wait("!document.getElementById('login-form').classList.contains('hidden')")
            record('revoked session returns sign-in requirement',True)
            signin('viewer');app.state.security.clock=lambda:time.time()+3601
            client.evaluate("document.getElementById('refresh').click();true")
            wait("!document.getElementById('login-form').classList.contains('hidden')")
            record('expired backend session requires sign-in in browser',True);app.state.security.clock=time.time
            report={'classification':'VERIFIED_INTERNAL_BROWSER_FIXTURE','browser':version.get('Browser'),'checks':results,'real_model_generations':0,'external_spend_usd':0,'limitations':['Seeded plan/receipt uses authored API setup','Foreground worker driven by test harness','Not a full accessibility audit or customer usability study','Basic keyboard/AX checks do not constitute full WCAG/accessibility certification']}
            (args.output/'browser-results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'browser':report['browser'],'checks':len(results),'status':'VERIFIED_BROWSER_FIXTURES'}))
        except BaseException as exc:
            (args.output/'browser-failure.json').write_text(json.dumps({'type':type(exc).__name__,'message':str(exc),'completed_checks':results},indent=2)+'\n');raise
        finally:
            if client:client.close()
            if chrome and chrome.poll() is None:
                import signal
                os.killpg(chrome.pid,signal.SIGTERM)
                try:chrome.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(chrome.pid,signal.SIGKILL);chrome.wait(timeout=3)
            log.close();server.should_exit=True;thread.join(timeout=5)
if __name__=='__main__':main()
