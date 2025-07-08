import gbinder
import logging
from tools import helpers
from gi.repository import GLib
from gbinder import RemoteRequest, Writer, Reader
from typing import List
from json import dumps

INTERFACE = "android.openfde.ITaskManager"
SERVICE_NAME = "openfdetaskmanager"

TRANSACTION_listTasksPid = 1
TRANSACTION_getTaskInfoByPid = 2
TRANSACTION_killTaskByPid = 3


def add_service(args, listTasksPid, getTaskInfoByPid, killTaskByPid):
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
        logging.debug("release 4")
        logging.debug(f"code:{code}")

        if code == TRANSACTION_listTasksPid:
            tasksPid: List[int] = [1, 2, 3]
            # tasksPid:List[int] = listTasksPid()
            local_response.append_int32(0)  # return status normal
            local_response.append_string16(dumps(tasksPid))

        if code == TRANSACTION_getTaskInfoByPid:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            # taskInfo = getTaskInfoByPid(arg1)
            taskInfo = {
                "name": "task-name",
                "user": "task-user",
                "vmsize": -1,
                "cpuUsage": -1,
                "pid": -1,
                "rss": -1,
                "readBytes": -1,
                "writeBytes": -1,
                "readIssued": -1,
                "writeIssued": -1
            }
            local_response.append_string16(dumps(taskInfo))
        
        if code == TRANSACTION_killTaskByPid:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            # killTaskByPid(arg1)
            

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
