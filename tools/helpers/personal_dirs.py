import os
import re
from typing import Dict

#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# Default directories (English XDG defaults)
_DEFAULTS = {
  "DESKTOP": os.path.expanduser("~/Desktop"),
  "DOWNLOAD": os.path.expanduser("~/Downloads"),
  "DOCUMENTS": os.path.expanduser("~/Documents"),
  "MUSIC": os.path.expanduser("~/Music"),
  "PICTURES": os.path.expanduser("~/Pictures"),
  "VIDEOS": os.path.expanduser("~/Videos"),
}

_USER_DIRS_PATH = os.path.expanduser("~/.config/user-dirs.dirs")

_LINE_RE = re.compile(
  r'^XDG_([A-Z]+)_DIR=(?P<quote>["\'])(?P<val>.*?)(?P=quote)\s*$'
)

def _expand_value(val: str, env: Dict[str, str]) -> str:
  # Expand $HOME and other env-like refs, and ~
  # Limit expansion to a safe subset ($HOME) typically used by user-dirs.dirs.
  # Fall back to os.path.expandvars for general cases.
  val = val.replace("$HOME", env.get("HOME", os.path.expanduser("~")))
  # Then expandvars for any remaining $VAR
  val = os.path.expandvars(val)
  # Finally expanduser for any leading ~
  val = os.path.expanduser(val)
  return val

def _parse_user_dirs(path: str) -> Dict[str, str]:
  result: Dict[str, str] = {}
  if not os.path.isfile(path):
    return result

  env = dict(os.environ)
  env.setdefault("HOME", os.path.expanduser("~"))

  try:
    with open(path, "r", encoding="utf-8") as f:
      for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
          continue
        m = _LINE_RE.match(line)
        if not m:
          continue
        key = m.group(1)  # e.g., DESKTOP, DOWNLOAD, MUSIC ...
        val = m.group("val")
        # Handle escaped quotes and trailing slashes
        val = val.replace(r"\"\"", r"\"").strip()
        expanded = _expand_value(val, env)
        result[key] = expanded
  except Exception:
    # Silently ignore parse errors and return what we have
    pass

  return result

def get_personal_dirs() -> Dict[str, str]:
  """
  Parse ~/.config/user-dirs.dirs and return a dict containing keys:
  MUSIC, PICTURES, DESKTOP, DOWNLOAD, DOCUMENTS, VIDEOS mapped to paths.
  If a key is missing, fall back to _DEFAULTS.
  """
  parsed = _parse_user_dirs(_USER_DIRS_PATH)

  out = dict(_DEFAULTS)  # start from defaults
  for key in ("MUSIC", "PICTURES", "DESKTOP", "DOWNLOAD", "DOCUMENTS", "VIDEOS"):
    if key in parsed:
      out[key] = parsed[key]
      if not os.path.isdir(out[key]):
        mkdir_if_not_exists(out[key])
  return out

def mkdir_if_not_exists(path: str):
  """
  Create the directory if it does not exist.
  """
  try:
    os.makedirs(path, exist_ok=True)
  except Exception:
    pass


if __name__ == "__main__":
  # Example usage: print the mapping
  dirs = get_personal_dirs()
  for k in ("MUSIC", "PICTURES", "DESKTOP", "DOWNLOAD", "DOCUMENTS", "VIDEOS"):
    print(f"{k}: {dirs[k]}")
