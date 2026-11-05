"""User-run private Tailscale Serve setup; leaves existing mappings untouched."""
import json,subprocess,os,sys,urllib.request,urllib.parse,datetime
from pathlib import Path
BASE=Path(__file__).resolve().parent
CLI=Path('/Applications/Tailscale.app/Contents/MacOS/Tailscale')
ENV={**os.environ,'TERM':os.environ.get('TERM','xterm-256color'),'TERM_PROGRAM':'Apple_Terminal','SHLVL':'1'}
def run(args):
 r=subprocess.run([str(CLI),*args],env=ENV,capture_output=True,text=True,timeout=20)
 if r.returncode:raise RuntimeError('Tailscale could not complete this check. Open Tailscale and confirm it is connected, then try again.')
 return json.loads(r.stdout)
def origin_from_status(status):
 if status.get('BackendState')!='Running':raise RuntimeError('Sign in to Tailscale on this laptop first.')
 dns=status.get('Self',{}).get('DNSName','').rstrip('.')
 parsed=urllib.parse.urlparse('https://'+dns)
 if not dns.endswith('.ts.net') or parsed.hostname!=dns or parsed.port or parsed.path:raise RuntimeError('No valid private Tailscale hostname was found.')
 return 'https://'+dns

def main():
 if not CLI.is_file():raise RuntimeError('Install Tailscale before continuing.')
 try:
  with urllib.request.urlopen('http://127.0.0.1:8765/api/auth/status',timeout=5) as r:state=json.load(r)
 except Exception:raise RuntimeError('Open ShelfMade with Open-ShelfMade.command first, then run this setup again.')
 if not state.get('configured'):raise RuntimeError('Create your owner passphrase in the local dashboard first.')
 origin=origin_from_status(run(['status','--json']))
 configuration=run(['serve','status','--json']) or {}
 if configuration.get('TCP') or configuration.get('Web') or configuration.get('AllowFunnel'):
  raise RuntimeError('Tailscale already has serving rules. Nothing was changed; ask Codex to review those rules before adding ShelfMade.')
 print('Creating private HTTPS access to ShelfMade on this laptop.\nFollow any Tailscale HTTPS approval shown below. Public Funnel access is not enabled.',flush=True)
 subprocess.run([str(CLI),'serve','--bg','--https=443','http://127.0.0.1:8765'],env=ENV,check=True)
 config=run(['serve','status','--json']) or {}
 web=config.get('Web',{});endpoint=web.get(urllib.parse.urlparse(origin).hostname+':443',{});proxy=endpoint.get('Handlers',{}).get('/',{}).get('Proxy','')
 if proxy not in ('http://127.0.0.1:8765','http://localhost:8765'):raise RuntimeError('The dashboard forwarding rule could not be verified. Ask Codex to inspect Tailscale Serve status.')
 if any(config.get('AllowFunnel',{}).values()):raise RuntimeError('Public Funnel access is enabled in this network configuration. Ask Codex to review it before using this link.')
 tmp=BASE/'remote.json.tmp';tmp.write_text(json.dumps({'origin':origin},indent=2));tmp.replace(BASE/'remote.json')
 (BASE/'Private-dashboard-link.txt').write_text(origin+'\n\nOpen this link on your phone while connected to the same Tailscale network. Sign in with your ShelfMade passphrase. Keep the laptop awake and the dashboard running.\n')
 print('\nPrivate dashboard link: '+origin+'\n\nInstall and sign in to Tailscale on your phone using the same network, then open this link.')
 subprocess.run(['open',origin])
if __name__=='__main__':
 result={'attempted_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'started'}
 (BASE/'remote-setup-result.json').write_text(json.dumps(result,indent=2))
 try:
  main();result['status']='completed'
 except Exception as e:
  result.update(status='failed',message=str(e));print('\nSetup stopped: '+str(e))
 finally:(BASE/'remote-setup-result.json').write_text(json.dumps(result,indent=2))
 if result['status']!='completed':sys.exit(1)

