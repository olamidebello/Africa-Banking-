#!/usr/bin/env python3
"""Create an Africa Bank super administrator from a server terminal."""
import getpass
import os
import secrets
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

def main():
    config = {}
    with open('/etc/africa-bankh.env') as source:
        for line in source:
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value.strip("\"'")
    db = config.get('BANKH_DB', '/var/lib/bankh/bankh.sqlite3')
    if not os.path.isfile(db):
        raise SystemExit('Application database not found. Deploy the application first.')
    if not sys.stdin.isatty():
        raise SystemExit('Run directly in an interactive terminal: python3 scripts/create-admin.py')
    email = input('Super admin email: ').strip().lower()
    if '@' not in email:
        raise SystemExit('Valid email required.')
    pw = getpass.getpass('New password (12+ characters): ')
    if len(pw) < 12:
        raise SystemExit('Use at least 12 characters.')
    if pw != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match.')
    salt = secrets.token_hex(16)
    with sqlite3.connect('file:' + str(Path(db).resolve()) + '?mode=rw', uri=True) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        if connection.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
            raise SystemExit('Email already exists; no changes made.')
        if not connection.execute("SELECT 1 FROM tenants WHERE id='africa'").fetchone():
            raise SystemExit('Default tenant not found. Deploy the application first.')
        uid = secrets.token_hex(12)
        connection.execute('INSERT INTO users (id,tenant,email,name,salt,hash,role) VALUES (?,?,?,?,?,?,?)',
                           (uid, 'africa', email, 'Africa Bank Administrator', salt, app.password(pw, salt), 'superadmin'))
        connection.execute("INSERT INTO audit(tenant,actor,action,created) VALUES ('africa',?,'local administrator provisioning',?)", (uid, int(app.time.time())))
    print('Super admin created successfully. Sign in at https://banking.africandroid.world/')

if __name__ == '__main__':
    main()
