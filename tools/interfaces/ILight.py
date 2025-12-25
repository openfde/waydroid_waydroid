import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "android.openfde.ILight"
SERVICE_NAME = "openfdelight"

TRANSACTION_setBacklight = 1
TRANSACTION_getBacklight = 2


def add_service(args, lightInit, setBacklight, getBacklight):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    def response_handler(req, code, flags):
        logging.verbose(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        local_response = response.new_reply()
        if code == TRANSACTION_setBacklight:
            status, arg = reader.read_int32()
            ret = setBacklight(arg)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        elif code == TRANSACTION_getBacklight:
            ret = getBacklight()
            local_response.append_int32(0)
            local_response.append_int32(ret)
        else:
            logging.error("unknown code: {}".format(code))
            local_response.append_int32(0)
            local_response.append_int32(0)
        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.lightLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.lightLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        lightInit()
        args.lightLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
