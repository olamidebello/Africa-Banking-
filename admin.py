"""Server-enforced Africa Bank administration. Financial mode remains sandbox."""
import json,secrets,time
DEFAULTS={'registration_open':True,'maintenance':False,'default_currency':'USD','disabled_currencies':[],'support_email':'','announcement':''}
ROLES=('customer','admin','superadmin')
def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS user_flags(user TEXT PRIMARY KEY REFERENCES users(id),disabled INTEGER NOT NULL DEFAULT 0);CREATE TABLE IF NOT EXISTS tenant_flags(tenant TEXT PRIMARY KEY REFERENCES tenants(id),disabled INTEGER NOT NULL DEFAULT 0);''')
def settings(c):
 result=dict(DEFAULTS)
 for row in c.execute('SELECT key,value FROM settings'):result[row['key']]=json.loads(row['value'])
 return result
def disabled(c,u):
 return bool(c.execute('SELECT 1 FROM user_flags WHERE user=? AND disabled=1',(u['id'],)).fetchone() or c.execute('SELECT 1 FROM tenant_flags WHERE tenant=? AND disabled=1',(u['tenant'],)).fetchone())
def data(c):
 return {'settings':settings(c),'users':[dict(r) for r in c.execute('SELECT u.id,u.tenant,u.email,u.name,u.role,COALESCE(f.disabled,0) disabled FROM users u LEFT JOIN user_flags f ON f.user=u.id ORDER BY u.email')],'tenants':[dict(r) for r in c.execute('SELECT t.*,COALESCE(f.disabled,0) disabled FROM tenants t LEFT JOIN tenant_flags f ON f.tenant=t.id ORDER BY t.name')],'audit':[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')],'requests':[dict(r) for r in c.execute('SELECT id,tenant,user,kind,status,created FROM requests ORDER BY created DESC LIMIT 500')],'counts':{table:c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('users','tenants','accounts','requests','entries')},'mode':'sandbox','livePayments':False}
def mutate(c,u,operation,d,currencies,hash_password):
 if u['role']!='superadmin':raise PermissionError('Super administrator required')
 c.execute('BEGIN IMMEDIATE')
 target=''
 if operation=='settings':
  updates={k:v for k,v in d.items() if k in DEFAULTS}
  for key in ('registration_open','maintenance'):
   if key in updates and type(updates[key]) is not bool:raise ValueError('Expected true or false')
  if 'default_currency' in updates and updates['default_currency'] not in currencies:raise ValueError('Unsupported default currency')
  if 'disabled_currencies' in updates and (not isinstance(updates['disabled_currencies'],list) or any(x not in currencies for x in updates['disabled_currencies'])):raise ValueError('Invalid currency selection')
  merged={**settings(c),**updates}
  if merged['default_currency'] in merged['disabled_currencies']:raise ValueError('Default currency must remain enabled')
  for key in ('support_email','announcement'):
   if key in updates and (not isinstance(updates[key],str) or len(updates[key])>1000):raise ValueError('Text exceeds allowed length')
  for key,value in updates.items():c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))
 elif operation=='user-create':
  if d.get('role') not in ROLES:raise ValueError('Invalid role')
  if not c.execute('SELECT 1 FROM tenants WHERE id=?',(d.get('tenant'),)).fetchone():raise ValueError('Tenant not found')
  if '@' not in d.get('email','') or len(d.get('password',''))<12 or not d.get('name','').strip():raise ValueError('Name, email and password of at least 12 characters required')
  target=secrets.token_hex(12);salt=secrets.token_hex(16)
  c.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',(target,d['tenant'],d['email'].lower().strip(),d['name'][:100],salt,hash_password(d['password'],salt),d['role']))
 elif operation in ('user-role','user-status','revoke-sessions'):
  target=d.get('id');user=c.execute('SELECT * FROM users WHERE id=?',(target,)).fetchone()
  if not user:raise ValueError('User not found')
  if operation!='revoke-sessions' and target==u['id']:raise ValueError('Self role changes and self suspension are disabled')
  if operation=='user-role':
   if d.get('role') not in ROLES:raise ValueError('Invalid role')
   c.execute('UPDATE users SET role=? WHERE id=?',(d['role'],target))
  if operation=='user-status':
   if type(d.get('disabled')) is not bool:raise ValueError('Expected true or false')
   c.execute('INSERT OR REPLACE INTO user_flags VALUES (?,?)',(target,int(d['disabled'])))
  c.execute('DELETE FROM sessions WHERE user=?',(target,))
 elif operation=='tenant-update':
  target=d.get('id')
  if not c.execute('SELECT 1 FROM tenants WHERE id=?',(target,)).fetchone():raise ValueError('Tenant not found')
  if 'name' in d:
   if not d['name'].strip():raise ValueError('Name required')
   c.execute('UPDATE tenants SET name=? WHERE id=?',(d['name'][:100],target))
  if 'disabled' in d:
   if target==u['tenant'] and d['disabled']:raise ValueError('Cannot suspend your own tenant')
   if type(d['disabled']) is not bool:raise ValueError('Expected true or false')
   c.execute('INSERT OR REPLACE INTO tenant_flags VALUES (?,?)',(target,int(d['disabled'])))
   c.execute('DELETE FROM sessions WHERE user IN (SELECT id FROM users WHERE tenant=?)',(target,))
 else:raise ValueError('Unknown admin operation')
 c.execute('INSERT INTO audit(tenant,actor,action,created) VALUES (?,?,?,?)',(u['tenant'],u['id'],'admin:'+operation+(':'+str(target) if target else ''),int(time.time())))
 return {'ok':True}
