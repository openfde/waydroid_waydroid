from tools import services
import dbus
import dbus.service
import dbus.exceptions
from gi.repository import GLib
import logging
import signal



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

def service(args, looper):
  dbus_obj = DbusInfraManager(looper, dbus.SystemBus(), '/InfraManager', args)
  looper.run()

def stop(args, quit_session=True):
  try:
      services.hardware_manager.stop(args)
      services.task_manager.stop(args)
  except:
      pass

def start(args):
  try:
    name = dbus.service.BusName("com.openfde.Infra", dbus.SystemBus(), do_not_queue=True)
  except dbus.exceptions.NameExistsException:
    logging.error("Infra service is already running")
    return
  mainloop = GLib.MainLoop()
  def sigint_handler(data):
      stop(args)
      mainloop.quit()

  GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, sigint_handler, None)
  GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, sigint_handler, None)
  services.task_manager.start(args)
  services.hardware_manager.start(args)
  service(args, mainloop)

def do_start(args):
  services.task_manager.start(args)
  services.hardware_manager.start(args)