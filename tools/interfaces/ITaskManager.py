import gbinder
import logging
import os
import pwd
import base64
from tools import helpers
from gi.repository import GLib
from gbinder import RemoteRequest, Writer, Reader
from typing import List
from json import dumps


INTERFACE = "android.openfde.ITaskManager"
SERVICE_NAME = "openfdetaskmanager"

TRANSACTION_getTasks = 1
TRANSACTION_killTaskByPid = 2
TRANSACTION_getIconB64ByTaskName = 3
TRANSACTION_getTaskPids = 4
TRANSACTION_getTaskByPid = 5
TRANSACTION_getEachCPUPercent = 6
TRANSACTION_getMemoryAndSwap = 7
TRANSACTION_getNetworkDownloadAndUpload = 8


def add_service(args, getTasks, killTaskByPid,
                getIconB64ByTaskName, getTaskPids, getTaskByPid,
                getEachCPUPercent, getMemoryAndSwap,getNetworkDownloadAndUpload):
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

        if code == TRANSACTION_getTasks:
            local_response.append_int32(0)  # return status normal
            try:
                tasks: List[dict] = getTasks()
            except Exception as e:
                euid = os.geteuid()
                logging.debug(f"getTasks error:{e}")
                logging.debug(f"euid:{euid}")
            local_response.append_string16(dumps(tasks))

        if code == TRANSACTION_killTaskByPid:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            logging.debug(f"killTask pid:{arg1}")
            killTaskByPid(arg1)

        if code == TRANSACTION_getIconB64ByTaskName:
            local_response.append_int32(0)  # return status normal
            arg1 = reader.read_string16()
            b64 = getIconB64ByTaskName(arg1)
            local_response.append_string16(b64)

        if code == TRANSACTION_getTaskPids:
            local_response.append_int32(0)  # return status normal
            taskPids = getTaskPids()
            local_response.append_string16(dumps(taskPids))

        if code == TRANSACTION_getTaskByPid:
            local_response.append_int32(0)  # return status normal
            statsu, arg1 = reader.read_int32()
            task = getTaskByPid(arg1)
            local_response.append_string16(dumps(task))

        if code == TRANSACTION_getEachCPUPercent:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            each_cpu_persent = getEachCPUPercent(arg1 / 1000.0)
            local_response.append_string16(dumps(each_cpu_persent))

        if code == TRANSACTION_getMemoryAndSwap:
            local_response.append_int32(0)  # return status normal
            memory_and_swap = getMemoryAndSwap()
            local_response.append_string16(dumps(memory_and_swap))

        if code == TRANSACTION_getNetworkDownloadAndUpload:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            network_info = getNetworkDownloadAndUpload(arg1)
            local_response.append_string16(dumps(network_info))


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
