# -*- coding: utf-8 -*-
"""Smoke test for DesktopIconStudio backend and icon extraction."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from desktop_icon_studio import DesktopController, _display_name_to_path, _get_file_icon

def main():
    ctl = DesktopController()
    area = ctl.work_area()
    print("work_area:", area)
    icons = ctl.list_icons()
    print("icons count:", len(icons))
    if icons:
        print("first 5 icons:")
        for ic in icons[:5]:
            print("  ", ic)
        ic = icons[0]
        path = _display_name_to_path(ic["name"])
        print("mapped path for first icon:", path)
        if path and os.path.exists(path):
            img = _get_file_icon(path, size=48)
            print("icon image size:", img.size if img else None)
        else:
            print("path not found; trying common desktop paths:")
            for p in [
                os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", ic["name"]),
                os.path.join(os.environ.get("PUBLIC", ""), "Desktop", ic["name"]),
            ]:
                print("  ", p, os.path.exists(p))

if __name__ == "__main__":
    main()
