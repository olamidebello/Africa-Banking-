import admin
import os,json,sqlite3,secrets,hashlib,hmac,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
CURRENCIES=json.loads((Path(__file__).parent/'static'/'currencies.json').read_text())
DB=os.getenv('BANKH_DB','bankh.sqlite3')
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def password(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),240000).hex()
def init():
 with connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY,name TEXT);CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,tenant TEXT REFERENCES tenants(id),email TEXT UNIQUE,name TEXT,salt TEXT,hash TEXT,role TEXT);CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user TEXT REFERENCES users(id),expires INTEGER);CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,tenant TEXT,user TEXT REFERENCES users(id),name TEXT,currency TEXT,balance INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,tenant TEXT,user TEXT,kind TEXT,data TEXT,status TEXT,created INTEGER);CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,tenant TEXT,actor TEXT,action TEXT,created INTEGER);CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY,transfer TEXT,account TEXT REFERENCES accounts(id),amount INTEGER,created INTEGER);''')
  admin.init(c)
  c.execute('INSERT OR IGNORE INTO tenants VALUES (?,?)',('africa','Africa Bank'))
  if os.getenv('BANKH_ADMIN_EMAIL') and os.getenv('BANKH_ADMIN_PASSWORD'):
   s=secrets.token_hex(16);c.execute('INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(12),'africa',os.environ['BANKH_ADMIN_EMAIL'].lower(),'Platform Administrator',s,password(os.environ['BANKH_ADMIN_PASSWORD'],s),'superadmin'))
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,status,data,cookie=None):
  b=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(b)
 def user(self,c):
  ck=SimpleCookie();ck.load(self.headers.get('Cookie',''));token=ck.get('bankh');u=c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user=u.id WHERE s.token=? AND s.expires>?',(token.value if token else '',time.time())).fetchone()
  return u if u and not admin.disabled(c,u) else None
 def do_GET(self):
  if self.path.split('?')[0].rstrip('/')=='/api/health':return self.send(200,{'status':'ok','service':'africa-bankh','mode':'demo','livePayments':False})
  if self.path=='/api/public-config':
   with connect() as c:
    conf=admin.settings(c);return self.send(200,conf)
  if self.path.startswith('/api/'):
   with connect() as c:
    u=self.user(c)
    if not u:return self.send(401,{'error':'Sign in to continue'})
    if self.path=='/api/admin':
     if u['role']!='superadmin':return self.send(403,{'error':'Super administrator required'})
     return self.send(200,admin.data(c))
    if self.path=='/api/state':
     is_admin=u['role'] in ('superadmin','admin');scope=u['tenant'];return self.send(200,{'user':{k:u[k] for k in ('id','name','email','role','tenant')},'accounts':[dict(r) for r in c.execute('SELECT * FROM accounts WHERE tenant=? '+('' if is_admin else 'AND user=?'),(scope,) if is_admin else (scope,u['id']))], 'requests':[dict(r) for r in c.execute('SELECT * FROM requests WHERE tenant=? '+('' if is_admin else 'AND user=?')+' ORDER BY created DESC',(scope,) if is_admin else (scope,u['id']))], 'audit':[dict(r) for r in c.execute('SELECT * FROM audit WHERE tenant=? ORDER BY id DESC LIMIT 100',(scope,))] if is_admin else [],'tenants':[dict(r) for r in c.execute('SELECT * FROM tenants')] if u['role']=='superadmin' else []})
   return self.send(404,{'error':'Unknown endpoint'})
  path=self.path.split('?')[0];path='/index.html' if path=='/' else path
  f=(Path(__file__).parent/'static'/path.lstrip('/')).resolve();root=(Path(__file__).parent/'static').resolve()
  if root not in f.parents or not f.is_file():return self.send(404,{'error':'Not found'})
  mime={'.html':'text/html','.json':'application/json','.js':'text/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'}.get(f.suffix,'application/octet-stream');self.send_response(200);self.send_header('Content-Type',mime);self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(f.read_bytes())
 def do_POST(self):
  try:
   if int(self.headers.get('Content-Length',0))>100000:raise ValueError('Request too large')
   origin=self.headers.get('Origin')
   if origin and origin.split('://')[-1]!=self.headers.get('Host'):return self.send(403,{'error':'Origin rejected'})
   d=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}')
   with connect() as c:
    conf=admin.settings(c)
    if self.path=='/api/register':
     if not conf['registration_open'] or conf['maintenance']:return self.send(403,{'error':'Registration is currently closed'})
     if len(d.get('password',''))<12:raise ValueError('Use at least 12 characters')
     if '@' not in d.get('email',''):raise ValueError('Valid email required')
     s=secrets.token_hex(16);uid=secrets.token_hex(12);c.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',(uid,'africa',d['email'].lower().strip(),d['name'][:100],s,password(d['password'],s),'customer'));return self.send(201,{'message':'Registered. Sign in to continue.'})
    if self.path=='/api/login':
     u=c.execute('SELECT * FROM users WHERE email=?',(d.get('email','').lower().strip(),)).fetchone()
     if not u or admin.disabled(c,u) or not hmac.compare_digest(u['hash'],password(d.get('password',''),u['salt'])):return self.send(401,{'error':'Invalid credentials'})
     token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES (?,?,?)',(token,u['id'],int(time.time())+3600));return self.send(200,{'ok':True},'bankh='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600'+('; Secure' if os.getenv('BANKH_SECURE_COOKIE')=='1' else ''))
    u=self.user(c)
    if not u:return self.send(401,{'error':'Sign in required'})
    if self.path=='/api/logout':
     c.execute('DELETE FROM sessions WHERE user=?',(u['id'],));return self.send(200,{'ok':True},'bankh=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
    if self.path=='/api/password':
     if not hmac.compare_digest(u['hash'],password(d.get('current_password',''),u['salt'])):return self.send(403,{'error':'Current password is incorrect'})
     if len(d.get('new_password',''))<12:raise ValueError('Use at least 12 characters')
     salt=secrets.token_hex(16)
     c.execute('UPDATE users SET salt=?,hash=? WHERE id=?',(salt,password(d['new_password'],salt),u['id']))
     c.execute('DELETE FROM sessions WHERE user=?',(u['id'],))
     c.execute('INSERT INTO audit(tenant,actor,action,created) VALUES (?,?,?,?)',(u['tenant'],u['id'],'password changed',int(time.time())))
     return self.send(200,{'ok':True})
    if self.path.startswith('/api/admin/'):

     if u['role']!='superadmin':return self.send(403,{'error':'Super administrator required'})
     return self.send(200,admin.mutate(c,u,self.path.removeprefix('/api/admin/'),d,CURRENCIES,password))
    if conf['maintenance'] and u['role']!='superadmin':return self.send(503,{'error':'Maintenance in progress; please try later'})
    action=self.path.removeprefix('/api/')
    if action=='accounts':
     currency=d.get('currency',conf['default_currency'])
     if currency in conf['disabled_currencies']:raise ValueError('Currency unavailable for new accounts')
     if currency not in CURRENCIES:raise ValueError('Unsupported currency')
     c.execute('INSERT INTO accounts VALUES (?,?,?,?,?,0)',(secrets.token_hex(8),u['tenant'],u['id'],d.get('name','Everyday Account')[:80],currency))
    elif action=='requests':
     if d.get('kind') not in ['Transfer','Card request','Loan application','Support ticket','Dispute','Deposit review','Account recovery','Business application']:raise ValueError('Unsupported request')
     if d['kind']=='Transfer':
      amount=d.get('amount');a=c.execute('SELECT * FROM accounts WHERE id=? AND user=? AND tenant=?',(d.get('from'),u['id'],u['tenant'])).fetchone();b=c.execute('SELECT * FROM accounts WHERE id=? AND tenant=?',(d.get('to'),u['tenant'])).fetchone()
      if type(amount)!=int or amount<=0 or not a or not b or a['id']==b['id']:raise ValueError('Select distinct tenant accounts and a positive amount in currency minor units')
      if a['currency']!=b['currency']:raise ValueError('Transfers require matching currencies; exchange is not configured')
      d['currency']=a['currency']
     c.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(12),u['tenant'],u['id'],d['kind'],json.dumps(d),'pending',int(time.time())))
    elif action=='decision':
     if u['role'] not in ('admin','superadmin'):return self.send(403,{'error':'Administrator required'})
     c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM requests WHERE id=? AND tenant=? AND status=?',(d.get('id'),u['tenant'],'pending')).fetchone()
     if not r:raise ValueError('Pending request not found')
     if r['user']==u['id']:raise ValueError('Independent approver required')
     status=d.get('status')
     if status not in ('approved','rejected'):raise ValueError('Invalid decision')
     if status=='approved' and r['kind']=='Transfer':
      x=json.loads(r['data']);amt=x['amount']
      pair=c.execute('SELECT currency FROM accounts WHERE tenant=? AND id IN (?,?)',(u['tenant'],x['from'],x['to'])).fetchall()
      if len(pair)!=2 or pair[0]['currency']!=pair[1]['currency']:raise ValueError('Transfers require matching currencies')
      cur=c.execute('UPDATE accounts SET balance=balance-? WHERE id=? AND tenant=? AND balance>=?',(amt,x['from'],u['tenant'],amt))
      if cur.rowcount!=1:raise ValueError('Insufficient demo funds')
      if c.execute('UPDATE accounts SET balance=balance+? WHERE id=? AND tenant=?',(amt,x['to'],u['tenant'])).rowcount!=1:raise ValueError('Recipient unavailable')
      c.executemany('INSERT INTO entries(transfer,account,amount,created) VALUES (?,?,?,?)',[(r['id'],x['from'],-amt,int(time.time())),(r['id'],x['to'],amt,int(time.time()))])
     c.execute('UPDATE requests SET status=? WHERE id=?',(status,r['id']))
    elif action=='tenants':
     if u['role']!='superadmin':return self.send(403,{'error':'Super administrator required'})
     c.execute('INSERT INTO tenants VALUES (?,?)',(secrets.token_hex(8),d['name'][:100]))
    else:return self.send(404,{'error':'Unknown operation'})
    c.execute('INSERT INTO audit(tenant,actor,action,created) VALUES (?,?,?,?)',(u['tenant'],u['id'],action,int(time.time())));return self.send(200,{'ok':True})
  except (ValueError,KeyError,sqlite3.IntegrityError) as e:self.send(400,{'error':str(e)})
if __name__=='__main__':init();ThreadingHTTPServer(('127.0.0.1',int(os.getenv('PORT','18840'))),Handler).serve_forever()
