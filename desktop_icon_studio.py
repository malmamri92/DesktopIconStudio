# -*- coding: utf-8 -*-
"""
استوديو أيقونات سطح المكتب — Desktop Icon Studio v2
=====================================================
برنامج احترافي للتحكم الكامل في أيقونات سطح المكتب على ويندوز 10/11:

  * عرض جميع الأيقونات مع أسمائها وإحداثياتها.
  * تحريك أي أيقونة (بالأسهم / بإدخال الإحداثيات / بالسحب على الخريطة المصغّرة).
  * تغيير حجم الأيقونات بأي قيمة من 16 إلى 256 بكسل.
  * التحكم في المسافات الأفقية والرأسية بين الأيقونات.
  * ترتيب تلقائي: شبكة / دائرة / صفوف وأعمدة على الحواف / توسيط /
                     موجة / حلزون / تجميع حسب نوع الملف.
  * حفظ تخطيطات متعددة واستعادتها (مع تصدير/استيراد JSON).
  * حفظ/استعادة تلقائية لكل دقة شاشة.
  * إخفاء/إظهار أيقونات سطح المكتب بنقرة واحدة.
  * أيقونة بجانب الساعة (System Tray) + اختصارات كيبورد عالمية.

يعمل ببايثون القياسي فقط — بدون أي مكتبات خارجية.
التشغيل:  python desktop_icon_studio.py
"""

import ctypes
import json
import math
import os
import queue
import sys
import threading
import time
import winreg
from ctypes import wintypes

# ==========================================================================
#  ثوابت Win32
# ==========================================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

LVM_FIRST            = 0x1000
LVM_GETITEMCOUNT     = LVM_FIRST + 4
LVM_SETITEMPOSITION  = LVM_FIRST + 15
LVM_GETITEMPOSITION  = LVM_FIRST + 16
LVM_REDRAWITEMS      = LVM_FIRST + 21
LVM_ARRANGE          = LVM_FIRST + 22
LVM_UPDATE           = LVM_FIRST + 42
LVM_GETITEMSPACING   = LVM_FIRST + 51
LVM_SETICONSPACING   = LVM_FIRST + 53
LVM_GETITEMTEXTW     = LVM_FIRST + 115

WM_MOUSEWHEEL = 0x020A
MK_CONTROL    = 0x0008
LVIF_TEXT     = 0x0001
LVA_SNAPTOGRID = 0x0005

PROCESS_VM_OPERATION      = 0x0008
PROCESS_VM_READ           = 0x0010
PROCESS_VM_WRITE          = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400

MEM_COMMIT     = 0x1000
MEM_RESERVE    = 0x2000
MEM_RELEASE    = 0x8000
PAGE_READWRITE = 0x04

SPI_GETWORKAREA = 0x0030

DEFAULT_SPACING = 75

# --- ثوابت الـ Tray / Hotkeys ---
WM_CLOSE          = 0x0010
WM_DESTROY        = 0x0002
WM_QUIT           = 0x0012
WM_HOTKEY         = 0x0312
WM_APP            = 0x8000
WM_TRAY           = WM_APP + 1

WS_POPUP          = 0x80000000
SW_HIDE           = 0

NIF_MESSAGE       = 0x01
NIF_ICON          = 0x02
NIF_TIP           = 0x04
NIM_ADD           = 0x00000000
NIM_MODIFY        = 0x00000001
NIM_DELETE        = 0x00000002

TPM_RETURNCMD     = 0x0100
TPM_NONOTIFY      = 0x0080
MF_STRING         = 0x00000000
MF_SEPARATOR      = 0x00000800

MOD_ALT           = 0x0001
MOD_CONTROL       = 0x0002
MOD_SHIFT         = 0x0004

IMAGE_ICON        = 1
LR_LOADFROMFILE   = 0x00000010
IDI_APPLICATION   = 32512


def MAKEINTRESOURCE(i):
    return ctypes.cast(ctypes.c_void_p(i), ctypes.c_wchar_p)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask",       wintypes.UINT),
        ("iItem",      ctypes.c_int),
        ("iSubItem",   ctypes.c_int),
        ("state",      wintypes.UINT),
        ("stateMask",  wintypes.UINT),
        ("pszText",    ctypes.c_void_p),
        ("cchTextMax", ctypes.c_int),
        ("iImage",     ctypes.c_int),
        ("lParam",     ctypes.c_void_p),
        ("iIndent",    ctypes.c_int),
        ("iGroupId",   ctypes.c_int),
        ("cColumns",   wintypes.UINT),
        ("puColumns",  ctypes.c_void_p),
        ("piColFmt",   ctypes.c_void_p),
        ("iGroup",     ctypes.c_int),
    ]


# ctypes.wintypes لا يعرّف LRESULT في بعض إصدارات بايثون
LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long


WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        wintypes.UINT),
        ("style",         wintypes.UINT),
        ("lpfnWndProc",   WNDPROC),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     wintypes.HINSTANCE),
        ("hIcon",         wintypes.HICON),
        ("hCursor",       wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName",  wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm",       wintypes.HICON),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize",               wintypes.DWORD),
        ("hWnd",                 wintypes.HWND),
        ("uID",                  wintypes.UINT),
        ("uFlags",               wintypes.UINT),
        ("uCallbackMessage",     wintypes.UINT),
        ("hIcon",                wintypes.HICON),
        ("szTip",                wintypes.WCHAR * 128),
        ("dwState",              wintypes.DWORD),
        ("dwStateMask",          wintypes.DWORD),
        ("szInfo",               wintypes.WCHAR * 256),
        ("uTimeout_or_uVersion", wintypes.UINT),
        ("szInfoTitle",          wintypes.WCHAR * 64),
        ("dwInfoFlags",          wintypes.DWORD),
        ("guidItem",             ctypes.c_byte * 16),
        ("hBalloonIcon",         wintypes.HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hWnd",    wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam",  wintypes.WPARAM),
        ("lParam",  wintypes.LPARAM),
        ("time",    wintypes.DWORD),
        ("pt",      POINT),
    ]


def makelong(lo, hi):
    return ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)


def last_error(msg):
    raise OSError(f"{msg} (رمز الخطأ: {ctypes.GetLastError()})")


# ==========================================================================
#  وحدة التحكم بسطح المكتب
# ==========================================================================
class DesktopController:
    """واجهة منخفضة المستوى للتحكم بقائمة أيقونات سطح المكتب (SysListView32)."""

    def __init__(self):
        self.hwnd = self._find_listview()
        if not self.hwnd:
            raise RuntimeError(
                "تعذّر العثور على نافذة أيقونات سطح المكتب.\n"
                "تأكد أن ويندوز Explorer يعمل وأن الأيقونات ظاهرة."
            )
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        self.pid = pid.value

    @staticmethod
    def _find_listview():
        progman = user32.FindWindowW("Progman", None)
        defview = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
        if not defview:
            workerw = None
            while True:
                workerw = user32.FindWindowExW(None, workerw, "WorkerW", None)
                if not workerw:
                    break
                defview = user32.FindWindowExW(workerw, None, "SHELLDLL_DefView", None)
                if defview:
                    break
        if not defview:
            return None
        return user32.FindWindowExW(defview, None, "SysListView32", "FolderView")

    def _open_process(self):
        h = kernel32.OpenProcess(
            PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE
            | PROCESS_QUERY_INFORMATION, False, self.pid)
        if not h:
            last_error("تعذّر فتح عملية Explorer")
        return h

    @staticmethod
    def _close_process(h):
        kernel32.CloseHandle(h)

    def _alloc(self, hproc, size):
        addr = kernel32.VirtualAllocEx(hproc, None, size,
                                       MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not addr:
            last_error("تعذّر حجز ذاكرة داخل Explorer")
        return addr

    def _free(self, hproc, addr):
        kernel32.VirtualFreeEx(hproc, addr, 0, MEM_RELEASE)

    @staticmethod
    def _write_mem(hproc, addr, data):
        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(hproc, addr, data, len(data),
                                           ctypes.byref(written)):
            last_error("فشلت الكتابة في ذاكرة Explorer")

    @staticmethod
    def _read_mem(hproc, addr, size):
        buf = (ctypes.c_char * size)()
        read = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(hproc, addr, buf, size,
                                          ctypes.byref(read)):
            last_error("فشلت القراءة من ذاكرة Explorer")
        return bytes(buf.raw)

    def count(self):
        return user32.SendMessageW(self.hwnd, LVM_GETITEMCOUNT, 0, 0)

    @staticmethod
    def work_area():
        rc = RECT()
        if not user32.SystemParametersInfoW(SPI_GETWORKAREA, 0,
                                            ctypes.byref(rc), 0):
            last_error("تعذّرت قراءة مساحة العمل")
        return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top

    def get_item_text(self, hproc, index):
        size_lv = ctypes.sizeof(LVITEMW)
        text_bytes = 520 * 2
        addr = self._alloc(hproc, size_lv + text_bytes)
        try:
            item = LVITEMW()
            item.mask = LVIF_TEXT
            item.iItem = index
            item.iSubItem = 0
            item.pszText = addr + size_lv
            item.cchTextMax = 520
            self._write_mem(hproc, addr,
                            ctypes.string_at(ctypes.byref(item), size_lv))
            user32.SendMessageW(self.hwnd, LVM_GETITEMTEXTW, index, addr)
            raw = self._read_mem(hproc, addr + size_lv, text_bytes)
            return raw.decode("utf-16-le", "ignore").split("\x00")[0]
        finally:
            self._free(hproc, addr)

    def get_item_position(self, hproc, index):
        addr = self._alloc(hproc, ctypes.sizeof(POINT))
        try:
            user32.SendMessageW(self.hwnd, LVM_GETITEMPOSITION, index, addr)
            raw = self._read_mem(hproc, addr, ctypes.sizeof(POINT))
            pt = POINT.from_buffer_copy(raw)
            return pt.x, pt.y
        finally:
            self._free(hproc, addr)

    def list_icons(self):
        n = self.count()
        icons = []
        hproc = self._open_process()
        try:
            for i in range(n):
                name = self.get_item_text(hproc, i)
                x, y = self.get_item_position(hproc, i)
                icons.append({"i": i, "name": name, "x": x, "y": y})
        finally:
            self._close_process(hproc)
        return icons

    def get_position(self, index):
        hproc = self._open_process()
        try:
            return self.get_item_position(hproc, index)
        finally:
            self._close_process(hproc)

    def set_position(self, index, x, y):
        x, y = max(0, int(x)), max(0, int(y))
        user32.SendMessageW(self.hwnd, LVM_SETITEMPOSITION, index,
                            makelong(x, y))

    def refresh_view(self):
        n = self.count()
        if n:
            user32.SendMessageW(self.hwnd, LVM_REDRAWITEMS, 0, n - 1)
        user32.SendMessageW(self.hwnd, LVM_UPDATE, 0, 0)

    def snap_to_grid(self):
        user32.SendMessageW(self.hwnd, LVM_ARRANGE, LVA_SNAPTOGRID, 0)

    def set_spacing(self, cx, cy):
        user32.SendMessageW(self.hwnd, LVM_SETICONSPACING, 0,
                            makelong(int(cx), int(cy)))
        self.refresh_view()

    def get_spacing(self):
        res = user32.SendMessageW(self.hwnd, LVM_GETITEMSPACING, 0, 0)
        return res & 0xFFFF, (res >> 16) & 0xFFFF

    @staticmethod
    def get_icon_size():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Bags\1\Desktop")
            size, _ = winreg.QueryValueEx(key, "IconSize")
            winreg.CloseKey(key)
            return int(size)
        except OSError:
            return None

    def _wheel_notch(self, delta):
        wx, wy, ww, wh = self.work_area()
        cx, cy = wx + ww // 2, wy + wh // 2
        old = POINT()
        user32.GetCursorPos(ctypes.byref(old))
        user32.SetCursorPos(cx, cy)
        time.sleep(0.03)
        wparam = ((delta & 0xFFFF) << 16) | MK_CONTROL
        lparam = makelong(cx, cy)
        user32.SendMessageW(self.hwnd, WM_MOUSEWHEEL, wparam, lparam)
        user32.SetCursorPos(old.x, old.y)

    def nudge_icon_size(self, bigger=True):
        self._wheel_notch(120 if bigger else -120)
        self.refresh_view()

    def set_icon_size(self, target, on_progress=None):
        target = max(16, min(256, int(target)))
        cur = self.get_icon_size()
        if cur is None:
            raise RuntimeError(
                "تعذّرت قراءة الحجم الحالي من سجل ويندوز.\n"
                "استخدم زرَّي (＋ / −) للتكبير والتصغير يدويًا."
            )
        for _ in range(80):
            cur = self.get_icon_size()
            if cur is None or cur == target:
                break
            self._wheel_notch(120 if cur < target else -120)
            time.sleep(0.12)
            if on_progress:
                on_progress(self.get_icon_size() or cur)
        self.refresh_view()
        return self.get_icon_size()

    def set_visible(self, visible):
        user32.ShowWindow(self.hwnd, 5 if visible else 0)


# ==========================================================================
#  إدارة التخطيطات المحفوظة (JSON)
# ==========================================================================
class LayoutStore:
    def __init__(self, path):
        self.path = path
        self.data = {}
        self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def put(self, name, icons, area, spacing):
        self.data[name] = {
            "work_area": list(area),
            "spacing": list(spacing),
            "icons": {ic["name"]: [ic["x"], ic["y"]] for ic in icons},
        }
        self.save()

    def delete(self, name):
        self.data.pop(name, None)
        self.save()


# ==========================================================================
#  أيقونة بجانب الساعة + اختصارات عالمية
# ==========================================================================
class TrayManager(threading.Thread):
    """يعمل في thread خاص. يرسل أوامر نصية عبر Queue إلى الواجهة الرئيسية."""

    def __init__(self, command_queue, icon_path=None):
        super().__init__(daemon=True, name="TrayManager")
        self.q = command_queue
        self.icon_path = icon_path
        self.hwnd = None
        self.hmenu = None
        self.class_atom = None
        self.hinst = kernel32.GetModuleHandleW(None)
        self._stop_event = threading.Event()

        self._cmd_map = {
            1000: "SHOW_WINDOW",
            1001: "TOGGLE_WINDOW",
            1002: "SAVE_RES",
            1003: "RESTORE_RES",
            1004: "ARRANGE_WAVE",
            1005: "ARRANGE_SPIRAL",
            1006: "ARRANGE_TYPE",
            1090: "EXIT",
        }
        # hotkey id -> command
        self._hotkey_map = {
            1: "SHOW_WINDOW",      # Ctrl+Alt+S
            2: "TOGGLE_WINDOW",    # Ctrl+Alt+H
            3: "RESTORE_RES",      # Ctrl+Alt+R
            4: "ARRANGE_WAVE",     # Ctrl+Alt+W
            5: "ARRANGE_SPIRAL",   # Ctrl+Alt+P
        }
        self._wnd_proc_cb = WNDPROC(self._wnd_proc)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            if lparam in (0x0201, 0x0202, 0x0203):  # LBUTTONUP / LBUTTONDBLCLK
                self.q.put("SHOW_WINDOW")
            elif lparam == 0x0205:                   # RBUTTONUP
                self._show_menu()
        elif msg == WM_HOTKEY:
            cmd = self._hotkey_map.get(wparam)
            if cmd:
                self.q.put(cmd)
        elif msg == WM_CLOSE:
            self._cleanup()
            user32.DestroyWindow(hwnd)
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self):
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(
            self.hmenu,
            TPM_RETURNCMD | TPM_NONOTIFY,
            pt.x, pt.y, 0,
            self.hwnd, None)
        if cmd:
            mapped = self._cmd_map.get(cmd)
            if mapped:
                self.q.put(mapped)

    def _load_icon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            hicon = user32.LoadImageW(
                0, self.icon_path, IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE)
            if hicon:
                return hicon
        return user32.LoadIconW(0, MAKEINTRESOURCE(IDI_APPLICATION))

    def _create_menu(self):
        hmenu = user32.CreatePopupMenu()
        items = [
            (1000, "فتح البرنامج"),
            (1001, "إخفاء / إظهار النافذة"),
            (0, None),
            (1002, "💾 حفظ تخطيط هذه الدقة"),
            (1003, "📂 استعادة تخطيط هذه الدقة"),
            (0, None),
            (1004, "〰 ترتيب موجة"),
            (1005, "🌀 ترتيب حلزون"),
            (1006, "📂 ترتيب حسب نوع الملف"),
            (0, None),
            (1090, "خروج"),
        ]
        for cid, text in items:
            if cid == 0:
                user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            else:
                user32.AppendMenuW(hmenu, MF_STRING, cid, text)
        return hmenu

    def _register_hotkeys(self):
        combos = [
            (1, MOD_CONTROL | MOD_ALT, 0x53),  # S
            (2, MOD_CONTROL | MOD_ALT, 0x48),  # H
            (3, MOD_CONTROL | MOD_ALT, 0x52),  # R
            (4, MOD_CONTROL | MOD_ALT, 0x57),  # W
            (5, MOD_CONTROL | MOD_ALT, 0x50),  # P
        ]
        for hid, mods, vk in combos:
            if not user32.RegisterHotKey(self.hwnd, hid, mods, vk):
                print(f"Warning: failed to register hotkey {hid}", file=sys.stderr)

    def run(self):
        class_name = "DesktopIconStudioTrayWnd"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc_cb
        wc.hInstance = self.hinst
        wc.lpszClassName = class_name
        self.class_atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not self.class_atom:
            return

        self.hwnd = user32.CreateWindowExW(
            0, class_name, "DITray",
            WS_POPUP,
            0, 0, 0, 0,
            None, None, self.hinst, None)
        if not self.hwnd:
            return

        user32.ShowWindow(self.hwnd, SW_HIDE)

        # أيقونة بجانب الساعة
        hicon = self._load_icon()
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = hicon
        nid.szTip = "استوديو أيقونات سطح المكتب - Ctrl+Alt+S"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

        self.hmenu = self._create_menu()
        self._register_hotkeys()

        msg = MSG()
        while not self._stop_event.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._cleanup()

    def _cleanup(self):
        self._stop_event.set()
        if self.hwnd:
            for hid in self._hotkey_map:
                user32.UnregisterHotKey(self.hwnd, hid)
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.hwnd
            nid.uID = 1
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            if self.hmenu:
                user32.DestroyMenu(self.hmenu)
                self.hmenu = None
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self.class_atom:
            user32.UnregisterClassW(
                MAKEINTRESOURCE(self.class_atom), self.hinst)
            self.class_atom = None

    def stop(self):
        self._stop_event.set()
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)


# ==========================================================================
#  الواجهة الرسومية
# ==========================================================================
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🖥️ استوديو أيقونات سطح المكتب v2")
        self.geometry("1080x720")
        self.minsize(980, 660)

        try:
            self.ctl = DesktopController()
        except RuntimeError as exc:
            messagebox.showerror("خطأ", str(exc))
            self.destroy()
            return

        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.store = LayoutStore(os.path.join(base, "layouts.json"))

        self.icons = []
        self.drag_index = None
        self.hidden = False
        self._size_busy = False
        self._res = self.ctl.work_area()

        self._build_ui()

        # Tray + hotkeys
        self.tray_q = queue.Queue()
        icon_path = os.path.join(base, "icon.ico")
        self.tray = TrayManager(self.tray_q, icon_path=icon_path)
        self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_tray_queue)
        self.after(2000, self._check_resolution)

        self.after(300, self.refresh_icons)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        left = ttk.LabelFrame(root, text=" خريطة سطح المكتب (انقر لتحديد أيقونة — اسحبها لتحريكها) ",
                              padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        wx, wy, ww, wh = self.ctl.work_area()
        self.area = (wx, wy, ww, wh)
        self.map_w = 430
        self.map_h = max(220, int(self.map_w * wh / max(1, ww)))
        self.canvas = tk.Canvas(left, width=self.map_w, height=self.map_h,
                                bg="#1e1e2e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=False)
        self.canvas.bind("<Button-1>", self._map_press)
        self.canvas.bind("<B1-Motion>", self._map_drag)
        self.canvas.bind("<ButtonRelease-1>", self._map_release)

        ttk.Button(left, text="🔄 تحديث القائمة", command=self.refresh_icons
                   ).pack(fill="x", pady=(8, 0))

        right = ttk.Frame(root)
        right.pack(side="left", fill="both", expand=True)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)

        tab_move = ttk.Frame(nb, padding=8)
        tab_look = ttk.Frame(nb, padding=8)
        tab_arrange = ttk.Frame(nb, padding=8)
        tab_layout = ttk.Frame(nb, padding=8)
        tab_res = ttk.Frame(nb, padding=8)
        nb.add(tab_move, text=" الأيقونات والتحريك ")
        nb.add(tab_look, text=" الحجم والمسافات ")
        nb.add(tab_arrange, text=" الترتيب التلقائي ")
        nb.add(tab_layout, text=" التخطيطات ")
        nb.add(tab_res, text=" دقة الشاشة ")

        self._build_move_tab(tab_move)
        self._build_look_tab(tab_look)
        self._build_arrange_tab(tab_arrange)
        self._build_layout_tab(tab_layout)
        self._build_resolution_tab(tab_res)

        self.status = tk.StringVar(value="جاهز")
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status, anchor="w",
                  font=("Segoe UI", 9)).pack(side="left", padx=8, pady=2)

        hint = ("💡 لتثبيت الأماكن يدويًا: زر أيمن على سطح المكتب ← عرض ← "
                "ألغِ «ترتيب الأيقونات تلقائيًا»")
        ttk.Label(bar, text=hint, anchor="e", foreground="#888",
                  font=("Segoe UI", 9)).pack(side="right", padx=8)

    def _build_move_tab(self, tab):
        cols = ("name", "x", "y")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        self.tree.heading("name", text="الأيقونة")
        self.tree.heading("x", text="X")
        self.tree.heading("y", text="Y")
        self.tree.column("name", width=230, anchor="w")
        self.tree.column("x", width=55, anchor="center")
        self.tree.column("y", width=55, anchor="center")
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="top", fill="both", expand=True)
        sb.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, anchor="ne")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        mv = ttk.LabelFrame(tab, text=" تحريك الأيقونة المحددة ", padding=8)
        mv.pack(fill="x", pady=8)

        row = ttk.Frame(mv)
        row.pack(fill="x")
        ttk.Label(row, text="X:", font=FONT).pack(side="left")
        self.var_x = tk.IntVar(value=0)
        tk.Spinbox(row, from_=0, to=10000, width=7, font=FONT,
                   textvariable=self.var_x).pack(side="left", padx=(2, 12))
        ttk.Label(row, text="Y:", font=FONT).pack(side="left")
        self.var_y = tk.IntVar(value=0)
        tk.Spinbox(row, from_=0, to=10000, width=7, font=FONT,
                   textvariable=self.var_y).pack(side="left", padx=(2, 12))
        ttk.Button(row, text="📍 نقل إلى هذه النقطة",
                   command=self._move_to_xy).pack(side="left")

        row2 = ttk.Frame(mv)
        row2.pack(pady=6)
        ttk.Label(row2, text="خطوة التحريك:", font=FONT).grid(
            row=0, column=0, rowspan=3, padx=(0, 10))
        self.var_step = tk.IntVar(value=10)
        tk.Spinbox(row2, from_=1, to=500, width=6, font=FONT,
                   textvariable=self.var_step).grid(row=1, column=1, padx=(0, 14))
        ttk.Button(row2, text="⬆", width=4,
                   command=lambda: self._nudge(0, -1)).grid(row=0, column=3)
        ttk.Button(row2, text="⬅", width=4,
                   command=lambda: self._nudge(-1, 0)).grid(row=1, column=2)
        ttk.Button(row2, text="➡", width=4,
                   command=lambda: self._nudge(1, 0)).grid(row=1, column=4)
        ttk.Button(row2, text="⬇", width=4,
                   command=lambda: self._nudge(0, 1)).grid(row=2, column=3)

        row3 = ttk.Frame(tab)
        row3.pack(fill="x")
        self.btn_hide = ttk.Button(row3, text="🙈 إخفاء كل الأيقونات",
                                   command=self._toggle_hide)
        self.btn_hide.pack(side="left", fill="x", expand=True)
        ttk.Button(row3, text="🧲 محاذاة الكل للشبكة",
                   command=self._snap).pack(side="left", fill="x",
                                            expand=True, padx=(8, 0))

    def _build_look_tab(self, tab):
        fs = ttk.LabelFrame(tab, text=" حجم الأيقونات (16 – 256 بكسل) ", padding=8)
        fs.pack(fill="x", pady=(0, 8))
        cur = self.ctl.get_icon_size()
        self.lbl_size = ttk.Label(fs, font=FONT_B,
                                  text=f"الحجم الحالي: {cur if cur else 'غير معروف'}")
        self.lbl_size.pack(anchor="w")
        row = ttk.Frame(fs)
        row.pack(fill="x", pady=4)
        self.var_size = tk.IntVar(value=cur or 48)
        tk.Scale(row, from_=16, to=256, orient="horizontal", length=300,
                 variable=self.var_size, font=FONT).pack(side="left")
        self.btn_size = ttk.Button(row, text="✔ تطبيق الحجم",
                                   command=self._apply_size)
        self.btn_size.pack(side="left", padx=10)
        row2 = ttk.Frame(fs)
        row2.pack(fill="x")
        ttk.Button(row2, text="➕ تكبير خطوة",
                   command=lambda: self._size_step(True)).pack(side="left")
        ttk.Button(row2, text="➖ تصغير خطوة",
                   command=lambda: self._size_step(False)).pack(side="left",
                                                                padx=8)

        fp = ttk.LabelFrame(tab, text=" المسافات بين الأيقونات (بكسل) ", padding=8)
        fp.pack(fill="x", pady=(0, 8))
        try:
            cx, cy = self.ctl.get_spacing()
        except OSError:
            cx, cy = DEFAULT_SPACING, DEFAULT_SPACING
        ttk.Label(fp, text="المسافة الأفقية:", font=FONT).pack(anchor="w")
        self.var_sx = tk.IntVar(value=cx or DEFAULT_SPACING)
        tk.Scale(fp, from_=32, to=400, orient="horizontal",
                 variable=self.var_sx, font=FONT).pack(fill="x")
        ttk.Label(fp, text="المسافة الرأسية:", font=FONT).pack(anchor="w")
        self.var_sy = tk.IntVar(value=cy or DEFAULT_SPACING)
        tk.Scale(fp, from_=32, to=400, orient="horizontal",
                 variable=self.var_sy, font=FONT).pack(fill="x")
        row3 = ttk.Frame(fp)
        row3.pack(fill="x", pady=4)
        ttk.Button(row3, text="✔ تطبيق المسافات",
                   command=self._apply_spacing).pack(side="left")
        ttk.Button(row3, text="↩ إعادة الافتراضي (75×75)",
                   command=self._reset_spacing).pack(side="left", padx=8)

        ttk.Label(tab, foreground="#888", font=("Segoe UI", 9),
                  text="ملاحظة: المسافات تُطبَّق عند «المحاذاة للشبكة» أو الترتيب التلقائي."
                  ).pack(anchor="w", pady=4)

    def _build_arrange_tab(self, tab):
        btns = [
            ("🔳 شبكة مرتبة (أبجديًا)", self._arrange_grid),
            ("⭕ دائرة حول المركز", self._arrange_circle),
            ("〰 موجة", self._arrange_wave),
            ("🌀 حلزون", self._arrange_spiral),
            ("📂 تجميع حسب نوع الملف", self._arrange_by_type),
            ("⬆ صف علوي", lambda: self._arrange_edge("top")),
            ("⬇ صف سفلي", lambda: self._arrange_edge("bottom")),
            ("◀ عمود أيسر", lambda: self._arrange_edge("left")),
            ("▶ عمود أيمن", lambda: self._arrange_edge("right")),
            ("🎯 توسيط أفقي في منتصف الشاشة", self._arrange_center),
            ("🧲 محاذاة الكل للشبكة", self._snap),
        ]
        for text, cmd in btns:
            ttk.Button(tab, text=text, command=cmd).pack(fill="x", pady=3)
        ttk.Label(tab, foreground="#888", font=("Segoe UI", 9),
                  text="يعتمد التوزيع على المسافات المضبوطة في تبويب «الحجم والمسافات»."
                  ).pack(anchor="w", pady=8)

    def _build_layout_tab(self, tab):
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 6))
        ttk.Label(row, text="اسم التخطيط:", font=FONT).pack(side="left")
        self.var_lname = tk.StringVar(value="تخطيطي")
        ttk.Entry(row, textvariable=self.var_lname, font=FONT,
                  width=20).pack(side="left", padx=6)
        ttk.Button(row, text="💾 حفظ الوضع الحالي",
                   command=self._save_layout).pack(side="left")

        row2 = ttk.Frame(tab)
        row2.pack(fill="x", pady=4)
        self.cmb = ttk.Combobox(row2, state="readonly", font=FONT, width=24)
        self.cmb.pack(side="left")
        ttk.Button(row2, text="📂 استعادة",
                   command=self._restore_layout).pack(side="left", padx=4)
        ttk.Button(row2, text="🗑 حذف",
                   command=self._delete_layout).pack(side="left")

        row3 = ttk.Frame(tab)
        row3.pack(fill="x", pady=4)
        ttk.Button(row3, text="⬇ تصدير كل التخطيطات…",
                   command=self._export_layouts).pack(side="left")
        ttk.Button(row3, text="⬆ استيراد تخطيطات…",
                   command=self._import_layouts).pack(side="left", padx=8)

        ttk.Label(tab, foreground="#888", font=("Segoe UI", 9),
                  wraplength=420, justify="left",
                  text=("يُحفَظ اسم كل أيقونة وموقعها. عند الاستعادة على شاشة "
                        "بدقة مختلفة تُقاس المواقع تلقائيًا لتناسبها.")).pack(anchor="w", pady=8)
        self._reload_layout_list()

    def _build_resolution_tab(self, tab):
        self._auto_save_res = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            tab, text="✅ حفظ/استعادة تلقائية عند تغيّر دقة الشاشة",
            variable=self._auto_save_res
        ).pack(anchor="w", pady=4)

        info = ttk.Label(tab, text=self._res_key(self._res), font=FONT_B)
        info.pack(anchor="w", pady=4)
        self._res_lbl = info

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="💾 حفظ تخطيط هذه الدقة",
                   command=lambda: self._save_resolution_layout(self.ctl.work_area())).pack(side="left")
        ttk.Button(row, text="📂 استعادة تخطيط هذه الدقة",
                   command=lambda: self._try_restore_resolution_layout(self.ctl.work_area())).pack(side="left", padx=8)

        ttk.Label(tab, foreground="#888", font=("Segoe UI", 9),
                  wraplength=420, justify="left",
                  text=("عند تغيّر الدقة يُحفظ الوضع الحالي للدقة القديمة ويُحاول "
                        "استعادة وضع محفوظ سابقًا للدقة الجديدة.")).pack(anchor="w", pady=8)

    # ==================================================================
    #  منطق الواجهة
    # ==================================================================
    def _set_status(self, msg):
        self.status.set(msg)
        self.update_idletasks()

    def _res_key(self, area):
        return f"auto_{area[2]}x{area[3]}"

    def refresh_icons(self):
        try:
            self._set_status("⏳ جارٍ قراءة أيقونات سطح المكتب…")
            self.icons = self.ctl.list_icons()
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))
            self._set_status("تعذّرت قراءة الأيقونات")
            return
        self.tree.delete(*self.tree.get_children())
        for ic in self.icons:
            self.tree.insert("", "end", iid=str(ic["i"]),
                             values=(ic["name"], ic["x"], ic["y"]))
        self._draw_map()
        cur = self.ctl.get_icon_size()
        self.lbl_size.config(
            text=f"الحجم الحالي: {cur if cur else 'غير معروف'}")
        self._res_lbl.config(text=self._res_key(self.ctl.work_area()))
        self._set_status(f"✅ {len(self.icons)} أيقونة")

    def _draw_map(self):
        c = self.canvas
        c.delete("all")
        wx, wy, ww, wh = self.area
        sx = self.map_w / max(1, ww)
        sy = self.map_h / max(1, wh)
        self._scale = (sx, sy)
        sel = set(self.tree.selection()) if hasattr(self, "tree") else set()
        for ic in self.icons:
            x = (ic["x"] - wx) * sx
            y = (ic["y"] - wy) * sy
            selected = str(ic["i"]) in sel
            color = "#f9a825" if selected else "#4fc3f7"
            c.create_rectangle(x, y, x + 10, y + 10, fill=color,
                               outline="", tags=f"ic{ic['i']}")

    def _selected_index(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _on_select(self, _evt=None):
        i = self._selected_index()
        if i is None or i >= len(self.icons):
            return
        ic = self.icons[i]
        self.var_x.set(ic["x"])
        self.var_y.set(ic["y"])
        self._draw_map()

    def _move_icon(self, i, x, y):
        self.ctl.set_position(i, x, y)
        if i < len(self.icons):
            self.icons[i]["x"], self.icons[i]["y"] = x, y
            self.tree.item(str(i), values=(self.icons[i]["name"], x, y))
        self._draw_map()

    def _move_to_xy(self):
        i = self._selected_index()
        if i is None:
            messagebox.showinfo("تنبيه", "اختر أيقونة من القائمة أولًا.")
            return
        self._move_icon(i, self.var_x.get(), self.var_y.get())
        self._set_status(f"📍 نُقلت الأيقونة إلى ({self.var_x.get()}, {self.var_y.get()})")

    def _nudge(self, dx, dy):
        i = self._selected_index()
        if i is None or i >= len(self.icons):
            messagebox.showinfo("تنبيه", "اختر أيقونة من القائمة أولًا.")
            return
        step = self.var_step.get()
        ic = self.icons[i]
        self._move_icon(i, ic["x"] + dx * step, ic["y"] + dy * step)

    def _map_to_desktop(self, mx, my):
        sx, sy = self._scale
        wx, wy = self.area[0], self.area[1]
        return int(mx / sx + wx), int(my / sy + wy)

    def _icon_at(self, mx, my):
        sx, sy = self._scale
        wx, wy = self.area[0], self.area[1]
        for ic in self.icons:
            x = (ic["x"] - wx) * sx
            y = (ic["y"] - wy) * sy
            if x - 6 <= mx <= x + 16 and y - 6 <= my <= y + 16:
                return ic["i"]
        return None

    def _map_press(self, evt):
        i = self._icon_at(evt.x, evt.y)
        if i is not None:
            self.tree.selection_set(str(i))
            self.tree.see(str(i))
            self._on_select()
            self.drag_index = i
        else:
            sel = self._selected_index()
            if sel is not None:
                x, y = self._map_to_desktop(evt.x, evt.y)
                self._move_icon(sel, x, y)

    def _map_drag(self, evt):
        if self.drag_index is not None:
            x, y = self._map_to_desktop(evt.x, evt.y)
            self._move_icon(self.drag_index, x, y)

    def _map_release(self, _evt):
        if self.drag_index is not None:
            self.drag_index = None
            self.ctl.refresh_view()

    def _apply_size(self):
        if self._size_busy:
            return
        target = self.var_size.get()
        self._size_busy = True
        self.btn_size.state(["disabled"])

        def worker():
            err = None
            try:
                final = self.ctl.set_icon_size(target)
                self.after(0, lambda: self.lbl_size.config(
                    text=f"الحجم الحالي: {final if final else 'غير معروف'}"))
            except RuntimeError as exc:
                err = str(exc)
            finally:
                def done():
                    self._size_busy = False
                    self.btn_size.state(["!disabled"])
                    if err:
                        messagebox.showwarning("تعذّر الضبط الدقيق", err)
                    self._set_status("✅ تم ضبط حجم الأيقونات")
                self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _size_step(self, bigger):
        try:
            self.ctl.nudge_icon_size(bigger)
            cur = self.ctl.get_icon_size()
            self.lbl_size.config(
                text=f"الحجم الحالي: {cur if cur else 'غير معروف'}")
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))

    def _apply_spacing(self):
        try:
            self.ctl.set_spacing(self.var_sx.get(), self.var_sy.get())
            self._set_status(
                f"✅ المسافات: {self.var_sx.get()}×{self.var_sy.get()} بكسل")
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))

    def _reset_spacing(self):
        self.var_sx.set(DEFAULT_SPACING)
        self.var_sy.set(DEFAULT_SPACING)
        self._apply_spacing()

    def _gap(self):
        return max(40, self.var_sx.get()), max(40, self.var_sy.get())

    def _place(self, positions):
        for ic, (x, y) in zip(self.icons, positions):
            self.ctl.set_position(ic["i"], x, y)
            ic["x"], ic["y"] = x, y
        self.ctl.refresh_view()
        self.refresh_icons()

    def _arrange_grid(self):
        if not self.icons:
            return
        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        cols = max(1, ww // gx)
        icons = sorted(self.icons, key=lambda c: c["name"].lower())
        pos = []
        for n, _ in enumerate(icons):
            r, cidx = divmod(n, cols)
            pos.append((wx + cidx * gx, wy + r * gy))
        self.icons = icons
        self._place(pos)
        self._set_status("🔳 تم الترتيب في شبكة")

    def _arrange_circle(self):
        n = len(self.icons)
        if not n:
            return
        wx, wy, ww, wh = self.area
        cx, cy = wx + ww // 2, wy + wh // 2
        r = max(120, min(ww, wh) // 2 - 90)
        pos = [(int(cx + r * math.cos(2 * math.pi * k / n - math.pi / 2)) - 30,
                int(cy + r * math.sin(2 * math.pi * k / n - math.pi / 2)) - 30)
               for k in range(n)]
        self._place(pos)
        self._set_status("⭕ تم الترتيب في دائرة")

    def _arrange_wave(self):
        n = len(self.icons)
        if not n:
            return
        wx, wy, ww, wh = self.area
        margin = max(60, ww // 12)
        usable = max(1, ww - 2 * margin)
        step = usable / max(1, n - 1)
        amplitude = max(80, wh // 4)
        cy = wy + wh // 2
        icons = sorted(self.icons, key=lambda c: c["name"].lower())
        pos = []
        for k, _ in enumerate(icons):
            x = wx + margin + int(k * step)
            y = int(cy + amplitude * math.sin(2 * math.pi * k / max(1, n - 1)))
            pos.append((x, y))
        self.icons = icons
        self._place(pos)
        self._set_status("〰 تم الترتيب في موجة")

    def _arrange_spiral(self):
        n = len(self.icons)
        if not n:
            return
        wx, wy, ww, wh = self.area
        cx, cy = wx + ww // 2, wy + wh // 2
        max_r = min(ww, wh) // 2 - 80
        a = max(8, max_r / (2 * math.pi * max(1, math.sqrt(n))))
        icons = sorted(self.icons, key=lambda c: c["name"].lower())
        pos = []
        for k, _ in enumerate(icons):
            t = math.sqrt(k + 1)
            r = a * t
            angle = t * 2 * math.pi
            x = int(cx + r * math.cos(angle))
            y = int(cy + r * math.sin(angle))
            pos.append((x, y))
        self.icons = icons
        self._place(pos)
        self._set_status("🌀 تم الترتيب في حلزون")

    def _arrange_by_type(self):
        if not self.icons:
            return
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        name_to_ext = {}
        if os.path.isdir(desktop):
            for name in os.listdir(desktop):
                base, ext = os.path.splitext(name)
                ext = ext.lower() if ext else "📄 ملف"
                name_to_ext[base.lower()] = ext

        groups = {}
        for ic in self.icons:
            ext = name_to_ext.get(ic["name"].lower().rstrip(), "🖥️ أيقونة نظام")
            groups.setdefault(ext, []).append(ic)

        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        col_width = gx * 2
        col_x = wx + gx
        row_y = wy + gy
        max_col_h = 0
        ordered = []
        pos = []
        for ext in sorted(groups.keys()):
            gicons = sorted(groups[ext], key=lambda c: c["name"].lower())
            if col_x + col_width > wx + ww - gx:
                col_x = wx + gx
                row_y += max_col_h + gy
                max_col_h = 0
            for idx, ic in enumerate(gicons):
                ordered.append(ic)
                pos.append((col_x, row_y + idx * gy))
            max_col_h = max(max_col_h, len(gicons) * gy)
            col_x += col_width
        self.icons = ordered
        self._place(pos)
        self._set_status("📂 تم الترتيب حسب نوع الملف")

    def _arrange_edge(self, edge):
        n = len(self.icons)
        if not n:
            return
        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        pos = []
        if edge == "top":
            pos = [(wx + k * gx, wy) for k in range(n)]
        elif edge == "bottom":
            y = wy + wh - gy
            pos = [(wx + k * gx, y) for k in range(n)]
        elif edge == "left":
            pos = [(wx, wy + k * gy) for k in range(n)]
        else:
            x = wx + ww - gx
            pos = [(x, wy + k * gy) for k in range(n)]
        self._place(pos)
        self._set_status("✅ تم الترتيب على الحافة")

    def _arrange_center(self):
        n = len(self.icons)
        if not n:
            return
        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        total = n * gx
        x0 = wx + max(0, (ww - total) // 2)
        y0 = wy + wh // 2 - gy // 2
        pos = [(x0 + k * gx, y0) for k in range(n)]
        self._place(pos)
        self._set_status("🎯 تم التوسيط")

    def _snap(self):
        self.ctl.snap_to_grid()
        self._set_status("🧲 تمت المحاذاة للشبكة")
        self.after(400, self.refresh_icons)

    def _toggle_hide(self):
        self.hidden = not self.hidden
        self.ctl.set_visible(not self.hidden)
        self.btn_hide.config(
            text="👁 إظهار الأيقونات" if self.hidden else "🙈 إخفاء كل الأيقونات")
        self._set_status("🙈 الأيقونات مخفية" if self.hidden else "👁 الأيقونات ظاهرة")

    # ---------------- التخطيطات ----------------
    def _reload_layout_list(self):
        names = sorted(self.store.data.keys())
        self.cmb["values"] = names
        if names and not self.cmb.get():
            self.cmb.set(names[0])

    def _save_layout(self):
        name = self.var_lname.get().strip()
        if not name:
            messagebox.showinfo("تنبيه", "اكتب اسمًا للتخطيط أولًا.")
            return
        if not self.icons:
            self.refresh_icons()
        try:
            spacing = self.ctl.get_spacing()
        except OSError:
            spacing = (DEFAULT_SPACING, DEFAULT_SPACING)
        self.store.put(name, self.icons, self.area, spacing)
        self._reload_layout_list()
        self.cmb.set(name)
        self._set_status(f"💾 حُفظ التخطيط «{name}»")

    def _restore_layout(self):
        name = self.cmb.get()
        lay = self.store.data.get(name)
        if not lay:
            messagebox.showinfo("تنبيه", "اختر تخطيطًا محفوظًا أولًا.")
            return
        self._apply_layout(lay)
        self._set_status(f"📂 استُعيد التخطيط «{name}»")

    def _apply_layout(self, lay):
        saved_area = lay.get("work_area") or self.area
        sx = self.area[2] / max(1, saved_area[2])
        sy = self.area[3] / max(1, saved_area[3])
        by_name = {ic["name"]: ic for ic in self.icons}
        moved = 0
        for iname, (x, y) in lay.get("icons", {}).items():
            ic = by_name.get(iname)
            if ic:
                nx = int(self.area[0] + (x - saved_area[0]) * sx)
                ny = int(self.area[1] + (y - saved_area[1]) * sy)
                self.ctl.set_position(ic["i"], nx, ny)
                moved += 1
        self.ctl.refresh_view()
        self.refresh_icons()

    def _delete_layout(self):
        name = self.cmb.get()
        if name and name in self.store.data:
            if messagebox.askyesno("تأكيد", f"حذف التخطيط «{name}»؟"):
                self.store.delete(name)
                self.cmb.set("")
                self._reload_layout_list()
                self._set_status(f"🗑 حُذف «{name}»")

    def _export_layouts(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="desktop_layouts.json",
            title="تصدير التخطيطات")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.store.data, f, ensure_ascii=False, indent=2)
                self._set_status(f"⬇ تم التصدير إلى {path}")
            except OSError as exc:
                messagebox.showerror("خطأ", str(exc))

    def _import_layouts(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], title="استيراد تخطيطات")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.store.data.update(data)
                    self.store.save()
                    self._reload_layout_list()
                    self._set_status("⬆ تم الاستيراد")
            except (OSError, json.JSONDecodeError) as exc:
                messagebox.showerror("خطأ", str(exc))

    # ---------------- دقة الشاشة ----------------
    def _save_resolution_layout(self, area):
        if not self.icons:
            self.refresh_icons()
        key = self._res_key(area)
        try:
            spacing = self.ctl.get_spacing()
        except OSError:
            spacing = (DEFAULT_SPACING, DEFAULT_SPACING)
        self.store.put(key, self.icons, area, spacing)
        self._reload_layout_list()
        self.cmb.set(key)
        self._set_status(f"💾 حُفظ تخطيط الدقة {key}")

    def _try_restore_resolution_layout(self, area):
        key = self._res_key(area)
        lay = self.store.data.get(key)
        if lay:
            self._apply_layout(lay)
            self._set_status(f"📂 استُعيد تخطيط الدقة {key}")
        else:
            self._set_status(f"ℹ لا يوجد تخطيط محفوظ للدقة {key}")

    def _check_resolution(self):
        try:
            new_area = self.ctl.work_area()
        except OSError:
            self.after(2000, self._check_resolution)
            return
        if (new_area[2], new_area[3]) != (self._res[2], self._res[3]):
            old_area = self._res
            self._res = new_area
            self.area = new_area
            if self._auto_save_res.get():
                self._save_resolution_layout(old_area)
            self._try_restore_resolution_layout(new_area)
            self._res_lbl.config(text=self._res_key(new_area))
        self.after(2000, self._check_resolution)

    # ---------------- Tray integration ----------------
    def _poll_tray_queue(self):
        while True:
            try:
                cmd = self.tray_q.get_nowait()
            except queue.Empty:
                break
            if cmd == "SHOW_WINDOW":
                self.deiconify()
                self.lift()
                self.focus_force()
            elif cmd == "TOGGLE_WINDOW":
                if self.state() == "withdrawn":
                    self.deiconify()
                    self.lift()
                else:
                    self.withdraw()
            elif cmd == "SAVE_RES":
                self._save_resolution_layout(self.ctl.work_area())
            elif cmd == "RESTORE_RES":
                self._try_restore_resolution_layout(self.ctl.work_area())
            elif cmd == "ARRANGE_WAVE":
                self._arrange_wave()
            elif cmd == "ARRANGE_SPIRAL":
                self._arrange_spiral()
            elif cmd == "ARRANGE_TYPE":
                self._arrange_by_type()
            elif cmd == "EXIT":
                self._exit_app()
        self.after(100, self._poll_tray_queue)

    def _on_close(self):
        self.withdraw()
        self._set_status("البرنامج يعمل بجانب الساعة — اضغط Ctrl+Alt+S لفتحه")

    def _exit_app(self):
        self.tray.stop()
        try:
            self.tray.join(timeout=2.0)
        except Exception:
            pass
        self.destroy()


# ==========================================================================
def _enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        try:
            user32.SetProcessDPIAware()
        except (OSError, AttributeError):
            pass


if __name__ == "__main__":
    if sys.platform != "win32":
        print("هذا البرنامج مخصص لنظام ويندوز فقط.")
        sys.exit(1)
    _enable_dpi_awareness()
    app = App()
    if app.winfo_exists():
        app.mainloop()
