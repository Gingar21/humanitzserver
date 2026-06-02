import uuid
import secrets
import hashlib
import zipfile
import urllib.request
import struct
import mimetypes
import shutil
import tarfile
import time
import subprocess
import socket
import re
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
import os, json, time, subprocess, zipfile, socket, struct, configparser, threading, shutil
import sys
try:
    import psutil
except Exception:
    psutil = None

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS and hasattr(subprocess, "CREATE_NO_WINDOW") else 0

if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    exe_dir = Path(sys.executable).resolve().parent
    ROOT = exe_dir.parent if exe_dir.name.lower().startswith("dist") and (exe_dir.parent / "data").exists() else exe_dir
else:
    BUNDLE_ROOT = Path(__file__).resolve().parents[1]
    ROOT = BUNDLE_ROOT
DATA = ROOT / 'data'
LOGS = ROOT / 'logs'
FRONTEND = BUNDLE_ROOT / 'frontend'
LANGUAGES = BUNDLE_ROOT / 'languages'
CONFIG = DATA / 'panel_config.json'
PANEL_LOG = LOGS / 'panel.log'
DATA.mkdir(exist_ok=True); LOGS.mkdir(exist_ok=True)

LANGUAGE_FILES = {
    "fr": "Fran#U00e7ais.ini",
    "en": "English.ini",
    "es": "Español.ini",
    "de": "Deutsch.ini",
    "it": "Italiano.ini",
    "pt": "Português.ini",
    "nl": "Nederlands.ini",
    "pl": "Polski.ini",
}

DEFAULT_CONFIG = {
    'server_dir': '', 'steamcmd_dir': '', 'port': '7777', 'query_port': '27015',
    'rcon_ip': '127.0.0.1', 'rcon_port': '8888', 'rcon_password': '',
    'watchdog_enabled': False, 'auto_message_enabled': False, 'auto_message_text': '',
    'auto_message_interval': 15, 'auto_restart_enabled': False, 'restart_times': [],
    'watchdog_enabled': False, 'watchdog_interval': 5, 'watchdog_relaunch_delay': 5,
    'auto_messages_enabled': False, 'auto_messages_interval': 15, 'auto_messages_mode': 'rotation',
    'auto_messages_list': ['Bienvenue sur HumanitZ !', 'Respectez les règles du serveur.', 'Bon jeu à tous !'],
    'chat_moderation_enabled': False, 'chat_warn_before_kick': 1,
    'chat_kick_enabled': True, 'chat_warning_enabled': True,
    'chat_infraction_reset_minutes': 60,
    'server_process_names': ['HumanitZServer-Win64-Shipping.exe', 'HumanitZServer.exe', 'HumanitZServer-Win64-Shipping-Cmd.exe', 'HumanitZ.exe', 'HumanitZServer', 'HumanitZServer.sh'],
    'humanitz_app_id': '2728330', 'steamcmd_url': 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip',
    'steamcmd_linux_url': 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz',
    'reset_spawners_before_save': False, 'auto_restart_warning_minutes': 10
}

SERVER_PROFILE_KEYS = [
    "server_dir",
    "steamcmd_dir",
    "rcon_ip",
    "rcon_port",
    "rcon_password",
    "port",
    "query_port",
    "net_port",
    "net_queryport",
    "humanitz_app_id",
]

INI_FIELDS = {
 'Host Settings': ['ServerName','Password','AdminPass','MaxPlayers','SaveName','SearchID','RCONEnabled','RConPort','RCONPass','UseGlobalBanList','AllowFamilySharing','LimitedSpawns','NoDeathFeedback','NoJoinFeedback'],
 'World Settings': ['PVP','PermaDeath','XpMultiplier','SaveIntervalSec','OnDeath','RespawnTimer','LogoutTimer','LootRespawn','LootRespawnTimer','PickupRespawnTimer','FoodDecay','PickupCleanup','RarityFood','RarityDrink','RarityMelee','RarityRanged','RarityAmmo','RarityArmor','RarityResources','MaxOwnedCars','RecycleCar','AllowDismantle','AllowHouseDismantle','BuildingHealth','Decay','BuildingDecay','GenFuel','AirDrop','AirDropInterval','WeaponBreak','Sleep','MultiplayerSleep','VitalDrain','DogEnabled','DogNum','ZombieDiffHealth','ZombieDiffSpeed','ZombieDiffDamage','ZombieAmountMulti','ZombieRespawnTimer','ZombieDogMulti','HumanHealth','HumanSpeed','HumanDamage','HumanAmountMulti','HumanRespawnTimer','AIEvent','StartingSeason','DaysPerSeason','DayDur','NightDur','FreezeTime','Weather_ClearSky','Weather_Cloudy','Weather_Foggy','Weather_LightRain','Weather_Rain','Weather_Thunderstorm','Weather_LightSnow','Weather_Snow','Weather_Blizzard']
}

def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    PANEL_LOG.open('a', encoding='utf-8').write(line)


def load_config():
    base = DEFAULT_CONFIG.copy()
    try:
        if CONFIG.exists():
            base.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    except Exception:
        pass
    try:
        srv = get_active_server_profile()
        # Le profil actif écrase seulement les champs spécifiques serveur.
        for key in SERVER_PROFILE_KEYS:
            if key in srv and srv.get(key) is not None:
                base[key] = srv.get(key)
        base["active_server_id"] = srv.get("id")
        base["active_server_name"] = srv.get("name", "Server")
    except Exception:
        pass
    return base

def save_config(data):
    clean = {**DEFAULT_CONFIG, **data}
    for key in SERVER_PROFILE_KEYS:
        if key in data:
            clean[key] = data[key]
    CONFIG.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding='utf-8')

def load_panel_translations():
    result = {}
    for code, filename in LANGUAGE_FILES.items():
        path = LANGUAGES / filename
        values = {}
        if path.exists():
            cp = configparser.ConfigParser(interpolation=None)
            cp.optionxform = str
            cp.read(path, encoding="utf-8")
            if cp.has_section("Translations"):
                values.update(dict(cp.items("Translations")))
        result[code] = values
    return result

def server_dir():
    d = load_config().get('server_dir') or ''
    return Path(d) if d else None

def settings_ini_path():
    d = server_dir()
    return d / 'HumanitZServer' / 'GameServerSettings.ini' if d else None

def find_exe():
    d = server_dir()
    if not d: return None
    candidates = [
        d/'HumanitZServer.exe',
        d/'HumanitZ'/'Binaries'/'Win64'/'HumanitZServer-Win64-Shipping.exe',
        d/'HumanitZServer',
        d/'HumanitZServer.sh',
        d/'HumanitZ'/'Binaries'/'Linux'/'HumanitZServer-Linux-Shipping',
    ]
    return next((p for p in candidates if p.exists()), None)




def get_detection_report():
    """
    Rapport de détection complet.

    Important :
    Le statut online du panel utilise maintenant cette fonction.
    On combine :
    - tasklist /FO CSV complet
    - wmic process Name,ExecutablePath
    - PowerShell Get-CimInstance
    - netstat sur ports configurés
    - option process_names configurable dans manager_config.json
    """
    cfg = load_config()
    names = cfg.get("server_process_names") or [
        "HumanitZServer-Win64-Shipping.exe",
        "HumanitZServer.exe",
        "HumanitZServer-Win64-Shipping-Cmd.exe",
        "HumanitZ.exe",
    ]
    names = [str(x).strip() for x in names if str(x).strip()]
    server_dir_cfg = str(cfg.get("server_dir", "") or "").lower().replace("/", "\\")
    report = {
        "online": False,
        "method": "",
        "configured_process_names": names,
        "server_dir": cfg.get("server_dir", ""),
        "matches": [],
        "checks": {},
    }

    if not IS_WINDOWS:
        if psutil:
            try:
                for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                    info = proc.info
                    name = str(info.get("name") or "")
                    exe = str(info.get("exe") or "")
                    cmdline = " ".join(str(x) for x in (info.get("cmdline") or []))
                    haystack = f"{name} {exe} {cmdline}".lower()
                    if "humanitz" in haystack or any(n.lower().replace(".exe", "") in haystack for n in names):
                        report["online"] = True
                        report["method"] = "psutil process match"
                        report["matches"].append({"type": "psutil", "pid": info.get("pid"), "name": name, "exe": exe, "cmdline": cmdline[:1000]})
            except Exception as e:
                report["checks"]["psutil_error"] = str(e)
        try:
            ports = [str(p) for p in [cfg.get("rcon_port", "8888"), cfg.get("port", "7777"), cfg.get("query_port", "27015")] if str(p).strip()]
            tool = shutil.which("ss") or shutil.which("netstat")
            if tool:
                cmd = [tool, "-tulpn"] if Path(tool).name == "ss" else [tool, "-tulpn"]
                out = subprocess.check_output(cmd, text=True, errors="ignore")
                hits = []
                for line in out.splitlines():
                    for p in ports:
                        if f":{p}" in line:
                            hits.append(line.strip())
                            report["online"] = True
                            if not report["method"]:
                                report["method"] = f"port {p}"
                report["checks"]["linux_port_hits"] = hits
        except Exception as e:
            report["checks"]["linux_port_error"] = str(e)
        return report

    # 1) Exact original filtered tasklist checks
    exact_outputs = {}
    for name in names:
        try:
            cmd = f'tasklist /FI "IMAGENAME eq {name}" /FO CSV'
            out = subprocess.check_output(cmd, creationflags=NO_WINDOW, text=True, errors="ignore")
            exact_outputs[name] = out
            if name.lower() in out.lower():
                report["online"] = True
                report["method"] = f"tasklist exact: {name}"
                report["matches"].append({"type": "tasklist_exact", "name": name, "line": out.strip()})
        except Exception as e:
            exact_outputs[name] = f"ERROR: {e}"
    report["checks"]["tasklist_exact"] = exact_outputs

    # 2) Full tasklist broad scan
    try:
        out = subprocess.check_output('tasklist /FO CSV', creationflags=NO_WINDOW, text=True, errors="ignore")
        hits = []
        low = out.lower()
        for line in out.splitlines():
            ll = line.lower()
            if "humanitz" in ll or any(n.lower().replace(".exe","") in ll for n in names):
                hits.append(line)
                report["online"] = True
                if not report["method"]:
                    report["method"] = "tasklist broad HumanitZ match"
                report["matches"].append({"type": "tasklist_broad", "line": line})
        report["checks"]["tasklist_broad_hits"] = hits
    except Exception as e:
        report["checks"]["tasklist_broad_error"] = str(e)

    # 3) WMIC path scan
    try:
        out = subprocess.check_output('wmic process get Name,ExecutablePath', creationflags=NO_WINDOW, text=True, errors="ignore")
        hits = []
        for line in out.splitlines():
            ll = line.lower().replace("/", "\\")
            if "humanitz" in ll or (server_dir_cfg and server_dir_cfg in ll):
                hits.append(line.strip())
                if ".exe" in ll:
                    report["online"] = True
                    if not report["method"]:
                        report["method"] = "wmic executable path match"
                    report["matches"].append({"type": "wmic", "line": line.strip()})
        report["checks"]["wmic_hits"] = hits
    except Exception as e:
        report["checks"]["wmic_error"] = str(e)

    # 4) PowerShell process scan fallback
    try:
        ps = (
            "powershell -NoProfile -Command "
            "\"Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -like '*HumanitZ*' -or $_.ExecutablePath -like '*HumanitZ*' } | "
            "Select-Object Name,ProcessId,ExecutablePath | ConvertTo-Json -Compress\""
        )
        out = subprocess.check_output(ps, creationflags=NO_WINDOW, text=True, errors="ignore", shell=True)
        report["checks"]["powershell_humanitz"] = out.strip()
        if "HumanitZ" in out:
            report["online"] = True
            if not report["method"]:
                report["method"] = "powershell Get-CimInstance HumanitZ"
            report["matches"].append({"type": "powershell", "line": out.strip()[:1000]})
    except Exception as e:
        report["checks"]["powershell_error"] = str(e)

    # 5) Netstat fallback: if game/query/rcon ports exist as LISTENING or ESTABLISHED
    try:
        ports = [
            cfg.get("rcon_port", "8888"),
            cfg.get("port", "7777"),
            cfg.get("query_port", "27015"),
            cfg.get("net_port", "7777"),
            cfg.get("net_queryport", "27015"),
        ]
        ports = [str(p) for p in ports if str(p).strip()]
        out = subprocess.check_output("netstat -ano", creationflags=NO_WINDOW, text=True, errors="ignore")
        hits = []
        for line in out.splitlines():
            for p in ports:
                if f":{p} " in line and ("LISTENING" in line.upper() or "ESTABLISHED" in line.upper()):
                    hits.append(line.strip())
                    report["online"] = True
                    if not report["method"]:
                        report["method"] = f"netstat port {p}"
                    report["matches"].append({"type": "netstat", "port": p, "line": line.strip()})
        report["checks"]["netstat_hits"] = hits
    except Exception as e:
        report["checks"]["netstat_error"] = str(e)

    return report

def is_running():
    return bool(get_detection_report().get("online"))

def kill_server():
    if IS_WINDOWS:
        for name in ['HumanitZServer.exe','HumanitZServer-Win64-Shipping.exe']:
            subprocess.run(f'taskkill /F /IM {name} /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if psutil:
        cfg = load_config()
        server_root = str(cfg.get("server_dir") or "")
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                haystack = " ".join([str(proc.info.get("name") or ""), str(proc.info.get("exe") or ""), " ".join(proc.info.get("cmdline") or [])])
                if "HumanitZ" in haystack or (server_root and server_root in haystack):
                    proc.terminate()
            except Exception:
                pass
    subprocess.run(["pkill", "-f", "HumanitZ"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_start_bat():
    cfg = load_config(); d = server_dir()
    if not d: raise HTTPException(400, 'server_dir manquant')
    exe = find_exe()
    if IS_WINDOWS:
        bat = d / 'start.bat'
        exe_name = exe.name if exe else 'HumanitZServer.exe'
        bat.write_text(f'start "HumanitZ" "{exe_name}" -log port={cfg["port"]} queryport={cfg["query_port"]}\n', encoding='utf-8')
        return bat
    sh = d / 'start.sh'
    exe_path = exe if exe else d / 'HumanitZServer'
    try:
        rel = str(exe_path.relative_to(d))
    except Exception:
        rel = str(exe_path)
    rel_run = rel if Path(rel).is_absolute() else f"./{rel}"
    sh.write_text(
        "#!/usr/bin/env bash\n"
        "cd \"$(dirname \"$0\")\"\n"
        f"chmod +x \"{rel}\" 2>/dev/null || true\n"
        f"nohup \"{rel_run}\" -log port={cfg['port']} queryport={cfg['query_port']} > humanitz-server.log 2>&1 &\n",
        encoding='utf-8'
    )
    sh.chmod(0o755)
    return sh

def launch_start_script(script: Path, cwd: Path):
    if IS_WINDOWS:
        return subprocess.Popen([str(script)], cwd=str(cwd), shell=True)
    return subprocess.Popen(["/bin/bash", str(script)], cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def rcon(ip, port, password, command):
    if not password: raise HTTPException(400, 'Mot de passe RCON manquant')
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.settimeout(3); sock.connect((ip, int(port)))
        packet_auth = struct.pack('<iii', len(password)+10, 101, 3) + password.encode() + b'\x00\x00'
        sock.sendall(packet_auth); res = sock.recv(12)
        if len(res)==12 and struct.unpack('<iii', res)[1] == -1:
            raise HTTPException(401, 'Authentification RCON refusée')
        sock.settimeout(.3)
        try: sock.recv(4096)
        except Exception: pass
        sock.settimeout(3)
        packet_cmd = struct.pack('<iii', len(command)+10, 202, 2) + command.encode() + b'\x00\x00'
        sock.sendall(packet_cmd); sock.sendall(struct.pack('<iii',10,303,2)+b'\x00\x00')
        response=b''
        while True:
            try:
                header=sock.recv(12)
                if len(header)<12: break
                size,pid,_=struct.unpack('<iii', header); body=sock.recv(max(size-8,0))
                if pid==303: break
                response += body
            except socket.timeout: break
        sock.close(); return response.decode('utf-8', errors='ignore').replace('\x00','').strip()
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f'Erreur RCON: {e}')

app = FastAPI(title='HumanitZ Windows Web Panel')
app.mount('/static', StaticFiles(directory=str(FRONTEND)), name='static')



class ServerProfileIn(BaseModel):
    id: str | None = None
    name: str | None = None
    server_dir: str | None = None
    steamcmd_dir: str | None = None
    rcon_ip: str | None = None
    rcon_port: str | None = None
    rcon_password: str | None = None
    port: str | None = None
    query_port: str | None = None

class ActiveServerIn(BaseModel):
    id: str

class LoginIn(BaseModel):
    username: str
    password: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

class ConfigIn(BaseModel):
    server_dir: str | None = None; steamcmd_dir: str | None = None; port: str | None = None; query_port: str | None = None
    rcon_ip: str | None = None; rcon_port: str | None = None; rcon_password: str | None = None
    watchdog_enabled: bool | None = None; auto_message_enabled: bool | None = None; auto_message_text: str | None = None
    auto_message_interval: int | None = None; auto_restart_enabled: bool | None = None; restart_times: list[str] | None = None
    reset_spawners_before_save: bool | None = None; auto_restart_warning_minutes: int | None = None
class CommandIn(BaseModel): command: str
class AutoRestartIn(BaseModel):
    enabled: bool | None = None
    restart_times: list[str] | None = None
    reset_spawners_before_save: bool | None = None
    warning_minutes: int | None = None

class WatchdogIn(BaseModel):
    enabled: bool | None = None
    interval: int | None = None
    relaunch_delay: int | None = None

class AutoMessagesIn(BaseModel):
    enabled: bool | None = None
    interval: int | None = None
    mode: str | None = None
    messages: list[str] | None = None
    test_message: str | None = None

class ChatModerationIn(BaseModel):
    enabled: bool | None = None
    banned_words: list[str] | None = None
    warn_before_kick: int | None = None
    kick_enabled: bool | None = None
    warning_enabled: bool | None = None
    infraction_reset_minutes: int | None = None

class IniIn(BaseModel): values: dict
class BrowseIn(BaseModel):
    target: str




# --- Multi-serveur ---
SERVERS_FILE = DATA / "servers.json"
ACTIVE_SERVER_FILE = DATA / "active_server.json"

def default_server_profile():
    return {
        "id": "default",
        "name": "Server 1",
        "server_dir": "",
        "steamcmd_dir": "",
        "rcon_ip": "127.0.0.1",
        "rcon_port": "8888",
        "rcon_password": "",
        "port": "7777",
        "query_port": "27015",
    }

def load_servers():
    DATA.mkdir(parents=True, exist_ok=True)
    if not SERVERS_FILE.exists():
        profile = default_server_profile()
        try:
            if CONFIG.exists():
                cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
                profile.update({k: v for k, v in cfg.items() if k in SERVER_PROFILE_KEYS and v is not None})
        except Exception:
            pass
        data = {"servers": [profile]}
        SERVERS_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        ACTIVE_SERVER_FILE.write_text(json.dumps({"id": "default"}, indent=4), encoding="utf-8")
        return data
    try:
        data = json.loads(SERVERS_FILE.read_text(encoding="utf-8"))
        if not data.get("servers"):
            data = {"servers": [default_server_profile()]}
            save_servers(data)
        return data
    except Exception:
        data = {"servers": [default_server_profile()]}
        save_servers(data)
        return data

def save_servers(data):
    DATA.mkdir(parents=True, exist_ok=True)
    SERVERS_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

def get_active_server_id():
    DATA.mkdir(parents=True, exist_ok=True)
    if ACTIVE_SERVER_FILE.exists():
        try:
            return json.loads(ACTIVE_SERVER_FILE.read_text(encoding="utf-8")).get("id", "default")
        except Exception:
            pass
    return "default"

def set_active_server_id(server_id):
    DATA.mkdir(parents=True, exist_ok=True)
    ACTIVE_SERVER_FILE.write_text(json.dumps({"id": server_id}, indent=4), encoding="utf-8")

def get_active_server_profile():
    data = load_servers()
    active = get_active_server_id()
    for srv in data.get("servers", []):
        if srv.get("id") == active:
            return srv
    srv = data["servers"][0]
    set_active_server_id(srv.get("id", "default"))
    return srv

def upsert_server_profile(profile):
    data = load_servers()
    sid = profile.get("id") or str(uuid.uuid4())
    profile["id"] = sid
    found = False
    for i, srv in enumerate(data.get("servers", [])):
        if srv.get("id") == sid:
            merged = srv.copy()
            merged.update({k: v for k, v in profile.items() if v is not None})
            data["servers"][i] = merged
            found = True
            break
    if not found:
        base = default_server_profile()
        base.update(profile)
        data.setdefault("servers", []).append(base)
    save_servers(data)
    return sid

def update_active_server_profile(values):
    server_values = {k: v for k, v in values.items() if k in SERVER_PROFILE_KEYS}
    if not server_values:
        return
    profile = get_active_server_profile().copy()
    profile.update(server_values)
    upsert_server_profile(profile)

def delete_server_profile(server_id):
    data = load_servers()
    servers = [s for s in data.get("servers", []) if s.get("id") != server_id]
    if not servers:
        raise HTTPException(400, "Impossible de supprimer le dernier serveur")
    data["servers"] = servers
    save_servers(data)
    if get_active_server_id() == server_id:
        set_active_server_id(servers[0]["id"])
    return data

@app.get("/api/servers")
def api_servers():
    data = load_servers()
    active = get_active_server_id()
    safe = []
    for s in data.get("servers", []):
        item = s.copy()
        if item.get("rcon_password"):
            item["rcon_password_set"] = True
            item["rcon_password"] = ""
        else:
            item["rcon_password_set"] = False
        item["active"] = item.get("id") == active
        safe.append(item)
    return {"ok": True, "active": active, "servers": safe}

@app.post("/api/servers")
def api_servers_save(body: ServerProfileIn):
    profile = body.model_dump()
    if not profile.get("name"):
        profile["name"] = "Nouveau serveur"
    sid = upsert_server_profile(profile)
    return {"ok": True, "id": sid, "servers": load_servers()}

@app.post("/api/servers/active")
def api_servers_active(body: ActiveServerIn):
    data = load_servers()
    ids = [s.get("id") for s in data.get("servers", [])]
    if body.id not in ids:
        raise HTTPException(404, "Serveur introuvable")
    set_active_server_id(body.id)
    return {"ok": True, "active": body.id}

@app.delete("/api/servers/{server_id}")
def api_servers_delete(server_id: str):
    data = delete_server_profile(server_id)
    return {"ok": True, "servers": data}

# --- Sécurité / Authentification panel ---
AUTH_FILE = DATA / "auth.json"
SESSIONS = {}
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "0000"

def auth_hash(password: str):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()

def init_auth_file():
    DATA.mkdir(parents=True, exist_ok=True)
    if not AUTH_FILE.exists():
        AUTH_FILE.write_text(json.dumps({
            "username": DEFAULT_USERNAME,
            "password_hash": auth_hash(DEFAULT_PASSWORD),
            "must_change": True,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=4), encoding="utf-8")

def load_auth():
    init_auth_file()
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "username": DEFAULT_USERNAME,
            "password_hash": auth_hash(DEFAULT_PASSWORD),
            "must_change": True,
        }

def save_auth(data):
    DATA.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")

def create_session(username):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "username": username,
        "created_at": time.time(),
        "last_seen": time.time(),
    }
    return token

def current_user_from_request(request: Request):
    token = request.cookies.get("hz_panel_session", "")
    session = SESSIONS.get(token)
    if not session:
        return None
    session["last_seen"] = time.time()
    return session.get("username")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Laisser passer la page, assets et endpoints d'auth.
    public_paths = (
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/change-password",
        "/api/translations",
        "/favicon.ico",
    )

    if path.startswith(public_paths):
        return await call_next(request)

    # Tous les endpoints API sont protégés.
    if path.startswith("/api/"):
        if not current_user_from_request(request):
            return JSONResponse({"ok": False, "error": "Authentification requise"}, status_code=401)

    return await call_next(request)

@app.get("/api/auth/status")
def auth_status(request: Request):
    auth = load_auth()
    user = current_user_from_request(request)
    return {
        "ok": True,
        "authenticated": bool(user),
        "username": user or "",
        "login_username": auth.get("username", DEFAULT_USERNAME),
        "must_change": bool(auth.get("must_change", True)) if user else False,
        "default_username": DEFAULT_USERNAME,
    }

@app.post("/api/auth/login")
def auth_login(body: LoginIn):
    auth = load_auth()
    if body.username != auth.get("username", DEFAULT_USERNAME):
        raise HTTPException(401, "Identifiant incorrect")
    if auth_hash(body.password) != auth.get("password_hash"):
        raise HTTPException(401, "Mot de passe incorrect")

    token = create_session(body.username)
    response = JSONResponse({
        "ok": True,
        "username": body.username,
        "must_change": bool(auth.get("must_change", True)),
    })
    response.set_cookie(
        "hz_panel_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return response

@app.post("/api/auth/change-password")
def auth_change_password(request: Request, body: ChangePasswordIn):
    user = current_user_from_request(request)
    if not user:
        raise HTTPException(401, "Authentification requise")

    auth = load_auth()
    if auth_hash(body.current_password) != auth.get("password_hash"):
        raise HTTPException(401, "Mot de passe actuel incorrect")

    new_password = str(body.new_password or "")
    if len(new_password) < 6:
        raise HTTPException(400, "Le nouveau mot de passe doit contenir au moins 6 caractères")
    if new_password == DEFAULT_PASSWORD:
        raise HTTPException(400, "Le nouveau mot de passe ne peut pas rester 0000")

    auth["password_hash"] = auth_hash(new_password)
    auth["must_change"] = False
    auth["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_auth(auth)
    return {"ok": True, "message": "Mot de passe modifié"}

@app.post("/api/auth/logout")
def auth_logout(request: Request):
    token = request.cookies.get("hz_panel_session", "")
    if token in SESSIONS:
        del SESSIONS[token]
    response = JSONResponse({"ok": True})
    response.delete_cookie("hz_panel_session")
    return response

@app.get('/')
def index(): return FileResponse(FRONTEND/'index.html')

@app.get('/api/translations')
def translations():
    return load_panel_translations()

@app.get('/api/status')
def status():
    cfg=load_config(); d=server_dir(); disk={}
    if psutil and d and d.exists():
        du=psutil.disk_usage(str(d)); disk={'total':du.total,'used':du.used,'free':du.free,'percent':du.percent}
    return {'running':is_running(),'config':cfg,'exe':str(find_exe() or ''),'disk':disk,'cpu':psutil.cpu_percent() if psutil else None,'ram':psutil.virtual_memory()._asdict() if psutil else None}


@app.post('/api/config')
def set_config(c:ConfigIn):
    cfg=load_config(); upd={k:v for k,v in c.model_dump().items() if v is not None}; cfg.update(upd); update_active_server_profile({k:v for k,v in upd.items() if k in SERVER_PROFILE_KEYS}); save_config(cfg); log('Configuration panel sauvegardée'); return {'ok':True,'config':cfg}
@app.get('/api/ini')
def get_ini():
    p=settings_ini_path(); result={}
    if not p or not p.exists(): return {'exists':False,'path':str(p or ''),'values':result,'fields':INI_FIELDS}
    cp=configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=';'); cp.optionxform=str; cp.read(p, encoding='utf-8')
    for sec, keys in INI_FIELDS.items():
        result[sec]={}
        for k in keys:
            result[sec][k]=cp.get(sec,k,fallback='').strip().strip('"')
    return {'exists':True,'path':str(p),'values':result,'fields':INI_FIELDS}
@app.post('/api/ini')
def save_ini(body:IniIn):
    p=settings_ini_path()
    if not p: raise HTTPException(400,'Dossier serveur manquant')
    p.parent.mkdir(parents=True, exist_ok=True)
    cp=configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=';'); cp.optionxform=str
    if p.exists(): cp.read(p, encoding='utf-8')
    for sec, vals in body.values.items():
        if not cp.has_section(sec): cp.add_section(sec)
        for k,v in vals.items():
            cp.set(sec,k,str(v))
    with p.open('w',encoding='utf-8') as f: cp.write(f, space_around_delimiters=False)
    log('GameServerSettings.ini sauvegardé'); return {'ok':True,'path':str(p)}
@app.post('/api/power/{action}')
def power(action:str):
    if action=='start':
        d=server_dir();
        if not d: raise HTTPException(400,'Dossier serveur manquant')
        bat=generate_start_bat(); launch_start_script(bat, d); log('Serveur démarré'); return {'ok':True}
    if action in ['stop','kill']:
        kill_server(); log('Serveur arrêté'); return {'ok':True}
    if action=='restart':
        kill_server(); time.sleep(2); d=server_dir(); bat=generate_start_bat(); launch_start_script(bat, d); log('Serveur redémarré'); return {'ok':True}
    raise HTTPException(400,'Action inconnue')
@app.post('/api/rcon')
def send_cmd(c:CommandIn):
    cfg=load_config(); out=rcon(cfg['rcon_ip'], cfg['rcon_port'], cfg['rcon_password'], c.command); log(f'RCON: {c.command}'); return {'response':out}

@app.get('/api/logs')
def logs():
    panel = PANEL_LOG.read_text(encoding='utf-8', errors='ignore')[-20000:] if PANEL_LOG.exists() else ''
    return {'panel':panel}
@app.post('/api/backup')
def backup():
    d=server_dir();
    if not d: raise HTTPException(400,'Dossier serveur manquant')
    src=d/'HumanitZServer';
    if not src.exists(): raise HTTPException(404,'Dossier HumanitZServer introuvable')
    bdir=DATA/'backups'; bdir.mkdir(exist_ok=True)
    dest=bdir/f'backup-{time.strftime("%Y%m%d-%H%M%S")}.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for file in src.rglob('*'):
            if file.is_file(): z.write(file, file.relative_to(src.parent))
    log(f'Backup créé: {dest.name}'); return {'ok':True,'file':str(dest)}
@app.get('/api/backups')
def backups():
    bdir=DATA/'backups'; bdir.mkdir(exist_ok=True)
    return {'backups':[{'name':p.name,'size':p.stat().st_size,'path':str(p)} for p in sorted(bdir.glob('*.zip'), reverse=True)]}




class FileManagerIn(BaseModel):
    path: str = ""
    content: str | None = None
    name: str | None = None
    is_dir: bool | None = False
    new_name: str | None = None

class ProcessNamesIn(BaseModel):
    names: list[str]

class PlayerActionIn(BaseModel):
    steamid: str | None = None
    player: str | None = None
    message: str | None = None


class InstallUpdateIn(BaseModel):
    server_dir: str | None = None
    steamcmd_dir: str | None = None
    app_id: str | None = None
    validate_update: bool | None = Field(default=True, alias="validate")
    restart_after: bool | None = False

# --- Auto-restart HumanitZ, repris de la logique du script principal ---
auto_restart_in_progress = False
last_auto_restart_key = ""

def parse_restart_time(value: str):
    value = (value or "").strip().upper()
    if not value:
        return None
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return time.strptime(value, fmt)
        except ValueError:
            pass
    return None

def minutes_of_day(t):
    return t.tm_hour * 60 + t.tm_min

def rcon_cfg():
    cfg = load_config()
    return cfg.get("rcon_ip", "127.0.0.1"), cfg.get("rcon_port", "8888"), cfg.get("rcon_password", "")

def auto_restart_sequence(minutes: int):
    global auto_restart_in_progress
    auto_restart_in_progress = True
    ip, port, password = rcon_cfg()
    try:
        log(f"Auto-restart lancé: compte à rebours {minutes} minute(s)")
        for minutes_left in range(minutes, 0, -1):
            try:
                rcon(ip, port, password, f"admin [Restart] T-{minutes_left} min...")
                log(f"Auto-restart: message T-{minutes_left} envoyé")
            except Exception as e:
                log(f"Auto-restart: erreur message T-{minutes_left}: {e}")
            time.sleep(60)

        cfg = load_config()
        if cfg.get("reset_spawners_before_save"):
            try:
                rcon(ip, port, password, "resetspawners true")
                log("Auto-restart: resetspawners true envoyé")
                time.sleep(2)
            except Exception as e:
                log(f"Auto-restart: erreur resetspawners: {e}")

        try:
            rcon(ip, port, password, "save")
            log("Auto-restart: save envoyé")
            time.sleep(4)
        except Exception as e:
            log(f"Auto-restart: erreur save: {e}")

        try:
            rcon(ip, port, password, "RestartNow")
            log("Auto-restart: RestartNow envoyé")
        except Exception as e:
            log(f"Auto-restart: erreur RestartNow, fallback power restart: {e}")
            try:
                kill_server()
                time.sleep(2)
                d = server_dir()
                bat = generate_start_bat()
                launch_start_script(bat, d)
            except Exception as e2:
                log(f"Auto-restart: fallback impossible: {e2}")
    finally:
        time.sleep(12)
        auto_restart_in_progress = False

def auto_restart_scheduler_loop():
    global last_auto_restart_key
    while True:
        try:
            cfg = load_config()
            if cfg.get("auto_restart_enabled") and is_running() and not auto_restart_in_progress:
                warning = int(cfg.get("auto_restart_warning_minutes") or 10)
                warning = max(1, min(60, warning))
                now = time.localtime()
                now_minutes = now.tm_hour * 60 + now.tm_min
                today_key = time.strftime("%Y-%m-%d")

                for raw_time in cfg.get("restart_times", []) or []:
                    parsed = parse_restart_time(str(raw_time))
                    if not parsed:
                        continue
                    target_minutes = minutes_of_day(parsed)
                    trigger_minutes = (target_minutes - warning) % (24 * 60)
                    key = f"{today_key}:{raw_time}:{warning}"

                    if now_minutes == trigger_minutes and last_auto_restart_key != key:
                        last_auto_restart_key = key
                        threading.Thread(target=auto_restart_sequence, args=(warning,), daemon=True).start()
                        break
        except Exception as e:
            log(f"Auto-restart scheduler erreur: {e}")
        time.sleep(10)

@app.get('/api/auto-restart')
def get_auto_restart():
    cfg = load_config()
    return {
        "enabled": bool(cfg.get("auto_restart_enabled")),
        "restart_times": cfg.get("restart_times", []),
        "reset_spawners_before_save": bool(cfg.get("reset_spawners_before_save")),
        "warning_minutes": int(cfg.get("auto_restart_warning_minutes") or 10),
        "in_progress": auto_restart_in_progress,
        "last_trigger": last_auto_restart_key
    }

@app.post('/api/auto-restart')
def set_auto_restart(body: AutoRestartIn):
    cfg = load_config()
    if body.enabled is not None:
        cfg["auto_restart_enabled"] = body.enabled
    if body.restart_times is not None:
        cfg["restart_times"] = [str(x).strip() for x in body.restart_times if str(x).strip()]
    if body.reset_spawners_before_save is not None:
        cfg["reset_spawners_before_save"] = body.reset_spawners_before_save
    if body.warning_minutes is not None:
        cfg["auto_restart_warning_minutes"] = max(1, min(60, int(body.warning_minutes)))
    save_config(cfg)
    log("Configuration auto-restart sauvegardée")
    return {"ok": True, "config": cfg}

@app.post('/api/auto-restart/run-test')
def run_auto_restart_test(body: AutoRestartIn):
    if auto_restart_in_progress:
        raise HTTPException(409, "Un redémarrage automatique est déjà en cours")
    minutes = body.warning_minutes or 1
    minutes = max(1, min(10, int(minutes)))
    threading.Thread(target=auto_restart_sequence, args=(minutes,), daemon=True).start()
    return {"ok": True, "message": f"Test auto-restart lancé avec {minutes} minute(s)"}


# --- Watchdog serveur HumanitZ ---
watchdog_stats = {
    "enabled": False,
    "running": False,
    "last_check": "",
    "last_action": "",
    "restart_count": 0,
    "last_error": "",
}

def watchdog_loop():
    while True:
        try:
            cfg = load_config()
            enabled = bool(cfg.get("watchdog_enabled"))
            interval = int(cfg.get("watchdog_interval") or 5)
            delay = int(cfg.get("watchdog_relaunch_delay") or 5)
            interval = max(2, min(60, interval))
            delay = max(1, min(120, delay))

            watchdog_stats["enabled"] = enabled
            watchdog_stats["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")

            if enabled:
                running = is_running()
                watchdog_stats["running"] = running

                if not running:
                    watchdog_stats["last_action"] = "Serveur hors ligne détecté, relance en cours..."
                    log("[Watchdog] Serveur hors ligne détecté.")
                    time.sleep(delay)

                    if not is_running():
                        try:
                            d = server_dir()
                            bat = generate_start_bat()
                            launch_start_script(bat, d)
                            watchdog_stats["restart_count"] += 1
                            watchdog_stats["last_action"] = "Serveur relancé automatiquement"
                            watchdog_stats["last_error"] = ""
                            log("[Watchdog] Relance automatique effectuée.")
                        except Exception as e:
                            watchdog_stats["last_error"] = str(e)
                            watchdog_stats["last_action"] = "Erreur pendant la relance"
                            log(f"[Watchdog] Erreur relance: {e}")
                else:
                    watchdog_stats["last_action"] = "Serveur en ligne"
            else:
                watchdog_stats["running"] = is_running()
                watchdog_stats["last_action"] = "Watchdog désactivé"
        except Exception as e:
            watchdog_stats["last_error"] = str(e)
            log(f"[Watchdog] Erreur boucle: {e}")

        time.sleep(int(load_config().get("watchdog_interval") or 5))

@app.get('/api/watchdog')
def get_watchdog():
    cfg = load_config()
    return {
        "enabled": bool(cfg.get("watchdog_enabled")),
        "interval": int(cfg.get("watchdog_interval") or 5),
        "relaunch_delay": int(cfg.get("watchdog_relaunch_delay") or 5),
        "stats": watchdog_stats,
    }

@app.post('/api/watchdog')
def set_watchdog(body: WatchdogIn):
    cfg = load_config()
    if body.enabled is not None:
        cfg["watchdog_enabled"] = body.enabled
    if body.interval is not None:
        cfg["watchdog_interval"] = max(2, min(60, int(body.interval)))
    if body.relaunch_delay is not None:
        cfg["watchdog_relaunch_delay"] = max(1, min(120, int(body.relaunch_delay)))
    save_config(cfg)
    log("[Watchdog] Configuration sauvegardée")
    return {"ok": True, "config": cfg, "stats": watchdog_stats}

@app.post('/api/watchdog/test')
def watchdog_test():
    cfg = load_config()
    try:
        d = server_dir()
        bat = generate_start_bat()
        return {
            "ok": True,
            "server_dir": str(d),
            "start_bat": str(bat),
            "server_running": is_running(),
            "watchdog_enabled": bool(cfg.get("watchdog_enabled")),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Auto Messages HumanitZ ---
auto_messages_stats = {
    "enabled": False,
    "last_sent": "",
    "last_message": "",
    "next_send": "",
    "sent_count": 0,
    "current_index": 0,
    "last_error": "",
    "history": [],
}

def auto_messages_clean_messages(messages):
    clean = []
    for msg in messages or []:
        msg = str(msg).strip()
        if msg:
            clean.append(msg)
    return clean

def auto_messages_send(message: str):
    message = str(message).strip()
    if not message:
        return {"ok": False, "error": "Message vide"}

    ip, port, password = rcon_cfg()
    if not password:
        return {"ok": False, "error": "Mot de passe RCON vide"}

    result = rcon(ip, port, password, f"admin {message}")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    auto_messages_stats["last_sent"] = now
    auto_messages_stats["last_message"] = message
    auto_messages_stats["sent_count"] = int(auto_messages_stats.get("sent_count") or 0) + 1
    auto_messages_stats["last_error"] = ""

    auto_messages_stats["history"].insert(0, {
        "time": now,
        "message": message,
        "response": result or "",
    })
    auto_messages_stats["history"] = auto_messages_stats["history"][:20]

    log(f"[Auto Messages] admin {message}")
    return {"ok": True, "message": message, "response": result or ""}

def auto_messages_pick_message(cfg):
    messages = auto_messages_clean_messages(cfg.get("auto_messages_list", []))
    if not messages:
        return ""

    mode = str(cfg.get("auto_messages_mode") or "rotation").lower()

    if mode == "fixed":
        return messages[0]

    if mode == "random":
        import random
        return random.choice(messages)

    idx = int(auto_messages_stats.get("current_index") or 0)
    message = messages[idx % len(messages)]
    auto_messages_stats["current_index"] = (idx + 1) % len(messages)
    return message

def auto_messages_loop():
    while True:
        try:
            cfg = load_config()
            enabled = bool(cfg.get("auto_messages_enabled"))
            interval = int(cfg.get("auto_messages_interval") or 15)
            interval = max(1, min(240, interval))
            messages = auto_messages_clean_messages(cfg.get("auto_messages_list", []))

            auto_messages_stats["enabled"] = enabled

            if not enabled:
                auto_messages_stats["next_send"] = ""
                time.sleep(5)
                continue

            if not messages:
                auto_messages_stats["last_error"] = "Aucun message configuré"
                time.sleep(10)
                continue

            # Attente fractionnée pour permettre la désactivation rapide.
            seconds = interval * 60
            next_ts = time.time() + seconds
            auto_messages_stats["next_send"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_ts))

            for _ in range(seconds):
                cfg_live = load_config()
                if not cfg_live.get("auto_messages_enabled"):
                    auto_messages_stats["enabled"] = False
                    auto_messages_stats["next_send"] = ""
                    break
                time.sleep(1)
            else:
                if is_running():
                    msg = auto_messages_pick_message(load_config())
                    if msg:
                        try:
                            auto_messages_send(msg)
                        except Exception as e:
                            auto_messages_stats["last_error"] = str(e)
                            log(f"[Auto Messages] Erreur envoi: {e}")
                else:
                    auto_messages_stats["last_error"] = "Serveur hors ligne, message non envoyé"
        except Exception as e:
            auto_messages_stats["last_error"] = str(e)
            log(f"[Auto Messages] Erreur boucle: {e}")
            time.sleep(10)

@app.get('/api/auto-messages')
def get_auto_messages():
    cfg = load_config()
    return {
        "enabled": bool(cfg.get("auto_messages_enabled")),
        "interval": int(cfg.get("auto_messages_interval") or 15),
        "mode": cfg.get("auto_messages_mode", "rotation"),
        "messages": auto_messages_clean_messages(cfg.get("auto_messages_list", [])),
        "stats": auto_messages_stats,
    }

@app.post('/api/auto-messages')
def set_auto_messages(body: AutoMessagesIn):
    cfg = load_config()
    if body.enabled is not None:
        cfg["auto_messages_enabled"] = body.enabled
    if body.interval is not None:
        cfg["auto_messages_interval"] = max(1, min(240, int(body.interval)))
    if body.mode is not None:
        mode = str(body.mode).lower().strip()
        if mode not in ["rotation", "random", "fixed"]:
            mode = "rotation"
        cfg["auto_messages_mode"] = mode
    if body.messages is not None:
        cfg["auto_messages_list"] = auto_messages_clean_messages(body.messages)
    save_config(cfg)
    log("[Auto Messages] Configuration sauvegardée")
    return {"ok": True, "config": cfg, "stats": auto_messages_stats}

@app.post('/api/auto-messages/test')
def test_auto_messages(body: AutoMessagesIn):
    cfg = load_config()
    msg = body.test_message or ""
    if not msg:
        msg = auto_messages_pick_message(cfg)
    if not msg:
        raise HTTPException(400, "Aucun message à envoyer")
    return auto_messages_send(msg)


# --- Modération Chat / Mots interdits ---
BANNED_WORDS_FILE = ROOT / "mots_interdits.txt"

chat_moderation_stats = {
    "enabled": False,
    "watched_file": "",
    "last_check": "",
    "warnings": 0,
    "kicks": 0,
    "detections": 0,
    "players_tracked": 0,
    "last_action": "",
    "last_error": "",
    "history": [],
}

chat_player_infractions = {}
chat_player_last_infraction = {}
chat_player_id_map = {}
chat_current_file = None
chat_processed_lines = 0
chat_first_read_done = False

def banned_words_default():
    return ["cheater", "noob"]

def ensure_banned_words_file():
    if not BANNED_WORDS_FILE.exists():
        BANNED_WORDS_FILE.write_text("; Un mot interdit par ligne\ncheater\nnoob\n", encoding="utf-8")

def load_banned_words():
    ensure_banned_words_file()
    words = []
    try:
        for line in BANNED_WORDS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip().lower()
            if line and not line.startswith(";"):
                words.append(line)
    except Exception:
        words = banned_words_default()
    return words

def save_banned_words(words):
    clean = []
    for w in words or []:
        w = str(w).strip().lower()
        if w and w not in clean:
            clean.append(w)
    ensure_banned_words_file()
    BANNED_WORDS_FILE.write_text("; Un mot interdit par ligne\n" + "\n".join(clean) + "\n", encoding="utf-8")
    return clean

def chat_logs_dir():
    return server_dir() / "HumanitZServer" / "HZLogs" / "Chat"

def latest_chat_log():
    d = chat_logs_dir()
    if not d.exists():
        return None
    files = [p for p in d.iterdir() if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)

def index_players_from_rcon():
    try:
        ip, port, password = rcon_cfg()
        if not password:
            return {}
        raw = rcon(ip, port, password, "Players") or ""
        for line in raw.splitlines():
            m = re.search(r"^\s*(.*?)\s*\((7656\d{13})", line)
            if m:
                name = m.group(1).strip()
                steamid = m.group(2).strip()
                if name and steamid:
                    chat_player_id_map[name] = steamid
    except Exception as e:
        chat_moderation_stats["last_error"] = str(e)
    return chat_player_id_map

def chat_history_add(player, word, action, command=""):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    chat_moderation_stats["history"].insert(0, {
        "time": now,
        "player": player,
        "word": word,
        "action": action,
        "command": command,
    })
    chat_moderation_stats["history"] = chat_moderation_stats["history"][:50]
    chat_moderation_stats["last_action"] = f"{action}: {player} ({word})"

def process_chat_line_for_moderation(line):
    cfg = load_config()
    if not cfg.get("chat_moderation_enabled"):
        return None

    words = load_banned_words()
    if not words:
        return None

    m = re.search(r"<\w+>(.*?):</>(.*)", line)
    if not m:
        # fallback simple: Player: message
        m2 = re.search(r"^\s*([^:]{2,32})\s*:\s*(.*)$", line)
        if not m2:
            return None
        player = m2.group(1).strip()
        message = m2.group(2).strip().lower()
    else:
        player = m.group(1).strip()
        message = m.group(2).strip().lower()

    detected = None
    for word in words:
        if word and word in message:
            detected = word
            break
    if not detected:
        return None

    return execute_chat_punishment(player, detected)

def execute_chat_punishment(player, detected_word):
    cfg = load_config()
    now = time.time()
    reset_minutes = int(cfg.get("chat_infraction_reset_minutes") or 60)
    reset_seconds = max(1, reset_minutes) * 60

    last = chat_player_last_infraction.get(player, 0)
    if now - last > reset_seconds:
        chat_player_infractions[player] = 0

    chat_player_last_infraction[player] = now
    chat_player_infractions[player] = int(chat_player_infractions.get(player, 0)) + 1
    chat_moderation_stats["detections"] += 1
    chat_moderation_stats["players_tracked"] = len(chat_player_infractions)

    index_players_from_rcon()
    target = chat_player_id_map.get(player, player)
    warn_before_kick = max(1, int(cfg.get("chat_warn_before_kick") or 1))
    warning_enabled = bool(cfg.get("chat_warning_enabled", True))
    kick_enabled = bool(cfg.get("chat_kick_enabled", True))

    ip, port, password = rcon_cfg()
    if not password:
        chat_history_add(player, detected_word, "Détection sans RCON", "")
        chat_moderation_stats["last_error"] = "Mot de passe RCON vide"
        return {"ok": False, "error": "Mot de passe RCON vide"}

    infractions = chat_player_infractions[player]

    if warning_enabled and infractions <= warn_before_kick:
        command = f"sendadminmsgto {target} Mot interdit détecté: {detected_word}"
        try:
            rcon(ip, port, password, command)
        except Exception as e:
            chat_moderation_stats["last_error"] = str(e)
        chat_moderation_stats["warnings"] += 1
        chat_history_add(player, detected_word, "Avertissement", command)
        log(f"[Modération] Avertissement {player}: {detected_word}")
        return {"ok": True, "action": "warning", "command": command}

    if kick_enabled:
        command = f"kick {target}"
        try:
            rcon(ip, port, password, command)
        except Exception as e:
            chat_moderation_stats["last_error"] = str(e)
        chat_moderation_stats["kicks"] += 1
        chat_player_infractions[player] = 0
        chat_history_add(player, detected_word, "Kick", command)
        log(f"[Modération] Kick {player}: {detected_word}")
        return {"ok": True, "action": "kick", "command": command}

    chat_history_add(player, detected_word, "Détection", "")
    return {"ok": True, "action": "detect"}

def chat_moderation_loop():
    global chat_current_file, chat_processed_lines, chat_first_read_done

    ensure_banned_words_file()

    while True:
        try:
            cfg = load_config()
            enabled = bool(cfg.get("chat_moderation_enabled"))
            chat_moderation_stats["enabled"] = enabled
            chat_moderation_stats["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")

            if not enabled:
                time.sleep(2)
                continue

            latest = latest_chat_log()
            if not latest:
                chat_moderation_stats["last_error"] = "Aucun fichier de chat trouvé"
                time.sleep(3)
                continue

            if chat_current_file != str(latest):
                chat_current_file = str(latest)
                chat_processed_lines = 0
                chat_first_read_done = False
                chat_moderation_stats["watched_file"] = str(latest)
                chat_moderation_stats["last_error"] = ""

            lines = latest.read_text(encoding="utf-8", errors="ignore").splitlines()

            if not chat_first_read_done:
                # Ignore old lines on first read, like the original script.
                chat_processed_lines = len(lines)
                chat_first_read_done = True

            if len(lines) > chat_processed_lines:
                new_lines = lines[chat_processed_lines:]
                chat_processed_lines = len(lines)
                for line in new_lines:
                    if line.strip():
                        process_chat_line_for_moderation(line.strip())

        except Exception as e:
            chat_moderation_stats["last_error"] = str(e)
            log(f"[Modération] Erreur: {e}")

        time.sleep(0.75)

@app.get('/api/chat-moderation')
def get_chat_moderation():
    cfg = load_config()
    return {
        "enabled": bool(cfg.get("chat_moderation_enabled")),
        "banned_words": load_banned_words(),
        "warn_before_kick": int(cfg.get("chat_warn_before_kick") or 1),
        "kick_enabled": bool(cfg.get("chat_kick_enabled", True)),
        "warning_enabled": bool(cfg.get("chat_warning_enabled", True)),
        "infraction_reset_minutes": int(cfg.get("chat_infraction_reset_minutes") or 60),
        "stats": chat_moderation_stats,
    }

@app.post('/api/chat-moderation')
def set_chat_moderation(body: ChatModerationIn):
    cfg = load_config()
    if body.enabled is not None:
        cfg["chat_moderation_enabled"] = body.enabled
    if body.banned_words is not None:
        save_banned_words(body.banned_words)
    if body.warn_before_kick is not None:
        cfg["chat_warn_before_kick"] = max(1, min(10, int(body.warn_before_kick)))
    if body.kick_enabled is not None:
        cfg["chat_kick_enabled"] = body.kick_enabled
    if body.warning_enabled is not None:
        cfg["chat_warning_enabled"] = body.warning_enabled
    if body.infraction_reset_minutes is not None:
        cfg["chat_infraction_reset_minutes"] = max(1, min(1440, int(body.infraction_reset_minutes)))
    save_config(cfg)
    log("[Modération] Configuration sauvegardée")
    return {"ok": True, "config": cfg, "banned_words": load_banned_words(), "stats": chat_moderation_stats}

@app.post('/api/chat-moderation/test')
def test_chat_moderation(body: ChatModerationIn):
    words = body.banned_words or load_banned_words()
    word = words[0] if words else "test"
    result = execute_chat_punishment("TestPlayer", word)
    return {"ok": True, "result": result, "stats": chat_moderation_stats}


# --- Players / Gestion joueurs ---
players_stats = {
    "last_refresh": "",
    "last_raw": "",
    "last_error": "",
    "count": 0,
    "history": [],
}

def parse_humanitz_players(raw: str):
    players = []
    raw = raw or ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # Format original script: PlayerName (7656...)
        m = re.search(r"^\s*(.*?)\s*\((7656\d{13})", line)
        if m:
            name = m.group(1).strip()
            steamid = m.group(2).strip()
            players.append({"name": name, "steamid": steamid, "raw": line})
            continue

        # Fallback: any SteamID with preceding name-ish text
        m = re.search(r"(7656\d{13})", line)
        if m:
            steamid = m.group(1)
            name = line.replace(steamid, "").replace("(", "").replace(")", "").strip(" -:|")
            players.append({"name": name or steamid, "steamid": steamid, "raw": line})
            continue

        # Unknown line kept for debug
        players.append({"name": line, "steamid": "", "raw": line})

    return players

def players_history(action, target="", command="", response=""):
    players_stats["history"].insert(0, {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "target": target,
        "command": command,
        "response": response or "",
    })
    players_stats["history"] = players_stats["history"][:30]






@app.get('/api/server-detect')
def server_detect():
    return get_detection_report()


@app.post('/api/server-detect/process-names')
def set_server_process_names(body: ProcessNamesIn):
    cfg = load_config()
    names = [str(x).strip() for x in body.names if str(x).strip()]
    if not names:
        raise HTTPException(400, "Liste vide")
    cfg["server_process_names"] = names
    save_config(cfg)
    return {"ok": True, "server_process_names": names, "report": get_detection_report()}


# --- Gestionnaire de fichiers ---
TEXT_EXTENSIONS = {
    ".txt", ".ini", ".cfg", ".json", ".log", ".bat", ".cmd", ".xml", ".yml", ".yaml",
    ".csv", ".md", ".properties", ".conf"
}

def file_manager_root():
    cfg = load_config()
    root = cfg.get("server_dir", "")
    if not root:
        raise HTTPException(400, "Dossier serveur HumanitZ non configuré")
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise HTTPException(404, f"Dossier serveur introuvable: {root_path}")
    return root_path

def file_manager_safe_path(relative_path: str = ""):
    root = file_manager_root()
    rel = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    target = (root / rel).resolve()

    # protection contre ../ hors dossier serveur
    try:
        target.relative_to(root)
    except Exception:
        raise HTTPException(403, "Chemin interdit hors du dossier serveur")

    return root, target

def file_manager_item(p: Path):
    stat = p.stat()
    return {
        "name": p.name,
        "path": str(p),
        "is_dir": p.is_dir(),
        "size": 0 if p.is_dir() else stat.st_size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        "ext": p.suffix.lower(),
        "editable": (not p.is_dir()) and p.suffix.lower() in TEXT_EXTENSIONS and stat.st_size <= 2 * 1024 * 1024,
    }

@app.get('/api/files')
def list_files(path: str = ""):
    root, target = file_manager_safe_path(path)
    if not target.exists():
        raise HTTPException(404, "Chemin introuvable")
    if not target.is_dir():
        raise HTTPException(400, "Le chemin n'est pas un dossier")

    items = []
    for p in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        try:
            items.append(file_manager_item(p))
        except Exception:
            pass

    parent = ""
    if target != root:
        try:
            parent = str(target.parent.relative_to(root)).replace("\\", "/")
        except Exception:
            parent = ""

    return {
        "ok": True,
        "root": str(root),
        "current": str(target),
        "relative": str(target.relative_to(root)).replace("\\", "/") if target != root else "",
        "parent": parent,
        "items": items,
    }

@app.get('/api/files/read')
def read_file(path: str):
    root, target = file_manager_safe_path(path)
    if not target.exists():
        raise HTTPException(404, "Fichier introuvable")
    if target.is_dir():
        raise HTTPException(400, "Impossible de lire un dossier")
    if target.stat().st_size > 2 * 1024 * 1024:
        raise HTTPException(400, "Fichier trop gros pour édition web (>2MB)")
    if target.suffix.lower() not in TEXT_EXTENSIONS:
        raise HTTPException(400, "Type de fichier non éditable")

    content = target.read_text(encoding="utf-8", errors="ignore")
    return {
        "ok": True,
        "path": str(target),
        "relative": str(target.relative_to(root)).replace("\\", "/"),
        "content": content,
        "size": target.stat().st_size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(target.stat().st_mtime)),
    }

@app.post('/api/files/save')
def save_file(body: FileManagerIn):
    root, target = file_manager_safe_path(body.path)
    if target.exists() and target.is_dir():
        raise HTTPException(400, "Impossible d'écrire dans un dossier")
    if target.suffix.lower() not in TEXT_EXTENSIONS:
        raise HTTPException(400, "Type de fichier non éditable")
    if len(body.content or "") > 2 * 1024 * 1024:
        raise HTTPException(400, "Contenu trop gros pour édition web (>2MB)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content or "", encoding="utf-8")
    log(f"[Fichiers] Sauvegarde: {target}")
    return {"ok": True, "item": file_manager_item(target)}

@app.post('/api/files/create')
def create_file_or_folder(body: FileManagerIn):
    root, base = file_manager_safe_path(body.path)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "Nom manquant")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "Nom invalide")

    target = (base / name).resolve()
    try:
        target.relative_to(root)
    except Exception:
        raise HTTPException(403, "Chemin interdit")

    if target.exists():
        raise HTTPException(409, "Existe déjà")

    if body.is_dir:
        target.mkdir(parents=True, exist_ok=False)
    else:
        target.write_text("", encoding="utf-8")

    log(f"[Fichiers] Création: {target}")
    return {"ok": True, "item": file_manager_item(target)}

@app.post('/api/files/delete')
def delete_file_or_folder(body: FileManagerIn):
    root, target = file_manager_safe_path(body.path)
    if not target.exists():
        raise HTTPException(404, "Chemin introuvable")
    if target == root:
        raise HTTPException(403, "Impossible de supprimer le dossier racine serveur")

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    log(f"[Fichiers] Suppression: {target}")
    return {"ok": True}

@app.post('/api/files/rename')
def rename_file_or_folder(body: FileManagerIn):
    root, target = file_manager_safe_path(body.path)
    if not target.exists():
        raise HTTPException(404, "Chemin introuvable")

    new_name = (body.new_name or "").strip()
    if not new_name:
        raise HTTPException(400, "Nouveau nom manquant")
    if "/" in new_name or "\\" in new_name or ".." in new_name:
        raise HTTPException(400, "Nouveau nom invalide")

    dest = (target.parent / new_name).resolve()
    try:
        dest.relative_to(root)
    except Exception:
        raise HTTPException(403, "Chemin interdit")

    if dest.exists():
        raise HTTPException(409, "Destination déjà existante")

    target.rename(dest)
    log(f"[Fichiers] Renommage: {target} -> {dest}")
    return {"ok": True, "item": file_manager_item(dest)}

@app.post('/api/files/upload')
async def upload_file(path: str = "", file: UploadFile = File(...)):
    root, target_dir = file_manager_safe_path(path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(400, "Dossier cible invalide")

    filename = Path(file.filename or "upload.bin").name
    dest = (target_dir / filename).resolve()
    try:
        dest.relative_to(root)
    except Exception:
        raise HTTPException(403, "Chemin interdit")

    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    log(f"[Fichiers] Upload: {dest}")
    return {"ok": True, "item": file_manager_item(dest)}

@app.get('/api/files/download')
def download_file(path: str):
    from fastapi.responses import FileResponse
    root, target = file_manager_safe_path(path)
    if not target.exists() or target.is_dir():
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(str(target), filename=target.name)


# --- RCON compatible HumanitZRCON.py ---
humanitz_rcon_request_id = 100

def humanitz_rcon_once(command: str, timeout: float = 3.0):
    """
    RCON repris de HumanitZRCON.py :
    auth = struct.pack('<ii', 1, 3) + password + nulls
    cmd  = struct.pack('<ii', request_id, 2) + command + nulls
    réponse = data[12:]
    """
    global humanitz_rcon_request_id
    cfg = load_config()
    ip = cfg.get("rcon_ip", "127.0.0.1") or "127.0.0.1"
    port = int(cfg.get("rcon_port", "8888") or 8888)
    password = cfg.get("rcon_password", "") or ""
    if not password:
        raise HTTPException(400, "Mot de passe RCON vide")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        auth = struct.pack('<ii', 1, 3) + password.encode("utf-8") + b'\x00\x00'
        sock.sendall(struct.pack('<i', len(auth)) + auth)
        try:
            sock.recv(4096)
        except Exception:
            pass

        sock.settimeout(0.1)
        try:
            while sock.recv(4096):
                pass
        except Exception:
            pass

        humanitz_rcon_request_id += 1
        pkt = struct.pack('<ii', humanitz_rcon_request_id, 2) + command.encode("utf-8") + b'\x00\x00'
        sock.settimeout(timeout)
        sock.sendall(struct.pack('<i', len(pkt)) + pkt)

        data = sock.recv(65535)
        if not data:
            return ""
        return data[12:].decode("utf-8", errors="ignore").replace("\x00", "").strip()
    finally:
        try:
            sock.close()
        except Exception:
            pass

def parse_players_from_humanitzrcon(data: str):
    """
    Parsing repris de HumanitZRCON.py :
    - ignore lignes vides
    - ignore lignes contenant "Players"
    - cherche SteamID 17 chiffres
    """
    players = []
    for line in (data or "").splitlines():
        if not line.strip() or "Players" in line:
            continue
        sid_match = re.search(r'(\d{17})', line)
        if not sid_match:
            continue
        sid = sid_match.group(1)
        cleaned = line.strip()
        before = cleaned.split(sid)[0].strip(" -:|()[]")
        players.append({
            "name": before or cleaned,
            "steamid": sid,
            "raw": cleaned,
        })
    return players


@app.get('/api/players')
def api_players():
    try:
        raw = humanitz_rcon_once("Players")
        parsed = parse_players_from_humanitzrcon(raw)

        players_stats["last_refresh"] = time.strftime("%Y-%m-%d %H:%M:%S")
        players_stats["last_raw"] = raw
        players_stats["count"] = len(parsed)
        players_stats["last_error"] = ""

        try:
            for p in parsed:
                if p.get("name") and p.get("steamid"):
                    chat_player_id_map[p["name"]] = p["steamid"]
        except Exception:
            pass

        return {"ok": True, "players": parsed, "raw": raw, "stats": players_stats}
    except Exception as e:
        players_stats["last_error"] = str(e)
        return {"ok": False, "players": [], "raw": "", "stats": players_stats, "error": str(e)}

@app.post('/api/players/kick')
def api_players_kick(body: PlayerActionIn):
    target = (body.steamid or body.player or "").strip()
    if not target:
        raise HTTPException(400, "SteamID ou joueur manquant")
    command = f"kick {target}"
    response = humanitz_rcon_once(command)
    players_history("kick", target, command, response)
    log(f"[Players] {command}")
    return {"ok": True, "command": command, "response": response}

@app.post('/api/players/ban')
def api_players_ban(body: PlayerActionIn):
    target = (body.steamid or body.player or "").strip()
    if not target:
        raise HTTPException(400, "SteamID ou joueur manquant")
    command = f"ban {target}"
    response = humanitz_rcon_once(command)
    players_history("ban", target, command, response)
    log(f"[Players] {command}")
    return {"ok": True, "command": command, "response": response}

@app.post('/api/players/unban')
def api_players_unban(body: PlayerActionIn):
    target = (body.steamid or body.player or "").strip()
    if not target:
        raise HTTPException(400, "SteamID manquant")
    command = f"unban {target}"
    response = humanitz_rcon_once(command)
    players_history("unban", target, command, response)
    log(f"[Players] {command}")
    return {"ok": True, "command": command, "response": response}

@app.get('/api/players/banned')
def api_players_banned():
    response = humanitz_rcon_once("fetchbanned")
    players_history("fetchbanned", "", "fetchbanned", response)
    return {"ok": True, "command": "fetchbanned", "response": response}

@app.post('/api/players/message')
def api_players_message(body: PlayerActionIn):
    target = (body.steamid or body.player or "").strip()
    message = (body.message or "").strip()
    if not target:
        raise HTTPException(400, "SteamID ou joueur manquant")
    if not message:
        raise HTTPException(400, "Message vide")
    command = f"sendadminmsgto {target} {message}"
    response = humanitz_rcon_once(command)
    players_history("message privé", target, command, response)
    log(f"[Players] {command}")
    return {"ok": True, "command": command, "response": response}

@app.post('/api/players/admin-message')
def api_players_admin_message(body: PlayerActionIn):
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(400, "Message vide")
    command = f"admin {message}"
    response = humanitz_rcon_once(command)
    players_history("message global", "all", command, response)
    log(f"[Players] {command}")
    return {"ok": True, "command": command, "response": response}

@app.post('/api/players/raw-command')
def api_players_raw_command(body: PlayerActionIn):
    command = (body.message or "").strip()
    if not command:
        raise HTTPException(400, "Commande vide")
    response = humanitz_rcon_once(command)
    players_history("commande", "", command, response)
    log(f"[Players] {command}")
    return {"ok": True, "command": command, "response": response}


# --- Logs Chat Live HumanitZ ---
chat_logs_live_state = {
    "current_file": "",
    "processed_lines": 0,
    "first_read_done": False,
    "last_error": "",
    "last_update": "",
    "lines_total": 0,
}

def chat_logs_folder():
    cfg = load_config()
    server = cfg.get("server_dir", "")
    if not server:
        raise HTTPException(400, "Dossier serveur HumanitZ non configuré")
    return Path(server) / "HumanitZServer" / "HZLogs" / "Chat"

def latest_chat_log_file():
    folder = chat_logs_folder()
    if not folder.exists():
        raise HTTPException(404, f"Dossier chat logs introuvable: {folder}")
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".log"]
    if not files:
        raise HTTPException(404, "Aucun fichier .log trouvé dans le dossier Chat")
    return max(files, key=lambda p: p.stat().st_mtime)

def clean_chat_line(raw: str):
    # Reprend l'idée du script original : supprimer les tags style <color>...</>
    line = re.sub(r'<[^>]+>', '', raw or '').strip()
    return line

@app.get('/api/chat-logs/latest')
def api_chat_logs_latest(limit: int = 200):
    try:
        latest = latest_chat_log_file()
        text = latest.read_text(encoding="utf-8", errors="ignore")
        lines = [clean_chat_line(x) for x in text.splitlines() if clean_chat_line(x)]
        limit = max(1, min(1000, int(limit or 200)))
        chat_logs_live_state["current_file"] = str(latest)
        chat_logs_live_state["processed_lines"] = len(lines)
        chat_logs_live_state["first_read_done"] = True
        chat_logs_live_state["last_error"] = ""
        chat_logs_live_state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
        chat_logs_live_state["lines_total"] = len(lines)
        return {
            "ok": True,
            "file": str(latest),
            "filename": latest.name,
            "folder": str(latest.parent),
            "lines": lines[-limit:],
            "state": chat_logs_live_state,
        }
    except HTTPException:
        raise
    except Exception as e:
        chat_logs_live_state["last_error"] = str(e)
        return {"ok": False, "error": str(e), "lines": [], "state": chat_logs_live_state}

@app.get('/api/chat-logs/poll')
def api_chat_logs_poll():
    """
    Lecture incrémentale façon script original :
    - prend le dernier fichier .log
    - si le fichier change, initialise le compteur
    - renvoie uniquement les nouvelles lignes depuis le dernier poll
    """
    global chat_logs_live_state
    try:
        latest = latest_chat_log_file()
        current = str(latest)

        raw_lines = latest.read_text(encoding="utf-8", errors="ignore").splitlines()

        if chat_logs_live_state.get("current_file") != current:
            chat_logs_live_state["current_file"] = current
            chat_logs_live_state["processed_lines"] = len(raw_lines)
            chat_logs_live_state["first_read_done"] = True
            chat_logs_live_state["last_error"] = ""
            chat_logs_live_state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
            chat_logs_live_state["lines_total"] = len(raw_lines)
            return {
                "ok": True,
                "file": current,
                "filename": latest.name,
                "new_file": True,
                "lines": [],
                "state": chat_logs_live_state,
            }

        start = int(chat_logs_live_state.get("processed_lines") or 0)
        total = len(raw_lines)
        new_raw = raw_lines[start:] if total > start else []
        chat_logs_live_state["processed_lines"] = total
        chat_logs_live_state["last_error"] = ""
        chat_logs_live_state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
        chat_logs_live_state["lines_total"] = total

        clean_lines = [clean_chat_line(x) for x in new_raw if clean_chat_line(x)]

        return {
            "ok": True,
            "file": current,
            "filename": latest.name,
            "new_file": False,
            "lines": clean_lines,
            "state": chat_logs_live_state,
        }
    except HTTPException:
        raise
    except Exception as e:
        chat_logs_live_state["last_error"] = str(e)
        return {"ok": False, "error": str(e), "lines": [], "state": chat_logs_live_state}

@app.post('/api/chat-logs/reset')
def api_chat_logs_reset():
    global chat_logs_live_state
    chat_logs_live_state["current_file"] = ""
    chat_logs_live_state["processed_lines"] = 0
    chat_logs_live_state["first_read_done"] = False
    chat_logs_live_state["last_error"] = ""
    chat_logs_live_state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
    chat_logs_live_state["lines_total"] = 0
    return {"ok": True, "state": chat_logs_live_state}


# --- Installation / Mise à jour HumanitZ via SteamCMD ---
install_update_state = {
    "running": False,
    "last_status": "idle",
    "started_at": "",
    "finished_at": "",
    "server_dir": "",
    "steamcmd_dir": "",
    "app_id": "2728330",
    "logs": [],
    "last_error": "",
    "success": False,
}

def install_log(message: str):
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    install_update_state["logs"].append(line)
    install_update_state["logs"] = install_update_state["logs"][-500:]
    try:
        log(f"[InstallUpdate] {message}")
    except Exception:
        pass

def steamcmd_exe_path(steamcmd_dir: str):
    return Path(steamcmd_dir) / ("steamcmd.exe" if IS_WINDOWS else "steamcmd.sh")

def ensure_steamcmd(steamcmd_dir: str):
    cfg = load_config()
    steamcmd_dir_p = Path(steamcmd_dir)
    steamcmd_dir_p.mkdir(parents=True, exist_ok=True)
    exe = steamcmd_exe_path(steamcmd_dir)
    if exe.exists():
        install_log(f"SteamCMD trouvé: {exe}")
        if not IS_WINDOWS:
            exe.chmod(0o755)
        return exe

    if not IS_WINDOWS:
        system_steamcmd = shutil.which("steamcmd")
        if system_steamcmd:
            install_log(f"SteamCMD système trouvé: {system_steamcmd}")
            return Path(system_steamcmd)
        url = cfg.get("steamcmd_linux_url", "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz")
        archive_path = steamcmd_dir_p / "steamcmd_linux.tar.gz"
        install_log("SteamCMD Linux absent, téléchargement...")
        urllib.request.urlretrieve(url, archive_path)
        install_log("Extraction SteamCMD Linux...")
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(steamcmd_dir_p)
        try:
            archive_path.unlink()
        except Exception:
            pass
        if not exe.exists():
            raise RuntimeError("steamcmd.sh introuvable après extraction")
        exe.chmod(0o755)
        install_log("SteamCMD installé.")
        return exe

    url = cfg.get("steamcmd_url", "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip")
    zip_path = steamcmd_dir_p / "steamcmd.zip"
    install_log("SteamCMD absent, téléchargement...")
    urllib.request.urlretrieve(url, zip_path)
    install_log("Extraction SteamCMD...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(steamcmd_dir_p)
    try:
        zip_path.unlink()
    except Exception:
        pass
    if not exe.exists():
        raise RuntimeError("steamcmd.exe introuvable après extraction")
    install_log("SteamCMD installé.")
    return exe

def detect_server_installed(server_dir: str):
    if not server_dir:
        return False
    d = Path(server_dir)
    if not d.exists():
        return False
    candidates = [
        d / "HumanitZServer.exe",
        d / "HumanitZ" / "Binaries" / "Win64" / "HumanitZServer-Win64-Shipping.exe",
        d / "HumanitZServer",
        d / "HumanitZServer.sh",
        d / "HumanitZ" / "Binaries" / "Linux" / "HumanitZServer-Linux-Shipping",
        d / "HumanitZServer" / "GameServerSettings.ini",
    ]
    return any(p.exists() for p in candidates) or any(d.iterdir())

def run_install_update_task(server_dir: str, steamcmd_dir: str, app_id: str, validate: bool = True, restart_after: bool = False):
    install_update_state["running"] = True
    install_update_state["success"] = False
    install_update_state["last_error"] = ""
    install_update_state["last_status"] = "running"
    install_update_state["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    install_update_state["finished_at"] = ""
    install_update_state["server_dir"] = server_dir
    install_update_state["steamcmd_dir"] = steamcmd_dir
    install_update_state["app_id"] = app_id
    install_update_state["logs"] = []

    try:
        server_dir_p = Path(server_dir)
        steamcmd_dir_p = Path(steamcmd_dir)
        server_dir_p.mkdir(parents=True, exist_ok=True)
        steamcmd_dir_p.mkdir(parents=True, exist_ok=True)

        cfg = load_config()
        cfg["server_dir"] = str(server_dir_p)
        cfg["steamcmd_dir"] = str(steamcmd_dir_p)
        cfg["humanitz_app_id"] = str(app_id)
        update_active_server_profile({
            "server_dir": str(server_dir_p),
            "steamcmd_dir": str(steamcmd_dir_p),
            "humanitz_app_id": str(app_id),
        })
        save_config(cfg)

        exe = ensure_steamcmd(str(steamcmd_dir_p))
        install_log(f"Dossier serveur: {server_dir_p}")
        install_log(f"AppID HumanitZ: {app_id}")

        args = [
            str(exe),
            "+force_install_dir", str(server_dir_p),
            "+login", "anonymous",
            "+app_update", str(app_id),
        ]
        if validate:
            args.append("validate")
        args.append("+quit")

        install_log("Lancement SteamCMD...")
        install_log("Commande: " + " ".join(f'"{a}"' if " " in a else a for a in args))

        proc = subprocess.Popen(
            args,
            cwd=str(steamcmd_dir_p),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            shell=False
        )

        if proc.stdout:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    install_log("[SteamCMD] " + line)

        code = proc.wait()
        install_log(f"SteamCMD terminé avec code {code}")

        if code != 0:
            raise RuntimeError(f"SteamCMD a retourné le code {code}")

        try:
            generate_start_bat()
            install_log("start.bat généré.")
        except Exception as e:
            install_log(f"Impossible de générer start.bat: {e}")

        install_update_state["success"] = True
        install_update_state["last_status"] = "success"
        install_log("Installation / mise à jour terminée avec succès.")

        if restart_after:
            install_log("Redémarrage automatique demandé après mise à jour.")
            try:
                if is_running():
                    kill_server()
                    time.sleep(3)
                d = server_dir()
                bat = generate_start_bat()
                launch_start_script(bat, d)
                install_log("Serveur relancé.")
            except Exception as e:
                install_log(f"Erreur redémarrage après update: {e}")

    except Exception as e:
        install_update_state["last_error"] = str(e)
        install_update_state["last_status"] = "error"
        install_log("ERREUR: " + str(e))
    finally:
        install_update_state["running"] = False
        install_update_state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

@app.get('/api/install-update/status')
def api_install_update_status():
    cfg = load_config()
    server_dir_cfg = cfg.get("server_dir", "")
    return {
        "ok": True,
        "state": install_update_state,
        "config": {
            "server_dir": server_dir_cfg,
            "steamcmd_dir": cfg.get("steamcmd_dir", ""),
            "app_id": cfg.get("humanitz_app_id", "2728330"),
            "installed": detect_server_installed(server_dir_cfg),
        }
    }

@app.post('/api/install-update/start')
def api_install_update_start(body: InstallUpdateIn):
    if is_running():
        raise HTTPException(409, "Impossible de mettre à jour pendant que le serveur est lancé. Arrête le serveur avant l'installation ou la mise à jour.")
    if install_update_state.get("running"):
        raise HTTPException(409, "Installation / mise à jour déjà en cours")

    cfg = load_config()
    server_dir_value = body.server_dir or cfg.get("server_dir", "")
    steamcmd_dir_value = body.steamcmd_dir or cfg.get("steamcmd_dir", "")
    app_id_value = body.app_id or cfg.get("humanitz_app_id", "2728330")

    if not server_dir_value:
        raise HTTPException(400, "Dossier d'installation serveur manquant")
    if not steamcmd_dir_value:
        raise HTTPException(400, "Dossier SteamCMD manquant")
    if not app_id_value:
        raise HTTPException(400, "AppID manquant")

    threading.Thread(
        target=run_install_update_task,
        args=(server_dir_value, steamcmd_dir_value, str(app_id_value), bool(body.validate_update), False),
        daemon=True
    ).start()

    return {"ok": True, "message": "Installation / mise à jour lancée"}

@app.post('/api/install-update/config')
def api_install_update_config(body: InstallUpdateIn):
    cfg = load_config()
    updates = {}
    if body.server_dir is not None:
        cfg["server_dir"] = body.server_dir
        updates["server_dir"] = body.server_dir
    if body.steamcmd_dir is not None:
        cfg["steamcmd_dir"] = body.steamcmd_dir
        updates["steamcmd_dir"] = body.steamcmd_dir
    if body.app_id is not None:
        cfg["humanitz_app_id"] = body.app_id
        updates["humanitz_app_id"] = body.app_id
    update_active_server_profile(updates)
    save_config(cfg)
    return {"ok": True, "config": cfg}


@app.get("/api/browse-folder")
@app.post("/api/browse-folder")
def api_browse_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Sélectionner un dossier")
        root.destroy()
        return {"ok": True, "path": folder or ""}
    except Exception as tk_error:
        if not IS_WINDOWS:
            for tool, args in (
                ("zenity", ["zenity", "--file-selection", "--directory", "--title=Sélectionner un dossier"]),
                ("kdialog", ["kdialog", "--getexistingdirectory", str(Path.home())]),
            ):
                if shutil.which(tool):
                    try:
                        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=120)
                        if result.returncode == 0:
                            return {"ok": True, "path": result.stdout.strip()}
                    except Exception:
                        pass
            raise HTTPException(500, "Sélecteur graphique indisponible sous Linux. Installe zenity/kdialog ou colle le chemin à la main.")
        try:
            ps_script = (
                "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
                "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$d.Description='Sélectionner un dossier';"
                "$d.ShowNewFolderButton=$true;"
                "if($d.ShowDialog() -eq 'OK'){[Console]::OutputEncoding=[Text.UTF8Encoding]::UTF8;Write-Output $d.SelectedPath}"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=120,
            )
            if result.returncode == 0:
                return {"ok": True, "path": result.stdout.strip()}
        except Exception:
            pass
        raise HTTPException(500, f"Impossible d'ouvrir le sélecteur de dossier: {tk_error}")

@app.on_event('startup')
def startup():
    log('Panel web démarré')
    threading.Thread(target=chat_moderation_loop, daemon=True).start()
    log('Modération Chat démarrée')
    threading.Thread(target=auto_messages_loop, daemon=True).start()
    log('Auto Messages démarré')
    threading.Thread(target=watchdog_loop, daemon=True).start()
    log('Watchdog démarré')
    threading.Thread(target=auto_restart_scheduler_loop, daemon=True).start()
    log('Auto-restart scheduler démarré')

if __name__ == '__main__':
    import webbrowser
    import uvicorn
    panel_host = os.environ.get("PANEL_HOST", "127.0.0.1")
    panel_port = int(os.environ.get("PANEL_PORT", "8765"))
    def open_panel_browser():
        url = f"http://127.0.0.1:{panel_port}"
        try:
            if IS_WINDOWS:
                os.startfile(url)
            else:
                webbrowser.open(url)
        except Exception:
            pass
    threading.Timer(1.0, open_panel_browser).start()
    uvicorn.run(app, host=panel_host, port=panel_port, log_config=None, access_log=False)
