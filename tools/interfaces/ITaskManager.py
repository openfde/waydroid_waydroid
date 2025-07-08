import gbinder
import logging
from tools import helpers
from gi.repository import GLib
from gbinder import RemoteRequest, Writer, Reader
from typing import List
from json import dumps

INTERFACE = "android.openfde.ITaskManager"
SERVICE_NAME = "openfdetaskmanager"

TRANSACTION_getTasks = 1


def add_service(args, getTasks, killTask):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager(
            "/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    def response_handler(req: RemoteRequest, code, flags):
        logging.debug(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader: Reader = req.init_reader()
        local_response: Writer = response.new_reply()
        logging.debug(f"code: {code}")

        if code == TRANSACTION_getTasks:
            tasks: List[dict] = [{
                "name": "name",
                "user": "user",
                "vmsize": 0,
                "cpuUsage": 0,
                "pid": 0,
                "rss": 0,
                "readBytes": 0,
                "writeBytes": 0,
                "readIssued": 0,
                "writeIssued": 0,
            }]  # dict list just for test
            local_response.append_int32(0)  # return status normal
            local_response.append_string16(dumps(tasks))

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.taskManagerLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.taskManagerLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.taskManagerLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
