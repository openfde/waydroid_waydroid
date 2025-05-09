# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import shutil
import time
import tools.config
import tools.helpers.props
import tools.helpers.ipc
from tools.interfaces import INotification
import dbus

def notify(args):
    try:
        notificationService = INotification.get_service(args)
        if notificationService:
            logging.info(args.PATH)
            if args.subaction == "desktop":
                notificationService.desktop_notify(args.PATH)
            elif args.subaction == "application":
                notificationService.application_notify(args.PATH)
        else:
            logging.error("Failed to access INotification service")
            cm.Freeze()
    except :
        logging.error("WayDroid session is stopped")

