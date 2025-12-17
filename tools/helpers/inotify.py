# -*- coding: utf-8 -*-
import os
import sys
from typing import Dict, Set
import pyinotify
from tools.helpers import logging
from tools.interfaces import INotification
import json
import argparse
from contextlib import suppress
import threading
import re


class InotifyRecursiveWatcher:
  def __init__(self, root: str, replacedRootPrefix: str = None):
    self.root = os.path.abspath(root)
    self.replacedRootPrefix = replacedRootPrefix
    self.wm = pyinotify.WatchManager()
    self.mask = (
      pyinotify.IN_CREATE
      | pyinotify.IN_DELETE
      | pyinotify.IN_MOVED_FROM
      | pyinotify.IN_MOVED_TO
    )
    self.wd_to_path: Dict[int, str] = {}
    self.watched_dirs: Set[str] = set()
    # 添加线程安全锁
    self._lock = threading.RLock()
    self.notifier = pyinotify.Notifier(self.wm, self._EventHandler(self))

  class _EventHandler(pyinotify.ProcessEvent):
    def __init__(self, watcher: "InotifyRecursiveWatcher"):
      self.watcher = watcher
      try:
        args = argparse.Namespace(
          config = "/var/lib/waydroid/waydroid.cfg",
        )
        self.notificationService = INotification.get_service(args)
      except:
        logging.error("service not available")

    def process_default(self, event: pyinotify.Event):
      is_dir = bool(event.dir)
      path = event.pathname

      if event.mask & (pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO):
        if is_dir:
          self.watcher.add_watch_dir(path)
          self.watcher.add_watch_recursive(path)
        if self.watcher.replacedRootPrefix:
          try:
            rel = os.path.relpath(path, self.watcher.root)
            if not rel.startswith(os.pardir):
              path = os.path.join(self.watcher.replacedRootPrefix, rel)
          except Exception:
            pass
        payload = {"FileName": path, "OpCode": "ADD"}
        json_str = json.dumps(payload, ensure_ascii=False)
        self.notificationService.desktop_notify(json_str)

      if event.mask & (pyinotify.IN_DELETE | pyinotify.IN_MOVED_FROM):
        if is_dir:
          self.watcher.remove_watch_dir_recursive(path)
        if self.watcher.replacedRootPrefix:
          try:
            rel = os.path.relpath(path, self.watcher.root)
            if not rel.startswith(os.pardir):
              path = os.path.join(self.watcher.replacedRootPrefix, rel)
          except Exception:
            pass
        payload = {"FileName": path, "OpCode": "DEL"}
        json_str = json.dumps(payload, ensure_ascii=False)
        self.notificationService.desktop_notify(json_str)


  def add_watch_dir(self, d: str):
    """添加目录监听（线程安全）"""
    d = os.path.abspath(d)
    if d in self.watched_dirs:
      return
    if not os.path.isdir(d):
      return
    try:
      ret = self.wm.add_watch(d, self.mask, rec=False, auto_add=False)
    except Exception:
      return
    
    with self._lock:
      for wd in ret.keys():
        self.wd_to_path[wd] = d
      self.watched_dirs.add(d)

  def remove_watch_dir(self, d: str):
    """移除单个目录的监听（线程安全）"""
    d = os.path.abspath(d)
    with self._lock:
      # 找到该目录对应的所有 watch descriptor
      wds_to_remove = []
      for wd, path in list(self.wd_to_path.items()):
        if path == d:
          wds_to_remove.append(wd)
      
      # 从 WatchManager 移除
      for wd in wds_to_remove:
        try:
          self.wm.rm_watch(wd)
        except Exception:
          pass
        self.wd_to_path.pop(wd, None)
      
      # 从 watched_dirs 中移除
      self.watched_dirs.discard(d)

  def remove_watch_dir_recursive(self, root_dir: str):
    """递归移除目录及其所有子目录的监听（线程安全）"""
    root_dir = os.path.abspath(root_dir)
    
    with self._lock:
      # 收集所有需要移除的目录
      dirs_to_remove = []
      for watched_dir in list(self.watched_dirs):
        # 检查是否为 root_dir 或其子目录
        if watched_dir == root_dir or watched_dir.startswith(root_dir + os.sep):
          dirs_to_remove.append(watched_dir)
      
      # 移除所有相关的 watch descriptor
      wds_to_remove = []
      for wd, path in list(self.wd_to_path.items()):
        if path in dirs_to_remove:
            wds_to_remove.append(wd)
      
      # 批量从 WatchManager 移除
      for wd in wds_to_remove:
        try:
          self.wm.rm_watch(wd)
        except Exception:
          pass
        self.wd_to_path.pop(wd, None)
      
      # 批量从 watched_dirs 中移除
      for dir_to_remove in dirs_to_remove:
        self.watched_dirs.discard(dir_to_remove)

  def stop(self):
    """停止监听"""
    self._stopped = True

  def do_stop(self):
    """安全停止所有资源"""
    notifier = getattr(self, "notifier", None)
    wm = getattr(self, "wm", None)

    # 安全停止 notifier
    with suppress(Exception):
        if notifier is not None:
            notifier.stop()

    # 安全关闭 watch manager
    with suppress(Exception):
        if wm is not None:
            wm.close()

    # 释放引用，避免重复使用
    self.notifier = None
    self.wm = None

    # 清理内部映射与集合（线程安全）
    with self._lock:
      self.wd_to_path.clear()
      self.watched_dirs.clear()

  def add_watch_recursive(self, start_dir: str):
    """递归添加目录监听"""
    for dirpath, dirnames, _filenames in os.walk(start_dir):
      self.add_watch_dir(dirpath)

  def run(self):
    """运行监听器"""
    self.add_watch_recursive(self.root)
    try:
      while not getattr(self, "_stopped", False):
        self.notifier.process_events()
        if self.notifier.check_events(timeout=1000):
          self.notifier.read_events()
    finally:
      self.do_stop()

  # 添加线程安全的查询方法（可选）
  def get_watched_dirs(self):
    """获取当前监听的目录列表（线程安全）"""
    with self._lock:
      return list(self.watched_dirs)

  def get_wd_to_path(self):
    """获取wd到路径的映射（线程安全）"""
    with self._lock:
      return dict(self.wd_to_path)


def main():
  if len(sys.argv) != 3:
    print("Usage: python inotify.py <dir> <dirKey>")
    sys.exit(1)

  target = sys.argv[1]
  if not os.path.isdir(target):
    print(f"Not a directory: {target}")
    sys.exit(1)

  targetKey = sys.argv[2]

  watcher = InotifyRecursiveWatcher(target,targetKey)
  try:
    watcher.run()
  except KeyboardInterrupt:
    print("\n[inotify] stopped.")
    watcher.do_stop()


