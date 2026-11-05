import sys,tempfile,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import access
with tempfile.TemporaryDirectory() as d:
 access.DB=Path(d)/'test.sqlite'
 assert not access.configured()
 try:access.setup('short');raise AssertionError()
 except ValueError:pass
 password='fixture-only-test-passphrase';token=access.setup(password);assert access.configured()
 assert access.valid('shelfmade_session='+token)
 assert not access.valid('shelfmade_session=forged')
 assert 'HttpOnly' in access.cookie(token) and 'SameSite=Strict' in access.cookie(token,True) and 'Secure' in access.cookie(token,True)
 raw=access.DB.read_bytes();assert password.encode() not in raw and token.encode() not in raw
 try:access.setup(password);raise AssertionError()
 except ValueError:pass
 for _ in range(5):
  try:access.login('incorrect','fixture');raise AssertionError()
  except ValueError:pass
 try:access.login(password,'fixture');raise AssertionError()
 except ValueError as e:assert '15 minutes' in str(e)
 next_token=access.login(password,'other');access.logout('shelfmade_session='+next_token);assert not access.valid('shelfmade_session='+next_token)
 with access.connect() as c:c.execute('UPDATE owner_sessions SET expires=0')
 assert not access.valid('shelfmade_session='+token)
 print('PASS: setup, password hashing, hashed session storage, session validation, expiry, logout, sign-in rate limit, secure cookie flags')
