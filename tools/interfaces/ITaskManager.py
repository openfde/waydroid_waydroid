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
from pathlib import Path


INTERFACE = "android.openfde.ITaskManager"
SERVICE_NAME = "openfdetaskmanager"

TRANSACTION_listTasksPid = 1
TRANSACTION_getTaskInfoByPid = 2
TRANSACTION_killTaskByPid = 3
TRANSACTION_getIconB64ByTaskName = 4

user_home_path: Path = None

for p in pwd.getpwall():
    if p.pw_uid != 0 and p.pw_uid >= 1000 and "home" in p.pw_dir:
        user_home_path = Path(p.pw_dir)

logging.debug(f"user_home:{user_home_path}")


def png_encode_base64(file_path: Path):
    with file_path.open("rb") as f:
        images_data = f.read()
        base64_encoded = base64.b64encode(images_data)
        base64_string = base64_encoded.decode()
    return base64_string


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
        logging.debug("release 11")

        if code == TRANSACTION_listTasksPid:
            tasksPid: List[int] = listTasksPid()
            local_response.append_int32(0)  # return status normal
            local_response.append_string16(dumps(tasksPid))

        if code == TRANSACTION_getTaskInfoByPid:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            logging.debug(f"getTaskInfo pid:{arg1}")
            taskInfo = getTaskInfoByPid(arg1)
            local_response.append_string16(dumps(taskInfo))

        if code == TRANSACTION_killTaskByPid:
            local_response.append_int32(0)  # return status normal
            status, arg1 = reader.read_int32()
            logging.debug(f"killTask pid:{arg1}")
            killTaskByPid(arg1)

        if code == TRANSACTION_getIconB64ByTaskName:
            try:
                local_response.append_int32(0)  # return status normal
                arg1 = reader.read_string16()
                icon_path = Path((user_home_path /
                             ".local/share/icons" / arg1).__str__() + ".png")
                logging.debug(f"getIconB64 icon path:{icon_path}")

                if icon_path.exists():
                    b64 = png_encode_base64(icon_path)
                    local_response.append_string16(b64)
                else:
                    local_response.append_string16("")
            except Exception as e:
                logging.debug(f"getIconB64 error:{e}")

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
