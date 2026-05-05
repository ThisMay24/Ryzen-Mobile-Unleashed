import customtkinter as ctk
import subprocess
import os
import sys
import psutil
import json
import wmi  
import pystray
import time
import ctypes
import atexit
import winreg as reg
from PIL import Image
from threading import Thread
from datetime import datetime
from tkinter import messagebox

# --- 1. FUNGSI ADMINISTRATOR & AUTO-START ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

def set_autostart(status=True):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_path = f'"{os.path.abspath(sys.executable)}" "{os.path.abspath(sys.argv[0])}"'
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_SET_VALUE)
        if status:
            reg.SetValueEx(key, "RyzenMobileUnleashed", 0, reg.REG_SZ, app_path)
        else:
            try: reg.DeleteValue(key, "RyzenMobileUnleashed")
            except: pass
        reg.CloseKey(key)
    except: pass

set_autostart(True)

# --- 2. LOCK FILE ---
LOCK_FILE = os.path.join(os.getenv('TEMP'), "ryzen_unleashed.lock")
if os.path.exists(LOCK_FILE):
    try: os.remove(LOCK_FILE)
    except: sys.exit()

with open(LOCK_FILE, "w") as f: f.write("running")
atexit.register(lambda: os.remove(LOCK_FILE) if os.path.exists(LOCK_FILE) else None)    

# --- 3. RESOURCE PATH & FONT ---
def get_resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_custom_font(font_path):
    if os.path.exists(font_path):
        FR_PRIVATE = 0x10
        ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)

FONT_FILE_PATH = get_resource_path("HoryzenTitle.ttf") 
load_custom_font(FONT_FILE_PATH)

RYZENADJ_PATH = get_resource_path("ryzenadj.exe")
ICON_PATH = get_resource_path("iconapp.ico")

# --- 4. CONFIG & UI SETUP ---
APP_NAME = "RYZEN MOBILE UNLEASHED"
CONFIG_FILE = "config.json"

LANGUAGES = {
    "Indonesia": {
        "title": APP_NAME, "cpu_load": "BEBAN SISTEM", "cpu_temp": "SUHU CPU",
        "default": "Bawaan", "presets": "PROFIL PERFORMA", "apply_btn": "UNLEASH POWER",
        "hw_info": "Hardware Info", "reset": "Reset Default", "warn_title": "PERINGATAN!",
        "warn_msg": "TDP {}W berisiko tinggi tanpa pendingin tambahan. Lanjutkan?",
        "success": "BERHASIL: {}W Diterapkan", "error": "EROR: Akses Hardware Gagal",
        "sys_summary": "HARDWARE SUMMARY", "raw_btn": "View Technical Details"
    },
    "English": {
        "title": APP_NAME, "cpu_load": "SYSTEM LOAD", "cpu_temp": "CPU TEMP",
        "default": "Default", "presets": "PERFORMANCE PROFILES", "apply_btn": "UNLEASH POWER",
        "hw_info": "Hardware Info", "reset": "Reset Default", "warn_title": "WARNING!",
        "warn_msg": "{}W TDP is risky without extra cooling. Continue?",
        "success": "SUCCESS: {}W Applied", "error": "ERROR: Hardware Access Failed",
        "sys_summary": "HARDWARE SUMMARY", "raw_btn": "View Technical Details"
    }
}

class RyzenUnleashed(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = self.load_settings()
        self.current_lang = self.config.get("language", "Indonesia")
        self.appearance_mode = self.config.get("appearance_mode", "Dark")
        
        ctk.set_appearance_mode(self.appearance_mode)
        self.title(APP_NAME)
        
        # --- PERBAIKAN: CENTER SCREEN LOGIC ---
        width = 500
        height = 820
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        self.configure(fg_color=("#ebebeb", "#0d0d0d")) 
        
        try: self.iconbitmap(ICON_PATH)
        except: pass
        
        self.default_tdp = self.get_current_tdp()
        self.hw_window = None
        
        self.protocol('WM_DELETE_WINDOW', self.hide_window)
        self.create_tray_icon()

        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        self.setup_ui()
        self.change_language(self.current_lang)
        self.update_slider_ui(self.default_tdp)
        self.update_monitoring()

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: return json.load(f)
            except: pass
        return {"language": "Indonesia", "appearance_mode": "Dark"}

    def save_settings(self):
        settings = {"language": self.current_lang, "appearance_mode": self.appearance_mode}
        with open(CONFIG_FILE, "w") as f: json.dump(settings, f)

    def toggle_appearance_mode(self):
        self.appearance_mode = "Light" if self.appearance_mode == "Dark" else "Dark"
        ctk.set_appearance_mode(self.appearance_mode)
        self.save_settings()
        self.update_slider_ui(self.slider.get())

    def setup_ui(self):
        font_name = "Horyzen Title"
        
        self.top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=10)
        
        right_f = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        right_f.pack(side="right")

        self.btn_mode = ctk.CTkButton(right_f, text="🌓", width=40, command=self.toggle_appearance_mode,
                                      fg_color=("#d1d1d1", "#222"), text_color=("#000", "#fff"), hover_color=("#bbb", "#333"))
        self.btn_mode.pack(side="left", padx=5)

        self.lang_menu = ctk.CTkOptionMenu(right_f, values=["Indonesia", "English"], 
                                          command=self.change_language, width=110)
        self.lang_menu.set(self.current_lang)
        self.lang_menu.pack(side="left")

        title_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        title_frame.pack(pady=(10, 0))
        ctk.CTkLabel(title_frame, text="RYZEN MOBILE ", font=(font_name, 24, "bold"), text_color="#ff4444").pack(side="left")
        ctk.CTkLabel(title_frame, text="UNLEASHED ", font=(font_name, 24, "bold", "italic"), text_color="#ff4444").pack(side="left")

        self.line = ctk.CTkFrame(self.main_container, height=2, width=280, fg_color="#ff4444")
        self.line.pack(pady=(10, 5))

        try:
            c = wmi.WMI()
            self.cpu_full_name = c.Win32_Processor()[0].Name.strip()
            self.gpu_name = c.Win32_VideoController()[0].Name
        except: 
            self.cpu_full_name = "AMD Ryzen Processor"
            self.gpu_name = "AMD Graphics"
            
        self.cpu_home_label = ctk.CTkLabel(self.main_container, text=self.cpu_full_name, font=(font_name, 13), text_color=("#006666", "#00ffff"))
        self.cpu_home_label.pack(pady=(0, 20))

        self.mon_frame = ctk.CTkFrame(self.main_container, fg_color=("#dbdbdb", "#1a1a1a"), border_width=2, border_color=("#bcbcbc", "#333"), corner_radius=15)
        self.mon_frame.pack(padx=25, pady=10, fill="both")
        self.load_label = ctk.CTkLabel(self.mon_frame, text="", font=("Consolas", 13), text_color=("#555", "#888"))
        self.load_label.pack(pady=(15, 0))
        self.temp_display = ctk.CTkLabel(self.mon_frame, text="--°C", font=("Consolas", 45, "bold"), text_color=("#00a385", "#00ffcc"))
        self.temp_display.pack(pady=(5, 15))

        self.preset_title = ctk.CTkLabel(self.main_container, text="", font=("Roboto", 11, "bold"), text_color=("#777", "#555"))
        self.preset_title.pack(pady=(15, 0))
        
        btn_f = ctk.CTkFrame(self.main_container, fg_color="transparent")
        btn_f.pack(pady=5)
        btn_cfg = {"width": 140, "height": 40, "font": ("Roboto", 12, "bold"), "corner_radius": 6}
        
        self.btn_eco = ctk.CTkButton(btn_f, text="ECO (10W)", fg_color="#27ae60", command=lambda: self.handle_preset_click(10, self.btn_eco, "#27ae60"), **btn_cfg)
        self.btn_eco.grid(row=0, column=0, padx=5, pady=5)
        
        self.btn_norm = ctk.CTkButton(btn_f, text="NORMAL (15W)", fg_color="#2980b9", command=lambda: self.handle_preset_click(15, self.btn_norm, "#2980b9"), **btn_cfg)
        self.btn_norm.grid(row=0, column=1, padx=5, pady=5)
        
        self.btn_stab = ctk.CTkButton(btn_f, text="STABLE (20W)", fg_color="#f39c12", command=lambda: self.handle_preset_click(20, self.btn_stab, "#f39c12"), **btn_cfg)
        self.btn_stab.grid(row=1, column=0, padx=5, pady=5)
        
        self.btn_max = ctk.CTkButton(btn_f, text="MAX (35W)", fg_color="#c0392b", command=lambda: self.handle_preset_click(35, self.btn_max, "#c0392b"), **btn_cfg)
        self.btn_max.grid(row=1, column=1, padx=5, pady=5)

        self.slide_frame = ctk.CTkFrame(self.main_container, fg_color=("#d1d1d1", "#111"), corner_radius=10)
        self.slide_frame.pack(padx=25, pady=20, fill="both")
        self.slider = ctk.CTkSlider(self.slide_frame, from_=10, to=35, command=self.update_slider_ui, button_color="#ff4444", progress_color="#ff4444")
        self.slider.set(self.default_tdp)
        self.slider.pack(padx=20, pady=20)
        self.watt_label = ctk.CTkLabel(self.slide_frame, text="", font=("Verdana", 24, "bold"), text_color=("#000", "#fff"))
        self.watt_label.pack(pady=(0, 15))

        self.btn_apply = ctk.CTkButton(self.main_container, text="", font=(font_name, 18, "bold", "italic"), height=55,
                                       fg_color=("#cc0000", "#181818"), text_color="white",
                                       border_width=2, border_color="#ff4444",
                                       hover_color=("#990000", "#300"), corner_radius=25, command=self.confirm_and_apply)
        self.btn_apply.pack(pady=10, padx=40, fill="x")

        self.log_box = ctk.CTkTextbox(self.main_container, height=100, fg_color=("#fff", "#050505"), text_color=("#006400", "#0f0"), font=("Consolas", 10))
        self.log_box.pack(padx=25, pady=10, fill="both")

        self.bot_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.bot_frame.pack(pady=10)
        self.btn_hw = ctk.CTkButton(self.bot_frame, text="", width=130, command=self.show_hw_info, fg_color=("#c0c0c0", "#333"), text_color=("#000", "#fff"))
        self.btn_hw.pack(side="left", padx=5)
        self.btn_res = ctk.CTkButton(self.bot_frame, text="", width=100, command=self.reset_settings, fg_color=("#b0b0b0", "#222"), text_color=("#000", "#fff"))
        self.btn_res.pack(side="left", padx=5)

    def change_language(self, lang):
        self.current_lang = lang
        self.save_settings()
        t = LANGUAGES[lang]
        self.preset_title.configure(text=t["presets"])
        self.btn_apply.configure(text=t["apply_btn"])
        self.btn_hw.configure(text=t["hw_info"])
        self.btn_res.configure(text=t["reset"])

    def update_slider_ui(self, val):
        w = int(val)
        color = "#ff4444" if w > self.default_tdp + 10 else ("#000000", "#ffffff")
        self.watt_label.configure(text=f"{w} WATT", text_color=color)

    def create_tray_icon(self):
        try: img = Image.open(ICON_PATH)
        except: img = Image.new('RGB', (64, 64), color=(255, 68, 68))
        self.tray_icon = pystray.Icon("RyzenUnleashed", img, APP_NAME)
        self.tray_icon.menu = pystray.Menu(
            pystray.MenuItem("Show App", self.show_window, default=True),
            pystray.MenuItem("ECO (10W)", lambda: self.set_preset(10)),
            pystray.MenuItem("NORMAL (15W)", lambda: self.set_preset(15)),
            pystray.MenuItem("STABLE (20W)", lambda: self.set_preset(20)),
            pystray.MenuItem("MAX (35W)", lambda: self.set_preset(35)),
            pystray.MenuItem("Exit", self.exit_application)
        )
        Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self): self.withdraw()
    def show_window(self): self.deiconify(); self.focus_force()
    def exit_application(self):
        if hasattr(self, 'tray_icon'): self.tray_icon.stop()
        self.destroy()
        os._exit(0)

    def handle_preset_click(self, val, btn, color):
        btn.configure(fg_color="#ffffff")
        self.after(200, lambda: btn.configure(fg_color=color))
        self.set_preset(val)

    def add_log(self, msg):
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")

    def get_current_tdp(self):
        try:
            res = subprocess.run(f'"{RYZENADJ_PATH}" --info', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in res.stdout.split('\n'):
                if "STAPM LIMIT" in line: return int(float(line.split('|')[2].strip()))
            return 15
        except: return 15

    def update_monitoring(self):
        try:
            res = subprocess.run(f'"{RYZENADJ_PATH}" --info', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            cur_temp = "--"
            for line in res.stdout.split('\n'):
                if "THM VALUE CORE" in line: cur_temp = line.split('|')[2].strip(); break
            self.temp_display.configure(text=f"{cur_temp}°C")
            if cur_temp != "--":
                self.temp_display.configure(text_color="#ff4444" if float(cur_temp) > 80 else ("#00a385", "#00ffcc"))
        except: pass
        t = LANGUAGES[self.current_lang]
        self.load_label.configure(text=f"{t['cpu_load']}: {psutil.cpu_percent()}% | {t['default']}: {self.default_tdp}W")
        self.after(2000, self.update_monitoring)

    def apply_tdp(self, w):
        t = LANGUAGES[self.current_lang]
        mw = str(w * 1000)
        try:
            subprocess.run(f'"{RYZENADJ_PATH}" --stapm-limit={mw} --fast-limit={mw} --slow-limit={mw}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.add_log(t["success"].format(w))
        except: self.add_log(t["error"])

    def confirm_and_apply(self):
        t = LANGUAGES[self.current_lang]
        w = int(self.slider.get())
        if w > 25 and not messagebox.askyesno(t["warn_title"], t["warn_msg"].format(w)): return
        self.apply_tdp(w)

    def set_preset(self, v): self.slider.set(v); self.update_slider_ui(v); self.confirm_and_apply()
    def reset_settings(self): self.slider.set(self.default_tdp); self.update_slider_ui(self.default_tdp); self.apply_tdp(self.default_tdp)

    def show_hw_info(self):
        if self.hw_window and self.hw_window.winfo_exists(): self.hw_window.focus(); return
        t = LANGUAGES[self.current_lang]
        self.hw_window = ctk.CTkToplevel(self)
        self.hw_window.title("Hardware Summary")
        
        # --- PERBAIKAN: CENTER SCREEN LOGIC UNTUK HW WINDOW ---
        hw_w, hw_h = 450, 700
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        hx = (sw // 2) - (hw_w // 2)
        hy = (sh // 2) - (hw_h // 2)
        self.hw_window.geometry(f"{hw_w}x{hw_h}+{hx}+{hy}")
        
        self.hw_window.attributes("-topmost", True)
        self.hw_window.configure(fg_color=("#ebebeb", "#0d0d0d"))
        
        try: self.hw_window.after(200, lambda: self.hw_window.iconbitmap(ICON_PATH))
        except: pass

        ctk.CTkLabel(self.hw_window, text=t["sys_summary"], font=("Horyzen Title", 20, "bold"), text_color="#ff4444").pack(pady=(20, 10))
        self.hw_f = ctk.CTkFrame(self.hw_window, fg_color=("#dbdbdb", "#141414"), corner_radius=12, border_width=1, border_color=("#bcbcbc", "#222"))
        self.hw_f.pack(padx=20, pady=5, fill="both", expand=True)
        
        self.name_lbl = ctk.CTkLabel(self.hw_f, text=self.cpu_full_name, font=("Horyzen Title", 14), text_color=("#006666", "#00ffff"), wraplength=380)
        self.name_lbl.pack(pady=(15, 10))

        info_cfg = {"font": ("Segoe UI", 11), "text_color": ("#333", "#bbb")}
        
        cores = psutil.cpu_count(logical=False)
        threads = psutil.cpu_count(logical=True)
        ctk.CTkLabel(self.hw_f, text=f"◇  Cores: {cores} Core / {threads} Thread", **info_cfg).pack(pady=2)
        ctk.CTkLabel(self.hw_f, text=f"◇  GPU: {self.gpu_name}", **info_cfg).pack(pady=2)
        
        self.clock_lbl = ctk.CTkLabel(self.hw_f, text="◇  Speed: Loading...", **info_cfg); self.clock_lbl.pack(pady=2)
        self.ram_lbl = ctk.CTkLabel(self.hw_f, text="◇  RAM: Loading...", **info_cfg); self.ram_lbl.pack(pady=2)
        self.pwr_lbl = ctk.CTkLabel(self.hw_f, text="◇  Power: Loading...", **info_cfg); self.pwr_lbl.pack(pady=2)
        self.family_lbl = ctk.CTkLabel(self.hw_f, text="◇  Family: Loading...", **info_cfg); self.family_lbl.pack(pady=2)
        self.tdp_hw_lbl = ctk.CTkLabel(self.hw_f, text="◇  TDP Aktif: --", **info_cfg); self.tdp_hw_lbl.pack(pady=2)

        self.temp_hw_lbl = ctk.CTkLabel(self.hw_f, text="--°C", font=("Consolas", 42, "bold"), text_color=("#008a3d", "#44ff88"))
        self.temp_hw_lbl.pack(pady=(20, 10))

        ctk.CTkButton(self.hw_window, text=t["raw_btn"], fg_color=("#c0c0c0", "#181818"), text_color=("#000", "#fff"), command=self.open_raw_detail).pack(pady=20)
        self.update_hw_loop()

    def update_hw_loop(self):
        if not self.hw_window or not self.hw_window.winfo_exists(): return
        try:
            self.clock_lbl.configure(text=f"◇  Speed: {psutil.cpu_freq().current:.0f} MHz")
            ram = psutil.virtual_memory()
            self.ram_lbl.configure(text=f"◇  RAM: {ram.percent}% ({round(ram.used/(1024**3),1)}GB / {round(ram.total/(1024**3),1)}GB)")
            batt = psutil.sensors_battery()
            pwr = "Plugged In" if (batt and batt.power_plugged) else "On Battery"
            self.pwr_lbl.configure(text=f"◇  Power: {pwr} ({batt.percent if batt else '--'}%)")

            res = subprocess.run(f'"{RYZENADJ_PATH}" --info', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in res.stdout.split('\n'):
                if "CPU Family:" in line: self.family_lbl.configure(text=f"◇  Family: {line.replace('CPU Family:', '').strip()}")
                if "STAPM LIMIT" in line: self.tdp_hw_lbl.configure(text=f"◇  TDP Aktif: {line.split('|')[2].strip()}W")
                if "THM VALUE CORE" in line: self.temp_hw_lbl.configure(text=f"{line.split('|')[2].strip()}°C")
        except: pass
        self.hw_window.after(2000, self.update_hw_loop)

    def open_raw_detail(self):
        try:
            res = subprocess.run(f'"{RYZENADJ_PATH}" --info', capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            win = ctk.CTkToplevel(self); win.title("Technical Details")
            win.configure(fg_color=("#fff", "#000"))
            try: win.after(200, lambda: win.iconbitmap(ICON_PATH))
            except: pass
            txt = ctk.CTkTextbox(win, width=600, height=500, font=("Consolas", 10), fg_color=("#fff", "#000"), text_color=("#000", "#0f0"))
            txt.pack(padx=10, pady=10, fill="both", expand=True)
            txt.insert("0.0", res.stdout); txt.configure(state="disabled")
        except: pass

if __name__ == "__main__":
    app = RyzenUnleashed()
    app.mainloop()