"""Run on the laptop with downloaded Desktop OAuth client JSON as argument."""
import sys,json,secrets,hashlib,base64,time,urllib.parse,subprocess
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import youtube_api as yt
SCOPES='https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly'
def main():
 path=Path(input('Drag your downloaded Google Desktop client JSON here, then press Enter: ').strip().strip("'\""))
 client=json.loads(path.read_text())
 if not isinstance(client.get('installed'),dict) or not client['installed'].get('client_id','').endswith('.apps.googleusercontent.com'):raise ValueError('Use a Desktop app OAuth client JSON from Google Cloud.')
 state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode();result={}
 class Callback(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   q=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
   if self.path.split('?')[0]!='/callback' or q.get('state',[''])[0]!=state:
    self.send_response(400);self.end_headers();self.wfile.write(b'Invalid sign-in request.');return
   result.update(code=q.get('code',[''])[0],error=q.get('error',[''])[0]);self.send_response(200);self.end_headers();self.wfile.write(b'Return to the ShelfMade setup window to confirm the channel.')
 server=HTTPServer(('127.0.0.1',0),Callback);server.timeout=1
 redirect='http://127.0.0.1:'+str(server.server_port)+'/callback'
 params={'client_id':client['installed']['client_id'],'redirect_uri':redirect,'response_type':'code','scope':SCOPES,'state':state,'code_challenge':challenge,'code_challenge_method':'S256','access_type':'offline','prompt':'consent select_account'}
 print('Select owner@example.com and the ShelfMade channel. Complete Google consent yourself.');subprocess.run(['open','https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(params)])
 end=time.time()+300
 while not result and time.time()<end:server.handle_request()
 server.server_close()
 if not result.get('code'):raise ValueError('Google authorization was cancelled or timed out.')
 payload=urllib.parse.urlencode({'client_id':client['installed']['client_id'],'client_secret':client['installed'].get('client_secret',''),'code':result['code'],'code_verifier':verifier,'redirect_uri':redirect,'grant_type':'authorization_code'}).encode()
 with yt.request('https://oauth2.googleapis.com/token',payload,{'Content-Type':'application/x-www-form-urlencoded'}) as r:tokens=json.load(r)
 channel=yt.verify_channel(tokens['access_token']);tokens['expires_at']=time.time()+tokens.get('expires_in',3600)
 yt.save_private(yt.AUTH/'client.json',client);yt.save_private(yt.AUTH/'tokens.json',tokens);yt.save_private(yt.AUTH/'channel.json',channel)
 print('Connected channel: '+channel['title']+'. Return to ShelfMade to upload a prepared video.')
if __name__=='__main__':
 try:main()
 except Exception as e:print('Setup stopped: '+str(e));sys.exit(1)
