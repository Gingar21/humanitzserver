import customtkinter as ctk
import os, urllib.request, zipfile, subprocess, threading, time, json, configparser, re, socket, struct
from tkinter import filedialog, messagebox
from datetime import datetime

STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
HUMANITZ_APP_ID = "2728330"  
CONFIG_FILE = "manager_config.json"  
BANNED_WORDS_FILE = "mots_interdits.txt"
RCON_COMMANDS_FILE = "RCONCommands.txt"
LANG_DIR = "languages"

class ServerManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.current_lang = "Français"
        self.translations = {}         
        self.available_languages = []  
        
        self.title("HumanitZ Advanced Server Manager v8.3 By PolarBear")
        self.geometry("1300x850")
        ctk.set_appearance_mode("dark")
        
        self.steamcmd_dir = ctk.StringVar(value="")
        self.server_dir = ctk.StringVar(value="")
        self.net_port = ctk.StringVar(value="7777")
        self.net_queryport = ctk.StringVar(value="27015")
        self.console_command_input = ctk.StringVar(value="")
        self.rcon_ip = ctk.StringVar(value="127.0.0.1")
        
        self.rcon_commands_list = [
            "info", "save", "QuickRestart", "Players", 
            "RestartNow", "CancelRestart", "admin", "kick", "restart", "shutdown"
        ]
        
        self.auto_restart_enabled = ctk.StringVar(value="false")
        self.restart_time_1 = ctk.StringVar(value="")
        self.restart_time_2 = ctk.StringVar(value="")
        self.restart_time_3 = ctk.StringVar(value="")
        self.restart_time_4 = ctk.StringVar(value="")
        self.reset_spawners_before_save = ctk.StringVar(value="false") 
        
        self.restart_in_progress = False 
        self.watchdog_enabled = ctk.StringVar(value="false")
        self.user_stopped_server = False  
        self.is_server_running = False
        self.rcon_auto_authenticated = False 
        self.manual_restart_in_progress = False  
        self.ini_vars = {}
        
        # Variables pour le Message Auto Cyclique
        self.auto_msg_text = ""
        self.auto_msg_interval = 0  
        self.auto_msg_thread_running = False
        
        self.banned_words = []
        self.player_infractions = {} 
        self.player_id_map = {} 
        self.tab_buttons_references = {} 
        self.labels_to_localize = {} 
        self.kick_cooldowns = {} 
        
        self.init_banned_words_file()
        self.init_rcon_commands_file()
        self.load_saved_paths() 
        self.init_languages_system() 
        
        self.setup_ui()
        self.update_ui_language() 
        
        if self.server_dir.get():
            self.load_server_settings()

        threading.Thread(target=self.monitoring_loop, daemon=True).start()
        threading.Thread(target=self.crash_watchdog_loop, daemon=True).start()
        threading.Thread(target=self.auto_restart_scheduler_loop, daemon=True).start()
        threading.Thread(target=self.chat_logs_watcher_loop, daemon=True).start()
        threading.Thread(target=self.players_indexer_loop, daemon=True).start()
        
        self.after(1000, lambda: self.log(self.tr("log_system_ready")))

    def init_languages_system(self):
        if not os.path.exists(LANG_DIR):
            os.makedirs(LANG_DIR, exist_ok=True)
            
        self.available_languages = [os.path.splitext(f)[0] for f in os.listdir(LANG_DIR) if f.endswith(".ini")]
        if not self.available_languages:
            self.available_languages = ["Français"]

        if self.current_lang not in self.available_languages:
            self.current_lang = self.available_languages[0]
            
        self.load_ini_language(self.current_lang)

    def load_ini_language(self, lang_name):
        self.translations = {}
        path = os.path.join(LANG_DIR, f"{lang_name}.ini")
        if os.path.exists(path):
            try:
                config = configparser.ConfigParser(interpolation=None)
                config.read(path, encoding="utf-8")
                if config.has_section("Translations"):
                    for key, val in config.items("Translations"):
                        self.translations[key.lower().strip()] = val.replace("\\n", "\n")
            except Exception as e:
                print(f"Erreur langue {lang_name}: {e}")

    def tr(self, key, **kwargs):
        text = self.translations.get(key.lower().strip(), f"[{key}]")
        if kwargs:
            try: return text.format(**kwargs)
            except Exception: return text
        return text

    def change_language_callback(self, choice):
        self.current_lang = choice
        self.load_ini_language(choice)
        self.update_ui_language()
        self.save_paths()

    def update_ui_language(self):
        if self.is_server_running:
            self.lbl_status.configure(text=self.tr("status_online"), text_color="#2ecc71")
            self.btn_control_server.configure(text=self.tr("btn_stop_server"), fg_color="#c0392b", hover_color="#e74c3c")
        else:
            self.lbl_status.configure(text=self.tr("status_offline"), text_color="#e74c3c")
            self.btn_control_server.configure(text=self.tr("btn_start_server"), fg_color="#e67e22", hover_color="#d35400")
            
        self.lbl_panel_title.configure(text=self.tr("panel_title"))
        self.lbl_sc_row.configure(text=self.tr("steamcmd_lbl"))
        self.lbl_sv_row.configure(text=self.tr("server_lbl"))
        self.btn_install.configure(text=self.tr("btn_install"))
        self.btn_save_config.configure(text=self.tr("btn_save_all"))
        self.btn_restart_timer.configure(text=self.tr("btn_restart_server"))
        
        if self.auto_msg_thread_running:
            self.btn_auto_msg.configure(text=f"AUTO MSG: ON ({self.auto_msg_interval}m)")
        else:
            self.btn_auto_msg.configure(text="AUTO MESSAGE SERVER")
            
        self.btn_open_banned_words.configure(text=self.tr("btn_banned_words"))
        
        # Le bouton RCON va chercher sa traduction dans les fichiers .ini
        self.btn_open_rcon_commands.configure(text=self.tr("btn_rcon_commands"))
        
        if "ports" in self.tab_buttons_references: self.tab_buttons_references["ports"].configure(text=self.tr("tab_ports"))
        if "restart" in self.tab_buttons_references: self.tab_buttons_references["restart"].configure(text=self.tr("tab_restart"))
        if "host" in self.tab_buttons_references: self.tab_buttons_references["host"].configure(text=self.tr("tab_host"))
        if "world" in self.tab_buttons_references: self.tab_buttons_references["world"].configure(text=self.tr("tab_world"))
        if "zombies" in self.tab_buttons_references: self.tab_buttons_references["zombies"].configure(text=self.tr("tab_zombies"))
        if "weather" in self.tab_buttons_references: self.tab_buttons_references["weather"].configure(text=self.tr("tab_weather"))
        if "lang" in self.tab_buttons_references: self.tab_buttons_references["lang"].configure(text=self.tr("tab_lang"))
        
        self.lbl_rcon_warning.configure(text=self.tr("rcon_warning"))
        self.lbl_console_right.configure(text=self.tr("console_title"))
        self.lbl_lang_select.configure(text=self.tr("lang_select_lbl"))
        
        for key, widget_ref in self.labels_to_localize.items():
            widget_ref.configure(text=self.tr(key))

        # Met à jour dynamiquement les placeholders des inputs de temps de restart
        for entry in self.restart_entries:
            ph_text = "ex: 04:00 PM" if self.current_lang != "Français" else "ex: 16:00"
            entry.configure(placeholder_text=ph_text)

    def init_banned_words_file(self):
        if not os.path.exists(BANNED_WORDS_FILE):
            try:
                with open(BANNED_WORDS_FILE, "w", encoding="utf-8") as f:
                    f.write("; Inscrivez un mot interdit par ligne\n")
                    f.write("cheater\n")
                    f.write("noob\n")
            except Exception: pass
        self.load_banned_words()

    def init_rcon_commands_file(self):
        if not os.path.exists(RCON_COMMANDS_FILE):
            try:
                with open(RCON_COMMANDS_FILE, "w", encoding="utf-8") as f:
                    f.write("// --- LISTE DES COMMANDES RCON HUMANITZ ---\n")
                    f.write("info             : Affiche les informations du serveur\n")
                    f.write("save             : Sauvegarde le monde actuel\n")
                    f.write("Players          : Liste les joueurs connectés avec SteamID\n")
                    f.write("admin <message>  : Envoie un message global à tout le serveur\n")
                    f.write("kick <SteamID>   : Expulse un joueur spécifique du serveur\n")
                    f.write("RestartNow       : Redémarre le serveur immédiatement\n")
            except Exception: pass

    def load_banned_words(self):
        if os.path.exists(BANNED_WORDS_FILE):
            try:
                with open(BANNED_WORDS_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                self.banned_words = [l.strip().lower() for l in lines if l.strip() and not l.strip().startswith(";")]
                self.after(0, lambda: self.log(self.tr("log_mod_connected", file=os.path.basename(BANNED_WORDS_FILE))))
            except Exception: pass

    def update_cmd_preview(self):
        p = self.net_port.get() if self.net_port.get() else "7777"
        qp = self.net_queryport.get() if self.net_queryport.get() else "27015"
        self.lbl_cmd_preview.configure(text=f" start HumanitZServer.exe -log port={p} queryport={qp} ")

    def open_banned_words_file(self):
        if os.path.exists(BANNED_WORDS_FILE):
            subprocess.Popen(["notepad.exe", BANNED_WORDS_FILE])
            def reload_watcher():
                time.sleep(5)
                self.load_banned_words()
            threading.Thread(target=reload_watcher, daemon=True).start()

    def open_rcon_commands_file(self):
        if os.path.exists(RCON_COMMANDS_FILE):
            subprocess.Popen(["notepad.exe", RCON_COMMANDS_FILE])

    def browse_steamcmd(self):
        d = filedialog.askdirectory()
        if d: self.steamcmd_dir.set(os.path.normpath(d)); self.save_paths()

    def browse_server(self):
        d = filedialog.askdirectory()
        if d: self.server_dir.set(os.path.normpath(d)); self.save_paths(); self.load_server_settings()

    def start_installation_thread(self):
        if not self.steamcmd_dir.get() or not self.server_dir.get(): return
        self.save_paths(); self.btn_install.configure(state="disabled", text=self.tr("btn_install_prog"))
        threading.Thread(target=self.run_installer, daemon=True).start()

    def run_installer(self):
        sc_dir, sv_dir = self.steamcmd_dir.get(), self.server_dir.get()
        exe = os.path.join(sc_dir, "steamcmd.exe")
        if not os.path.exists(exe):
            try:
                os.makedirs(sc_dir, exist_ok=True)
                urllib.request.urlretrieve(STEAMCMD_URL, os.path.join(sc_dir, "sc.zip"))
                with zipfile.ZipFile(os.path.join(sc_dir, "sc.zip"), 'r') as z: z.extractall(sc_dir)
                os.remove(os.path.join(sc_dir, "sc.zip"))
            except Exception: self.reset_button(); return
        try:
            p = subprocess.Popen([exe, "+force_install_dir", sv_dir, "+login", "anonymous", "+app_update", HUMANITZ_APP_ID, "validate", "+quit"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
            for line in p.stdout:
                if any(x in line for x in ["Update:", "Downloading", "Success"]): self.after(0, lambda l=line.strip(): self.log(f"[SteamCMD] {l}"))
            p.wait(); self.run_first_launch_routine(sv_dir)
        except Exception: pass
        self.reset_button()

    def run_first_launch_routine(self, server_path):
        exe = os.path.join(server_path, "HumanitZServer.exe")
        if not os.path.exists(exe): exe = os.path.join(server_path, "HumanitZ", "Binaries", "Win64", "HumanitZServer-Win64-Shipping.exe")
        if not os.path.exists(exe): return
        try:
            proc = subprocess.Popen([exe, "-log"], creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(30)
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
            self.after(0, self.load_server_settings)
        except Exception: pass

    def reset_button(self):
        self.after(0, lambda: self.btn_install.configure(state="normal", text=self.tr("btn_install")))

    def toggle_server(self):
        if not self.server_dir.get(): return
        if not self.is_server_running:
            self.user_stopped_server = False 
            bat_file = os.path.join(self.server_dir.get(), "start.bat")
            if not os.path.exists(bat_file): self.generate_start_bat()
            try: subprocess.Popen([bat_file], cwd=self.server_dir.get(), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass
        else:
            try:
                self.user_stopped_server = True 
                subprocess.run(["taskkill", "/F", "/IM", "HumanitZServer.exe", "/T"], creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run(["taskkill", "/F", "/IM", "HumanitZServer-Win64-Shipping.exe", "/T"], creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception: pass

    def request_manual_restart(self):
        if not self.server_dir.get() or not self.is_server_running or self.manual_restart_in_progress or self.restart_in_progress: return
        rc_enabled = self.ini_vars.get("RCONEnabled")
        rc_pass = self.ini_vars.get("RCONPass")
        r_enabled_str = rc_enabled["var"].get() if rc_enabled else "false"
        r_pass_str = rc_pass["var"].get().strip('"') if rc_pass else ""
        if r_enabled_str.lower() != "true" or not r_pass_str: return
        
        dialog = ctk.CTkInputDialog(text=self.tr("minutes_before_restart"), title=self.tr("rcon_restart_title"))
        input_value = dialog.get_input()
        if input_value:
            try:
                minutes = int(input_value)
                if minutes <= 0: return
                rc_port = self.ini_vars.get("RConPort")
                r_port_str = rc_port["var"].get() if rc_port else "8888"
                target_ip = self.rcon_ip.get().strip()
                self.manual_restart_in_progress = True
                threading.Thread(target=self.run_manual_restart_timer, args=(minutes, target_ip, r_port_str, r_pass_str), daemon=True).start()
            except ValueError: pass

    def open_auto_message_popup(self):
        if self.auto_msg_thread_running:
            if messagebox.askyesno("Auto Message", "Le message automatique est actif. Voulez-vous l'arrêter ?"):
                self.auto_msg_thread_running = False
                self.log("Système de Message Auto désactivé.")
                self.update_ui_language()
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Configuration Auto Message")
        popup.geometry("450x250")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        
        ctk.CTkLabel(popup, text="Message à envoyer (Commande 'admin' automatique) :", font=("Segoe UI", 12, "bold")).pack(pady=(15, 2))
        entry_msg = ctk.CTkEntry(popup, width=380, placeholder_text="Ex: Bienvenue ! Rejoignez notre Discord...")
        entry_msg.pack(pady=5)
        if self.auto_msg_text: entry_msg.insert(0, self.auto_msg_text)
        
        ctk.CTkLabel(popup, text="Intervalle d'apparition (en minutes) :", font=("Segoe UI", 12, "bold")).pack(pady=(10, 2))
        entry_time = ctk.CTkEntry(popup, width=120, justify="center", placeholder_text="ex: 15")
        entry_time.pack(pady=5)
        if self.auto_msg_interval > 0: entry_time.insert(0, str(self.auto_msg_interval))
        
        def validate_and_start():
            msg = entry_msg.get().strip()
            t_str = entry_time.get().strip()
            if not msg:
                messagebox.showerror("Erreur", "Le message ne peut pas être vide.", parent=popup)
                return
            try:
                minutes = int(t_str)
                if minutes <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Erreur", "Veuillez entrer un nombre de minutes valide (> 0).", parent=popup)
                return
            
            self.auto_msg_text = msg
            self.auto_msg_interval = minutes
            self.auto_msg_thread_running = True
            
            popup.destroy()
            self.log(f"Message Auto activé ! Chaque {minutes} min : '{msg}'")
            self.update_ui_language()
            threading.Thread(target=self.auto_message_cycler_loop, daemon=True).start()

        btn_confirm = ctk.CTkButton(popup, text="DÉMARRER LE CYCLE", fg_color="#27ae60", hover_color="#2196F3", font=("Segoe UI", 12, "bold"), command=validate_and_start)
        btn_confirm.pack(pady=20)

    def auto_message_cycler_loop(self):
        while self.auto_msg_thread_running:
            for _ in range(self.auto_msg_interval * 60):
                if not self.auto_msg_thread_running:
                    return
                time.sleep(1)
                
            if self.auto_msg_thread_running and self.is_server_running:
                r_port_str = self.ini_vars["RConPort"]["var"].get() if "RConPort" in self.ini_vars else "8888"
                r_pass_str = self.ini_vars["RCONPass"]["var"].get().strip('"') if "RCONPass" in self.ini_vars else ""
                if r_pass_str:
                    full_cmd = f"admin {self.auto_msg_text}"
                    threading.Thread(target=self.send_rcon_command, args=(self.rcon_ip.get().strip(), r_port_str, r_pass_str, full_cmd), daemon=True).start()
                    self.after(0, lambda m=self.auto_msg_text: self.log(f"[Auto-Msg] admin {m}"))

    def generate_start_bat(self):
        if not self.server_dir.get(): return
        p = self.net_port.get() if self.net_port.get() else "7777"
        qp = self.net_queryport.get() if self.net_queryport.get() else "27015"
        try:
            with open(os.path.join(self.server_dir.get(), "start.bat"), "w", encoding="utf-8") as f:
                f.write(f"start HumanitZServer.exe -log port={p} queryport={qp}\n")
        except Exception: pass

    def save_restart_schedules_live(self):
        self.save_paths()
        messagebox.showinfo(title=self.tr("msg_saved_title"), message=self.tr("msg_saved_text"))

    def save_all_settings(self):
        self.save_paths(); self.save_server_settings(); self.generate_start_bat()
        messagebox.showinfo(title=self.tr("msg_saved_title"), message=self.tr("msg_saved_text"))

    def save_paths(self):
        try:
            data = {
                "current_lang": self.current_lang,
                "steamcmd_dir": self.steamcmd_dir.get(), "server_dir": self.server_dir.get(), 
                "net_port": self.net_port.get(), "net_queryport": self.net_queryport.get(), 
                "watchdog_enabled": self.watchdog_enabled.get(), "auto_restart_enabled": self.auto_restart_enabled.get(), 
                "restart_time_1": self.restart_time_1.get(), "restart_time_2": self.restart_time_2.get(), 
                "restart_time_3": self.restart_time_3.get(), "restart_time_4": self.restart_time_4.get(), 
                "rcon_ip": self.rcon_ip.get(),
                "reset_spawners_before_save": self.reset_spawners_before_save.get(),
                "auto_msg_text": self.auto_msg_text,
                "auto_msg_interval": self.auto_msg_interval
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        except Exception: pass

    def load_saved_paths(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self.current_lang = d.get("current_lang", "Français")
                    self.steamcmd_dir.set(d.get("steamcmd_dir", ""))
                    self.server_dir.set(d.get("server_dir", ""))
                    self.net_port.set(d.get("net_port", "7777"))
                    self.net_queryport.set(d.get("net_queryport", "27015"))
                    self.watchdog_enabled.set(d.get("watchdog_enabled", "false"))
                    self.auto_restart_enabled.set(d.get("auto_restart_enabled", "false"))
                    self.restart_time_1.set(d.get("restart_time_1", ""))
                    self.restart_time_2.set(d.get("restart_time_2", ""))
                    self.restart_time_3.set(d.get("restart_time_3", ""))
                    self.restart_time_4.set(d.get("restart_time_4", ""))
                    self.rcon_ip.set(d.get("rcon_ip", "127.0.0.1"))
                    self.reset_spawners_before_save.set(d.get("reset_spawners_before_save", "false")) 
                    self.auto_msg_text = d.get("auto_msg_text", "")
                    self.auto_msg_interval = d.get("auto_msg_interval", 0)
            except Exception: pass

    def get_settings_ini_path(self):
        if not self.server_dir.get(): return None
        return os.path.join(self.server_dir.get(), "HumanitZServer", "GameServerSettings.ini")

    def load_server_settings(self):
        ini_path = self.get_settings_ini_path()
        if not ini_path or not os.path.exists(ini_path): return
        try:
            config = configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=';')
            config.optionxform = str; config.read(ini_path, encoding="utf-8")
            for key, info in self.ini_vars.items():
                sec = info["section"]
                if config.has_option(sec, key):
                    raw_val = config.get(sec, key).strip().strip('"')
                    if key == "Weather_Blizzard" and "serverpassword" in raw_val.lower(): raw_val = re.sub(r'[^0-9]', '', raw_val.split("ServerPassword")[0])
                    info["var"].set(raw_val)
                    if info["type"] == "switch":
                        if raw_val.lower() == "true": info["widget"].select()
                        else: info["widget"].deselect()
        except Exception: pass

    def save_server_settings(self):
        ini_path = self.get_settings_ini_path()
        if not self.server_dir.get(): return
        os.makedirs(os.path.dirname(ini_path), exist_ok=True)
        config = configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=';')
        config.optionxform = str
        if os.path.exists(ini_path): config.read(ini_path, encoding="utf-8")
        for key, info in self.ini_vars.items():
            sec = info["section"]; val = info["var"].get()
            if not config.has_section(sec): config.add_section(sec)
            if key in ["Password", "AdminPass", "SaveName", "SearchID"] and not val.startswith('"'): val = f'"{val}"'
            config.set(sec, key, val)
        try:
            with open(ini_path, "w", encoding="utf-8") as f: config.write(f, space_around_delimiters=False)
        except Exception: pass

    def setup_ui(self):
        self.restart_entries = []
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=20, pady=(10, 0))
        self.lbl_status = ctk.CTkLabel(self.header, text="", font=("Segoe UI", 14, "bold"), text_color="#e74c3c")
        self.lbl_status.pack(side="right", padx=15)
        
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        main_container.grid_columnconfigure(0, weight=2)
        main_container.grid_columnconfigure(1, weight=5)
        main_container.grid_columnconfigure(2, weight=3)
        main_container.grid_rowconfigure(0, weight=1)
        
        left_panel = ctk.CTkFrame(main_container)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.lbl_panel_title = ctk.CTkLabel(left_panel, text="", font=("Segoe UI", 14, "bold"), text_color="#3498db")
        self.lbl_panel_title.pack(pady=10)
        
        self.lbl_sc_row = self.create_path_row(left_panel, "steamcmd_lbl", self.steamcmd_dir, self.browse_steamcmd)
        self.lbl_sv_row = self.create_path_row(left_panel, "server_lbl", self.server_dir, self.browse_server)
        
        self.btn_install = ctk.CTkButton(left_panel, text="", fg_color="#1f538d", height=35, font=("Segoe UI", 12, "bold"), command=self.start_installation_thread)
        self.btn_install.pack(fill="x", padx=15, pady=15)
        ctk.CTkFrame(left_panel, height=2, fg_color="#333").pack(fill="x", padx=10, pady=10)
        
        # --- PANNEAU DE GAUCHE : LES BOUTONS PRINCIPAUX ---
        self.btn_save_config = ctk.CTkButton(left_panel, text="", fg_color="#27ae60", hover_color="#2196F3", height=50, font=("Segoe UI", 13, "bold"), command=self.save_all_settings)
        self.btn_save_config.pack(fill="x", padx=15, pady=10)
        
        self.btn_control_server = ctk.CTkButton(left_panel, text="", fg_color="#e67e22", hover_color="#d35400", height=45, font=("Segoe UI", 13, "bold"), command=self.toggle_server)
        self.btn_control_server.pack(fill="x", padx=15, pady=10)
        
        # BOUTON MANUEL RESTART (VIOLET)
        self.btn_restart_timer = ctk.CTkButton(left_panel, text="", fg_color="#8e44ad", hover_color="#9b59b6", height=45, font=("Segoe UI", 13, "bold"), command=self.request_manual_restart)
        self.btn_restart_timer.pack(fill="x", padx=15, pady=10)
        
        # BOUTON AUTO MESSAGE SERVER (CYAN)
        self.btn_auto_msg = ctk.CTkButton(left_panel, text="AUTO MESSAGE SERVER", height=45, font=("Segoe UI", 13, "bold"), fg_color="#16a085", hover_color="#1abc9c", command=self.open_auto_message_popup)
        self.btn_auto_msg.pack(fill="x", padx=15, pady=10)
        
        # BOUTON MOTS INTERDITS (ROUGE)
        self.btn_open_banned_words = ctk.CTkButton(left_panel, text="", height=35, font=("Segoe UI", 12, "bold"), fg_color="#c0392b", hover_color="#e74c3c", command=self.open_banned_words_file)
        self.btn_open_banned_words.pack(fill="x", padx=15, pady=5)

        # BOUTON LISTE COMMANDES RCON (TURQUOISE)
        self.btn_open_rcon_commands = ctk.CTkButton(left_panel, text="", height=35, font=("Segoe UI", 12, "bold"), fg_color="#17a2b8", hover_color="#138496", command=self.open_rcon_commands_file)
        self.btn_open_rcon_commands.pack(fill="x", padx=15, pady=5)

        # Onglets de configuration (Milieu)
        self.config_panel = ctk.CTkTabview(main_container)
        self.config_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.tab_ports = self.config_panel.add("Ports & Lancement")
        self.tab_buttons_references["ports"] = self.config_panel._segmented_button._buttons_dict["Ports & Lancement"]
        
        self.tab_restart = self.config_panel.add("Auto-Restart")  
        self.tab_buttons_references["restart"] = self.config_panel._segmented_button._buttons_dict["Auto-Restart"]
        
        self.tab_host = self.config_panel.add("Hébergement & RCON")
        self.tab_buttons_references["host"] = self.config_panel._segmented_button._buttons_dict["Hébergement & RCON"]
        
        self.tab_world = self.config_panel.add("Monde & Survie")
        self.tab_buttons_references["world"] = self.config_panel._segmented_button._buttons_dict["Monde & Survie"]
        
        self.tab_zombies = self.config_panel.add("IA & Difficulté")
        self.tab_buttons_references["zombies"] = self.config_panel._segmented_button._buttons_dict["IA & Difficulté"]
        
        self.tab_weather = self.config_panel.add("Météo")
        self.tab_buttons_references["weather"] = self.config_panel._segmented_button._buttons_dict["Météo"]
        
        self.tab_lang = self.config_panel.add("Langage / Language") 
        self.tab_buttons_references["lang"] = self.config_panel._segmented_button._buttons_dict["Langage / Language"]
        
        self.setup_ports_tab()
        self.setup_restart_tab()
        self.setup_host_tab()
        self.setup_world_tab()
        self.setup_zombies_tab()
        self.setup_weather_tab()
        self.setup_language_tab()

        # Panneau console (Droite)
        right_panel = ctk.CTkFrame(main_container)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        self.lbl_console_right = ctk.CTkLabel(right_panel, text="", font=("Segoe UI", 13, "bold"))
        self.lbl_console_right.pack(pady=5)
        self.txt_log = ctk.CTkTextbox(right_panel, font=("Consolas", 11), fg_color="black", state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        f_terminal = ctk.CTkFrame(right_panel, fg_color="transparent")
        f_terminal.pack(fill="x", padx=10, pady=(0, 10))
        self.cmb_console_cmd = ctk.CTkComboBox(f_terminal, values=self.rcon_commands_list, font=("Consolas", 11), variable=self.console_command_input, dropdown_font=("Consolas", 11))
        self.cmb_console_cmd.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.cmb_console_cmd.set("") 
        self.cmb_console_cmd.bind("<Return>", lambda event: self.send_manual_console_command())
        
        self.btn_send_cmd = ctk.CTkButton(f_terminal, text="SEND", width=65, font=("Segoe UI", 11, "bold"), fg_color="#1f538d", command=self.send_manual_console_command)
        self.btn_send_cmd.pack(side="right")

    def create_path_row(self, parent, translation_key, variable, command):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=5, pady=4)
        lbl = ctk.CTkLabel(f, text="", font=("Segoe UI", 11, "bold"))
        lbl.pack(anchor="w", padx=5)
        self.labels_to_localize[translation_key] = lbl
        row = ctk.CTkFrame(f, fg_color="transparent"); row.pack(fill="x")
        ctk.CTkEntry(row, textvariable=variable, placeholder_text="...").pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(row, text="...", width=35, command=command).pack(side="right", padx=5)
        return lbl

    def add_ini_input(self, parent, key, section, default_val, **kwargs):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=5, pady=3)
        lbl = ctk.CTkLabel(f, text="", font=("Segoe UI", 11))
        lbl.pack(side="left", padx=5)
        self.labels_to_localize[f"{key.lower()}_lbl"] = lbl
        
        var = ctk.StringVar(value=default_val)
        self.ini_vars[key] = {"var": var, "type": "input", "section": section}
        ctk.CTkEntry(f, textvariable=var, width=200, justify="right", **kwargs).pack(side="right", padx=5)

    def add_ini_switch(self, parent, key, section, default_bool):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=5, pady=3)
        lbl = ctk.CTkLabel(f, text="", font=("Segoe UI", 11))
        lbl.pack(side="left", padx=5)
        self.labels_to_localize[f"{key.lower()}_lbl"] = lbl
        
        var = ctk.StringVar(value="true" if default_bool else "false")
        sw = ctk.CTkSwitch(f, text="")
        sw.pack(side="right", padx=5)
        if default_bool: sw.select()
        else: sw.deselect()
        sw.configure(command=lambda: var.set("true" if sw.get() else "false"))
        self.ini_vars[key] = {"var": var, "type": "switch", "widget": sw, "section": section}

    def setup_ports_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_ports, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        f_alert = ctk.CTkFrame(scroll, fg_color="#d35400", corner_radius=6); f_alert.pack(fill="x", padx=5, pady=(5, 15))
        self.lbl_rcon_warning = ctk.CTkLabel(f_alert, text="", font=("Segoe UI", 11, "bold"), text_color="white", justify="left")
        self.lbl_rcon_warning.pack(padx=10, pady=8)
        
        lbl_net = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#e67e22")
        lbl_net.pack(anchor="w", pady=5)
        self.labels_to_localize["net_config_title"] = lbl_net
        
        f_port = ctk.CTkFrame(scroll, fg_color="transparent"); f_port.pack(fill="x", padx=5, pady=5)
        lbl_p = ctk.CTkLabel(f_port, text="", font=("Segoe UI", 11))
        lbl_p.pack(side="left", padx=5)
        self.labels_to_localize["port_lbl"] = lbl_p
        ctk.CTkEntry(f_port, textvariable=self.net_port, width=150, justify="right").pack(side="right", padx=5)
        
        f_query_port = ctk.CTkFrame(scroll, fg_color="transparent"); f_query_port.pack(fill="x", padx=5, pady=5)
        lbl_qp = ctk.CTkLabel(f_query_port, text="", font=("Segoe UI", 11))
        lbl_qp.pack(side="left", padx=5)
        self.labels_to_localize["query_port_lbl"] = lbl_qp
        ctk.CTkEntry(f_query_port, textvariable=self.net_queryport, width=150, justify="right").pack(side="right", padx=5)
        
        ctk.CTkFrame(scroll, height=2, fg_color="#333").pack(fill="x", padx=5, pady=15)
        lbl_wd_title = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#2ecc71")
        lbl_wd_title.pack(anchor="w", pady=5)
        self.labels_to_localize["watchdog_title"] = lbl_wd_title
        
        f_wd = ctk.CTkFrame(scroll, fg_color="transparent"); f_wd.pack(fill="x", padx=5, pady=5)
        lbl_wd = ctk.CTkLabel(f_wd, text="", font=("Segoe UI", 11))
        lbl_wd.pack(side="left", padx=5)
        self.labels_to_localize["watchdog_lbl"] = lbl_wd
        
        self.sw_wd = ctk.CTkSwitch(f_wd, text="")
        self.sw_wd.pack(side="right", padx=5)
        if self.watchdog_enabled.get() == "true": self.sw_wd.select()
        else: self.sw_wd.deselect()
        self.sw_wd.configure(command=lambda: self.watchdog_enabled.set("true" if self.sw_wd.get() else "false"))

        ctk.CTkFrame(scroll, height=2, fg_color="#333").pack(fill="x", padx=5, pady=15)
        self.lbl_cmd_preview = ctk.CTkLabel(scroll, text="", font=("Consolas", 11, "italic"), text_color="#2ecc71", bg_color="#111", corner_radius=5, height=35)
        self.lbl_cmd_preview.pack(fill="x", padx=5, pady=10)
        self.net_port.trace_add("write", lambda *args: self.update_cmd_preview())
        self.net_queryport.trace_add("write", lambda *args: self.update_cmd_preview())
        self.update_cmd_preview()

    def setup_restart_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_restart, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        lbl_title = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#6c5ce7")
        lbl_title.pack(anchor="w", pady=10)
        self.labels_to_localize["restart_sched_title"] = lbl_title
        
        f_sw = ctk.CTkFrame(scroll, fg_color="transparent"); f_sw.pack(fill="x", padx=5, pady=5)
        lbl_enable = ctk.CTkLabel(f_sw, text="", font=("Segoe UI", 11, "bold"))
        lbl_enable.pack(side="left", padx=5)
        self.labels_to_localize["restart_sched_enable"] = lbl_enable
        
        self.sw_restart = ctk.CTkSwitch(f_sw, text="")
        self.sw_restart.pack(side="right", padx=5)
        if self.auto_restart_enabled.get() == "true": self.sw_restart.select()
        else: self.sw_restart.deselect()
        self.sw_restart.configure(command=lambda: self.auto_restart_enabled.set("true" if self.sw_restart.get() else "false"))
        
        self.create_time_input_row(scroll, "time_lbl_1", self.restart_time_1)
        self.create_time_input_row(scroll, "time_lbl_2", self.restart_time_2)
        self.create_time_input_row(scroll, "time_lbl_3", self.restart_time_3)
        self.create_time_input_row(scroll, "time_lbl_4", self.restart_time_4)
        
        f_rs_sw = ctk.CTkFrame(scroll, fg_color="transparent"); f_rs_sw.pack(fill="x", padx=5, pady=10)
        lbl_rs = ctk.CTkLabel(f_rs_sw, text="", font=("Segoe UI", 11))
        lbl_rs.pack(side="left", padx=5)
        self.labels_to_localize["sw_reset_spawners"] = lbl_rs 
        
        self.sw_reset_spawners = ctk.CTkSwitch(f_rs_sw, text="")
        self.sw_reset_spawners.pack(side="right", padx=5)
        if self.reset_spawners_before_save.get() == "true": self.sw_reset_spawners.select()
        else: self.sw_reset_spawners.deselect()
        self.sw_reset_spawners.configure(command=lambda: self.reset_spawners_before_save.set("true" if self.sw_reset_spawners.get() else "false"))
        
        self.btn_save_restart_only = ctk.CTkButton(scroll, text="", fg_color="#6c5ce7", hover_color="#5b4bc4", height=38, font=("Segoe UI", 12, "bold"), command=self.save_restart_schedules_live)
        self.btn_save_restart_only.pack(fill="x", padx=5, pady=15)
        self.labels_to_localize["btn_save_restart_only"] = self.btn_save_restart_only

    def create_time_input_row(self, parent, context_key, variable):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=5, pady=4)
        lbl = ctk.CTkLabel(f, text="", font=("Segoe UI", 11))
        lbl.pack(side="left", padx=5)
        self.labels_to_localize[context_key] = lbl
        
        ph_text = "ex: 04:00 PM" if self.current_lang != "Français" else "ex: 16:00"
        entry = ctk.CTkEntry(f, textvariable=variable, width=120, placeholder_text=ph_text, justify="center")
        entry.pack(side="right", padx=5)
        self.restart_entries.append(entry)

    def setup_host_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_host, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        lbl_sec1 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#3498db")
        lbl_sec1.pack(anchor="w", pady=5)
        self.labels_to_localize["host_settings_title"] = lbl_sec1

        self.add_ini_input(scroll, "ServerName", "Host Settings", "HumanitZ Server")
        self.add_ini_input(scroll, "Password", "Host Settings", "", show="*")
        self.add_ini_input(scroll, "AdminPass", "Host Settings", "", show="*")
        self.add_ini_input(scroll, "MaxPlayers", "Host Settings", "16")
        self.add_ini_input(scroll, "SaveName", "Host Settings", "DedicatedSaveMP")
        self.add_ini_input(scroll, "SearchID", "Host Settings", "HumanitZ_Dedicated")
        
        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec2 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#3498db")
        lbl_sec2.pack(anchor="w", pady=5)
        self.labels_to_localize["rcon_connectivity_title"] = lbl_sec2

        self.add_ini_switch(scroll, "RCONEnabled", "Host Settings", False)
        
        f_ip = ctk.CTkFrame(scroll, fg_color="transparent"); f_ip.pack(fill="x", padx=5, pady=3)
        lbl_rcon_ip = ctk.CTkLabel(f_ip, text="", font=("Segoe UI", 11))
        lbl_rcon_ip.pack(side="left", padx=5)
        self.labels_to_localize["rcon_ip_lbl"] = lbl_rcon_ip
        ctk.CTkEntry(f_ip, textvariable=self.rcon_ip, width=200, justify="right").pack(side="right", padx=5)
        
        self.add_ini_input(scroll, "RConPort", "Host Settings", "8888")
        self.add_ini_input(scroll, "RCONPass", "Host Settings", "", show="*")
        
        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec3 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#3498db")
        lbl_sec3.pack(anchor="w", pady=5)
        self.labels_to_localize["security_filters_title"] = lbl_sec3

        self.add_ini_switch(scroll, "UseGlobalBanList", "Host Settings", True)
        self.add_ini_switch(scroll, "AllowFamilySharing", "Host Settings", True)
        self.add_ini_switch(scroll, "LimitedSpawns", "Host Settings", False)
        self.add_ini_switch(scroll, "NoDeathFeedback", "Host Settings", True)
        self.add_ini_switch(scroll, "NoJoinFeedback", "Host Settings", True)

    def setup_world_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_world, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        self.add_ini_switch(scroll, "PVP", "World Settings", True)
        self.add_ini_switch(scroll, "PermaDeath", "World Settings", False)
        self.add_ini_input(scroll, "XpMultiplier", "World Settings", "1")
        self.add_ini_input(scroll, "SaveIntervalSec", "World Settings", "300")
        self.add_ini_input(scroll, "OnDeath", "World Settings", "2")
        self.add_ini_input(scroll, "RespawnTimer", "World Settings", "15")
        self.add_ini_input(scroll, "LogoutTimer", "World Settings", "30")

        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec1 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#1abc9c")
        lbl_sec1.pack(anchor="w", pady=5)
        self.labels_to_localize["loot_settings_title"] = lbl_sec1

        self.add_ini_switch(scroll, "LootRespawn", "World Settings", True)
        self.add_ini_input(scroll, "LootRespawnTimer", "World Settings", "60")
        self.add_ini_input(scroll, "PickupRespawnTimer", "World Settings", "90")
        self.add_ini_input(scroll, "FoodDecay", "World Settings", "1")
        self.add_ini_input(scroll, "PickupCleanup", "World Settings", "6")

        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec2 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#1abc9c")
        lbl_sec2.pack(anchor="w", pady=5)
        self.labels_to_localize["loot_rarity_title"] = lbl_sec2

        self.add_ini_input(scroll, "RarityFood", "World Settings", "2")
        self.add_ini_input(scroll, "RarityDrink", "World Settings", "2")
        self.add_ini_input(scroll, "RarityMelee", "World Settings", "2")
        self.add_ini_input(scroll, "RarityRanged", "World Settings", "2")
        self.add_ini_input(scroll, "RarityAmmo", "World Settings", "2")
        self.add_ini_input(scroll, "RarityArmor", "World Settings", "2")
        self.add_ini_input(scroll, "RarityResources", "World Settings", "2")

        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec3 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#1abc9c")
        lbl_sec3.pack(anchor="w", pady=5)
        self.labels_to_localize["cars_bases_title"] = lbl_sec3

        self.add_ini_input(scroll, "MaxOwnedCars", "World Settings", "2")
        self.add_ini_input(scroll, "RecycleCar", "World Settings", "14")
        self.add_ini_switch(scroll, "AllowDismantle", "World Settings", True)
        self.add_ini_switch(scroll, "AllowHouseDismantle", "World Settings", True)
        self.add_ini_input(scroll, "BuildingHealth", "World Settings", "1")
        self.add_ini_input(scroll, "Decay", "World Settings", "7")
        self.add_ini_input(scroll, "BuildingDecay", "World Settings", "7")
        self.add_ini_input(scroll, "GenFuel", "World Settings", "1")

        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec4 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#1abc9c")
        lbl_sec4.pack(anchor="w", pady=5)
        self.labels_to_localize["survival_mechanics_title"] = lbl_sec4

        self.add_ini_switch(scroll, "AirDrop", "World Settings", True)
        self.add_ini_input(scroll, "AirDropInterval", "World Settings", "1")
        self.add_ini_switch(scroll, "WeaponBreak", "World Settings", True)
        self.add_ini_switch(scroll, "Sleep", "World Settings", True)
        self.add_ini_switch(scroll, "MultiplayerSleep", "World Settings", False)
        self.add_ini_input(scroll, "VitalDrain", "World Settings", "1")
        self.add_ini_switch(scroll, "DogEnabled", "World Settings", True)
        self.add_ini_input(scroll, "DogNum", "World Settings", "8")

    def setup_zombies_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_zombies, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        self.add_ini_input(scroll, "ZombieDiffHealth", "World Settings", "1")
        self.add_ini_input(scroll, "ZombieDiffSpeed", "World Settings", "2")
        self.add_ini_input(scroll, "ZombieDiffDamage", "World Settings", "3")
        self.add_ini_input(scroll, "ZombieAmountMulti", "World Settings", "1")
        self.add_ini_input(scroll, "ZombieRespawnTimer", "World Settings", "90")
        self.add_ini_input(scroll, "ZombieDogMulti", "World Settings", "1")

        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec1 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#e74c3c")
        lbl_sec1.pack(anchor="w", pady=5)
        self.labels_to_localize["human_bandits_title"] = lbl_sec1

        self.add_ini_input(scroll, "HumanHealth", "World Settings", "2")
        self.add_ini_input(scroll, "HumanSpeed", "World Settings", "2")
        self.add_ini_input(scroll, "HumanDamage", "World Settings", "2")
        self.add_ini_input(scroll, "HumanAmountMulti", "World Settings", "1")
        self.add_ini_input(scroll, "HumanRespawnTimer", "World Settings", "90")
        self.add_ini_input(scroll, "AIEvent", "World Settings", "2")

    def setup_weather_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_weather, fg_color="transparent"); scroll.pack(fill="both", expand=True)
        self.add_ini_input(scroll, "StartingSeason", "World Settings", "1")
        self.add_ini_input(scroll, "DaysPerSeason", "World Settings", "5")
        self.add_ini_input(scroll, "DayDur", "World Settings", "40")
        self.add_ini_input(scroll, "NightDur", "World Settings", "20")
        self.add_ini_switch(scroll, "FreezeTime", "World Settings", True)

        ctk.CTkFrame(scroll, height=1, fg_color="#444").pack(fill="x", padx=5, pady=10)
        lbl_sec1 = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 13, "bold"), text_color="#34495e")
        lbl_sec1.pack(anchor="w", pady=5)
        self.labels_to_localize["weather_chances_title"] = lbl_sec1

        self.add_ini_input(scroll, "Weather_ClearSky", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_Cloudy", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_Foggy", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_LightRain", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_Rain", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_Thunderstorm", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_LightSnow", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_Snow", "World Settings", "1")
        self.add_ini_input(scroll, "Weather_Blizzard", "World Settings", "1")

    def setup_language_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_lang, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self.lbl_lang_select = ctk.CTkLabel(scroll, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_lang_select.pack(anchor="w", padx=10, pady=15)
        
        self.cmb_lang = ctk.CTkOptionMenu(scroll, values=self.available_languages, command=self.change_language_callback, font=("Segoe UI", 12))
        self.cmb_lang.pack(anchor="w", padx=10, pady=5)
        self.cmb_lang.set(self.current_lang)

    def monitoring_loop(self):
        while True:
            try:
                cmd = 'tasklist /FI "IMAGENAME eq HumanitZServer-Win64-Shipping.exe" /FO CSV'
                output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW, text=True)
                if "HumanitZServer-Win64-Shipping.exe" in output or "HumanitZServer.exe" in subprocess.check_output('tasklist /FI "IMAGENAME eq HumanitZServer.exe" /FO CSV', creationflags=subprocess.CREATE_NO_WINDOW, text=True):
                    if not self.is_server_running:
                        self.is_server_running = True
                        self.after(0, self.update_ui_language)
                else:
                    if self.is_server_running:
                        self.is_server_running = False
                        self.rcon_auto_authenticated = False
                        self.after(0, self.update_ui_language)
            except Exception: pass
            time.sleep(5)

    def crash_watchdog_loop(self):
        while True:
            if self.watchdog_enabled.get() == "true" and not self.user_stopped_server and not self.is_server_running and not self.manual_restart_in_progress:
                if self.server_dir.get():
                    time.sleep(5)
                    if not self.is_server_running:
                        self.after(0, lambda: self.log(self.tr("log_watchdog_trigger")))
                        self.auto_start_server_action()
                        time.sleep(20) 
            time.sleep(4) 

    def auto_start_server_action(self):
        bat_file = os.path.join(self.server_dir.get(), "start.bat")
        if os.path.exists(bat_file):
            try: subprocess.Popen([bat_file], cwd=self.server_dir.get(), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass

    def query_and_index_players(self):
        rc_enabled = self.ini_vars.get("RCONEnabled")
        rc_pass = self.ini_vars.get("RCONPass")
        r_enabled_str = rc_enabled["var"].get() if rc_enabled else "false"
        r_pass_str = rc_pass["var"].get().strip('"') if rc_pass else ""
        
        if r_enabled_str.lower() == "true" and r_pass_str:
            rc_port = self.ini_vars.get("RConPort")
            r_port_str = rc_port["var"].get() if rc_port else "8888"
            target_ip = self.rcon_ip.get().strip()
            
            raw_data = self.send_rcon_command(target_ip, r_port_str, r_pass_str, "Players")
            if raw_data and "erreur" not in raw_data.lower():
                lines = raw_data.split("\n")
                for line in lines:
                    match = re.search(r'^\s*(.*?)\s*\((7656\d{13})', line)
                    if match:
                        player_name = match.group(1).strip()
                        steam_id = match.group(2).strip()
                        if player_name and steam_id:
                            self.player_id_map[player_name] = steam_id

    def players_indexer_loop(self):
        while True:
            if self.is_server_running and self.server_dir.get():
                try: self.query_and_index_players()
                except Exception: pass
            time.sleep(15)

    def auto_restart_scheduler_loop(self):
        while True:
            if self.auto_restart_enabled.get() == "true" and self.is_server_running and not self.restart_in_progress and not self.manual_restart_in_progress:
                now_str = time.strftime("%H:%M")
                current_now = datetime.strptime(now_str, "%H:%M")
                
                times_to_check = []
                if self.restart_time_1.get().strip(): times_to_check.append(self.restart_time_1.get().strip())
                if self.restart_time_2.get().strip(): times_to_check.append(self.restart_time_2.get().strip())
                if self.restart_time_3.get().strip(): times_to_check.append(self.restart_time_3.get().strip())
                if self.restart_time_4.get().strip(): times_to_check.append(self.restart_time_4.get().strip())
                
                for r_time in times_to_check:
                    target_time = None
                    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
                        try:
                            target_time = datetime.strptime(r_time.upper(), fmt)
                            break
                        except ValueError:
                            continue
                    
                    if target_time:
                        diff_minutes = (target_time - current_now).total_seconds() / 60
                        
                        if diff_minutes == -10 or diff_minutes == 1430:
                            rc_enabled = self.ini_vars.get("RCONEnabled")
                            rc_pass = self.ini_vars.get("RCONPass")
                            if rc_enabled and rc_enabled["var"].get().lower() == "true":
                                self.restart_in_progress = True 
                                threading.Thread(target=self.run_scheduled_restart_timer, args=(self.rcon_ip.get().strip(), self.ini_vars["RConPort"]["var"].get(), rc_pass["var"].get().strip('"')), daemon=True).start()
                                break
            time.sleep(5) 

    def run_scheduled_restart_timer(self, target_ip, r_port_str, r_pass_str):
        for minutes_left in range(10, 0, -1):
            msg_cmd = f"admin [Restart] T-{minutes_left} min..."
            self.send_rcon_command(target_ip, r_port_str, r_pass_str, msg_cmd)
            time.sleep(60)
            
        if self.reset_spawners_before_save.get() == "true":
            self.send_rcon_command(target_ip, r_port_str, r_pass_str, "resetspawners true")
            time.sleep(2)
            
        self.send_rcon_command(target_ip, r_port_str, r_pass_str, "save")
        time.sleep(4)
        self.send_rcon_command(target_ip, r_port_str, r_pass_str, "RestartNow")
        time.sleep(12)
        self.restart_in_progress = False 

    def run_manual_restart_timer(self, total_minutes, target_ip, r_port_str, r_pass_str):
        for m_left in range(total_minutes, 0, -1):
            msg_cmd = f"admin [Restart] T-{m_left} min..."
            self.send_rcon_command(target_ip, r_port_str, r_pass_str, msg_cmd)
            time.sleep(60)
            
        if self.reset_spawners_before_save.get() == "true":
            self.send_rcon_command(target_ip, r_port_str, r_pass_str, "resetspawners true")
            time.sleep(2)
            
        self.send_rcon_command(target_ip, r_port_str, r_pass_str, "save")
        time.sleep(4)
        self.send_rcon_command(target_ip, r_port_str, r_pass_str, "RestartNow")
        time.sleep(12)
        self.manual_restart_in_progress = False

    def chat_logs_watcher_loop(self):
        current_file_path = None
        processed_lines_count = 0
        first_read_done = False
        
        while True:
            if self.is_server_running and self.server_dir.get():
                chat_dir = os.path.join(self.server_dir.get(), "HumanitZServer", "HZLogs", "Chat")
                if os.path.exists(chat_dir):
                    try:
                        files = [os.path.join(chat_dir, f) for f in os.listdir(chat_dir) if os.path.isfile(os.path.join(chat_dir, f))]
                        if files:
                            latest_file = max(files, key=os.path.getmtime)
                            if latest_file != current_file_path:
                                current_file_path = latest_file
                                processed_lines_count = 0
                                first_read_done = False
                                self.after(0, lambda f=os.path.basename(latest_file): self.log(self.tr("log_mod_connected", file=f)))
                            
                            with open(current_file_path, "r", encoding="utf-8", errors="ignore") as f_flash:
                                all_lines = f_flash.readlines()
                            
                            if not first_read_done:
                                processed_lines_count = len(all_lines)
                                first_read_done = True
                                
                            current_total = len(all_lines)
                            if current_total > processed_lines_count:
                                new_lines = all_lines[processed_lines_count:]
                                processed_lines_count = current_total
                                for line in new_lines:
                                    if line.strip(): self.process_chat_line(line.strip())
                    except Exception: pass
            else:
                current_file_path = None
                processed_lines_count = 0
                first_read_done = False
            time.sleep(0.5)

    def process_chat_line(self, line):
        match = re.search(r'<\w+>(.*?):</>(.*)', line)
        if match:
            player_name = match.group(1).strip()
            message_text = match.group(2).strip().lower()
            for word in self.banned_words:
                if word in message_text:
                    self.execute_chat_punishment(player_name, word)
                    break

    def execute_chat_punishment(self, player_name, detected_word):
        now = time.time()
        if player_name in self.kick_cooldowns and (now - self.kick_cooldowns[player_name]) < 3.0:
            return
        
        rc_port = self.ini_vars.get("RConPort")
        rc_pass = self.ini_vars.get("RCONPass")
        r_port_str = rc_port["var"].get() if rc_port else "8888"
        r_pass_str = rc_pass["var"].get().strip('"') if rc_pass else ""
        target_ip = self.rcon_ip.get().strip()
        if not r_pass_str: return
        
        if player_name not in self.player_id_map:
            try: self.query_and_index_players(); time.sleep(0.4)
            except Exception: pass

        target_id = self.player_id_map.get(player_name, player_name)
        if player_name not in self.player_infractions: self.player_infractions[player_name] = 1
        else: self.player_infractions[player_name] += 1
            
        current_infractions = self.player_infractions[player_name]
        self.kick_cooldowns[player_name] = now
        
        if current_infractions == 1:
            self.after(0, lambda: self.log(self.tr("log_mod_word", word=detected_word, player=player_name, id=target_id)))
            warn_msg = self.tr("rcon_msg_warn", word=detected_word)
            warn_cmd = f"sendadminmsgto {target_id} {warn_msg}"
            threading.Thread(target=self.send_rcon_command, args=(target_ip, r_port_str, r_pass_str, warn_cmd), daemon=True).start()
        elif current_infractions >= 2:
            self.after(0, lambda: self.log(self.tr("log_mod_kick", player=player_name, id=target_id)))
            kick_cmd = f"kick {target_id}"
            self.player_infractions[player_name] = 0
            threading.Thread(target=self.send_rcon_command, args=(target_ip, r_port_str, r_pass_str, kick_cmd), daemon=True).start()

    def send_rcon_command(self, ip, port, password, command):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5) 
            sock.connect((ip, int(port)))
            
            packet_auth = struct.pack('<iii', len(password) + 10, 101, 3) + password.encode('utf-8') + b'\x00\x00'
            sock.sendall(packet_auth)
            res_auth = sock.recv(12)
            if len(res_auth) == 12:
                _, auth_id, _ = struct.unpack('<iii', res_auth)
                if auth_id == -1: sock.close(); return "ERROR"
            
            sock.settimeout(0.3)
            try: sock.recv(4096)
            except socket.timeout: pass
            
            sock.settimeout(2.5)
            packet_cmd = struct.pack('<iii', len(command) + 10, 202, 2) + command.encode('utf-8') + b'\x00\x00'
            sock.sendall(packet_cmd)
            sock.sendall(struct.pack('<iii', 10, 303, 2) + b'\x00\x00')
            
            response = b""
            while True:
                try:
                    header = sock.recv(12)
                    if len(header) < 12: break
                    size, packet_id, _ = struct.unpack('<iii', header)
                    if packet_id == 303: sock.recv(size - 8); break
                    response += sock.recv(size - 8)
                except socket.timeout: break
            sock.close()
            return response.decode('utf-8', errors='ignore').replace('\x00', '').strip()
        except Exception: return ""

    def send_manual_console_command(self):
        cmd_text = self.console_command_input.get().strip()
        if not cmd_text: return
        r_port_str = self.ini_vars["RConPort"]["var"].get() if "RConPort" in self.ini_vars else "8888"
        r_pass_str = self.ini_vars["RCONPass"]["var"].get().strip('"') if "RCONPass" in self.ini_vars else ""
        
        self.console_command_input.set("")
        threading.Thread(target=lambda: self.log(f"[RCON] {self.send_rcon_command(self.rcon_ip.get().strip(), r_port_str, r_pass_str, cmd_text)}"), daemon=True).start()

    def log(self, message):
        if not message: return
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[*] {message}\n")
        self.txt_log.configure(state="disabled")
        self.txt_log.see("end")

if __name__ == "__main__":
    app = ServerManagerApp()
    app.mainloop()