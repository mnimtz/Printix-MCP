#!/usr/bin/env python3
"""Restart web server inside container with correct FERNET_KEY from /data/fernet.key."""
import os, signal, subprocess, time

# 1. Fernet Key aus Container lesen
fk = open('/data/fernet.key').read().strip()
print(f"Fernet key: {len(fk)} chars — OK")

# 2. Aktuellen Web-Server-Prozess finden und beenden
web_pid = None
for p in os.listdir('/proc'):
    if not p.isdigit(): continue
    try:
        cmd = open(f'/proc/{p}/cmdline', 'rb').read().decode('utf-8', 'ignore')
        if 'web/run.py' in cmd and '\x00-c\x00' not in cmd:
            web_pid = int(p)
            break
    except: pass

if web_pid:
    os.kill(web_pid, signal.SIGTERM)
    print(f"Killed web PID {web_pid}")
    time.sleep(2)
else:
    print("No existing web process found")

# 3. Neuen Web-Server mit korrekter Umgebung starten
env = os.environ.copy()
env['FERNET_KEY'] = fk
env['WEB_PORT'] = '8080'
env['WEB_HOST'] = '0.0.0.0'
proc = subprocess.Popen(
    ['python3', '/app/web/run.py'],
    env=env,
    stdout=open('/tmp/web.log', 'w'),
    stderr=subprocess.STDOUT
)
print(f"Web-Server gestartet mit PID {proc.pid}")
time.sleep(3)

# 4. Verify
alive = False
try:
    with open(f'/proc/{proc.pid}/cmdline', 'rb') as f:
        alive = 'web/run.py' in f.read().decode('utf-8', 'ignore')
except: pass
print(f"Prozess läuft: {'JA ✓' if alive else 'NEIN ✗'}")

# 5. Show first log lines
try:
    log = open('/tmp/web.log').read()[:500]
    print("Log:", log)
except: pass
