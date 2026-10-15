import argparse,json,os,time,subprocess
from pathlib import Path
from gi.repository import Gio,GLib
p=argparse.ArgumentParser();p.add_argument('desktop');p.add_argument('enabled',type=int);a=p.parse_args()
expected=bool(a.enabled);bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
uuid='wifi-relay@3togo.github.io';tray='io.github.erhanzeyrek.WifiHotspot.Tray'
def call(name,path,interface,method,args=None):return bus.call_sync(name,path,interface,method,args,None,0,3000,None).unpack()[0]
def has_owner(name):return call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','NameHasOwner',GLib.Variant('(s)',(name,)))
def processes():
 result=[]
 for q in Path('/proc').iterdir():
  if not q.name.isdigit():continue
  try:
   if q.stat().st_uid!=os.getuid():continue
   if any(v.endswith(b'/wifi-hotspot/settings/tray.py') for v in (q/'cmdline').read_bytes().split(b'\0')):result.append(int(q.name))
  except OSError:pass
 return len(result)
r={'desktop':a.desktop,'expected_startup_enabled':expected,'uid_is_unprivileged':os.getuid()!=0}
end=time.monotonic()+60
while True:
 try:
  r['tray_bus_owner']=has_owner(tray);r['tray_process_count']=processes()
  if a.desktop=='gnome':
   info=call('org.gnome.Shell','/org/gnome/Shell','org.gnome.Shell.Extensions','GetExtensionInfo',GLib.Variant('(s)',(uuid,)))
   r['extension_state']=info.get('state');r['extension_error']=bool(info.get('error'));r['enabled_extensions']=Gio.Settings.new('org.gnome.shell').get_strv('enabled-extensions')
   r['first_login_marker_exists']=(Path.home()/'.local/state/wifi-hotspot/extension-initialized').exists()
   good=(r['extension_state']==1)==expected and not r['extension_error'] and r['tray_process_count']==0 and not r['tray_bus_owner']
   if expected:good &= r['first_login_marker_exists']
  else:
   good=r['tray_bus_owner']==expected and r['tray_process_count']==int(expected)
   if expected:
    r['indicator_status']=call(tray,'/org/ayatana/NotificationItem/wifi_hotspot','org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.kde.StatusNotifierItem','Status')))
    good &= r['indicator_status'] in ('Active','Passive')
    registered=call('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher','org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.kde.StatusNotifierWatcher','RegisteredStatusNotifierItems')))
    tray_owner=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',GLib.Variant('(s)',(tray,)))
    r['registered_with_panel']=any(v.startswith(tray_owner+'/') or v.startswith(tray+'/') for v in registered)
    good &= r['registered_with_panel']
  if good:break
 except GLib.Error as e:r['waiting_error_type']=type(e).__name__
 if time.monotonic()>=end:raise RuntimeError(json.dumps(r))
 time.sleep(1)
r.pop('waiting_error_type',None);r['status']='pass';print(json.dumps(r),flush=True)
