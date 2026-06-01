
import os
import re
import json
import time
import socket
import struct
import threading
import subprocess
import configparser
from datetime import datetime
from pathlib import Path

CONFIG_FILE = "manager_config.json"
BANNED_WORDS_FILE = "mots_interdits.txt"
RCON_COMMANDS_FILE = "RCONCommands.txt"

DEFAULT_RCON_COMMANDS = [
    "info",
    "save",
    "QuickRestart",
    "Players",
    "RestartNow",
    "CancelRestart",
    "admin",
    "kick",
    "restart",
    "shutdown",
]

TRUE_FALSE_KEYS = {
    "RCONEnabled", "UseGlobalBanList", "AllowFamilySharing", "LimitedSpawns",
    "NoDeathFeedback", "NoJoinFeedback", "PVP", "PermaDeath", "LootRespawn",
    "AllowDismantle", "AllowHouseDismantle", "AirDrop", "WeaponBreak",
    "Sleep", "MultiplayerSleep", "DogEnabled", "FreezeTime"
}

SECRET_KEYS = {"Password", "AdminPass", "RCONPass"}

class HumanitZAdvancedService:
    """
    Web-friendly port of the original CustomTkinter manager logic.

    Included:
    - manager_config.json load/save
    - GameServerSettings.ini load/save
    - RCON command sender
    - watchdog restart support
    - auto restart scheduler support
    - auto message support
    - banned words/modération chat support
    - player SteamID indexing through RCON Players
    """

    def __init__(self, base_dir=None, logger=None):
        self.base_dir = Path(base_dir or os.getcwd())
        self.logger = logger or (lambda msg: None)

        self.config_path = self.base_dir / CONFIG_FILE
        self.banned_words_path = self.base_dir / BANNED_WORDS_FILE
        self.rcon_commands_path = self.base_dir / RCON_COMMANDS_FILE

        self.state = {
            "steamcmd_dir": "",
            "server_dir": "",
            "net_port": "7777",
            "net_queryport": "27015",
            "rcon_ip": "127.0.0.1",
            "watchdog_enabled": "false",
            "auto_restart_enabled": "false",
            "restart_time_1": "",
            "restart_time_2": "",
            "restart_time_3": "",
            "restart_time_4": "",
            "reset_spawners_before_save": "false",
            "auto_msg_text": "",
            "auto_msg_interval": 0,
            "auto_msg_enabled": "false",
        }

        self.player_id_map = {}
        self.player_infractions = {}
        self.kick_cooldowns = {}
        self.banned_words = []

        self.restart_in_progress = False
        self.manual_restart_in_progress = False
        self.user_stopped_server = False
        self.auto_msg_thread_running = False

        self.init_files()
        self.load_state()

    def init_files(self):
        if not self.banned_words_path.exists():
            self.banned_words_path.write_text(
                "; Inscrivez un mot interdit par ligne\ncheater\nnoob\n",
                encoding="utf-8"
            )
        if not self.rcon_commands_path.exists():
            self.rcon_commands_path.write_text(
                "// --- LISTE DES COMMANDES RCON HUMANITZ ---\n"
                "info             : Affiche les informations du serveur\n"
                "save             : Sauvegarde le monde actuel\n"
                "Players          : Liste les joueurs connectés avec SteamID\n"
                "admin <message>  : Envoie un message global à tout le serveur\n"
                "kick <SteamID>   : Expulse un joueur spécifique du serveur\n"
                "RestartNow       : Redémarre le serveur immédiatement\n",
                encoding="utf-8"
            )
        self.load_banned_words()

    def load_state(self):
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.state.update(data)
            except Exception as exc:
                self.logger(f"[Config] Impossible de charger {CONFIG_FILE}: {exc}")
        return self.state

    def save_state(self, data=None):
        if data:
            self.state.update(data)
        self.config_path.write_text(json.dumps(self.state, indent=4, ensure_ascii=False), encoding="utf-8")
        return self.state

    def get_settings_ini_path(self):
        server_dir = self.state.get("server_dir", "")
        if not server_dir:
            return None
        return Path(server_dir) / "HumanitZServer" / "GameServerSettings.ini"

    def load_ini(self):
        ini_path = self.get_settings_ini_path()
        if not ini_path or not ini_path.exists():
            return {"ok": False, "error": "GameServerSettings.ini introuvable", "path": str(ini_path) if ini_path else ""}

        config = configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=";")
        config.optionxform = str
        config.read(ini_path, encoding="utf-8")

        data = {}
        for section in config.sections():
            data[section] = {}
            for key, value in config.items(section):
                value = (value or "").strip().strip('"')
                if key in SECRET_KEYS and value:
                    data[section][key] = {"value": value, "secret": True}
                elif key in TRUE_FALSE_KEYS or value.lower() in ("true", "false"):
                    data[section][key] = {"value": value.lower(), "type": "switch"}
                else:
                    data[section][key] = {"value": value}
        return {"ok": True, "path": str(ini_path), "data": data}

    def save_ini(self, payload):
        ini_path = self.get_settings_ini_path()
        if not ini_path:
            return {"ok": False, "error": "Dossier serveur non configuré"}

        ini_path.parent.mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=";")
        config.optionxform = str

        if ini_path.exists():
            config.read(ini_path, encoding="utf-8")

        for section, values in payload.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, raw in values.items():
                value = raw.get("value") if isinstance(raw, dict) else raw
                value = str(value)
                if key in SECRET_KEYS and value and not value.startswith('"'):
                    value = f'"{value}"'
                config.set(section, key, value)

        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f, space_around_delimiters=False)

        self.generate_start_bat()
        return {"ok": True, "path": str(ini_path)}

    def generate_start_bat(self):
        server_dir = self.state.get("server_dir", "")
        if not server_dir:
            return {"ok": False, "error": "Dossier serveur non configuré"}

        p = self.state.get("net_port") or "7777"
        qp = self.state.get("net_queryport") or "27015"
        bat = Path(server_dir) / "start.bat"
        bat.write_text(f"start HumanitZServer.exe -log port={p} queryport={qp}\n", encoding="utf-8")
        return {"ok": True, "path": str(bat)}

    def is_server_running(self):
        try:
            out1 = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq HumanitZServer-Win64-Shipping.exe" /FO CSV',
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True
            )
            out2 = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq HumanitZServer.exe" /FO CSV',
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True
            )
            return "HumanitZServer-Win64-Shipping.exe" in out1 or "HumanitZServer.exe" in out2
        except Exception:
            return False

    def start_server(self):
        server_dir = self.state.get("server_dir", "")
        if not server_dir:
            return {"ok": False, "error": "Dossier serveur non configuré"}

        bat = Path(server_dir) / "start.bat"
        if not bat.exists():
            self.generate_start_bat()

        self.user_stopped_server = False
        subprocess.Popen([str(bat)], cwd=server_dir, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "message": "Serveur démarré"}

    def stop_server(self):
        self.user_stopped_server = True
        try:
            subprocess.run(["taskkill", "/F", "/IM", "HumanitZServer.exe", "/T"], creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run(["taskkill", "/F", "/IM", "HumanitZServer-Win64-Shipping.exe", "/T"], creationflags=subprocess.CREATE_NO_WINDOW)
            return {"ok": True, "message": "Serveur arrêté"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def restart_server(self):
        self.stop_server()
        time.sleep(2)
        return self.start_server()

    def get_rcon_settings_from_ini(self):
        result = self.load_ini()
        if not result.get("ok"):
            return None

        host = result["data"].get("Host Settings", {})
        return {
            "enabled": str(host.get("RCONEnabled", {}).get("value", "false")).lower() == "true",
            "ip": self.state.get("rcon_ip", "127.0.0.1"),
            "port": host.get("RConPort", {}).get("value", "8888"),
            "password": host.get("RCONPass", {}).get("value", ""),
        }

    def send_rcon_command(self, command, ip=None, port=None, password=None):
        settings = self.get_rcon_settings_from_ini() or {}
        ip = ip or settings.get("ip") or "127.0.0.1"
        port = port or settings.get("port") or "8888"
        password = password or settings.get("password") or ""

        if not password:
            return {"ok": False, "error": "Mot de passe RCON vide", "response": ""}

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect((ip, int(port)))

            packet_auth = struct.pack("<iii", len(password) + 10, 101, 3) + password.encode("utf-8") + b"\x00\x00"
            sock.sendall(packet_auth)

            # read auth response(s)
            auth_ok = False
            start = time.time()
            while time.time() - start < 3:
                header = sock.recv(12)
                if len(header) < 12:
                    break
                size, packet_id, packet_type = struct.unpack("<iii", header)
                body = sock.recv(max(size - 8, 0))
                if packet_id == -1:
                    sock.close()
                    return {"ok": False, "error": "Authentification RCON refusée", "response": ""}
                if packet_id == 101:
                    auth_ok = True
                    break

            if not auth_ok:
                # HumanitZ may not echo auth normally, continue cautiously
                pass

            sock.settimeout(0.5)
            try:
                while sock.recv(4096):
                    pass
            except Exception:
                pass

            sock.settimeout(3.0)
            packet_cmd = struct.pack("<iii", len(command) + 10, 202, 2) + command.encode("utf-8") + b"\x00\x00"
            sock.sendall(packet_cmd)

            # terminator packet
            sock.sendall(struct.pack("<iii", 10, 303, 2) + b"\x00\x00")

            response = b""
            while True:
                try:
                    header = sock.recv(12)
                    if len(header) < 12:
                        break
                    size, packet_id, packet_type = struct.unpack("<iii", header)
                    body = sock.recv(max(size - 8, 0))
                    if packet_id == 303:
                        break
                    response += body
                except socket.timeout:
                    break

            sock.close()
            text = response.decode("utf-8", errors="ignore").replace("\x00", "").strip()
            return {"ok": True, "command": command, "response": text}
        except Exception as exc:
            return {"ok": False, "command": command, "error": str(exc), "response": ""}

    def test_rcon(self):
        settings = self.get_rcon_settings_from_ini()
        if not settings:
            return {"ok": False, "error": "Impossible de lire la configuration RCON"}
        if not settings["enabled"]:
            return {"ok": False, "error": "RCONEnabled=false dans GameServerSettings.ini"}
        return self.send_rcon_command("save", settings["ip"], settings["port"], settings["password"])

    def load_banned_words(self):
        try:
            lines = self.banned_words_path.read_text(encoding="utf-8").splitlines()
            self.banned_words = [l.strip().lower() for l in lines if l.strip() and not l.strip().startswith(";")]
        except Exception:
            self.banned_words = []
        return self.banned_words

    def save_banned_words(self, words):
        clean = []
        for w in words:
            w = str(w).strip().lower()
            if w:
                clean.append(w)
        self.banned_words_path.write_text("; Inscrivez un mot interdit par ligne\n" + "\n".join(clean) + "\n", encoding="utf-8")
        self.load_banned_words()
        return self.banned_words

    def query_and_index_players(self):
        result = self.send_rcon_command("Players")
        text = result.get("response", "")
        if not result.get("ok"):
            return result

        for line in text.splitlines():
            match = re.search(r"^\s*(.*?)\s*\((7656\d{13})", line)
            if match:
                player_name = match.group(1).strip()
                steam_id = match.group(2).strip()
                if player_name and steam_id:
                    self.player_id_map[player_name] = steam_id

        return {"ok": True, "players": self.player_id_map, "raw": text}

    def process_chat_line(self, line):
        match = re.search(r"<\w+>(.*?):</>(.*)", line)
        if not match:
            return None

        player_name = match.group(1).strip()
        message_text = match.group(2).strip().lower()

        for word in self.banned_words:
            if word in message_text:
                return self.execute_chat_punishment(player_name, word)
        return None

    def execute_chat_punishment(self, player_name, detected_word):
        now = time.time()
        if player_name in self.kick_cooldowns and (now - self.kick_cooldowns[player_name]) < 3.0:
            return {"ok": False, "error": "Cooldown actif"}

        if player_name not in self.player_id_map:
            self.query_and_index_players()
            time.sleep(0.4)

        target_id = self.player_id_map.get(player_name, player_name)
        self.player_infractions[player_name] = self.player_infractions.get(player_name, 0) + 1
        current = self.player_infractions[player_name]
        self.kick_cooldowns[player_name] = now

        if current == 1:
            cmd = f"sendadminmsgto {target_id} Mot interdit détecté: {detected_word}"
            return self.send_rcon_command(cmd)
        else:
            self.player_infractions[player_name] = 0
            return self.send_rcon_command(f"kick {target_id}")

    def scheduled_restart_sequence(self, minutes):
        settings = self.get_rcon_settings_from_ini()
        if not settings:
            return {"ok": False, "error": "RCON non configuré"}

        for m_left in range(int(minutes), 0, -1):
            self.send_rcon_command(f"admin [Restart] T-{m_left} min...", settings["ip"], settings["port"], settings["password"])
            time.sleep(60)

        if self.state.get("reset_spawners_before_save") == "true":
            self.send_rcon_command("resetspawners true", settings["ip"], settings["port"], settings["password"])
            time.sleep(2)

        self.send_rcon_command("save", settings["ip"], settings["port"], settings["password"])
        time.sleep(4)
        self.send_rcon_command("RestartNow", settings["ip"], settings["port"], settings["password"])
        return {"ok": True}
