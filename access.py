"""Owner sign-in and expiring sessions. Shared state stays in the dashboard database."""
import hashlib,hmac,secrets,sqlite3,time
from http.cookies import SimpleCookie
from pathlib import Path
DB=Path(__file__).resolve().parent/'decisions.sqlite3'
MAX_AGE=8*60*60

def connect():
 c=sqlite3.connect(DB,timeout=20)
 c.execute('CREATE TABLE IF NOT EXISTS owner_access(singleton INTEGER PRIMARY KEY CHECK(singleton=1), salt TEXT NOT NULL, digest TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS owner_sessions(digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS login_failures(address TEXT NOT NULL, created INTEGER NOT NULL)')
 return c

def configured():
 with connect() as c:return c.execute('SELECT 1 FROM owner_access').fetchone() is not None

def derive(password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()

def setup(password):
 if not isinstance(password,str) or not 12<=len(password)<=256:raise ValueError('Use a passphrase between 12 and 256 characters.')
 salt=secrets.token_hex(32);digest=derive(password,salt)
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM owner_access').fetchone():raise ValueError('Owner access is already configured. Sign in instead.')
  c.execute('INSERT INTO owner_access VALUES (1,?,?)',(salt,digest))
 return new_session()

def new_session():
 token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
 with connect() as c:
  c.execute('DELETE FROM owner_sessions WHERE expires<=?',(int(time.time()),))
  c.execute('INSERT INTO owner_sessions VALUES (?,?)',(digest,int(time.time())+MAX_AGE))
 return token

def login(password,address):
 now=int(time.time())
 with connect() as c:
  c.execute('DELETE FROM login_failures WHERE created<?',(now-900,))
  if c.execute('SELECT count(*) FROM login_failures WHERE address=?',(address,)).fetchone()[0]>=5:raise ValueError('Too many attempts. Try again in 15 minutes.')
  row=c.execute('SELECT salt,digest FROM owner_access').fetchone()
  good=isinstance(password,str) and len(password)<=256 and row and hmac.compare_digest(derive(password,row[0]),row[1])
  if not good:
   c.execute('INSERT INTO login_failures VALUES (?,?)',(address,now));c.commit();raise ValueError('Passphrase not accepted.')
  c.execute('DELETE FROM login_failures WHERE address=?',(address,))
 return new_session()

def token_from_cookie(value):
 try:
  cookie=SimpleCookie();cookie.load(value or '');return cookie['shelfmade_session'].value if 'shelfmade_session' in cookie else ''
 except Exception:return ''

def valid(value):
 token=token_from_cookie(value)
 if not token:return False
 with connect() as c:return c.execute('SELECT 1 FROM owner_sessions WHERE digest=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone() is not None

def logout(value):
 token=token_from_cookie(value)
 with connect() as c:c.execute('DELETE FROM owner_sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),))

def cookie(token='',secure=False):
 return f'shelfmade_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={MAX_AGE if token else 0}'+('; Secure' if secure else '')
