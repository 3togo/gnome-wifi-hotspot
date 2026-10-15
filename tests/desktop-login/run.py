import hashlib,json,os,shlex,subprocess,tempfile,time,sys
from pathlib import Path
from datetime import datetime,timezone
fixtures=Path(__file__).resolve().parent
root=Path(os.environ.get('WIFI_RELAY_DESKTOP_OUTPUT') or fixtures.parents[1]/'dist/desktop-login').resolve()
root.mkdir(parents=True,exist_ok=True)
name='wifi-relay-login-'+str(os.getpid())
image=os.environ.get('WIFI_RELAY_DESKTOP_IMAGE','wifi-relay-desktop-test:rc1')
report={'started_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Disposable Docker container, LightDM PAM autologin, virtual display, actual GNOME/XFCE sessions','host_login_tested':False,'virtual_display_adaptations':['LightDM kernel-VT hints cleared before pam_systemd; real PAM and logind registration retained','GNOME headless Wayland compositor with software rendering; LightDM virtual X display'],'cases':[]}
def docker(*args,timeout=60):
 return subprocess.check_output(['docker',*args],text=True,stderr=subprocess.STDOUT,timeout=timeout)
def execute(*args,timeout=60):return docker('exec',name,*args,timeout=timeout)
def save():(root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
uid=None
try:
 docker('run','-d','--name',name,'--cgroupns','private','--cap-add','SYS_ADMIN','--cap-add','SYS_RESOURCE','--cap-add','AUDIT_WRITE','--security-opt','seccomp=unconfined','--security-opt','apparmor=unconfined','--shm-size','512m','--tmpfs','/run','--tmpfs','/run/lock','--tmpfs','/tmp','--memory','4g',image,'bash','-c','umount /sys/fs/cgroup && mount -t cgroup2 none /sys/fs/cgroup && exec /sbin/init')
 for attempt in range(30):
  try:
   if execute('systemctl','is-system-running').strip() in ('running','degraded'):break
  except subprocess.CalledProcessError as e:
   if e.output.strip()=='degraded':break
  time.sleep(1)
 report['image_id']=docker('image','inspect',image,'--format','{{.Id}}').strip()
 with tempfile.TemporaryDirectory(prefix='relay-login-package-') as directory:
  files=name+'-files'
  docker('create','--name',files,image,'/bin/true')
  try:
   candidate=Path(directory)/'candidate.deb';docker('cp',files+':/tmp/candidate.deb',str(candidate))
   report['package_sha256']=hashlib.sha256(candidate.read_bytes()).hexdigest()
  finally:docker('rm',files)
 uid=execute('id','-u','relaytest').strip()
 for file in ('setup.sh','probe.py'):docker('cp',str(fixtures/file),name+':/opt/'+file)
 execute('bash','/opt/setup.sh')
 previous=None
 for desktop,enabled in [('gnome',True),('gnome',False),('gnome',True),('xfce',True),('xfce',False),('xfce',True)]:
  if previous:
   env=['runuser','-u','relaytest','--','env','XDG_RUNTIME_DIR=/run/user/'+uid,'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/'+uid+'/bus']
   prepare="import sys;sys.path.insert(0,'/usr/share/wifi-hotspot/settings');from startup import set_auto_start;from gi.repository import Gio;set_auto_start("+str(enabled)+",Gio.Settings.new('org.gnome.shell') if "+str(previous=='gnome')+" else None,Gio.Settings.sync)"
   execute(*env,'python3','-c',prepare)
   execute('systemctl','stop','lightdm.service')
   try:execute('loginctl','terminate-user','relaytest')
   except subprocess.CalledProcessError:pass
   time.sleep(2)
   session='relay-gnome' if desktop=='gnome' else 'xfce'
   execute('sed','-i','-E','s/^(autologin-session|user-session)=.*/\\1='+session+'/', '/etc/lightdm/lightdm.conf.d/90-relay-test.conf')
   execute('systemctl','start','lightdm.service')
  cutoff=time.monotonic()+45;sessionid=None
  while time.monotonic()<cutoff:
   sessions=json.loads(execute('loginctl','list-sessions','--json=short'))
   eligible=[s for s in sessions if str(s.get('uid'))==uid and s.get('class')=='user']
   if eligible:
    sessionid=eligible[-1]['session'];break
   time.sleep(1)
  assert sessionid,'No LightDM login session'
  assert sessionid not in {c['session_id'] for c in report['cases']},'Session was reused'
  props=dict(line.split('=',1) for line in execute('loginctl','show-session',sessionid,'-p','Service','-p','Type','-p','Desktop','-p','State','-p','TimestampMonotonic').splitlines() if '=' in line)
  assert props['Service']=='lightdm-autologin',props
  env=['runuser','-u','relaytest','--','env','XDG_RUNTIME_DIR=/run/user/'+uid,'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/'+uid+'/bus']
  output=execute(*env,'python3','/opt/probe.py',desktop,str(int(enabled)),timeout=75)
  result=json.loads(next(line for line in output.splitlines() if line.startswith('{')))
  result['login']=props;result['session_id']=sessionid
  report['cases'].append(result);save()
  print(desktop,'startup',enabled,': pass; new LightDM session',sessionid,flush=True)
  previous=desktop
 report['status']='pass'
except Exception as e:
 report['status']='fail';report['error']=str(e)[-2500:];report['error_output']=str(getattr(e,'output',''))[-2500:];print('Desktop test failed:',report['error'],flush=True)
finally:
 try:
  (root/'journal.log').write_text(execute('journalctl','-b','--no-pager','-n','500'))
  docker('cp',name+':/var/log/lightdm',str(root/'lightdm-logs'))
 except Exception:pass
 try:
  docker('stop','-t','10',name);docker('rm',name);report['container_removed']=True
 except Exception:report['container_removed']=False
 report['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
 print('Report:',root/'report.json',flush=True)

sys.exit(0 if report.get('status')=='pass' and report.get('container_removed') else 1)
