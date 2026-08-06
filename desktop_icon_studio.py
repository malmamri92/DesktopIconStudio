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

يعمل بـ Python + customtkinter لواجهة احترافية حديثة.
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
import tkinter as tk
import winreg
from ctypes import wintypes

import customtkinter as ctk
from PIL import Image, ImageTk

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

# --- ثوابت استخراج الأيقونات ---
SHGFI_ICON        = 0x000000100
SHGFI_LARGEICON   = 0x000000000
SHGFI_SMALLICON   = 0x000000001
SHGFI_USEFILEATTRIBUTES = 0x000000010

GCL_HMODULE       = -16
SRCCOPY           = 0x00CC0020
DIB_RGB_COLORS    = 0


class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.c_long),
        ("bmWidth", ctypes.c_long),
        ("bmHeight", ctypes.c_long),
        ("bmWidthBytes", ctypes.c_long),
        ("bmPlanes", ctypes.c_ushort),
        ("bmBitsPixel", ctypes.c_ushort),
        ("bmBits", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [("rgbBlue", ctypes.c_ubyte), ("rgbGreen", ctypes.c_ubyte),
                ("rgbRed", ctypes.c_ubyte), ("rgbReserved", ctypes.c_ubyte)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


# ==========================================================================
#  توقيعات دوال Win32 المستخدمة في استخراج الأيقونات
# ==========================================================================
user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.DestroyIcon.restype = wintypes.BOOL

gdi32 = ctypes.windll.gdi32
gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi32.GetObjectW.restype = ctypes.c_int
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    wintypes.LPVOID, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int

shell32.SHGetFileInfoW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFOW),
    wintypes.UINT, wintypes.UINT,
]
shell32.SHGetFileInfoW.restype = wintypes.DWORD


def MAKEINTRESOURCE(i):
    return ctypes.cast(ctypes.c_void_p(i), ctypes.c_wchar_p)


def _hicon_to_pil(hicon, size=32):
    """تحويل HICON Win32 إلى PIL Image RGBA."""
    info = ICONINFO()
    if not user32.GetIconInfo(hicon, ctypes.byref(info)):
        return None
    try:
        if info.hbmColor:
            bmp = BITMAP()
            gdi32 = ctypes.windll.gdi32
            if not gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bmp)):
                return None
            w, h = bmp.bmWidth, bmp.bmHeight
            hdc = user32.GetDC(None)
            memdc = gdi32.CreateCompatibleDC(hdc)
            old = gdi32.SelectObject(memdc, info.hbmColor)
            bi = BITMAPINFO()
            bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bi.bmiHeader.biWidth = w
            bi.bmiHeader.biHeight = -h
            bi.bmiHeader.biPlanes = 1
            bi.bmiHeader.biBitCount = 32
            bi.bmiHeader.biCompression = 0
            buf = (ctypes.c_ubyte * (w * h * 4))()
            gdi32.GetDIBits(memdc, info.hbmColor, 0, h, buf, ctypes.byref(bi), DIB_RGB_COLORS)
            img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)
            gdi32.SelectObject(memdc, old)
            gdi32.DeleteDC(memdc)
            user32.ReleaseDC(None, hdc)
            if size and (w != size or h != size):
                img = img.resize((size, size), Image.LANCZOS)
            return img
        else:
            # أيقونة أحادية اللون (mask)
            gdi32 = ctypes.windll.gdi32
            bmp = BITMAP()
            if not gdi32.GetObjectW(info.hbmMask, ctypes.sizeof(BITMAP), ctypes.byref(bmp)):
                return None
            w, h = bmp.bmWidth, bmp.bmHeight // 2
            hdc = user32.GetDC(None)
            memdc = gdi32.CreateCompatibleDC(hdc)
            old = gdi32.SelectObject(memdc, info.hbmMask)
            bi = BITMAPINFO()
            bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bi.bmiHeader.biWidth = w
            bi.bmiHeader.biHeight = -h * 2
            bi.bmiHeader.biPlanes = 1
            bi.bmiHeader.biBitCount = 32
            bi.bmiHeader.biCompression = 0
            buf = (ctypes.c_ubyte * (w * h * 2 * 4))()
            gdi32.GetDIBits(memdc, info.hbmMask, 0, h * 2, buf, ctypes.byref(bi), DIB_RGB_COLORS)
            # نأخذ النصف السفلي كقناع ألفا
            data = bytearray(w * h * 4)
            for y in range(h):
                for x in range(w):
                    src = (y * w + x) * 4
                    dst = (y * w + x) * 4
                    a = 255 if buf[src] == 0 else 0
                    data[dst:dst+4] = (0, 0, 0, a)
            img = Image.frombuffer("RGBA", (w, h), bytes(data), "raw", "BGRA", 0, 1)
            gdi32.SelectObject(memdc, old)
            gdi32.DeleteDC(memdc)
            user32.ReleaseDC(None, hdc)
            if size and (w != size or h != size):
                img = img.resize((size, size), Image.LANCZOS)
            return img
    finally:
        gdi32 = ctypes.windll.gdi32
        if info.hbmMask:
            gdi32.DeleteObject(info.hbmMask)
        if info.hbmColor:
            gdi32.DeleteObject(info.hbmColor)


def _get_file_icon(path, size=32):
    """يستخرج أيقونة ملف/مجلد ويعيد PIL Image."""
    sfi = SHFILEINFOW()
    res = shell32.SHGetFileInfoW(path, 0, ctypes.byref(sfi),
                                 ctypes.sizeof(sfi),
                                 SHGFI_ICON | SHGFI_LARGEICON)
    if not res or not sfi.hIcon:
        return None
    try:
        img = _hicon_to_pil(sfi.hIcon, size=size)
        return img
    finally:
        user32.DestroyIcon(sfi.hIcon)


def _display_name_to_path(name):
    """يحاول إيجاد المسار الحقيقي لأيقونة سطح المكتب من اسمها الظاهر."""
    name_lower = name.lower().strip()
    candidates = []
    for base in (os.environ.get("USERPROFILE", ""), os.environ.get("PUBLIC", "")):
        desktop = os.path.join(base, "Desktop")
        if os.path.isdir(desktop):
            candidates.append(desktop)
    for desktop in candidates:
        for item in os.listdir(desktop):
            full = os.path.join(desktop, item)
            base, ext = os.path.splitext(item)
            item_lower = item.lower()
            base_lower = base.lower()
            # قارن بعدة أشكال: الاسم الكامل، بدون امتداد، مع/بدون مسافات
            if name_lower in (item_lower, base_lower,
                              item_lower.strip(), base_lower.strip()):
                return full
    # أيقونات النظام الشائعة
    system_icons = {
        "سلة المحذوفات": "::{645FF040-5081-101B-9F08-00AA002F954E}",
        "recycle bin": "::{645FF040-5081-101B-9F08-00AA002F954E}",
        "هذا الكمبيوتر": "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
        "this pc": "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
        "لوحة التحكم": "::{26EE0668-A00A-44D7-9371-BEB064C98683}",
        "control panel": "::{26EE0668-A00A-44D7-9371-BEB064C98683}",
        "شبكة": "::{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}",
        "network": "::{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}",
    }
    return system_icons.get(name_lower)


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
    # نستخدم HANDLE لكل المقابض لأن بعض إصدارات بايثون لا تعرّف الأنواع الفرعية
    _fields_ = [
        ("cbSize",        wintypes.UINT),
        ("style",         wintypes.UINT),
        ("lpfnWndProc",   WNDPROC),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     wintypes.HANDLE),
        ("hIcon",         wintypes.HANDLE),
        ("hCursor",       wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName",  wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm",       wintypes.HANDLE),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize",               wintypes.DWORD),
        ("hWnd",                 wintypes.HWND),
        ("uID",                  wintypes.UINT),
        ("uFlags",               wintypes.UINT),
        ("uCallbackMessage",     wintypes.UINT),
        ("hIcon",                wintypes.HANDLE),
        ("szTip",                wintypes.WCHAR * 128),
        ("dwState",              wintypes.DWORD),
        ("dwStateMask",          wintypes.DWORD),
        ("szInfo",               wintypes.WCHAR * 256),
        ("uTimeout_or_uVersion", wintypes.UINT),
        ("szInfoTitle",          wintypes.WCHAR * 64),
        ("dwInfoFlags",          wintypes.DWORD),
        ("guidItem",             ctypes.c_byte * 16),
        ("hBalloonIcon",         wintypes.HANDLE),
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
#  إدارة الإعدادات (JSON)
# ==========================================================================
class SettingsStore:
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

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
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
from tkinter import messagebox, filedialog

FONT = ("Segoe UI", 12)
FONT_B = ("Segoe UI", 12, "bold")
SMALL = ("Segoe UI", 11)


class App(ctk.CTk):
    SECTIONS = {
        "icons": "🖥️ الأيقونات",
        "look": "🎨 المظهر",
        "arrange": "📐 الترتيب",
        "layouts": "💾 التخطيطات",
        "display": "🖥️ الدقة",
        "settings": "⚙️ الإعدادات",
    }

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.title("Desktop Icon Studio")
        self.geometry("1280x850")
        self.minsize(1080, 760)

        try:
            self.ctl = DesktopController()
        except RuntimeError as exc:
            messagebox.showerror("خطأ", str(exc))
            self.destroy()
            return

        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.store = LayoutStore(os.path.join(base, "layouts.json"))
        self.settings = SettingsStore(os.path.join(base, "settings.json"))

        self.icons = []
        self.selection = set()
        self.drag_index = None
        self.hidden = False
        self._size_busy = False
        self._res = self.ctl.work_area()
        self.area = self._res
        self.map_bbox = self.area

        # --- tk variables ---
        self.preview_size = tk.IntVar(value=self.settings.get("preview_size", 48))
        self.var_x = tk.IntVar(value=0)
        self.var_y = tk.IntVar(value=0)
        self.var_step = tk.IntVar(value=10)
        self.var_size = tk.IntVar(value=48)
        self.var_sx = tk.IntVar(value=DEFAULT_SPACING)
        self.var_sy = tk.IntVar(value=DEFAULT_SPACING)
        self.var_lname = tk.StringVar(value="تخطيطي")
        self._auto_save_res = tk.BooleanVar(value=True)
        self.theme_var = tk.StringVar(value="Dark")
        self.status = tk.StringVar(value="جاهز")

        self.nav_buttons = {}
        self.section_frames = {}
        self.icon_photos = {}

        self._build_ui()
        self._apply_saved_theme()

        # --- tray + hotkeys ---
        self.tray_q = queue.Queue()
        icon_path = os.path.join(base, "icon.ico")
        self.tray = TrayManager(self.tray_q, icon_path=icon_path)
        self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_tray_queue)
        self.after(2000, self._check_resolution)
        self.after(300, self.refresh_icons)

    # ==================================================================
    #  Window / theme
    # ==================================================================
    def _set_title_bar_dark(self, dark=True):
        """تفعيل الوضع الداكن لشريط عنوان النافذة في ويندوز 10/11."""
        try:
            hwnd = wintypes.HWND(self.winfo_id())
            value = ctypes.c_int(1 if dark else 0)
            dwm = ctypes.windll.dwmapi
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
                try:
                    dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value),
                                              ctypes.sizeof(value))
                    break
                except OSError:
                    continue
        except Exception:
            pass

    def _apply_theme(self, theme_name="dark"):
        mode = theme_name.capitalize() if theme_name in ("dark", "light") else "System"
        ctk.set_appearance_mode(mode)
        self._set_title_bar_dark(dark=(theme_name != "light"))

    def _apply_saved_theme(self):
        stored = self.settings.get("theme", "dark")
        self.theme_var.set(stored.capitalize())
        self._apply_theme(stored)

    # ==================================================================
    #  UI builders
    # ==================================================================
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- sidebar ---
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="Desktop Icon\nStudio",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, pady=(24, 16), padx=20)

        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)

        for key, label in self.SECTIONS.items():
            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                anchor="w",
                height=42,
                font=ctk.CTkFont("Segoe UI", 14),
                fg_color="transparent",
                hover_color=("gray70", "gray35"),
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn

        ctk.CTkLabel(
            sidebar,
            textvariable=self.status,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=12)

        # --- main area ---
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # header
        header = ctk.CTkFrame(main, height=70, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)

        self.header_title = ctk.CTkLabel(
            header,
            text="🖥️ الأيقونات",
            font=ctk.CTkFont("Segoe UI", 24, "bold"),
        )
        self.header_title.grid(row=0, column=0, sticky="w")

        # content container
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self._build_icons_section(content)
        self._build_look_section(content)
        self._build_arrange_section(content)
        self._build_layouts_section(content)
        self._build_display_section(content)
        self._build_settings_section(content)

        self._show_section("icons")

    def _show_section(self, key):
        for k, frame in self.section_frames.items():
            if k == key:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=("gray75", "gray30"))
            else:
                btn.configure(fg_color="transparent")
        self.header_title.configure(text=self.SECTIONS[key])

    def _build_icons_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["icons"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # خريطة كبيرة تملأ الشاشة
        map_card = ctk.CTkFrame(frame)
        map_card.grid(row=0, column=0, sticky="nsew")
        map_card.grid_rowconfigure(0, weight=1)
        map_card.grid_columnconfigure(0, weight=1)

        wx, wy, ww, wh = self.area
        self.map_w = 1100
        self.map_h = max(500, int(self.map_w * wh / max(1, ww)))
        self._scale = 1.0
        self._map_offset = (0.0, 0.0)
        self.canvas = tk.Canvas(
            map_card,
            bg="#14141b",
            highlightthickness=0,
            width=self.map_w,
            height=self.map_h,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._map_press)
        self.canvas.bind("<B1-Motion>", self._map_drag)
        self.canvas.bind("<ButtonRelease-1>", self._map_release)

        # شريط أدوات سفلي
        toolbar = ctk.CTkFrame(frame, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.btn_hide = ctk.CTkButton(
            toolbar, text="🙈 إخفاء", width=90, command=self._toggle_hide
        )
        self.btn_hide.pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="🧲 محاذاة للشبكة", width=130,
                      command=self._snap).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="🔄 تحديث", width=90,
                      command=self.refresh_icons).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="❌ إلغاء التحديد", width=130,
                      command=self._clear_selection).pack(side="left", padx=4)

        ctk.CTkLabel(toolbar, text="X:").pack(side="left", padx=(20, 2))
        ctk.CTkEntry(toolbar, width=70, textvariable=self.var_x).pack(side="left", padx=2)
        ctk.CTkLabel(toolbar, text="Y:").pack(side="left", padx=(8, 2))
        ctk.CTkEntry(toolbar, width=70, textvariable=self.var_y).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="📍 نقل", width=70,
                      command=self._move_to_xy).pack(side="left", padx=(8, 4))

        ctk.CTkLabel(toolbar, text="خطوة:").pack(side="left", padx=(16, 2))
        ctk.CTkEntry(toolbar, width=55, textvariable=self.var_step).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="⬆", width=36,
                      command=lambda: self._nudge(0, -1)).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="⬇", width=36,
                      command=lambda: self._nudge(0, 1)).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="⬅", width=36,
                      command=lambda: self._nudge(-1, 0)).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="➡", width=36,
                      command=lambda: self._nudge(1, 0)).pack(side="left", padx=2)

        ctk.CTkLabel(toolbar, text="حجم المعاينة:").pack(side="left", padx=(20, 4))
        self.lbl_preview = ctk.CTkLabel(toolbar, text=f"{self.preview_size.get()}px")
        self.lbl_preview.pack(side="left", padx=2)
        ctk.CTkSlider(
            toolbar, from_=16, to=96, number_of_steps=80,
            width=120, variable=self.preview_size,
            command=lambda v: self._set_preview_size(int(float(v))),
        ).pack(side="left", padx=4)

    def _set_preview_size(self, size):
        self.preview_size.set(size)
        self.lbl_preview.configure(text=f"{size}px")
        self.settings.set("preview_size", size)
        if self.icons:
            self._load_icon_images()
            self._draw_map()

    def _build_look_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["look"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # icon size
        size_card = ctk.CTkFrame(frame)
        size_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        size_card.grid_columnconfigure(0, weight=1)

        cur = self.ctl.get_icon_size()
        self.var_size.set(cur or 48)
        self.lbl_size = ctk.CTkLabel(
            size_card,
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text=f"حجم الأيقونات: {cur if cur else 'غير معروف'} بكسل",
        )
        self.lbl_size.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        ctk.CTkSlider(
            size_card,
            from_=16,
            to=256,
            number_of_steps=240,
            variable=self.var_size,
            command=lambda v: self.lbl_size.configure(
                text=f"حجم الأيقونات: {int(float(v))} بكسل"),
        ).grid(row=1, column=0, sticky="ew", padx=15, pady=5)

        row = ctk.CTkFrame(size_card, fg_color="transparent")
        row.grid(row=2, column=0, sticky="w", padx=15, pady=(5, 15))
        ctk.CTkButton(
            row,
            text="−",
            width=40,
            command=lambda: self._size_step(False),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            row,
            text="+",
            width=40,
            command=lambda: self._size_step(True),
        ).grid(row=0, column=1, padx=4)
        self.btn_size = ctk.CTkButton(
            row,
            text="✔ تطبيق الحجم",
            command=self._apply_size,
        )
        self.btn_size.grid(row=0, column=2, padx=(20, 4))

        # spacing
        spacing_card = ctk.CTkFrame(frame)
        spacing_card.grid(row=1, column=0, sticky="ew")
        spacing_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            spacing_card,
            text="المسافات بين الأيقونات",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        try:
            cx, cy = self.ctl.get_spacing()
        except OSError:
            cx, cy = DEFAULT_SPACING, DEFAULT_SPACING
        self.var_sx.set(cx or DEFAULT_SPACING)
        self.var_sy.set(cy or DEFAULT_SPACING)

        ctk.CTkLabel(spacing_card, text="أفقي:").grid(
            row=1, column=0, sticky="w", padx=15)
        ctk.CTkSlider(
            spacing_card,
            from_=32,
            to=400,
            number_of_steps=368,
            variable=self.var_sx,
        ).grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        ctk.CTkLabel(spacing_card, text="رأسي:").grid(
            row=3, column=0, sticky="w", padx=15)
        ctk.CTkSlider(
            spacing_card,
            from_=32,
            to=400,
            number_of_steps=368,
            variable=self.var_sy,
        ).grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 10))

        row2 = ctk.CTkFrame(spacing_card, fg_color="transparent")
        row2.grid(row=5, column=0, sticky="w", padx=15, pady=(5, 15))
        ctk.CTkButton(row2, text="✔ تطبيق المسافات", command=self._apply_spacing).grid(
            row=0, column=0, padx=4)
        ctk.CTkButton(row2, text="↩ إعادة الافتراضي", command=self._reset_spacing).grid(
            row=0, column=1, padx=4)

    def _build_arrange_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["arrange"] = frame
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)

        buttons = [
            ("🔳 شبكة", self._arrange_grid),
            ("⭕ دائرة", self._arrange_circle),
            ("〰 موجة", self._arrange_wave),
            ("🌀 حلزون", self._arrange_spiral),
            ("📂 حسب النوع", self._arrange_by_type),
            ("⬆ صف علوي", lambda: self._arrange_edge("top")),
            ("⬇ صف سفلي", lambda: self._arrange_edge("bottom")),
            ("◀ عمود أيسر", lambda: self._arrange_edge("left")),
            ("▶ عمود أيمن", lambda: self._arrange_edge("right")),
            ("🎯 توسيط", self._arrange_center),
            ("🧲 محاذاة للشبكة", self._snap),
        ]
        for idx, (text, cmd) in enumerate(buttons):
            r, c = divmod(idx, 2)
            ctk.CTkButton(
                frame,
                text=text,
                command=cmd,
                height=70,
                font=ctk.CTkFont("Segoe UI", 14),
            ).grid(row=r, column=c, sticky="nsew", padx=8, pady=8)

    def _build_layouts_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["layouts"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # save
        save_card = ctk.CTkFrame(frame)
        save_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        save_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(save_card, text="اسم التخطيط:").grid(
            row=0, column=0, padx=15, pady=15)
        ctk.CTkEntry(save_card, textvariable=self.var_lname).grid(
            row=0, column=1, sticky="ew", padx=10, pady=15)
        ctk.CTkButton(save_card, text="💾 حفظ", command=self._save_layout).grid(
            row=0, column=2, padx=15, pady=15)

        # restore/delete
        restore_card = ctk.CTkFrame(frame)
        restore_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        restore_card.grid_columnconfigure(0, weight=1)

        self.cmb = ctk.CTkOptionMenu(restore_card, values=[])
        self.cmb.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        ctk.CTkButton(restore_card, text="📂 استعادة", command=self._restore_layout).grid(
            row=0, column=1, padx=(0, 10), pady=15)
        ctk.CTkButton(restore_card, text="🗑 حذف", command=self._delete_layout).grid(
            row=0, column=2, padx=(0, 15), pady=15)

        # import/export
        io_card = ctk.CTkFrame(frame)
        io_card.grid(row=2, column=0, sticky="ew")
        ctk.CTkButton(io_card, text="⬇ تصدير JSON", command=self._export_layouts).grid(
            row=0, column=0, padx=15, pady=15)
        ctk.CTkButton(io_card, text="⬆ استيراد JSON", command=self._import_layouts).grid(
            row=0, column=1, padx=(0, 15), pady=15)

        self._reload_layout_list()

    def _build_display_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["display"] = frame
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkSwitch(
            frame,
            text="✅ حفظ/استعادة تلقائية عند تغيّر الدقة",
            variable=self._auto_save_res,
        ).grid(row=0, column=0, sticky="w", padx=15, pady=15)

        self._res_lbl = ctk.CTkLabel(
            frame,
            text=self._res_key(self._res),
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        )
        self._res_lbl.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 15))
        ctk.CTkButton(
            row,
            text="💾 حفظ تخطيط هذه الدقة",
            command=lambda: self._save_resolution_layout(self.ctl.work_area()),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            row,
            text="📂 استعادة تخطيط هذه الدقة",
            command=lambda: self._try_restore_resolution_layout(self.ctl.work_area()),
        ).grid(row=0, column=1, padx=4)

    def _build_settings_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["settings"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # theme
        theme_card = ctk.CTkFrame(frame)
        theme_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        theme_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            theme_card,
            text="المظهر",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        self.theme_cmb = ctk.CTkOptionMenu(
            theme_card,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            command=self._on_theme_change,
        )
        self.theme_cmb.grid(row=1, column=0, sticky="w", padx=15, pady=(5, 15))

        # hotkeys
        hotkeys_card = ctk.CTkFrame(frame)
        hotkeys_card.grid(row=1, column=0, sticky="ew")
        hotkeys_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hotkeys_card,
            text="اختصارات الكيبورد",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        hotkeys_text = (
            "Ctrl+Alt+S    فتح البرنامج\n"
            "Ctrl+Alt+H    إخفاء/إظهار النافذة\n"
            "Ctrl+Alt+R    استعادة تخطيط الدقة\n"
            "Ctrl+Alt+W    ترتيب موجة\n"
            "Ctrl+Alt+P    ترتيب حلزون"
        )
        ctk.CTkLabel(
            hotkeys_card,
            text=hotkeys_text,
            justify="right",
            anchor="e",
            font=ctk.CTkFont("Consolas", 14),
        ).grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 15))

    def _on_theme_change(self, choice):
        key = choice.lower()
        self.settings.set("theme", key)
        self._apply_theme(key)
        self._set_status(f"✅ تم تطبيق المظهر: {choice}")

    # ==================================================================
    #  Icon list helpers
    # ==================================================================
    def _select(self, idx, only=False):
        if only:
            self.selection = {idx}
        else:
            self.selection.add(idx)
        self._on_select()
        self._draw_map()

    def _clear_selection(self):
        self.selection.clear()
        self._on_select()
        self._draw_map()

    # ==================================================================
    #  Core backend (kept/reimplemented)
    # ==================================================================
    def _set_status(self, msg):
        self.status.set(msg)
        self.update_idletasks()

    def _res_key(self, area):
        return f"auto_{area[2]}x{area[3]}"

    def refresh_icons(self):
        try:
            self._set_status("⏳ جارٍ قراءة الأيقونات…")
            self.icons = self.ctl.list_icons()
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))
            self._set_status("تعذّرت قراءة الأيقونات")
            return
        self._compute_map_bbox()
        self._load_icon_images()
        self._draw_map()
        cur = self.ctl.get_icon_size()
        self.lbl_size.configure(
            text=f"حجم الأيقونات: {cur if cur else 'غير معروف'} بكسل")
        self._res_lbl.configure(text=self._res_key(self.ctl.work_area()))
        self._set_status(f"✅ {len(self.icons)} أيقونة")

    def _compute_map_bbox(self):
        if not self.icons:
            self.map_bbox = self.area
            return
        xs = [ic["x"] for ic in self.icons]
        ys = [ic["y"] for ic in self.icons]
        pad = 60
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        # تأكد من تضمين مساحة العمل أيضًا
        wx, wy, ww, wh = self.area
        min_x = min(min_x, wx)
        min_y = min(min_y, wy)
        max_x = max(max_x, wx + ww)
        max_y = max(max_y, wy + wh)
        self.map_bbox = (min_x - pad, min_y - pad, max_x + pad, max_y + pad)
        # اجعل أبعاد الخريطة بنفس نسبة شاشة سطح المكتب الفعلية
        wx, wy, ww, wh = self.area
        self.map_h = max(500, int(self.map_w * wh / max(1, ww)))
        if hasattr(self, "canvas"):
            self.canvas.config(width=self.map_w, height=self.map_h)

    def _load_icon_images(self):
        self.icon_photos = {}
        size = max(16, min(96, self.preview_size.get()))
        for ic in self.icons:
            path = _display_name_to_path(ic["name"])
            img = _get_file_icon(path, size=size) if path else None
            if img is None:
                img = Image.new("RGBA", (size, size), (79, 195, 247, 255))
            self.icon_photos[ic["i"]] = ImageTk.PhotoImage(img)

    def _draw_map(self):
        c = self.canvas
        c.delete("all")
        bx, by, bx2, by2 = self.map_bbox
        bw = max(1, bx2 - bx)
        bh = max(1, by2 - by)
        # نسبة ثابتة بنفس شكل الشاشة، مع مراعاة وضع الإطار في المنتصف
        s = min(self.map_w / bw, self.map_h / bh)
        off_x = (self.map_w - bw * s) / 2
        off_y = (self.map_h - bh * s) / 2
        self._scale = s
        self._map_offset = (off_x, off_y)
        for ic in self.icons:
            x = (ic["x"] - bx) * s + off_x
            y = (ic["y"] - by) * s + off_y
            photo = self.icon_photos.get(ic["i"])
            w = h = 10
            if photo:
                w, h = photo.width(), photo.height()
                c.create_image(x, y, image=photo, anchor="nw",
                               tags=f"ic{ic['i']}")
            else:
                color = "#f9a825" if ic["i"] in self.selection else "#4fc3f7"
                c.create_rectangle(x, y, x + w, y + h, fill=color,
                                   outline="", tags=f"ic{ic['i']}")
            if ic["i"] in self.selection:
                c.create_rectangle(x - 2, y - 2, x + w + 2, y + h + 2,
                                   outline="#f9a825", width=2,
                                   tags=f"sel{ic['i']}")

    def _selected_index(self):
        if not self.selection:
            return None
        return min(self.selection)

    def _on_select(self, _evt=None):
        i = self._selected_index()
        if i is None or i >= len(self.icons):
            return
        ic = self.icons[i]
        self.var_x.set(ic["x"])
        self.var_y.set(ic["y"])

    def _move_icon(self, i, x, y):
        self.ctl.set_position(i, x, y)
        if i < len(self.icons):
            self.icons[i]["x"], self.icons[i]["y"] = x, y
        self._draw_map()

    def _move_to_xy(self):
        if not self.selection:
            messagebox.showinfo("تنبيه", "اختر أيقونة من القائمة أولًا.")
            return
        x, y = self.var_x.get(), self.var_y.get()
        base = self.icons[min(self.selection)]
        dx, dy = x - base["x"], y - base["y"]
        for idx in self.selection:
            ic = self.icons[idx]
            self._move_icon(idx, ic["x"] + dx, ic["y"] + dy)
        self.ctl.refresh_view()
        self._set_status(f"📍 نُقلت الأيقونات إلى ({x}, {y})")

    def _nudge(self, dx, dy):
        if not self.selection:
            messagebox.showinfo("تنبيه", "اختر أيقونة من القائمة أولًا.")
            return
        step = self.var_step.get()
        for i in list(self.selection):
            ic = self.icons[i]
            self._move_icon(i, ic["x"] + dx * step, ic["y"] + dy * step)
        self.ctl.refresh_view()

    def _map_to_desktop(self, mx, my):
        s = self._scale
        off_x, off_y = self._map_offset
        bx, by = self.map_bbox[0], self.map_bbox[1]
        return int((mx - off_x) / s + bx), int((my - off_y) / s + by)

    def _icon_at(self, mx, my):
        s = self._scale
        off_x, off_y = self._map_offset
        bx, by = self.map_bbox[0], self.map_bbox[1]
        for ic in self.icons:
            x = (ic["x"] - bx) * s + off_x
            y = (ic["y"] - by) * s + off_y
            photo = self.icon_photos.get(ic["i"])
            w = photo.width() if photo else 10
            h = photo.height() if photo else 10
            if x <= mx <= x + w and y <= my <= y + h:
                return ic["i"]
        return None

    def _map_press(self, evt):
        i = self._icon_at(evt.x, evt.y)
        if i is not None:
            self._select(i, only=True)
            self.drag_index = i
        else:
            if self.selection:
                x, y = self._map_to_desktop(evt.x, evt.y)
                base = self.icons[min(self.selection)]
                dx, dy = x - base["x"], y - base["y"]
                for idx in self.selection:
                    ic = self.icons[idx]
                    self._move_icon(idx, ic["x"] + dx, ic["y"] + dy)
                self.ctl.refresh_view()

    def _map_drag(self, evt):
        if self.drag_index is not None and self.selection:
            x, y = self._map_to_desktop(evt.x, evt.y)
            base = self.icons[self.drag_index]
            dx, dy = x - base["x"], y - base["y"]
            for idx in self.selection:
                ic = self.icons[idx]
                self._move_icon(idx, ic["x"] + dx, ic["y"] + dy)

    def _map_release(self, _evt):
        if self.drag_index is not None:
            self.drag_index = None
            self.ctl.refresh_view()

    def _apply_size(self):
        if self._size_busy:
            return
        target = self.var_size.get()
        self._size_busy = True
        self.btn_size.configure(state="disabled")

        def worker():
            err = None
            try:
                final = self.ctl.set_icon_size(target)
                self.after(0, lambda: self.lbl_size.configure(
                    text=f"حجم الأيقونات: {final if final else 'غير معروف'} بكسل"))
            except RuntimeError as exc:
                err = str(exc)
            finally:
                def done():
                    self._size_busy = False
                    self.btn_size.configure(state="normal")
                    if err:
                        messagebox.showwarning("تعذّر الضبط الدقيق", err)
                    self._set_status("✅ تم ضبط حجم الأيقونات")
                self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _size_step(self, bigger):
        try:
            self.ctl.nudge_icon_size(bigger)
            cur = self.ctl.get_icon_size()
            self.lbl_size.configure(
                text=f"حجم الأيقونات: {cur if cur else 'غير معروف'} بكسل")
            self.var_size.set(cur or self.var_size.get())
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
        self.btn_hide.configure(
            text="👁 إظهار الأيقونات" if self.hidden else "🙈 إخفاء الأيقونات")
        self._set_status("🙈 الأيقونات مخفية" if self.hidden else "👁 الأيقونات ظاهرة")

    # ---------------- Layouts ----------------
    def _reload_layout_list(self):
        names = sorted(self.store.data.keys())
        self.cmb.configure(values=names)
        if names:
            if self.cmb.get() not in names:
                self.cmb.set(names[0])
        else:
            self.cmb.set("")

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

    # ---------------- Resolution ----------------
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
            self._res_lbl.configure(text=self._res_key(new_area))
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
