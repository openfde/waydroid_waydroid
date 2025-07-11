import logging
import os
import threading
import pwd
import base64
import psutil
from typing import List
from tools.interfaces import ITaskManager
from pathlib import Path

stopping = False

user_home_path: Path = None

for p in pwd.getpwall():
    if p.pw_uid != 0 and p.pw_uid >= 1000 and "home" in p.pw_dir:
        user_home_path = Path(p.pw_dir)


def getTasks():
    tasks: List[dict] = []
    for p in psutil.process_iter(['pid', 'name',
                                         'username', 'memory_percent', 'cpu_percent']):
        try:
            task = {}
            task["name"] = p.name()
            task["user"] = p.username()
            task["vmsize"] = p.memory_info().vms
            task["cpuUsage"] = p.cpu_percent()
            task["pid"] = p.pid
            task["rss"] = p.memory_info().rss
            io_counters = p.io_counters()
            task["readIssued"] = io_counters.read_count
            task["writeIssued"] = io_counters.write_count
            task["readBytes"] = io_counters.read_bytes
            task["writeBytes"] = io_counters.write_bytes
            tasks.append(task)
        except psutil.NoSuchProcess:
            continue

    return tasks


def killTaskByPid(pid: int):
    try:
        os.system(f"kill -9 {pid}")
    except ProcessLookupError:
        pass


def png_encode_base64(file_path: Path):
    with file_path.open("rb") as f:
        images_data = f.read()
        base64_encoded = base64.b64encode(images_data)
        base64_string = base64_encoded.decode()
    return base64_string


def getIconB64ByTaskName(name: str):
    try:
        icon_path = Path((user_home_path /
                          ".local/share/icons" / name).__str__() + ".png")
        logging.debug(f"getIconB64 icon path:{icon_path}")

        if icon_path.exists():
            b64 = png_encode_base64(icon_path)
            return b64
        else:
            return ""
    except Exception as e:
        logging.debug(f"getIconB64 error:{e}")


def getTaskPids():
    pids = []
    for process in psutil.process_iter(['pid']):
        try:
            pids.append(process.info['pid'])
        except psutil.NoSuchProcess:
            continue
    return pids


def getTaskByPid(pid: int):
    try:
        p = psutil.Process(pid)
        task = {}
        task["name"] = p.name()
        task["user"] = p.username()
        task["vmsize"] = p.memory_info().vms
        task["cpuUsage"] = p.cpu_percent()
        task["pid"] = p.pid
        task["rss"] = p.memory_info().rss
        io_counters = p.io_counters()
        task["readIssued"] = io_counters.read_count
        task["writeIssued"] = io_counters.write_count
        task["readBytes"] = io_counters.read_bytes
        task["writeBytes"] = io_counters.write_bytes
        return task
    except psutil.NoSuchProcess:
        return None


def start(args):
    def service_thread():
        while not stopping:
            ITaskManager.add_service(
                args, getTasks, killTaskByPid, getIconB64ByTaskName, getTaskPids, getTaskByPid)

    args.task_manager = threading.Thread(target=service_thread)
    args.task_manager.start()


def stop(args):
    global stopping
    stopping = True
    try:
        if args.taskManagerLoop:
            args.taskManagerLoop.quit()
    except AttributeError:
        logging.debug("TaskManager service is not even started")
