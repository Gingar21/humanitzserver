import customtkinter as ctk
import socket, struct, threading, time, re, os, json
import paramiko
from cryptography.fernet import Fernet
from tkinter import filedialog

# --- CONFIGURATION APPDATA & SÉCURITÉ ---
APP_NAME = "HumanitZManager"
APPDATA_DIR = os.path.join(os.environ["APPDATA"], APP_NAME)
if not os.path.exists(APPDATA_DIR):
    os.makedirs(APPDATA_DIR)

HELP_FILE = "RCONCommands.txt"
KEY = For Encrypted file change this

HUMANITZ_COMMANDS = [
    "--- Info & Players ---", "info", "Players", "fetchbanned",
    "--- World ---", "season ", "weather ",
    "--- Admin ---", "admin ", "kick ", "ban ", "unban "
]

class Encryptor:
    def __init__(self, key):
        self.fernet = Fernet(key)
    def encrypt(self, data):
        if not data: return ""
        return self.fernet.encrypt(str(data).encode()).decode()
    def decrypt(self, data):
        if not data: return ""
        try: return self.fernet.decrypt(data.encode()).decode()
        except: return ""

class ServerManagerFrame(ctk.CTkFrame):
    def __init__(self, master, server_id, cipher, info_labels, main_app, **kwargs):
        super().__init__(master, **kwargs)
        
        self.server_id = server_id
        self.cipher = cipher
        self.main_app = main_app
        self.config_path = os.path.join(APPDATA_DIR, f"server_{server_id}.enc")
        self.info_labels = info_labels
        
        self.sock = None
        self.ssh_client = None
        self.sftp = None
        self.request_id = 100
        self.last_log_size = 0
        self.local_log_path = None
        self.is_local_mode = False
        self.ssh_key_path = None # Chemin vers la clé privée
        
        self.player_widgets = {}
        self.network_lock = threading.Lock()
        self.help_window = None
        self.auto_msg_window = None
        self.auto_msg_active = False
        self.auto_msg_text = ""
        self.auto_msg_interval = 10 
        
        self.config = self.load_config()
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure((1, 2, 3), weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.setup_ui()
        threading.Thread(target=self.monitoring_loop, daemon=True).start()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    enc_data = json.load(f)
                    dec_data = {k: self.cipher.decrypt(v) for k, v in enc_data.items()}
                    self.ssh_key_path = dec_data.get("ssh_key_path", None)
                    return dec_data
            except: return {}
        return {}

    def save_config(self):
        data = {
            "ip": self.cipher.encrypt(self.ip_ent.get()),
            "port": self.cipher.encrypt(self.port_ent.get()),
            "pass": self.cipher.encrypt(self.pass_ent.get()),
            "ssh_host": self.cipher.encrypt(self.ssh_host.get()),
            "ssh_user": self.cipher.encrypt(self.ssh_user.get()),
            "ssh_pass": self.cipher.encrypt(self.ssh_pass.get()),
            "ssh_port": self.cipher.encrypt(self.ssh_port.get()),
            "ssh_path": self.cipher.encrypt(self.ssh_path.get()),
            "ssh_key_path": self.cipher.encrypt(self.ssh_key_path if self.ssh_key_path else "")
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=4)

    def setup_ui(self):
        self.sidebar = ctk.CTkScrollableFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # --- RCON ---
        ctk.CTkLabel(self.sidebar, text="RCON SETTINGS", font=("Segoe UI", 16, "bold")).pack(pady=(10, 5))
        self.ip_ent = self.create_ent("Server IP", self.config.get("ip", ""))
        self.port_ent = self.create_ent("RCON Port", self.config.get("port", ""))
        self.pass_ent = self.create_ent("RCON Password", self.config.get("pass", ""), show="*")
        ctk.CTkButton(self.sidebar, text="CONNECT RCON", fg_color="#1f538d", command=self.connect_rcon).pack(pady=10, padx=20, fill="x")

        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333").pack(fill="x", padx=10, pady=10)

        # --- CHAT LOGS ---
        ctk.CTkLabel(self.sidebar, text="CHAT LOGS", font=("Segoe UI", 16, "bold"), text_color="#3498db").pack(pady=5)
        self.ssh_host = self.create_ent("SSH Host IP", self.config.get("ssh_host", ""))
        self.ssh_user = self.create_ent("SSH User", self.config.get("ssh_user", ""))
        self.ssh_pass = self.create_ent("SSH Password", self.config.get("ssh_pass", ""), show="*")
        self.ssh_port = self.create_ent("SSH Port", self.config.get("ssh_port", ""))
        self.ssh_path = self.create_ent("Remote Logs Path", self.config.get("ssh_path", ""))
        
        ctk.CTkButton(self.sidebar, text="CONNECT SSH", fg_color="#2980b9", command=lambda: self.connect_ssh(use_key=False)).pack(pady=5, padx=20, fill="x")
        
        # NOUVEAU BOUTON SSH-KEY
        ctk.CTkButton(self.sidebar, text="CONNECT WITH SSH-KEY", fg_color="#16a085", command=self.select_ssh_key).pack(pady=5, padx=20, fill="x")
        
        ctk.CTkLabel(self.sidebar, text="--- OR ---", font=("Segoe UI", 12, "bold"), text_color="gray").pack(pady=2)
        ctk.CTkButton(self.sidebar, text="LOCAL LOGS CHAT", fg_color="#5d6d7e", command=self.select_local_logs).pack(pady=5, padx=20, fill="x")

        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333").pack(fill="x", padx=10, pady=10)
        
        # --- ACTIONS ---
        ctk.CTkButton(self.sidebar, text="SAVE ID ON THIS PC", fg_color="#6c5ce7", command=self.save_config).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="SAVE WORLD", fg_color="#2d8a4e", command=lambda: self.send_command("save")).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="RESTART", fg_color="#c0392b", command=self.ask_restart_time).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="CANCEL RESTART", fg_color="#555555", command=lambda: self.send_command("CancelRestart")).pack(pady=5, padx=20, fill="x")
        self.btn_auto_msg = ctk.CTkButton(self.sidebar, text="AUTOMATIQUE MESSAGE", fg_color="#d35400", command=self.open_auto_msg_window)
        self.btn_auto_msg.pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(self.sidebar, text="LIST RCON COMMANDS", fg_color="#8e44ad", command=self.open_help_window).pack(pady=5, padx=20, fill="x")
        self.cmd_menu = ctk.CTkOptionMenu(self.sidebar, values=HUMANITZ_COMMANDS, command=self.on_menu_select)
        self.cmd_menu.pack(pady=15, padx=20, fill="x")
        self.cmd_menu.set("QUICK CMDS")

        # --- PANELS ---
        f1 = ctk.CTkFrame(self, fg_color="transparent")
        f1.grid(row=0, column=1, sticky="nsew", padx=5, pady=10)
        ctk.CTkLabel(f1, text="ACTIVE PLAYERS", font=("Segoe UI", 13, "bold")).pack()
        self.player_scroll = ctk.CTkScrollableFrame(f1, fg_color="#151515")
        self.player_scroll.pack(fill="both", expand=True)

        f2 = ctk.CTkFrame(self, fg_color="transparent")
        f2.grid(row=0, column=2, sticky="nsew", padx=5, pady=10)
        ctk.CTkLabel(f2, text="GAME CHAT", font=("Segoe UI", 13, "bold"), text_color="#3498db").pack()
        self.txt_chat = ctk.CTkTextbox(f2, state="disabled", font=("Segoe UI", 14), fg_color="#0a0a0a")
        self.txt_chat.pack(fill="both", expand=True)
        chat_input_f = ctk.CTkFrame(f2, fg_color="transparent")
        chat_input_f.pack(fill="x", pady=5)
        self.ent_chat = ctk.CTkEntry(chat_input_f, placeholder_text="Type a message...", fg_color="#000000", border_color="#333333")
        self.ent_chat.pack(side="left", fill="x", expand=True, padx=2)
        self.ent_chat.bind("<Return>", lambda e: self.send_chat_msg())
        ctk.CTkButton(chat_input_f, text="SEND", width=60, command=self.send_chat_msg).pack(side="right")

        f3 = ctk.CTkFrame(self, fg_color="transparent")
        f3.grid(row=0, column=3, sticky="nsew", padx=5, pady=10)
        ctk.CTkLabel(f3, text="RCON CONSOLE", font=("Segoe UI", 13, "bold")).pack()
        self.txt_con = ctk.CTkTextbox(f3, state="disabled", font=("Consolas", 14), fg_color="black")
        self.txt_con.pack(fill="both", expand=True)
        cmd_f = ctk.CTkFrame(f3, fg_color="transparent")
        cmd_f.pack(fill="x", pady=5)
        self.ent_cmd = ctk.CTkEntry(cmd_f, placeholder_text="Command Rcon...", fg_color="#000000", border_color="#333333")
        self.ent_cmd.pack(side="left", fill="x", expand=True, padx=2)
        self.ent_cmd.bind("<Return>", lambda e: self.send_command())
        ctk.CTkButton(cmd_f, text="SEND", width=60, command=self.send_command).pack(side="right")

    def create_ent(self, p, v, **kwargs):
        e = ctk.CTkEntry(self.sidebar, placeholder_text=p, **kwargs)
        if v: e.insert(0, v)
        e.pack(pady=2, padx=20, fill="x")
        return e

    # --- LOGIQUE SSH-KEY ---
    def select_ssh_key(self):
        file_path = filedialog.askopenfilename(title="Select Private Key File")
        if file_path:
            self.ssh_key_path = file_path
            self.log_chat(f"<SYSTEM>: SSH-KEY LOADED: {os.path.basename(file_path)}")
            # On tente la connexion immédiatement avec la clé
            self.connect_ssh(use_key=True)

    # --- LOGIQUE CONNEXION SSH ---
    def connect_ssh(self, use_key=False):
        self.is_local_mode = False
        try:
            if self.ssh_client: self.ssh_client.close()
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            host = self.ssh_host.get()
            user = self.ssh_user.get()
            port = int(self.ssh_port.get())
            
            if use_key and self.ssh_key_path:
                self.log_chat("<SYSTEM>: Connecting using SSH-Key...")
                # Tente de charger la clé (gère les formats RSA, DSS, ECDSA, Ed25519 automatiquement)
                self.ssh_client.connect(host, username=user, port=port, key_filename=self.ssh_key_path, timeout=10)
            else:
                self.log_chat("<SYSTEM>: Connecting using Password...")
                self.ssh_client.connect(host, username=user, password=self.ssh_pass.get(), port=port, timeout=10)

            self.ssh_client.get_transport().set_keepalive(30)
            self.sftp = self.ssh_client.open_sftp()
            self.log_chat("<SYSTEM>: SSH CONNECTED SUCCESSFULLY")
        except Exception as e: 
            self.log_chat(f"<SYSTEM>: SSH ERROR - {e}")

    # --- LOGIQUE LOGS LOCAUX ---
    def select_local_logs(self):
        folder = filedialog.askdirectory(title="Select HumanitZ Logs Folder")
        if folder:
            self.local_log_path = folder
            self.is_local_mode = True
            self.last_log_size = 0
            self.log_chat(f"<SYSTEM>: LOCAL MODE ACTIVE - Folder: {folder}")

    def monitoring_loop(self):
        while True:
            if self.sock:
                active_tab = self.main_app.tabview.get()
                is_active = active_tab == f"Server {self.server_id}"
                self.send_command("Players", silent=True, update_header=is_active)
                if is_active:
                    if self.is_local_mode: self.check_local_logs()
                    else: self.check_ssh_logs()
            time.sleep(4)

    def check_local_logs(self):
        if not self.local_log_path: return
        try:
            files = [os.path.join(self.local_log_path, f) for f in os.listdir(self.local_log_path) if f.endswith(".log")]
            if not files: return
            latest_file = max(files, key=os.path.getmtime)
            curr_size = os.path.getsize(latest_file)
            if curr_size > self.last_log_size:
                with open(latest_file, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.last_log_size)
                    for line in f.readlines():
                        if line.strip(): self.after(0, lambda l=line: self.log_chat(l))
                self.last_log_size = curr_size
        except: pass

    def check_ssh_logs(self):
        if not self.sftp: return
        try:
            if not self.ssh_client.get_transport().is_active(): 
                # Reconnexion automatique avec le dernier mode utilisé
                self.connect_ssh(use_key=(self.ssh_key_path is not None))
                return
            path = self.ssh_path.get()
            files = self.sftp.listdir(path)
            logs = [f for f in files if f.endswith(".log")]
            if not logs: return
            latest = max(logs, key=lambda f: self.sftp.stat(os.path.join(path, f)).st_mtime)
            full = os.path.join(path, latest).replace("\\", "/")
            size = self.sftp.stat(full).st_size
            if size > self.last_log_size:
                with self.sftp.open(full, "r") as f:
                    f.seek(self.last_log_size)
                    for line in f.readlines(): self.after(0, lambda l=line: self.log_chat(l))
                self.last_log_size = size
        except: pass

    def connect_rcon(self):
        def _task():
            with self.network_lock:
                try:
                    if self.sock: self.sock.close()
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(3)
                    self.sock.connect((self.ip_ent.get(), int(self.port_ent.get())))
                    auth = struct.pack('<ii', 1, 3) + self.pass_ent.get().encode() + b'\x00\x00'
                    self.sock.sendall(struct.pack('<i', len(auth)) + auth)
                    self.sock.recv(4096)
                    if self.main_app.tabview.get() == f"Server {self.server_id}":
                        self.after(0, lambda: self.info_labels['status'].configure(text="STATUS: ONLINE", text_color="#2ecc71"))
                except: 
                    if self.main_app.tabview.get() == f"Server {self.server_id}":
                        self.after(0, lambda: self.info_labels['status'].configure(text="STATUS: OFFLINE", text_color="#e74c3c"))
        threading.Thread(target=_task, daemon=True).start()

    def log_chat(self, raw):
        clean = re.sub(r'<[^>]+>', '', raw).strip()
        if clean:
            if "(" not in clean or "/" not in clean: clean = f"[{time.strftime('%H:%M')}] {clean}"
            self.txt_chat.configure(state="normal")
            self.txt_chat.insert("end", clean + "\n")
            self.txt_chat.configure(state="disabled"); self.txt_chat.see("end")

    def send_command(self, cmd=None, silent=False, update_header=False):
        c = cmd if cmd else self.ent_cmd.get()
        if not c or not self.sock: return
        with self.network_lock:
            try:
                self.sock.settimeout(0.1)
                try: 
                    while self.sock.recv(4096): pass
                except: pass
                self.request_id += 1
                pkt = struct.pack('<ii', self.request_id, 2) + c.encode() + b'\x00\x00'
                self.sock.sendall(struct.pack('<i', len(pkt)) + pkt)
                self.sock.settimeout(3.0)
                data = self.sock.recv(16384)
                res = data[12:].decode('utf-8', errors='ignore').replace('\x00', '').strip()
                if c == "Players": self.after(0, lambda: self.update_players(res, update_header))
                if not silent: self.after(0, lambda: self.display_con(c, res))
            except: pass

    def update_players(self, data, update_header):
        current_ids = []
        for line in data.split('\n'):
            if not line.strip() or "Players" in line: continue
            sid_match = re.search(r'(\d{17})', line)
            if not sid_match: continue
            sid = sid_match.group(1)
            current_ids.append(sid)
            if sid not in self.player_widgets:
                row = ctk.CTkFrame(self.player_scroll, fg_color="#222")
                row.pack(fill="x", pady=2, padx=5)
                ctk.CTkLabel(row, text=line.strip(), font=("Consolas", 10), wraplength=200).pack(pady=2)
                btn_f = ctk.CTkFrame(row, fg_color="transparent")
                btn_f.pack(fill="x")
                ctk.CTkButton(btn_f, text="KICK", height=22, fg_color="#d35400", command=lambda s=sid: self.send_command(f"kick {s}")).pack(side="left", expand=True, padx=2, pady=2)
                ctk.CTkButton(btn_f, text="BAN", height=22, fg_color="#c0392b", command=lambda s=sid: self.send_command(f"ban {s}")).pack(side="left", expand=True, padx=2, pady=2)
                self.player_widgets[sid] = row
            else:
                for child in self.player_widgets[sid].winfo_children():
                    if isinstance(child, ctk.CTkLabel): child.configure(text=line.strip())
        if update_header:
            self.info_labels['players'].configure(text=f"ONLINE PLAYERS: {len(current_ids)}")
            self.info_labels['status'].configure(text="STATUS: ONLINE", text_color="#2ecc71")
        for sid in list(self.player_widgets.keys()):
            if sid not in current_ids:
                self.player_widgets[sid].destroy()
                del self.player_widgets[sid]

    def display_con(self, c, r):
        self.txt_con.configure(state="normal")
        self.txt_con.insert("end", f"> {c}: {r if r else 'OK'}\n")
        self.txt_con.configure(state="disabled"); self.txt_con.see("end")
        self.ent_cmd.delete(0, 'end')

    def open_help_window(self):
        if self.help_window is None or not self.help_window.winfo_exists():
            self.help_window = ctk.CTkToplevel(self)
            self.help_window.title("RCON Commands")
            self.help_window.geometry("500x600")
            self.help_window.attributes("-topmost", True)
            txt = ctk.CTkTextbox(self.help_window, font=("Consolas", 13))
            txt.pack(fill="both", expand=True, padx=10, pady=10)
            if os.path.exists(HELP_FILE):
                with open(HELP_FILE, "r", encoding="utf-8") as f: txt.insert("0.0", f.read())
            txt.configure(state="disabled")
        else: self.help_window.focus()

    def open_auto_msg_window(self):
        if self.auto_msg_window is None or not self.auto_msg_window.winfo_exists():
            self.auto_msg_window = ctk.CTkToplevel(self)
            self.auto_msg_window.title("Auto Message Config")
            self.auto_msg_window.geometry("400x300")
            self.auto_msg_window.attributes("-topmost", True)
            ctk.CTkLabel(self.auto_msg_window, text="MESSAGE TO BROADCAST:", font=("Segoe UI", 12, "bold")).pack(pady=10)
            msg_entry = ctk.CTkEntry(self.auto_msg_window, width=350)
            msg_entry.insert(0, self.auto_msg_text)
            msg_entry.pack(pady=5)
            ctk.CTkLabel(self.auto_msg_window, text="INTERVAL (MINUTES):", font=("Segoe UI", 12, "bold")).pack(pady=10)
            time_entry = ctk.CTkEntry(self.auto_msg_window, width=100)
            time_entry.insert(0, str(self.auto_msg_interval))
            time_entry.pack(pady=5)
            btn_f = ctk.CTkFrame(self.auto_msg_window, fg_color="transparent")
            btn_f.pack(pady=20)
            def start():
                self.auto_msg_text = msg_entry.get()
                self.auto_msg_interval = int(time_entry.get())
                self.auto_msg_active = True
                self.btn_auto_msg.configure(fg_color="#27ae60", text="AUTO MESSAGE: ON")
                threading.Thread(target=self.auto_message_loop, daemon=True).start()
                self.auto_msg_window.destroy()
            def stop():
                self.auto_msg_active = False
                self.btn_auto_msg.configure(fg_color="#d35400", text="AUTOMATIQUE MESSAGE")
                self.auto_msg_window.destroy()
            ctk.CTkButton(btn_f, text="START", fg_color="#27ae60", width=100, command=start).pack(side="left", padx=10)
            ctk.CTkButton(btn_f, text="STOP / OFF", fg_color="#c0392b", width=100, command=stop).pack(side="left", padx=10)

    def auto_message_loop(self):
        while self.auto_msg_active:
            if self.sock: self.send_command(f"admin {self.auto_msg_text}", silent=True)
            for _ in range(self.auto_msg_interval * 60):
                if not self.auto_msg_active: return
                time.sleep(1)

    def ask_restart_time(self):
        d = ctk.CTkInputDialog(text="Minutes:", title="Restart")
        m = d.get_input()
        if m: self.send_command(f"restart {m}")

    def send_chat_msg(self):
        msg = self.ent_chat.get()
        if msg: self.send_command(f"admin {msg}"); self.ent_chat.delete(0, 'end')

    def on_menu_select(self, sel):
        if "---" in sel: return
        if sel.endswith(" "):
            v = ctk.CTkInputDialog(text=f"Value for {sel}:", title="Admin").get_input()
            if v: self.send_command(f"{sel}{v}")
        else: self.send_command(sel)
        self.cmd_menu.set("QUICK CMDS")

class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HumanitZ Rcon By PolarBear v1.5")
        self.geometry("1400x900")
        ctk.set_appearance_mode("dark")
        self.cipher = Encryptor(KEY)
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=20, pady=(10, 0))
        self.info_labels = {
            'players': ctk.CTkLabel(self.header, text="ONLINE PLAYERS: 0", font=("Segoe UI", 12, "bold"), text_color="#3498db"),
            'status': ctk.CTkLabel(self.header, text="STATUS: OFFLINE", font=("Segoe UI", 12, "bold"), text_color="gray")
        }
        self.info_labels['status'].pack(side="right", padx=20)
        self.info_labels['players'].pack(side="right", padx=20)
        self.tabview = ctk.CTkTabview(self, segmented_button_fg_color="#1a1a1a", command=self.on_tab_change)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabview.add("Server 1")
        self.server1 = ServerManagerFrame(self.tabview.tab("Server 1"), 1, self.cipher, self.info_labels, self)
        self.server1.pack(fill="both", expand=True)
        self.tabview.add("Server 2")
        self.server2 = ServerManagerFrame(self.tabview.tab("Server 2"), 2, self.cipher, self.info_labels, self)
        self.server2.pack(fill="both", expand=True)
    def on_tab_change(self):
        self.info_labels['players'].configure(text="ONLINE PLAYERS: 0")
        self.info_labels['status'].configure(text="STATUS: OFFLINE", text_color="gray")

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
