# Copyright 2023 Maximilian Wende
# SPDX-License-Identifier: GPL-3.0-or-later
from shutil import which
import tools.helpers.run
import logging
import re
import signal

from functools import partial

import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from tools.interfaces import IPlatform


NM_BUS_NAME = "org.freedesktop.NetworkManager"

NM_PATH = "/org/freedesktop/NetworkManager"

PROP_IFACE = "org.freedesktop.DBus.Properties"

stopping = False
WifiStatusDisable = 0
WifiStatusEnable = 1
WifiStatusNoDevice = 2

def adb_connect(args):
    """
    Creates an android debugging connection from the host system to the
    Waydroid device, if ADB is found on the host system and the device
    has booted.
    """
    # Check if adb exists on the system.
    if not which("adb"):
        return

    # Start and 'warm up' the adb server
    tools.helpers.run.user(args, ["adb", "start-server"])

    ip = get_device_ip_address()
    if not ip:
        return

    tools.helpers.run.user(args, ["adb", "connect", ip])
    logging.info("Established ADB connection to Waydroid device at {}.".format(ip))

def get_device_ip_address():
    # The IP address is queried from the DHCP lease file.
    lease_file = "/var/lib/misc/dnsmasq.waydroid0.leases"

    try:
        with open(lease_file) as f:
            return re.search(r"(\d{1,3}\.){3}\d{1,3}\s", f.read()).group().strip()
    except:
        pass

class FdeNetService:
  def __init__(self):
    #
    # DBus
    #
    self.bus = None

    #
    # MainLoop
    #
    self.mainloop = None

    #
    # DBus signal callback
    #
    self.signal_handler = None

    self.platformService = None

    #
    # 是否已启动
    #
    self.running = False   

    # =====================================================
    # DBus callback
    # =====================================================

  def properties_changed(self,
                           interface,
                           changed_properties,
                           invalidated_properties):

    # 50 -disconnected 、  40 -connecting 、60 70 -connected 
    if("State") in changed_properties:
        state = int(changed_properties["State"])
        logging.info(f"NetState---> {state}" )
        if self.platformService:
            self.platformService.settingsPutString(1, "NetState", str(state))

    #802-3-ethernet  、 802-11-wireless
    if("PrimaryConnectionType") in changed_properties:
        type = changed_properties["PrimaryConnectionType"]
        logging.info(f"NetType---> {type}")
        if self.platformService:
            self.platformService.settingsPutString(1,"NetType",str(type))

        
    # =====================================================
    # Start
    # =====================================================

  def start(self, args):
        try:
            logging.info("service start....111111111111111....")
            self.platformService = IPlatform.get_service(args)
            if not self.platformService:
                logging.info("platformService is null....")
                return 
           
        except:
            logging.info("platformService not available")
            return 
        if self.running:
            logging.warning(
                "service already running"
            )
            return

        logging.info("service start")

        #
        # GLib DBus MainLoop
        #
        dbus.mainloop.glib.DBusGMainLoop(
            set_as_default=True
        )

        #
        # SystemBus
        #
        self.bus = dbus.SystemBus()
        self.args = args
        # 保存 callback
        #
        self.signal_handler = partial(
            self.properties_changed
        )

        #
        # add signal receiver
        #
        self.bus.add_signal_receiver(
            self.signal_handler,

            signal_name="PropertiesChanged",

            dbus_interface=PROP_IFACE,

            bus_name=NM_BUS_NAME,

            path=NM_PATH
        )

        logging.info("add_signal_receiver success")

        #
        # MainLoop
        #
        self.mainloop = GLib.MainLoop()

        #
        # Unix signals
        #
        GLib.unix_signal_add(
            GLib.PRIORITY_HIGH,
            signal.SIGINT,
            self.on_sigint,
            None
        )

        GLib.unix_signal_add(
            GLib.PRIORITY_HIGH,
            signal.SIGTERM,
            self.on_sigterm,
            None
        )

        GLib.unix_signal_add(
            GLib.PRIORITY_HIGH,
            signal.SIGHUP,
            self.on_sigterm,
            None
        )

        self.running = True

        self.mainloop.run()

    # =====================================================
    # Stop
    # =====================================================

  def stop(self):
        logging.info("service stop........")
        IPlatform.remove_service()
        logging.info("service stop......3..")
        if not self.running:
            return

        #
        # remove signal receiver
        #
        if self.bus and self.signal_handler:

            try:

                self.bus.remove_signal_receiver(
                    self.signal_handler,

                    signal_name="PropertiesChanged",

                    dbus_interface=PROP_IFACE,

                    bus_name=NM_BUS_NAME,

                    path=NM_PATH
                )


            except Exception:

                logging.exception(
                    "remove_signal_receiver failed"
                )

            self.signal_handler = None

        #
        # quit mainloop
        #
        if self.mainloop:

            try:

                self.mainloop.quit()

            except Exception:

                logging.exception(
                    "mainloop quit failed"
                )

            self.mainloop = None

        #
        # release bus
        #
        self.bus = None

        self.running = False

    # =====================================================
    # SIGINT
    # =====================================================

  def on_sigint(self, data):
        logging.info("on_sigint..........")

        self.stop()

        return False

    # =====================================================
    # SIGTERM
    # =====================================================

  def on_sigterm(self, data):
        logging.info("on_sigterm..........")

        self.stop()

        return False
