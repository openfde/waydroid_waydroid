from tools import services
import dbus
import dbus.service
import multiprocessing
import dbus.exceptions
from gi.repository import GLib
import logging
import signal
from tools.helpers.inotify import InotifyRecursiveWatcher
import threading
from tools.interfaces import IPlatform
import argparse
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class DbusInfraManager(dbus.service.Object):
  def __init__(self, looper, bus, object_path, args):
      self.args = args
      self.looper = looper
      dbus.service.Object.__init__(self, bus, object_path)

  @dbus.service.method("com.openfde.InfraManager", in_signature='a{ss}', out_signature='', sender_keyword="sender", connection_keyword="conn")
  def Start(self, session, sender, conn):
      dbus_info = dbus.Interface(conn.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus/Bus", False), "org.freedesktop.DBus")
      uid = dbus_info.GetConnectionUnixUser(sender)
      if str(uid) not in ["0", session["user_id"]]:
        raise RuntimeError("Cannot start a session on behalf of another user")
      pid = dbus_info.GetConnectionUnixProcessID(sender)
      if str(uid) != "0" and str(pid) != session["pid"]:
        raise RuntimeError("Invalid session pid")
      do_start(self.args)

  @dbus.service.method("com.openfde.InfraManager", in_signature='', out_signature='')
  def Stop(self):
     stop(self.args)

  @dbus.service.method("com.openfde.InfraManager", in_signature='a{ss}', out_signature='')
  def Monitor(self, rootDirDict):
      # 监听 rootDirDict 的所有 value
      if not hasattr(self, "_watchers"):
        self._watchers = []
      if not hasattr(self, "_watcher_threads"):
        self._watcher_threads = []
      for key, rootDir in rootDirDict.items():
        if not key or not rootDir:
          continue
        try:
          logging.info(f"inotify watcher key={key} path={rootDir}")
          watcher = InotifyRecursiveWatcher(rootDir,key)
          t = threading.Thread(
            target=watcher.run,
            name=f"watcher-thread-{abs(hash(rootDir))}",
            daemon=False,
          )
          t.start()
          self._watchers.append(watcher)
          self._watcher_threads.append(t)
        except Exception:
          logging.exception("Failed to start watcher for %s", rootDir)

  @dbus.service.method("com.openfde.InfraManager", in_signature='', out_signature='')
  def StopMonitor(self):
      stopMonitor(self)

   # =========================
  # Method
  # =========================
  @dbus.service.method(
      "com.openfde.Infra",
      in_signature='',
      out_signature='s'
  )
  def GetNetworkState(self):

      return "connected"


  # =========================
  # Signal
  # =========================
  @dbus.service.signal(
      "com.openfde.Infra",
      signature='ss'
  )
  def NetworkStateChanged(self, state, iface):
      """
      网络状态变化 signal
      """
      pass    

    # =========================
    # emit signal
    # =========================
  # def emit_network_changed(self, state, iface):

  #     logging.info(
  #         f"emit NetworkStateChanged "
  #         f"{state} {iface}"
  #     )

  #     self.NetworkStateChanged(
  #         state,
  #         iface
  #     )    


def stopMonitor(self):
      logging.info("infra stop monitor")
      try:
        if hasattr(self, "_watchers"):
          for w in self._watchers:
            try:
              if hasattr(w, "stop"):
                w.stop()
              elif hasattr(w, "close"):
                w.close()
            except Exception:
              logging.exception("Failed to stop watcher")
          self._watchers.clear()
        if hasattr(self, "_watcher_threads"):
          for t in self._watcher_threads:
            try:
              if t.is_alive():
                t.join(timeout=1)
            except Exception:
              logging.exception("Failed to join watcher thread")
          self._watcher_threads.clear()
      except Exception:
        logging.exception("Failed to stop monitors")

 


def properties_changed(
        interface,
        changed_properties,
        invalidated_properties):

    args = argparse.Namespace(
              config = "/var/lib/waydroid/waydroid.cfg",
            )
    platformService = IPlatform.get_service(args)
    if("State") in changed_properties:
        state = int(changed_properties["State"])
        logging.info(f"State: {state}" )
        platformService.netMonitor("State",str(state))

    if("PrimaryConnectionType") in changed_properties:
        type = changed_properties["PrimaryConnectionType"]
        logging.info(f"type: {type}")
        platformService.netMonitor("type",str(type))


    if "Connectivity" in changed_properties:

        connectivity = int(
            changed_properties["Connectivity"]
        )
        logging.info(f"NM PropertiesChanged {connectivity}")
        platformService.netMonitor("connectivity",str(connectivity))
        if connectivity == 4:
            netStatus = "connected"
        else:
            netStatus = "disconnected"

        logging.info(f"NM PropertiesChanged netStatus {netStatus}")   
        # service.emit_network_changed(
        #     state,
        #     "wlan0"
        # )


bus = dbus.SystemBus()

def service(args, looper):
  dbus_obj = DbusInfraManager(looper, bus, '/InfraManager', args)
  looper.run()


bus.add_signal_receiver(
    properties_changed,
    signal_name="PropertiesChanged",
    dbus_interface="org.freedesktop.DBus.Properties",
    path="/org/freedesktop/NetworkManager"
)  

def stop(args, quit_session=True):
  try:
      services.hardware_manager.stop(args)
  except:
      pass
  try:
      services.task_manager.stop(args)
  except:
      pass

def start(args):
  try:
    name = dbus.service.BusName("com.openfde.Infra", bus, do_not_queue=True)
  except dbus.exceptions.NameExistsException:
    logging.error("Infra service is already running")
    return
  mainloop = GLib.MainLoop()
  def sigint_handler(data):
      stop(args)
      mainloop.quit()

  GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, sigint_handler, None)
  GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, sigint_handler, None)
  service(args, mainloop)

def do_start(args):
  services.task_manager.start(args)
  services.hardware_manager.start(args)
