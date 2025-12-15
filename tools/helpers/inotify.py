# -*- coding: utf-8 -*-
import os
import sys
from typing import Dict, Set
import pyinotify
import logging
from tools.interfaces import INotification
import json
import argparse
from contextlib import suppress


class InotifyRecursiveWatcher:
  def __init__(self, root: str, replacedRootPrefix: str = None):
    self.root = os.path.abspath(root)
    self.replacedRootPrefix = os.path.abspath(replacedRootPrefix)
    self.wm = pyinotify.WatchManager()
    self.mask = (
      pyinotify.IN_CREATE
      | pyinotify.IN_DELETE
      | pyinotify.IN_MOVED_FROM
      | pyinotify.IN_MOVED_TO
      | pyinotify.IN_DELETE_SELF
      | pyinotify.IN_MOVE_SELF
    )
    self.wd_to_path: Dict[int, str] = {}
    self.watched_dirs: Set[str] = set()
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
          #self.watcher.add_watch_recursive(path)
        else:
          if self.watcher.replacedRootPrefix:
            try:
              rel = os.path.relpath(path, self.watcher.root)
              if not rel.startswith(os.pardir):
                path = os.path.abspath(os.path.join(self.watcher.replacedRootPrefix, rel))
            except Exception:
              pass
          payload = {"FileName": path, "OpCode": "ADD"}
          json_str = json.dumps(payload, ensure_ascii=False)
          self.notificationService.desktop_notify(json_str)

      if event.mask & (pyinotify.IN_DELETE | pyinotify.IN_MOVED_FROM):
        if not is_dir:
          if self.watcher.replacedRootPrefix:
            try:
              rel = os.path.relpath(path, self.watcher.root)
              if not rel.startswith(os.pardir):
                path = os.path.abspath(os.path.join(self.watcher.replacedRootPrefix, rel))
            except Exception:
              pass
          payload = {"FileName": path, "OpCode": "DEL"}
          json_str = json.dumps(payload, ensure_ascii=False)
          self.notificationService.desktop_notify(json_str)

      if event.mask & (pyinotify.IN_DELETE_SELF | pyinotify.IN_MOVE_SELF):
        dirpath = event.path
        if dirpath:
          self.watcher.watched_dirs.discard(dirpath)
          for wd, p in list(self.watcher.wd_to_path.items()):
            if p == dirpath:
              self.watcher.wd_to_path.pop(wd, None)

  def add_watch_dir(self, d: str):
    d = os.path.abspath(d)
    if d in self.watched_dirs:
      return
    if not os.path.isdir(d):
      return
    try:
      ret = self.wm.add_watch(d, self.mask, rec=False, auto_add=False)
    except Exception:
      return
    for wd in ret.keys():
      self.wd_to_path[wd] = d
    self.watched_dirs.add(d)

  def stop(self):
    self._stopped = True
    
  def do_stop(self):
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

    # 清理内部映射与集合
    self.wd_to_path.clear()
    self.watched_dirs.clear()

  def add_watch_recursive(self, start_dir: str):
    for dirpath, dirnames, _filenames in os.walk(start_dir):
      self.add_watch_dir(dirpath)

  def run(self):
    self.add_watch_recursive(self.root)
    try:
      while not getattr(self, "_stopped", False):
        self.notifier.process_events()
        if self.notifier.check_events(timeout=1000):
          self.notifier.read_events()
    finally:
      self.do_stop()

def main():
  if len(sys.argv) != 2:
    print("Usage: python inotify.py <dir>")
    sys.exit(1)

  target = sys.argv[1]
  if not os.path.isdir(target):
    print(f"Not a directory: {target}")
    sys.exit(1)

  watcher = InotifyRecursiveWatcher(target)
  try:
    watcher.run()
  except KeyboardInterrupt:
    print("\n[inotify] stopped.")

