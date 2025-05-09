import gbinder
import logging
import time
from tools import helpers
from gi.repository import GLib
import signal


INTERFACE = "android.app.INotificationManager"
SERVICE_NAME = "notification"

TRANSACTION_desktopfile_updated = 157

class INotification:
    def __init__(self, remote):
        self.client = gbinder.Client(remote, INTERFACE)

    def application_notify(self, arg1):
        request = self.client.new_request()
        request.append_string16("com.boringdroid.systemui")
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_desktopfile_updated, request)

        if status:
            logging.error("Sending reply failed")
        return None


    def desktop_notify(self, arg1):
        request = self.client.new_request()
        request.append_string16("com.android.documentsui")
        request.append_string16(arg1)
        reply, status = self.client.transact_sync_reply(
            TRANSACTION_desktopfile_updated, request)

        if status:
            logging.error("Sending reply failed")
        return None


def get_service(args):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    if not serviceManager.is_present():
        logging.info("Waiting for binder Service Manager...")
        if not wait_for_manager(serviceManager):
            logging.error("Service Manager never appeared")
            return None

    tries = 1000

    remote, status = serviceManager.get_service_sync(SERVICE_NAME)
    while(not remote):
        if tries > 0:
            logging.warning(
                "Failed to get service {}, trying again...".format(SERVICE_NAME))
            time.sleep(1)
            remote, status = serviceManager.get_service_sync(SERVICE_NAME)
            tries = tries - 1
        else:
            return None

    return INotification(remote)

# Like ServiceManager.wait() but can be interrupted
def wait_for_manager(sm):
    mainloop = GLib.MainLoop()
    hndl = sm.add_presence_handler(lambda: mainloop.quit() if sm.is_present() else None)
    GLib.timeout_add_seconds(60, lambda: mainloop.quit())
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, lambda _: mainloop.quit(), None)
    mainloop.run()
    sm.remove_handler(hndl)
    if not sm.is_present():
        return False
    return True
