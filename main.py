import sys
import os
import json
import struct
import ctypes
import ctypes.wintypes
import time
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFrame, QSizePolicy,
    QDialog, QLineEdit, QGridLayout, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

# ─────────────────────────────────────────────────────────────
#  Paths & Config
# ─────────────────────────────────────────────────────────────
BASE_DIR    = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"

# ─────────────────────────────────────────────────────────────
#  Game constants
#  Each stat uses different integer values in memory:
#    Health:   0 = None,  5 = Large
#    Stamina:  0 = None,  2 = Large
#    Attack:   0 = None,  1 = Small,  2 = Medium,  3 = Large
#    Defense:  0 = None,  1 = Small,  2 = Medium,  3 = Large
#    Elemental:0 = None,  1 = Small,  2 = Medium,  3 = Large
#  Skills: -1=none, 2=Heroics, 6=BlackBelt, 26=Lander,
#          31=Bombardier, 34=Groomer, 36=Acrobat, 39=Booster
# ─────────────────────────────────────────────────────────────

BOOST_OPTIONS_HEALTH   = [(0,"None"), (5,"Large")]
BOOST_OPTIONS_STAMINA  = [(0,"None"), (2,"Large")]
BOOST_OPTIONS_ATTACK   = [(0,"None"), (1,"Small"), (2,"Medium"), (3,"Large")]
BOOST_OPTIONS_DEFENSE  = [(0,"None"), (1,"Small"), (2,"Medium"), (3,"Large")]
BOOST_OPTIONS_ELEMENTAL= [(0,"None"), (1,"Small"), (2,"Medium"), (3,"Large")]

BOOST_NAMES = {0:"None", 1:"Small", 2:"Medium", 3:"Large", 5:"Large"}

# Per-stat display names (values mean different things per stat)
HEALTH_NAMES   = {0:"None", 5:"Large"}
STAMINA_NAMES  = {0:"None", 2:"Large"}
ATTACK_NAMES   = {0:"None", 1:"Small", 2:"Medium", 3:"Large"}
DEFENSE_NAMES  = {0:"None", 1:"Small", 2:"Medium", 3:"Large"}
ELEMENTAL_NAMES= {0:"None", 1:"Small", 2:"Medium", 3:"Large"}

SKILL_OPTIONS = [
    (-1, "(none)"),
    (0,  "Felyne Polisher"),
    (1,  "Felyne Rider"),
    (2,  "Felyne Heroics"),
    (3,  "Felyne Carver (Hi)"),
    (4,  "Felyne Carver (Lo)"),
    (5,  "Felyne Medic"),
    (6,  "Felyne Black Belt"),
    (7,  "Felyne Pyro"),
    (8,  "Felyne Specialist"),
    (9,  "Felyne Defender (Hi)"),
    (10, "Felyne Defender (Lo)"),
    (11, "Felyne Harvester"),
    (12, "Felyne Sharpshooter"),
    (13, "Lucky Cat"),
    (14, "Felyne Deflector"),
    (15, "Felyne Escape Artist"),
    (16, "Felyne Sprinter"),
    (17, "Felynebacker"),
    (18, "Felyne Weakener"),
    (19, "Felyne Exchanger"),
    (20, "Felyne Riser (Hi)"),
    (21, "Felyne Riser (Lo)"),
    (22, "Felyne Temper"),
    (23, "Felyne Cliffhanger"),
    (24, "Felyne Gripper"),
    (25, "Felyne Iron Carver"),
    (26, "Felyne Lander"),
    (27, "Felyne Bulldozer"),
    (28, "Felyne Foodie"),
    (29, "Felyne Slugger"),
    (30, "Felyne Fat Cat"),
    (31, "Felyne Bombardier"),
    (32, "Felyne Moxie"),
    (33, "Felyne Dungmaster"),
    (34, "Felyne Groomer"),
    (35, "Felyne Fur Coating"),
    (36, "Felyne Acrobat"),
    (37, "Felyne Gamechanger"),
    (38, "Felyne Trainer"),
    (39, "Felyne Booster"),
    (40, "Felyne Feet"),
    (41, "Felyne Fisher"),
    (42, "Cool Cat"),
    (43, "Felyne Insurance"),
    (44, "Felyne Provoker"),
    (45, "Felyne Parting Gift"),
    (46, "Felyne Researcher"),
    (47, "Felyne Weathercat"),
    (48, "Felyne Cleats"),
    (49, "Felyne Tailor"),
    (50, "Felyne Safeguard"),
    (51, "Felyne Gardener"),
    (52, "Felyne Scavenger"),
    (53, "Felyne Zoomaster"),
    (54, "Felyne Biologist"),
    (55, "Felyne Macrozoologist"),
    (56, "Felyne Microzoologist"),
]
SKILL_NAMES = {val: label for val, label in SKILL_OPTIONS}

# Memory field order (sequential 4-byte ints from food base address)
FIELD_ORDER = [
    "healthType",    # +0x00
    "staminaType",   # +0x04
    "attackType",    # +0x08
    "defenseType",   # +0x0C
    "elementalType", # +0x10
    "skill1",        # +0x14
    "skill2",        # +0x18
    "skill3",        # +0x1C
]

DEFAULT_CONFIG = {
    "loadouts": [
        {"name":"Heroics",    "healthType":0,"staminaType":2,"attackType":3,"defenseType":0,"elementalType":0,"skill1":2, "skill2":39,"skill3":26},
        {"name":"Groomer",    "healthType":5,"staminaType":2,"attackType":3,"defenseType":0,"elementalType":0,"skill1":34,"skill2":39,"skill3":6},
        {"name":"Bombardier", "healthType":5,"staminaType":2,"attackType":3,"defenseType":0,"elementalType":0,"skill1":31,"skill2":39,"skill3":26},
        {"name":"Acrobat",    "healthType":5,"staminaType":2,"attackType":3,"defenseType":0,"elementalType":0,"skill1":36,"skill2":39,"skill3":6},
    ]
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            cfg.setdefault("loadouts", DEFAULT_CONFIG["loadouts"])
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

# ─────────────────────────────────────────────────────────────
#  Windows memory API (pure ctypes, no pymem)
# ─────────────────────────────────────────────────────────────
PROCESS_ALL_ACCESS  = 0x1F0FFF
MEM_COMMIT          = 0x1000
PAGE_NOACCESS       = 0x01
PAGE_GUARD          = 0x100
TH32CS_SNAPPROCESS  = 0x00000002
TH32CS_SNAPMODULE   = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize",              ctypes.wintypes.DWORD),
        ("cntUsage",            ctypes.wintypes.DWORD),
        ("th32ProcessID",       ctypes.wintypes.DWORD),
        ("th32DefaultHeapID",   ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID",        ctypes.wintypes.DWORD),
        ("cntThreads",          ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase",      ctypes.c_long),
        ("dwFlags",             ctypes.wintypes.DWORD),
        ("szExeFile",           ctypes.c_char * 260),
    ]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress",       ctypes.c_void_p),
        ("AllocationBase",    ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize",        ctypes.c_size_t),
        ("State",             ctypes.wintypes.DWORD),
        ("Protect",           ctypes.wintypes.DWORD),
        ("Type",              ctypes.wintypes.DWORD),
    ]

def get_pid(process_name: str):
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap:
        return None
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    pid = None
    try:
        if kernel32.Process32First(snap, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.decode(errors="ignore").lower() == process_name.lower():
                    pid = entry.th32ProcessID
                    break
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return pid

def open_proc(pid):
    h = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    return h if h else None

def read_mem(handle, addr, size) -> bytes:
    buf = ctypes.create_string_buffer(size)
    n   = ctypes.c_size_t(0)
    kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    return bytes(buf[:n.value])

def write_int32(handle, addr, value):
    data    = struct.pack("<i", value)
    written = ctypes.c_size_t(0)
    ok = kernel32.WriteProcessMemory(handle, ctypes.c_void_p(addr),
                                      data, 4, ctypes.byref(written))
    return ok and written.value == 4

def read_int32(handle, addr) -> int:
    data = read_mem(handle, addr, 4)
    if len(data) < 4:
        return None
    return struct.unpack("<i", data)[0]

# ─────────────────────────────────────────────────────────────
#  AOB scan
#  We scan for the static 8-byte anchor that sits immediately
#  BEFORE the food struct (confirmed identical across sessions):
#    38 8F 11 43 01 00 00 00
#  Health Type address = anchor_address + 8
# ─────────────────────────────────────────────────────────────
# Static offset of player_data pointer from MonsterHunterWorld.exe base
# MonsterHunterWorld.exe + 0x500CDA0 -> pointer -> +0x80 -> +0x7D20 -> +0x181 + 0x8
PLAYER_DATA_OFFSET = 0x500CDA0

def read_qword(handle, addr) -> int:
    """Read an 8-byte unsigned integer (pointer)."""
    data = read_mem(handle, addr, 8)
    if len(data) < 8:
        return None
    return struct.unpack("<Q", data)[0]

def get_module_base(pid: int, module_name: str) -> int:
    """Get the base address of a loaded module by name."""
    class MODULEENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize",        ctypes.wintypes.DWORD),
            ("th32ModuleID",  ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("GlblcntUsage",  ctypes.wintypes.DWORD),
            ("ProccntUsage",  ctypes.wintypes.DWORD),
            ("modBaseAddr",   ctypes.POINTER(ctypes.c_byte)),
            ("modBaseSize",   ctypes.wintypes.DWORD),
            ("hModule",       ctypes.wintypes.HMODULE),
            ("szModule",      ctypes.c_char * 256),
            ("szExePath",     ctypes.c_char * 260),
        ]
    TH32CS_SNAPMODULE   = 0x00000008
    TH32CS_SNAPMODULE32 = 0x00000010
    snap = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if not snap:
        return 0
    entry = MODULEENTRY32()
    entry.dwSize = ctypes.sizeof(MODULEENTRY32)
    base = 0
    try:
        if kernel32.Module32First(snap, ctypes.byref(entry)):
            while True:
                if entry.szModule.decode(errors="ignore").lower() == module_name.lower():
                    base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                    break
                if not kernel32.Module32Next(snap, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return base

# ─────────────────────────────────────────────────────────────
#  MHW memory interface
# ─────────────────────────────────────────────────────────────
class MHWMemory:
    def __init__(self):
        self.handle    = None
        self.pid       = None
        self.food_addr = 0   # address of Health Type (first field)

    def is_attached(self):
        return self.handle is not None and self.food_addr != 0

    def attach(self) -> tuple:
        # Close any existing handle
        self.detach()

        pid = get_pid("MonsterHunterWorld.exe")
        if not pid:
            return False, "MonsterHunterWorld.exe not found.\nLaunch the game first."

        handle = open_proc(pid)
        if not handle:
            return False, "Failed to open process.\nTry running the app as Administrator."

        self.pid    = pid
        self.handle = handle
        return True, "Attached to process."

    def find_food_struct(self) -> tuple:
        if not self.handle:
            return False, "Not attached to process."

        exe_base = get_module_base(self.pid, "MonsterHunterWorld.exe")
        if not exe_base:
            return False, "Could not find MonsterHunterWorld.exe module."

        # Full pointer chain (from CT offsets, read bottom to top):
        # [exe_base + 0x500CDA0] -> p1
        # [p1 + 0x80]            -> p2
        # [p2 + 0x7D20]          -> p3
        # [p3 + 0x18]            -> p4
        # p4 + 0x8               = Health Type address
        try:
            addr0 = exe_base + 0x500CDA0
            p1 = read_qword(self.handle, addr0)
            if not p1 or p1 == 0:
                return False, "Pointer step 1 failed.\nLoad into the hub or a quest first."

            p2 = read_qword(self.handle, p1 + 0x80)
            if not p2 or p2 == 0:
                return False, "Pointer step 2 failed.\nLoad into the hub or a quest first."

            p3 = read_qword(self.handle, p2 + 0x7D20)
            if not p3 or p3 == 0:
                return False, "Pointer step 3 failed.\nLoad into the hub or a quest first."

            p4 = read_qword(self.handle, p3 + 0x18)
            if not p4 or p4 == 0:
                return False, "Pointer step 4 failed.\nLoad into the hub or a quest first."

            self.food_addr = p4 + 0x8
            return True, "Food struct found. Ready to apply loadouts."

        except Exception as e:
            return False, f"Pointer chain error: {e}"


    def apply_loadout(self, loadout: dict) -> tuple:
        if not self.handle:
            return False, "Not attached — click Attach first."
        if not self.food_addr:
            ok, msg = self.find_food_struct()
            if not ok:
                return False, msg

        failed = []
        for i, field in enumerate(FIELD_ORDER):
            val  = loadout.get(field, 0)
            addr = self.food_addr + i * 4
            if not write_int32(self.handle, addr, val):
                failed.append(field)

        if failed:
            # struct may have moved (zone change), rescan and retry
            self.food_addr = 0
            ok, msg = self.find_food_struct()
            if not ok:
                return False, f"Lost food struct: {msg}"
            for i, field in enumerate(FIELD_ORDER):
                write_int32(self.handle, self.food_addr + i * 4, loadout.get(field, 0))

        return True, f"Applied: {loadout.get('name','?')}"

    def detach(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle    = None
            self.food_addr = 0
            self.pid       = None

# ─────────────────────────────────────────────────────────────
#  Status thread
# ─────────────────────────────────────────────────────────────
class StatusThread(QThread):
    updated = pyqtSignal(bool)
    def run(self):
        while not self.isInterruptionRequested():
            self.updated.emit(get_pid("MonsterHunterWorld.exe") is not None)
            time.sleep(3)

# ─────────────────────────────────────────────────────────────
#  Attach thread — runs AOB scan off the main thread
# ─────────────────────────────────────────────────────────────
class AttachThread(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, mem, parent=None):
        super().__init__(parent)
        self.mem = mem

    def run(self):
        ok, msg = self.mem.attach()
        if not ok:
            self.done.emit(False, msg)
            return
        ok2, msg2 = self.mem.find_food_struct()
        self.done.emit(ok2, msg2)

# ─────────────────────────────────────────────────────────────
#  Loadout editor
# ─────────────────────────────────────────────────────────────
DEFAULT_LD = {"name":"New Loadout","healthType":0,"staminaType":0,
              "attackType":0,"defenseType":0,"elementalType":0,
              "skill1":-1,"skill2":-1,"skill3":-1}

class LoadoutEditor(QDialog):
    def __init__(self, loadout=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Loadout")
        self.setMinimumWidth(420)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        self._build(loadout or dict(DEFAULT_LD))

    def _combo(self, options, current):
        c = QComboBox()
        for val, label in options:
            c.addItem(label, val)
        for i in range(c.count()):
            if c.itemData(i) == current:
                c.setCurrentIndex(i)
                break
        return c

    def _build(self, d):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20,20,20,20)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(d["name"])
        name_row.addWidget(self.name_edit)
        lay.addLayout(name_row)

        boost_grp = QGroupBox("Food Boosts")
        bg = QGridLayout(boost_grp)
        self.boost_combos = {}
        boost_fields = [
            ("healthType",    "Health",    BOOST_OPTIONS_HEALTH),
            ("staminaType",   "Stamina",   BOOST_OPTIONS_STAMINA),
            ("attackType",    "Attack",    BOOST_OPTIONS_ATTACK),
            ("defenseType",   "Defense",   BOOST_OPTIONS_DEFENSE),
            ("elementalType", "Elemental", BOOST_OPTIONS_ELEMENTAL),
        ]
        for r,(key,label,opts) in enumerate(boost_fields):
            bg.addWidget(QLabel(label+":"), r, 0)
            c = self._combo(opts, d[key])
            self.boost_combos[key] = c
            bg.addWidget(c, r, 1)
        lay.addWidget(boost_grp)

        skill_grp = QGroupBox("Felyne Skills")
        sg = QGridLayout(skill_grp)
        self.skill_combos = {}
        for r,key in enumerate(["skill1","skill2","skill3"]):
            sg.addWidget(QLabel(f"Slot {r+1}:"), r, 0)
            c = self._combo(SKILL_OPTIONS, d[key])
            self.skill_combos[key] = c
            sg.addWidget(c, r, 1)
        lay.addWidget(skill_grp)

        btns = QHBoxLayout()
        save_btn   = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        lay.addLayout(btns)

    def get_loadout(self):
        ld = {"name": self.name_edit.text().strip() or "Unnamed"}
        for key,c in self.boost_combos.items():
            ld[key] = c.currentData()
        for key,c in self.skill_combos.items():
            ld[key] = c.currentData()
        return ld

# ─────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────
STYLE = """
    QMainWindow, QDialog { background: #0f0f13; }
    QWidget { background: #0f0f13; color: #e8e0d0; font-family: 'Segoe UI'; font-size: 13px; }
    QGroupBox { border: 1px solid #2a2a35; border-radius: 6px; margin-top: 10px;
                padding-top: 8px; color: #8a7f6e; font-size: 11px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; }
    QLabel { color: #a09880; background: transparent; }
    QLabel#title   { font-size: 22px; font-weight: bold; color: #e8c97a; letter-spacing: 2px; }
    QLabel#sub     { font-size: 11px; color: #5a5248; letter-spacing: 3px; }
    QLabel#ok      { color: #4caf7d; font-size: 12px; }
    QLabel#bad     { color: #cf6679; font-size: 12px; }
    QLabel#info    { color: #7a9ecf; font-size: 11px; }
    QComboBox { background: #1a1a22; border: 1px solid #2a2a35; border-radius: 4px;
                padding: 6px 10px; color: #e8e0d0; min-height: 28px; }
    QComboBox:hover { border-color: #e8c97a; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox QAbstractItemView { background: #1a1a22; border: 1px solid #2a2a35;
        selection-background-color: #2a2a1a; selection-color: #e8c97a; }
    QPushButton { background: #1a1a22; border: 1px solid #2a2a35; border-radius: 4px;
                  padding: 8px 16px; color: #a09880; min-height: 32px; }
    QPushButton:hover { border-color: #e8c97a; color: #e8e0d0; }
    QPushButton:pressed { background: #252530; }
    QPushButton#primary { background: #2a2210; border: 1px solid #e8c97a; color: #e8c97a; font-weight: bold; }
    QPushButton#primary:hover { background: #3a3218; }
    QPushButton#danger  { border-color: #cf6679; color: #cf6679; }
    QPushButton#danger:hover { background: #2a1520; }
    QPushButton#auto_on { background: #1a2a1a; border: 1px solid #4caf7d; color: #4caf7d; font-weight: bold; }
    QLineEdit { background: #1a1a22; border: 1px solid #2a2a35; border-radius: 4px;
                padding: 6px 10px; color: #e8e0d0; }
    QLineEdit:focus { border-color: #e8c97a; }
    QFrame#div  { background: #2a2a35; max-height: 1px; }
    QFrame#card { background: #14141c; border: 1px solid #1e1e28; border-radius: 8px; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.mem = MHWMemory()
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_apply)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._start_status()

    def _div(self):
        f = QFrame(); f.setObjectName("div"); return f

    def _build_ui(self):
        self.setWindowTitle("MHW Food Loadouts")
        self.setMinimumSize(460, 600)
        self.resize(460, 640)

        c = QWidget()
        self.setCentralWidget(c)
        root = QVBoxLayout(c)
        root.setContentsMargins(24,24,24,24)
        root.setSpacing(0)

        # Header
        t = QLabel("FOOD LOADOUTS"); t.setObjectName("title")
        s = QLabel("MONSTER HUNTER WORLD"); s.setObjectName("sub")
        root.addWidget(t); root.addWidget(s)
        root.addSpacing(16)

        # Status card
        card = QFrame(); card.setObjectName("card")
        cl = QHBoxLayout(card); cl.setContentsMargins(16,12,16,12)
        self.lbl_mhw  = QLabel("● MHW: Not running"); self.lbl_mhw.setObjectName("bad")
        self.lbl_att  = QLabel("● Not attached");     self.lbl_att.setObjectName("bad")
        cl.addWidget(self.lbl_mhw); cl.addStretch(); cl.addWidget(self.lbl_att)
        root.addWidget(card); root.addSpacing(12)

        # Attach
        self.btn_attach = QPushButton("Attach to Game")
        self.btn_attach.setObjectName("primary")
        self.btn_attach.clicked.connect(self._attach)
        root.addWidget(self.btn_attach); root.addSpacing(16)

        root.addWidget(self._div()); root.addSpacing(16)

        # Loadout selector
        lbl = QLabel("SELECT LOADOUT"); lbl.setObjectName("sub")
        root.addWidget(lbl); root.addSpacing(8)
        self.combo = QComboBox()
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.currentIndexChanged.connect(self._update_preview)
        root.addWidget(self.combo); root.addSpacing(8)

        # Preview card
        self.prev_frame = QFrame(); self.prev_frame.setObjectName("card")
        self.prev_layout = QGridLayout(self.prev_frame)
        self.prev_layout.setContentsMargins(16,12,16,12)
        self.prev_layout.setSpacing(6)
        root.addWidget(self.prev_frame); root.addSpacing(12)

        # Apply row
        ar = QHBoxLayout()
        self.btn_apply = QPushButton("Apply Loadout")
        self.btn_apply.setObjectName("primary")
        self.btn_apply.setMinimumHeight(40)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_auto = QPushButton("Auto-Apply: OFF")
        self.btn_auto.setMinimumHeight(40)
        self.btn_auto.setMinimumWidth(160)
        self.btn_auto.clicked.connect(self._toggle_auto)
        ar.addWidget(self.btn_apply); ar.addWidget(self.btn_auto)
        root.addLayout(ar); root.addSpacing(16)

        root.addWidget(self._div()); root.addSpacing(16)

        # Manage
        ml = QLabel("MANAGE LOADOUTS"); ml.setObjectName("sub")
        root.addWidget(ml); root.addSpacing(8)
        mr = QHBoxLayout()
        bn = QPushButton("+ New")
        be = QPushButton("✎ Edit")
        bd = QPushButton("✕ Delete"); bd.setObjectName("danger")
        bn.clicked.connect(self._new); be.clicked.connect(self._edit); bd.clicked.connect(self._delete)
        mr.addWidget(bn); mr.addWidget(be); mr.addWidget(bd)
        root.addLayout(mr); root.addStretch()

        root.addWidget(self._div()); root.addSpacing(8)
        self.lbl_status = QLabel("Launch MHW, then click Attach to Game.")
        self.lbl_status.setObjectName("info")
        root.addWidget(self.lbl_status)

        self._refresh_combo()

    # ── Combo ─────────────────────────────────────────────────
    def _refresh_combo(self, keep=0):
        self.combo.blockSignals(True)
        self.combo.clear()
        for ld in self.cfg["loadouts"]:
            self.combo.addItem(ld["name"])
        self.combo.setCurrentIndex(min(keep, max(0, self.combo.count()-1)))
        self.combo.blockSignals(False)
        self._update_preview()

    def _current(self):
        i = self.combo.currentIndex()
        return self.cfg["loadouts"][i] if 0 <= i < len(self.cfg["loadouts"]) else None

    def _update_preview(self):
        while self.prev_layout.count():
            item = self.prev_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        ld = self._current()
        if not ld: return
        def v(text, gold=False):
            l = QLabel(text)
            l.setStyleSheet(f"color:{'#e8c97a' if gold else '#e8e0d0'};background:transparent;")
            return l
        def d(text):
            l = QLabel(text)
            l.setStyleSheet("color:#5a5248;background:transparent;font-size:11px;")
            return l
        boosts = [("Health",   HEALTH_NAMES.get(ld["healthType"],"None")),
                  ("Stamina",  STAMINA_NAMES.get(ld["staminaType"],"None")),
                  ("Attack",   ATTACK_NAMES.get(ld["attackType"],"None")),
                  ("Defense",  DEFENSE_NAMES.get(ld["defenseType"],"None")),
                  ("Elemental",ELEMENTAL_NAMES.get(ld["elementalType"],"None"))]
        skills = [("Skill 1", SKILL_NAMES.get(ld["skill1"],"?")),
                  ("Skill 2", SKILL_NAMES.get(ld["skill2"],"?")),
                  ("Skill 3", SKILL_NAMES.get(ld["skill3"],"?"))]
        for r,(k,val) in enumerate(boosts):
            self.prev_layout.addWidget(d(k), r, 0)
            self.prev_layout.addWidget(v(val, val!="None"), r, 1)
        for r,(k,val) in enumerate(skills):
            self.prev_layout.addWidget(d(k), r, 2)
            self.prev_layout.addWidget(v(val, val!="(none)"), r, 3)

    # ── Attach ────────────────────────────────────────────────
    def _attach(self):
        self.btn_attach.setEnabled(False)
        self.btn_attach.setText("Scanning memory...")
        self.lbl_status.setText("Attaching and scanning — please wait...")

        self._attach_thread = AttachThread(self.mem, self)
        self._attach_thread.done.connect(self._on_attach_done)
        self._attach_thread.start()

    def _on_attach_done(self, ok, msg):
        self.btn_attach.setEnabled(True)
        self.btn_attach.setText("Attach to Game")
        self.lbl_status.setText(msg)
        if ok:
            self.lbl_att.setText("● Attached ✓")
            self.lbl_att.setObjectName("ok")
        else:
            self.lbl_att.setText("● Not attached")
            self.lbl_att.setObjectName("bad")
        self.lbl_att.setStyle(self.lbl_att.style())

    # ── Apply ─────────────────────────────────────────────────
    def _apply(self):
        ld = self._current()
        if not ld: return
        ok, msg = self.mem.apply_loadout(ld)
        self.lbl_status.setText(msg)

    def _toggle_auto(self):
        if self.auto_timer.isActive():
            self.auto_timer.stop()
            self.btn_auto.setText("Auto-Apply: OFF")
            self.btn_auto.setObjectName("")
            self.lbl_status.setText("Auto-apply off.")
        else:
            self.auto_timer.start(3000)
            self.btn_auto.setText("Auto-Apply: ON (3s)")
            self.btn_auto.setObjectName("auto_on")
            self.lbl_status.setText("Auto-apply on — buffs will reapply every 3s.")
        self.btn_auto.setStyle(self.btn_auto.style())

    def _auto_apply(self):
        ld = self._current()
        if ld: self.mem.apply_loadout(ld)

    # ── Loadout management ────────────────────────────────────
    def _new(self):
        dlg = LoadoutEditor(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.cfg["loadouts"].append(dlg.get_loadout())
            save_config(self.cfg)
            self._refresh_combo(len(self.cfg["loadouts"])-1)

    def _edit(self):
        i = self.combo.currentIndex(); ld = self._current()
        if not ld: return
        dlg = LoadoutEditor(loadout=ld, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.cfg["loadouts"][i] = dlg.get_loadout()
            save_config(self.cfg); self._refresh_combo(i)

    def _delete(self):
        if len(self.cfg["loadouts"]) <= 1:
            QMessageBox.warning(self, "Cannot delete", "Need at least one loadout.")
            return
        i = self.combo.currentIndex(); ld = self._current()
        if QMessageBox.question(self, "Delete", f"Delete '{ld['name']}'?",
                QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.cfg["loadouts"].pop(i)
            save_config(self.cfg); self._refresh_combo(max(0,i-1))

    # ── Status thread ─────────────────────────────────────────
    def _start_status(self):
        self._st = StatusThread(self)
        self._st.updated.connect(self._on_status)
        self._st.start()

    def _on_status(self, running):
        if running:
            self.lbl_mhw.setText("● MHW: Running")
            self.lbl_mhw.setObjectName("ok")
        else:
            self.lbl_mhw.setText("● MHW: Not running")
            self.lbl_mhw.setObjectName("bad")
            self.mem.detach()
            self.lbl_att.setText("● Not attached")
            self.lbl_att.setObjectName("bad")
            self.lbl_att.setStyle(self.lbl_att.style())
        self.lbl_mhw.setStyle(self.lbl_mhw.style())

    def closeEvent(self, event):
        self._st.requestInterruption()
        self._st.wait(1000)
        self.mem.detach()
        event.accept()

# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
