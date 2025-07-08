import logging
import os
import threading
import pwd
from typing import List
from tools.interfaces import ITaskManager
from pathlib import Path

stopping = False


def listTasksPid() -> List[int]:
    return [int(p) for p in os.listdir("/proc") if p.isdigit()]


def getTaskInfoByPid(pid):
    proc_path = Path("/proc") / str(pid)
    status_path = proc_path / "status"
    cmdline_path = proc_path / "cmdline"

    if not proc_path.exists():
        return None

    task = {}
    cmdline = cmdline_path.read_text().strip().strip("\x00")
    if cmdline == "":
        # 内核线程，用户名为root,taskName去status里面找
        task["user"] = "root"
        with status_path.open("r") as f:
            for line in f:
                if line.startswith("Name:"):
                    task["name"] = line.split(":")[1].strip().strip("\x00")
                    break
            else:
                task["name"] = "unknown"  # 不可能
    else:  # 用户线程，用户名要靠Uid获取
        task["name"] = cmdline
        with status_path.open("r") as f:
            for line in f:
                if line.startswith("Uid:"):
                    uid_str = line.split(":")[1].strip().strip("\x00")
                    if uid_str.isdigit():
                        task["user"] = pwd.getpwuid(int(uid_str)).pw_name
                    else:
                        logging.debug(f"uid:{uid_str}")
                        task["user"] = uid_str.strip().strip("\x00").split()[0]

    task["cpuUsage"] = -1
    task["pid"] = pid
    task["rss"] = -1
    task["readBytes"] = -1
    task["writeBytes"] = -1
    task["readIssued"] = -1
    task["writeIssued"] = -1

    logging.debug(str(task))

    return task


def killTaskByPid(pid: int):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pass


def start(args):
    def service_thread():
        while not stopping:
            ITaskManager.add_service(
                args, listTasksPid, getTaskInfoByPid, killTaskByPid)

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
