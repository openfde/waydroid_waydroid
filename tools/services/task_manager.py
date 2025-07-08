import logging
import os
import threading
import pwd
from typing import List
from tools.interfaces import ITaskManager

stopping = False


def getTasksPid() -> List[int]:
    return [int(p) for p in os.listdir("/proc") if p.isdigit()]


def getTaskByPid(pid):
    task = {}

    # 进程名称
    try:
        with open(f"/proc/{pid}/comm", "r") as f:
            task["name"] = f.read().strip()
    except FileNotFoundError:
        task["name"] = "unknown"

    # 用户
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("Uid:"):
                    uid = int(line.split()[1])
                    task["user"] = pwd.getpwuid(uid).pw_name
    except (FileNotFoundError, KeyError):
        task["user"] = "unknown"

    # 虚拟内存
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    task["vmsize"] = int(line.strip().split()[1])
    except FileNotFoundError:
        task["vmsize"] = -1

    # % CPU
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            stat_line = f.readline()
        stat_values = stat_line.strip().split()
        utime = float(stat_values[13])
        stime = float(stat_values[14])
        # starttime = float(stat_values[21])

        with open("/proc/stat", "r") as f:
            cpu_line = f.readline()
        cpu_values = cpu_line.strip().split()
        total_time = sum(float(x) for x in cpu_values[1:])

        clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        seconds = total_time / os.sysconf(clk_tck)
        task["cpuUsage"] = int((utime + stime) / seconds * 1000)  # /10得到 xx.x%
    except FileNotFoundError:
        task["cpuUsage"] = -1

    # 获取内存
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    task["rss"] = int(line.strip().split()[1])
    except FileNotFoundError:
        task["rss"] = -1

    # 读盘总量 / 写入总量
    try:
        with open(f"/proc/{pid}/io", "r") as f:
            for line in f:
                if line.startswith("read_bytes:"):
                    task["readBytes"] = int(line.strip().split()[1])
                elif line.startswith("write_bytes:"):
                    task["writeBytes"] = int(line.strip().split()[1])
    except FileNotFoundError:
        task["readBytes"] = -1
        task["writeBytes"] = -1

    # 磁盘读取 / 磁盘写入
    # NOTE: 暂时不支持

    # try:
    #     with open(f"/proc/{pid}/disk_io", "r") as f:
    #         print(f)
    #         for line in f:
    #             if line.startswith("read_issued:"):
    #                 info["readIssued"] = line.strip().split()[1]
    #             elif line.startswith("write_issued:"):
    #                 info["writeIssued"] = line.strip().split()[1]
    # except FileNotFoundError:
    #     info["readIssued"] = -1
    #     info["writeIssued"] = -1

    task["readIssued"] = -1
    task["writeIssued"] = -1

    task["pid"] = pid

    return task


def getTasks():
    tasks: List[dict] = []
    for pid in getTasksPid():
        task = getTaskByPid(pid)
        tasks.append(task)
    logging.debug("call getTasks")
    return tasks


def killTask(pid: int):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pass


def start(args):
    def service_thread():
        while not stopping:
            ITaskManager.add_service(
                args, getTasks, killTask)

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
