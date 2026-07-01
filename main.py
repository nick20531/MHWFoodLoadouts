import sys
import os
import json
import subprocess
import time
import threading
import winreg
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QFrame, QDialog, QLineEdit, QScrollArea, QGridLayout,
    QGroupBox, QSpinBox, QCheckBox, QSizePolicy, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QFontDatabase, QIcon

# ─────────────────────────────────────────────────────────────
#  Paths
# ─────────────────────────────────────────────────────────────
BASE_DIR   = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
CT_FILE     = BASE_DIR / "MonsterHunterWorld.CT"
LUA_BRIDGE  = BASE_DIR / "_bridge.lua"

# ─────────────────────────────────────────────────────────────
#  Data
# ─────────────────────────────────────────────────────────────
BOOST_OPTIONS_HEALTH  = [(0,"None"),(5,"Large")]
BOOST_OPTIONS_STAMINA = [(0,"None"),(2,"Large")]
BOOST_OPTIONS_ATTACK  = [(0,"None"),(1,"Small"),(2,"Medium"),(3,"Large")]
BOOST_OPTIONS_DEFAULT = [(0,"None"),(1,"Small"),(2,"Medium"),(3,"Large")]
BOOST_OPTIONS = BOOST_OPTIONS_DEFAULT  # kept for compatibility
BOOST_NAMES   = {0:"None", 1:"Small", 2:"Large", 3:"Large", 5:"Large"}
SKILL_NAMES   = {-1:"(none)", 2:"Felyne Heroics", 6:"Felyne Black Belt", 26:"Felyne Lander", 31:"Felyne Bombardier", 34:"Felyne Groomer", 39:"Felyne Booster"}
SKILL_OPTIONS = [
    (-1,"(none)"),
    (2, "Felyne Heroics"),
    (6, "Felyne Black Belt"),
    (26,"Felyne Lander"),
    (31,"Felyne Bombardier"),
    (34,"Felyne Groomer"),
    (39,"Felyne Booster"),
]

DEFAULT_LOADOUT = {
    "name":"New Loadout",
    "healthType":0,"staminaType":0,"attackType":0,
    "defenseType":0,"elementalType":0,
    "skill1":-1,"skill2":-1,"skill3":-1
}

DEFAULT_CONFIG = {
    "ce_path":"",
    "auto_apply":False,
    "auto_interval":3,
    "loadouts":[
        {"name":"Heroics","healthType":0,"staminaType":2,"attackType":3,
         "defenseType":0,"elementalType":0,"skill1":2,"skill2":39,"skill3":26}
    ]
}

# ─────────────────────────────────────────────────────────────
#  Config helpers
# ─────────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            for k,v in DEFAULT_CONFIG.items():
                cfg.setdefault(k,v)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

def find_ce_path():
    """Try to locate CE via registry or common paths."""
    common = [
        r"C:\Program Files\Cheat Engine 7.6\cheatengine-x86_64.exe",
        r"C:\Program Files (x86)\Cheat Engine 7.6\cheatengine-x86_64.exe",
        r"C:\Program Files\Cheat Engine 7.5\cheatengine-x86_64.exe",
        r"C:\Program Files (x86)\Cheat Engine 7.5\cheatengine-x86_64.exe",
        r"C:\Program Files\Cheat Engine\cheatengine-x86_64.exe",
    ]
    for p in common:
        if Path(p).exists():
            return p
    # try registry
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Cheat Engine")
        path,_ = winreg.QueryValueEx(key,"InstallDir")
        candidate = Path(path) / "cheatengine-x86_64.exe"
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return ""

# ─────────────────────────────────────────────────────────────
#  CE bridge — writes a Lua file then launches CE with --lua
# ─────────────────────────────────────────────────────────────
class CEBridge:
    def __init__(self, cfg):
        self.cfg = cfg

    def _ce_running(self):
        import psutil
        for p in psutil.process_iter(['name']):
            try:
                if 'cheatengine' in (p.info['name'] or '').lower():
                    return True
            except Exception:
                pass
        return False

    def _mhw_running(self):
        import psutil
        for p in psutil.process_iter(['name']):
            try:
                if 'monsterhunterworld' in (p.info['name'] or '').lower():
                    return True
            except Exception:
                pass
        return False

    def launch_ce_with_ct(self):
        ce = self.cfg.get("ce_path","")
        if not ce or not Path(ce).exists():
            return False, "CE path not set or not found."
        if self._ce_running():
            return True, "CE already running."
        if not CT_FILE.exists():
            return False, f"CT file not found at: {CT_FILE}"

        # Write a small autorun lua that CE will execute on startup.
        # This opens the CT and enables the Pointers entry automatically.
        autorun = Path(ce).parent / "autorun" / "_mhw_load.lua"
        autorun.parent.mkdir(exist_ok=True)
        # Use forward slashes — Lua on Windows handles them fine, avoids escape issues
        ct_path_lua  = str(CT_FILE).replace("\\", "/")
        ce_dir_lua   = str(Path(ce).parent).replace("\\", "/")
        autorun_path = ce_dir_lua + "/autorun/_mhw_load.lua"

        entries_lua = (
            '        for i = 0, al.Count-1 do\n'
            '            local rec = al.getMemoryRecord(i)\n'
            '            if rec and rec.Description == "[ACTIVATE]" then\n'
            '                rec.Active = true\n'
            '                print("[Auto] Enabled: [ACTIVATE]")\n'
            '                break\n'
            '            end\n'
            '        end\n'
            '        for i = 0, al.Count-1 do\n'
            '            local rec = al.getMemoryRecord(i)\n'
            '            if rec and rec.Description == "Marcus101RR\'s Scripts" then\n'
            '                rec.Active = true\n'
            '                print("[Auto] Enabled: Marcus101RR\'s Scripts")\n'
            '                break\n'
            '            end\n'
            '        end\n'
            '        for i = 0, al.Count-1 do\n'
            '            local rec = al.getMemoryRecord(i)\n'
            '            if rec and rec.Description == "Pointers" then\n'
            '                rec.Active = true\n'
            '                print("[Auto] Enabled: Pointers")\n'
            '                break\n'
            '            end\n'
            '        end\n'
        )
        lua_script = (
            "-- Auto-generated by MHW Food Loadouts app\n"
            "-- Suppress the copyright dialog so table loads silently\n"
            "function PostNotice() enableCompactMode = true end\n"
            "local function doLoad()\n"
            "    loadTable([[" + ct_path_lua + "]])\n"
            "    local t = createTimer(nil, false)\n"
            "    t.Interval = 15000\n"
            "    t.OnTimer = function()\n"
            "        t.Enabled = false\n"
            "        local al = getAddressList()\n"
            + entries_lua +
            "        os.remove([[" + autorun_path + "]])\n"
            "    end\n"
            "    t.Enabled = true\n"
            "end\n"
            "local init = createTimer(nil, false)\n"
            "init.Interval = 800\n"
            "init.OnTimer = function()\n"
            "    init.Enabled = false\n"
            "    doLoad()\n"
            "end\n"
            "init.Enabled = true\n"
        )
        autorun.write_text(lua_script)

        try:
            subprocess.Popen([ce])
            return True, "CE launched — CT will load automatically."
        except Exception as e:
            return False, str(e)

    def apply_loadout(self, loadout):
        # Write to temp dir — reliable location both .exe and CE Lua can find
        import tempfile
        pending = Path(tempfile.gettempdir()) / "_mhw_pending.json"
        try:
            pending.write_text(json.dumps(loadout))
            return True, "Pending file written."
        except Exception as e:
            return False, str(e)

    def status(self):
        return self._ce_running(), self._mhw_running()

# ─────────────────────────────────────────────────────────────
#  Background status thread
# ─────────────────────────────────────────────────────────────
class StatusThread(QThread):
    updated = pyqtSignal(bool, bool)
    def run(self):
        import psutil
        while not self.isInterruptionRequested():
            ce = mhw = False
            for p in psutil.process_iter(['name']):
                try:
                    n = (p.info['name'] or '').lower()
                    if 'cheatengine' in n: ce = True
                    if 'monsterhunterworld' in n: mhw = True
                except Exception:
                    pass
            self.updated.emit(ce, mhw)
            time.sleep(2)

# ─────────────────────────────────────────────────────────────
#  Loadout editor dialog
# ─────────────────────────────────────────────────────────────
class LoadoutEditor(QDialog):
    def __init__(self, loadout=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Loadout")
        self.setMinimumWidth(400)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        data = loadout or dict(DEFAULT_LOADOUT)
        self._data = dict(data)
        self._build(data)

    def _combo(self, options, current_val):
        c = QComboBox()
        for val, label in options:
            c.addItem(label, val)
        for i in range(c.count()):
            if c.itemData(i) == current_val:
                c.setCurrentIndex(i)
                break
        return c

    def _build(self, d):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20,20,20,20)

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(d["name"])
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Boost section
        boost_group = QGroupBox("Food Boosts")
        bg = QGridLayout(boost_group)
        self.boost_combos = {}
        fields = [
            ("healthType",    "Health",    BOOST_OPTIONS_HEALTH),
            ("staminaType",   "Stamina",   BOOST_OPTIONS_STAMINA),
            ("attackType",    "Attack",    BOOST_OPTIONS_ATTACK),
            ("defenseType",   "Defense",   BOOST_OPTIONS_DEFAULT),
            ("elementalType", "Elemental", BOOST_OPTIONS_DEFAULT),
        ]
        for row,(key,label,opts) in enumerate(fields):
            bg.addWidget(QLabel(label+":"), row, 0)
            c = self._combo(opts, d[key])
            self.boost_combos[key] = c
            bg.addWidget(c, row, 1)
        layout.addWidget(boost_group)

        # Skills section
        skill_group = QGroupBox("Felyne Skills")
        sg = QGridLayout(skill_group)
        self.skill_combos = {}
        for row, key in enumerate(["skill1","skill2","skill3"]):
            sg.addWidget(QLabel(f"Slot {row+1}:"), row, 0)
            c = self._combo(SKILL_OPTIONS, d[key])
            self.skill_combos[key] = c
            sg.addWidget(c, row, 1)
        layout.addWidget(skill_group)

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def get_loadout(self):
        ld = {}
        ld["name"] = self.name_edit.text().strip() or "Unnamed"
        for key, combo in self.boost_combos.items():
            ld[key] = combo.currentData()
        for key, combo in self.skill_combos.items():
            ld[key] = combo.currentData()
        return ld

# ─────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.bridge = CEBridge(self.cfg)
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._auto_apply)
        self._apply_style()
        self._build_ui()
        self._start_status_thread()
        self._check_ce_path_on_start()

    # ── Style ──────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QDialog { background: #0f0f13; }
            QWidget { background: #0f0f13; color: #e8e0d0; font-family: 'Segoe UI'; font-size: 13px; }
            QGroupBox {
                border: 1px solid #2a2a35;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 8px;
                color: #8a7f6e;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QLabel { color: #a09880; background: transparent; }
            QLabel#title {
                font-size: 22px;
                font-weight: bold;
                color: #e8c97a;
                letter-spacing: 2px;
            }
            QLabel#subtitle { font-size: 11px; color: #5a5248; letter-spacing: 3px; }
            QLabel#status_ok  { color: #4caf7d; font-size: 11px; }
            QLabel#status_bad { color: #cf6679; font-size: 11px; }
            QComboBox {
                background: #1a1a22;
                border: 1px solid #2a2a35;
                border-radius: 4px;
                padding: 6px 10px;
                color: #e8e0d0;
                min-height: 28px;
            }
            QComboBox:hover { border-color: #e8c97a; }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background: #1a1a22;
                border: 1px solid #2a2a35;
                selection-background-color: #2a2a1a;
                selection-color: #e8c97a;
            }
            QPushButton {
                background: #1a1a22;
                border: 1px solid #2a2a35;
                border-radius: 4px;
                padding: 8px 16px;
                color: #a09880;
                min-height: 32px;
            }
            QPushButton:hover { border-color: #e8c97a; color: #e8e0d0; }
            QPushButton:pressed { background: #252530; }
            QPushButton#primary {
                background: #2a2210;
                border: 1px solid #e8c97a;
                color: #e8c97a;
                font-weight: bold;
            }
            QPushButton#primary:hover { background: #3a3218; }
            QPushButton#danger { border-color: #cf6679; color: #cf6679; }
            QPushButton#danger:hover { background: #2a1520; }
            QPushButton#auto_on {
                background: #1a2a1a;
                border: 1px solid #4caf7d;
                color: #4caf7d;
                font-weight: bold;
            }
            QPushButton#auto_on:hover { background: #223022; }
            QLineEdit {
                background: #1a1a22;
                border: 1px solid #2a2a35;
                border-radius: 4px;
                padding: 6px 10px;
                color: #e8e0d0;
            }
            QLineEdit:focus { border-color: #e8c97a; }
            QFrame#divider { background: #2a2a35; max-height: 1px; }
            QFrame#card {
                background: #14141c;
                border: 1px solid #1e1e28;
                border-radius: 8px;
            }
        """)

    # ── UI ─────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("MHW Food Loadouts")
        self.setMinimumSize(480, 620)
        self.resize(480, 660)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # ── Header
        header = QVBoxLayout()
        title = QLabel("FOOD LOADOUTS")
        title.setObjectName("title")
        sub = QLabel("MONSTER HUNTER WORLD")
        sub.setObjectName("subtitle")
        header.addWidget(title)
        header.addWidget(sub)
        root.addLayout(header)
        root.addSpacing(20)

        # ── Status card
        status_card = QFrame()
        status_card.setObjectName("card")
        sc_layout = QHBoxLayout(status_card)
        sc_layout.setContentsMargins(16,12,16,12)
        self.lbl_ce  = QLabel("● Cheat Engine")
        self.lbl_mhw = QLabel("● Monster Hunter World")
        self.lbl_ce.setObjectName("status_bad")
        self.lbl_mhw.setObjectName("status_bad")
        sc_layout.addWidget(self.lbl_ce)
        sc_layout.addStretch()
        sc_layout.addWidget(self.lbl_mhw)
        root.addWidget(status_card)
        root.addSpacing(16)

        # ── Launch button
        self.btn_launch = QPushButton("Launch Cheat Engine + CT")
        self.btn_launch.setObjectName("primary")
        self.btn_launch.clicked.connect(self._launch_ce)
        root.addWidget(self.btn_launch)
        root.addSpacing(20)

        divider = QFrame()
        divider.setObjectName("divider")
        root.addWidget(divider)
        root.addSpacing(20)

        # ── Loadout selector
        sel_label = QLabel("SELECT LOADOUT")
        sel_label.setObjectName("subtitle")
        root.addWidget(sel_label)
        root.addSpacing(8)

        self.loadout_combo = QComboBox()
        self.loadout_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self.loadout_combo)
        root.addSpacing(8)

        # Loadout preview
        self.preview_card = QFrame()
        self.preview_card.setObjectName("card")
        self.preview_layout = QGridLayout(self.preview_card)
        self.preview_layout.setContentsMargins(16,12,16,12)
        self.preview_layout.setSpacing(6)
        root.addWidget(self.preview_card)
        root.addSpacing(12)

        # Apply + auto row
        apply_row = QHBoxLayout()
        self.btn_apply = QPushButton("Apply Loadout")
        self.btn_apply.setObjectName("primary")
        self.btn_apply.setMinimumHeight(40)
        self.btn_apply.clicked.connect(self._apply_loadout)
        self.btn_auto = QPushButton("Auto-Apply: OFF")
        self.btn_auto.setMinimumHeight(40)
        self.btn_auto.setMinimumWidth(160)
        self.btn_auto.clicked.connect(self._toggle_auto)
        apply_row.addWidget(self.btn_apply)
        apply_row.addWidget(self.btn_auto)
        root.addLayout(apply_row)
        root.addSpacing(20)

        divider2 = QFrame()
        divider2.setObjectName("divider")
        root.addWidget(divider2)
        root.addSpacing(20)

        # ── Manage loadouts
        manage_label = QLabel("MANAGE LOADOUTS")
        manage_label.setObjectName("subtitle")
        root.addWidget(manage_label)
        root.addSpacing(8)

        manage_row = QHBoxLayout()
        btn_new  = QPushButton("+ New")
        btn_edit = QPushButton("✎ Edit")
        btn_del  = QPushButton("✕ Delete")
        btn_del.setObjectName("danger")
        btn_new.clicked.connect(self._new_loadout)
        btn_edit.clicked.connect(self._edit_loadout)
        btn_del.clicked.connect(self._delete_loadout)
        manage_row.addWidget(btn_new)
        manage_row.addWidget(btn_edit)
        manage_row.addWidget(btn_del)
        root.addLayout(manage_row)

        root.addStretch()

        # ── Footer
        divider3 = QFrame()
        divider3.setObjectName("divider")
        root.addWidget(divider3)
        root.addSpacing(8)

        footer_row = QHBoxLayout()
        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setObjectName("subtitle")
        btn_ce_path = QPushButton("⚙ CE Path")
        btn_ce_path.setFixedWidth(90)
        btn_ce_path.clicked.connect(self._set_ce_path)
        footer_row.addWidget(self.lbl_status)
        footer_row.addStretch()
        footer_row.addWidget(btn_ce_path)
        root.addLayout(footer_row)

        self._refresh_loadout_combo()
        self.loadout_combo.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

    # ── Loadout combo ──────────────────────────────────────
    def _refresh_loadout_combo(self, keep_index=0):
        self.loadout_combo.blockSignals(True)
        self.loadout_combo.clear()
        for ld in self.cfg["loadouts"]:
            self.loadout_combo.addItem(ld["name"])
        idx = min(keep_index, self.loadout_combo.count()-1)
        self.loadout_combo.setCurrentIndex(max(0, idx))
        self.loadout_combo.blockSignals(False)
        self._update_preview()

    def _current_loadout(self):
        idx = self.loadout_combo.currentIndex()
        if 0 <= idx < len(self.cfg["loadouts"]):
            return self.cfg["loadouts"][idx]
        return None

    # ── Preview panel ──────────────────────────────────────
    def _update_preview(self):
        # clear
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ld = self._current_loadout()
        if not ld:
            return

        def make_val(text, highlight=False):
            l = QLabel(text)
            l.setStyleSheet(f"color: {'#e8c97a' if highlight else '#e8e0d0'}; background: transparent;")
            return l

        rows = [
            ("Health",    BOOST_NAMES.get(ld["healthType"],"None")),
            ("Stamina",   BOOST_NAMES.get(ld["staminaType"],"None")),
            ("Attack",    BOOST_NAMES.get(ld["attackType"],"None")),
            ("Defense",   BOOST_NAMES.get(ld["defenseType"],"None")),
            ("Elemental", BOOST_NAMES.get(ld["elementalType"],"None")),
        ]
        skill_rows = [
            ("Skill 1", dict(SKILL_OPTIONS).get(ld["skill1"],"?")),
            ("Skill 2", dict(SKILL_OPTIONS).get(ld["skill2"],"?")),
            ("Skill 3", dict(SKILL_OPTIONS).get(ld["skill3"],"?")),
        ]
        for r,(k,v) in enumerate(rows):
            lbl = QLabel(k)
            lbl.setStyleSheet("color: #5a5248; background: transparent; font-size: 11px;")
            self.preview_layout.addWidget(lbl, r, 0)
            self.preview_layout.addWidget(make_val(v, v != "None"), r, 1)
        for r,(k,v) in enumerate(skill_rows):
            lbl = QLabel(k)
            lbl.setStyleSheet("color: #5a5248; background: transparent; font-size: 11px;")
            self.preview_layout.addWidget(lbl, r, 2)
            self.preview_layout.addWidget(make_val(v, v != "(none)"), r, 3)

    # ── Apply ──────────────────────────────────────────────
    def _apply_loadout(self):
        ld = self._current_loadout()
        if not ld:
            return
        ok, msg = self.bridge.apply_loadout(ld)
        self.lbl_status.setText(f"Applied: {ld['name']}" if ok else f"Error: {msg}")

    def _toggle_auto(self):
        self.cfg["auto_apply"] = not self.cfg.get("auto_apply", False)
        if self.cfg["auto_apply"]:
            interval = self.cfg.get("auto_interval", 3) * 1000
            self.auto_timer.start(interval)
            self.btn_auto.setText(f"Auto-Apply: ON ({self.cfg.get('auto_interval',3)}s)")
            self.btn_auto.setObjectName("auto_on")
            self.lbl_status.setText("Auto-apply enabled.")
        else:
            self.auto_timer.stop()
            self.btn_auto.setText("Auto-Apply: OFF")
            self.btn_auto.setObjectName("")
        self.btn_auto.setStyle(self.btn_auto.style())
        save_config(self.cfg)

    def _auto_apply(self):
        ld = self._current_loadout()
        if ld:
            self.bridge.apply_loadout(ld)

    # ── Launch CE ──────────────────────────────────────────
    def _launch_ce(self):
        if not self.cfg.get("ce_path"):
            self._set_ce_path()
            if not self.cfg.get("ce_path"):
                return
        ok, msg = self.bridge.launch_ce_with_ct()
        self.lbl_status.setText(msg)

    # ── CE path ────────────────────────────────────────────
    def _set_ce_path(self):
        auto = find_ce_path()
        start = auto or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate Cheat Engine", start,
            "Cheat Engine (cheatengine*.exe);;All executables (*.exe)"
        )
        if path:
            self.cfg["ce_path"] = path
            self.bridge.cfg = self.cfg
            save_config(self.cfg)
            self.lbl_status.setText(f"CE path saved.")

    # ── Loadout management ─────────────────────────────────
    def _new_loadout(self):
        dlg = LoadoutEditor(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.cfg["loadouts"].append(dlg.get_loadout())
            save_config(self.cfg)
            self._refresh_loadout_combo(len(self.cfg["loadouts"])-1)

    def _edit_loadout(self):
        idx = self.loadout_combo.currentIndex()
        ld = self._current_loadout()
        if not ld:
            return
        dlg = LoadoutEditor(loadout=ld, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.cfg["loadouts"][idx] = dlg.get_loadout()
            save_config(self.cfg)
            self._refresh_loadout_combo(idx)

    def _delete_loadout(self):
        idx = self.loadout_combo.currentIndex()
        if len(self.cfg["loadouts"]) <= 1:
            QMessageBox.warning(self, "Cannot delete", "You need at least one loadout.")
            return
        ld = self._current_loadout()
        reply = QMessageBox.question(self, "Delete loadout",
            f"Delete '{ld['name']}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.cfg["loadouts"].pop(idx)
            save_config(self.cfg)
            self._refresh_loadout_combo(max(0, idx-1))

    # ── Status thread ──────────────────────────────────────
    def _start_status_thread(self):
        self._status_thread = StatusThread(self)
        self._status_thread.updated.connect(self._on_status)
        self._status_thread.start()

    def _on_status(self, ce_running, mhw_running):
        self.lbl_ce.setText("● Cheat Engine")
        self.lbl_mhw.setText("● Monster Hunter World")
        self.lbl_ce.setObjectName("status_ok" if ce_running else "status_bad")
        self.lbl_mhw.setObjectName("status_ok" if mhw_running else "status_bad")
        self.lbl_ce.setStyle(self.lbl_ce.style())
        self.lbl_mhw.setStyle(self.lbl_mhw.style())

    def _check_ce_path_on_start(self):
        if not self.cfg.get("ce_path"):
            found = find_ce_path()
            if found:
                self.cfg["ce_path"] = found
                self.bridge.cfg = self.cfg
                save_config(self.cfg)
                self.lbl_status.setText(f"CE auto-detected.")
            else:
                self.lbl_status.setText("CE not found — click ⚙ CE Path to locate it.")

    def closeEvent(self, event):
        self._status_thread.requestInterruption()
        self._status_thread.wait(1000)
        event.accept()

# ─────────────────────────────────────────────────────────────
#  Entrypoint
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())