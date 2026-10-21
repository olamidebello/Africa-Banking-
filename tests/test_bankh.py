import unittest,tempfile,sys,threading,json,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class BankHTest(unittest.TestCase):
 def test_isolation_and_ledger(self):
  with tempfile.TemporaryDirectory() as td:
   app.DB=td+'/test.db';app.init()
   with app.connect() as c:
    c.execute("INSERT INTO tenants VALUES ('other','Other')")
    for uid,tenant,role in [('alice','africa','customer'),('reviewer','africa','admin'),('outsider','other','customer'),('owner','africa','superadmin')]:
     c.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',(uid,tenant,uid+'@test.com',uid,'salt',app.password('longpassword123','salt'),role));c.execute('INSERT INTO sessions VALUES (?,?,?)',(uid,uid,9999999999))
    c.executemany('INSERT INTO accounts VALUES (?,?,?,?,?,?)',[('a','africa','alice','A','USD',1000),('b','africa','reviewer','B','USD',0),('c','other','outsider','C','USD',1000),('f','africa','alice','Afira','AFR',1000),('g','africa','reviewer','Afira receiver','AFR',0)])
   server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   def call(user,path,data=None):
    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/api/'+path,headers={'Cookie':'bankh='+user,'Content-Type':'application/json'},data=json.dumps(data).encode() if data is not None else None)
    try:
     with urllib.request.urlopen(req) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as r:return r.code,json.load(r)
   try:
    self.assertEqual(call('', 'health')[0],200)
    self.assertEqual(call('', 'health')[1]['service'],'africa-bankh')
    self.assertEqual(call('', 'state')[0],401)
    self.assertEqual([a['id'] for a in call('outsider','state')[1]['accounts']],['c'])
    self.assertEqual(call('alice','requests',{'kind':'Transfer','from':'a','to':'c','amount':50})[0],400)
    self.assertEqual(call('alice','requests',{'kind':'Transfer','from':'a','to':'b','amount':250})[0],200)
    self.assertEqual(call('alice','requests',{'kind':'Transfer','from':'f','to':'b','amount':50})[0],400)
    rid=call('alice','state')[1]['requests'][0]['id']
    self.assertEqual(call('alice','decision',{'id':rid,'status':'approved'})[0],403)
    self.assertEqual(call('reviewer','decision',{'id':rid,'status':'approved'})[0],200)
    self.assertEqual(call('reviewer','decision',{'id':rid,'status':'approved'})[0],400)
    with app.connect() as c:
     self.assertEqual(c.execute('SELECT SUM(amount) FROM entries').fetchone()[0],0)
     self.assertEqual(c.execute("SELECT balance FROM accounts WHERE id='a'").fetchone()[0],750)
    self.assertEqual(call('alice','requests',{'kind':'Transfer','from':'f','to':'g','amount':125})[0],200)
    rid=next(r['id'] for r in call('alice','state')[1]['requests'] if json.loads(r['data']).get('from')=='f')
    self.assertEqual(call('reviewer','decision',{'id':rid,'status':'approved'})[0],200)
    with app.connect() as c:
     self.assertEqual(c.execute("SELECT balance FROM accounts WHERE id='f'").fetchone()[0],875)
     self.assertEqual(c.execute("SELECT balance FROM accounts WHERE id='g'").fetchone()[0],125)
    self.assertEqual(call('alice','admin')[0],403)
    self.assertEqual(call('reviewer','admin/settings',{'maintenance':True})[0],403)
    self.assertEqual(call('owner','admin')[0],200)
    self.assertEqual(call('owner','admin/settings',{'registration_open':False,'default_currency':'AFR'})[0],200)
    self.assertEqual(call('', 'register',{'name':'Closed','email':'closed@test.com','password':'longpassword123'})[0],403)
    self.assertEqual(call('owner','admin/user-role',{'id':'owner','role':'customer'})[0],400)
    self.assertEqual(call('owner','admin/user-create',{'tenant':'other','name':'New tenant admin','email':'newadmin@test.com','role':'admin','password':'longpassword123'})[0],200)
    self.assertEqual(call('owner','admin/user-status',{'id':'outsider','disabled':True})[0],200)
    self.assertEqual(call('outsider','state')[0],401)
    self.assertEqual(call('owner','admin/settings',{'maintenance':True})[0],200)
    self.assertEqual(call('alice','accounts',{'name':'Blocked'})[0],503)
    self.assertEqual(call('owner','admin/settings',{'maintenance':False})[0],200)
    self.assertEqual(call('alice','accounts',{'name':'Afira default'})[0],200)
    with app.connect() as c:
     self.assertEqual(c.execute("SELECT currency FROM accounts WHERE name='Afira default'").fetchone()[0],'AFR')
   finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
