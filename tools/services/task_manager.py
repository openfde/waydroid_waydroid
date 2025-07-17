import logging
import os
import threading
import pwd
import base64
import psutil
import time
import subprocess
from typing import List
from tools.interfaces import ITaskManager
from pathlib import Path

stopping = False

user_home_path: Path = None
user_name: str = None

for p in pwd.getpwall():
    if p.pw_uid != 0 and p.pw_uid >= 1000 and "home" in p.pw_dir:
        user_home_path = Path(p.pw_dir)
        user_name = p.pw_name


def getTasks():
    tasks: List[dict] = []
    for p in psutil.process_iter(['pid', 'name',
                                         'username', 'memory_percent', 'cpu_percent', "nice"]):
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
            task["nice"] = p.nice()
            task["isAndroidApp"] = False
            cmdlines = p.cmdline()
            if len(cmdlines) == 0:
                task["isAndroidApp"] = False
            elif "." not in cmdlines[0] or "." not in task["name"]:
                task["isAndroidApp"] = False
            elif "/" in cmdlines[0]:
                task["isAndroidApp"] = False
            elif task["name"] in cmdlines[0]:
                task["isAndroidApp"] = True
                task["name"] = cmdlines[0]
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


def getTaskUpdateInfoByPid(pid: int):
    try:
        task = {}
        p = psutil.Process(pid)
        task["vmsize"] = p.memory_info().vms
        task["cpuUsage"] = p.cpu_percent()
        task["rss"] = p.memory_info().rss
        io_counters = p.io_counters()
        task["readIssued"] = io_counters.read_count
        task["writeIssued"] = io_counters.write_count
        task["readBytes"] = io_counters.read_bytes
        task["writeBytes"] = io_counters.write_bytes
        task["nice"] = p.nice()
    except psutil.NoSuchProcess:
        return None


def getEachCPUPercent(interval: float):
    return psutil.cpu_percent(interval=interval, percpu=True)


def getMemoryAndSwap():
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "memory": {
            "percent": memory.percent,
            "used": memory.used,
            "total": memory.total,
            "cache": memory.cached
        },
        "swap": {
            "percent": swap.percent,
            "used": swap.used,
            "total": swap.total
        }
    }


def getDiskReadAndWrite(interval: int):
    interval /= 1000.0
    io_start = psutil.disk_io_counters()
    time.sleep(interval)
    io_end = psutil.disk_io_counters()
    read_speed = (io_end.read_bytes - io_start.read_bytes) / interval
    write_speed = (io_end.write_bytes - io_start.write_bytes) / interval
    read_total = io_end.read_bytes
    write_total = io_end.write_bytes

    return {
        "read": {
            "speed": read_speed,
            "total": read_total
        },
        "write": {
            "speed": write_speed,
            "total": write_total
        }
    }


def getNetworkDownloadAndUpload(interval: int):
    interval /= 1000.0
    net_io_old = psutil.net_io_counters()
    time.sleep(interval)
    net_io_new = psutil.net_io_counters()
    bytes_sent = net_io_new.bytes_sent - net_io_old.bytes_sent
    bytes_recv = net_io_new.bytes_recv - net_io_old.bytes_recv
    upload_speed = bytes_sent / interval
    download_speed = bytes_recv / interval
    total_upload = net_io_new.bytes_sent
    total_download = net_io_new.bytes_recv

    return {
        "download": {
            "total": total_download,
            "speed": download_speed
        },
        "upload": {
            "total": total_upload,
            "speed": upload_speed
        }
    }


def getFileSystemUsage():
    result = subprocess.run(["df", "-Th"], capture_output=True, text=True)
    output = result.stdout
    outputs = output.split("\n")
    ret = []
    for i, line in enumerate(outputs):
        if i == 0 or i == len(outputs)-1:
            continue
        items = line.split()
        file_system, file_system_type, storage, used, available, percent, mount_point = items
        ret.append({
            "used": used,
            "catalogue": mount_point,
            "device": file_system,
            "type": file_system_type,
            "storage": storage,
            "available": available,
            "percent": int(percent.strip("%"))
        })
    return ret


def changeTaskPriority(pid: int, priority: int):
    os.system(f"renice {priority} -p {pid}")


def start(args):
    def service_thread():
        args.user_name = user_name
        while not stopping:
            ITaskManager.add_service(
                args, getTasks, killTaskByPid,
                getIconB64ByTaskName, getTaskPids,
                getTaskUpdateInfoByPid, getEachCPUPercent,
                getMemoryAndSwap, getNetworkDownloadAndUpload,
                getDiskReadAndWrite, getFileSystemUsage, changeTaskPriority)

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
