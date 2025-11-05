# Minecraft Server Management Tool v0.3.0-beta
# Professional Minecraft server management utility with comprehensive features
# Built: 2025/11/5

import customtkinter as ctk
import requests
import os
import json
import threading
import subprocess
import shutil
import datetime
import webbrowser
import psutil
import sys
import platform
import zipfile
import io
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
from PIL import Image
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(BUNDLE_DIR, 'app.ico')
# ==============================================================================
# CORE BACKEND MODULE - Server Management & Configuration
# ==============================================================================

# --- Configuration Management System ---
APP_DIR = os.path.join(os.getenv('APPDATA'), 'MinecraftServerTool')
JAVA_DIR = os.path.join(APP_DIR, 'java')
CONFIG_FILE = os.path.join(APP_DIR, 'settings.json')
DEFAULT_SETTINGS = {
    'scan_path': os.path.join(os.path.expanduser('~'), 'Desktop'),
    'min_ram_mb': 1024,
    'max_ram_mb': 2048,
    'theme': 'blue',  
    'appearance_mode': 'system', 
    'use_server_gui': False,
    'auto_download_java': False,
    'auto_accept_eula': True,
    'java_executable_path': 'java',
    'default_server_port': '25565',
    'default_max_players': '20',
    'default_difficulty': 'easy',
    'default_gamemode': 'survival',
    'default_online_mode': True,
    'default_pvp': True
}

def ensure_config_exists():
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(JAVA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)

def load_settings():
    ensure_config_exists()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            settings = DEFAULT_SETTINGS.copy()
            settings.update(json.load(f))
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return DEFAULT_SETTINGS

def save_settings(settings):
    ensure_config_exists()
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)

# --- API Integration & Java Runtime Management ---
API_URLS = {
    "Paper": "https://api.papermc.io/v2/projects/paper",
    "Purpur": "https://api.purpurmc.org/v2/purpur",
    "Vanilla": "https://launchermeta.mojang.com/mc/game/version_manifest.json",
    "Forge": "https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json",
    "NeoForge": "https://maven.neoforged.net/net/neoforged/neoforge/maven-metadata.xml",
    "Fabric": "https://meta.fabricmc.net/v2/versions/game"
}

def get_versions(core_type, filters={"release"}):
    try:
        if core_type in ["Paper", "Purpur"]:
            response = requests.get(API_URLS[core_type])
            response.raise_for_status()
            versions = response.json()['versions'][::-1]
            filtered_versions = []
            for v in versions:
                is_snapshot = "pre" in v or "rc" in v or "SNAPSHOT" in v.upper()
                if "release" in filters and not is_snapshot: filtered_versions.append(v)
                if "snapshot" in filters and is_snapshot: filtered_versions.append(v)
            return filtered_versions
        elif core_type == "Vanilla":
            response = requests.get(API_URLS[core_type])
            response.raise_for_status()
            return [v['id'] for v in response.json()['versions'] if v['type'] in filters]
        elif core_type == "Fabric":
            response = requests.get(API_URLS[core_type])
            response.raise_for_status()
            versions = response.json()
            filtered_versions = []
            for v in versions:
                if "release" in filters and v['stable']:
                    filtered_versions.append(v['version'])
                if "snapshot" in filters and not v['stable']:
                    filtered_versions.append(v['version'])
            return filtered_versions
        elif core_type == "Forge":
            response = requests.get(API_URLS[core_type])
            response.raise_for_status()
            # The keys of the JSON are the Minecraft versions, return them in reverse order
            return sorted(list(response.json().keys()), reverse=True)
        elif core_type == "NeoForge":
            response = requests.get(API_URLS[core_type])
            response.raise_for_status()
            root = ET.fromstring(response.content)
            # Find all <version> tags and return their text content in reverse order
            versions = [v.text for v in root.findall('.//versioning/versions/version')]
            return sorted(versions, reverse=True)
    except (requests.RequestException, ET.ParseError, KeyError, json.JSONDecodeError) as e:
        print(f"｡ﾟ(ﾟ´Д｀)ﾟ｡ 網路錯誤或資料解析失敗：{e}")
        return []
    return []

def get_download_url(core_type, mc_version):
    try:
        if core_type == "Paper":
            build_res = requests.get(f"{API_URLS[core_type]}/versions/{mc_version}/builds")
            build_res.raise_for_status()
            latest_build = build_res.json()['builds'][-1]['build']
            jar_name = build_res.json()['builds'][-1]['downloads']['application']['name']
            return f"{API_URLS[core_type]}/versions/{mc_version}/builds/{latest_build}/downloads/{jar_name}"
        elif core_type == "Purpur":
            return f"{API_URLS[core_type]}/{mc_version}/latest/download"
        elif core_type == "Vanilla":
            manifest_res = requests.get(API_URLS['Vanilla'])
            manifest_res.raise_for_status()
            version_url = next((v['url'] for v in manifest_res.json()['versions'] if v['id'] == mc_version), None)
            if version_url:
                version_data_res = requests.get(version_url)
                version_data_res.raise_for_status()
                return version_data_res.json()['downloads']['server']['url']
        elif core_type == "Fabric":
            # Get latest stable loader version
            loader_res = requests.get(f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}")
            loader_res.raise_for_status()
            # The 'stable' key is inside the 'loader' object
            stable_loaders = [v for v in loader_res.json() if v.get('loader', {}).get('stable')]
            if not stable_loaders:
                raise Exception(f"找不到適用於 Minecraft {mc_version} 的穩定版 Fabric loader")
            loader_version = stable_loaders[0]['loader']['version']
            
            # Get latest stable installer version
            installer_res = requests.get("https://meta.fabricmc.net/v2/versions/installer")
            installer_res.raise_for_status()
            stable_installers = [v for v in installer_res.json() if v.get('stable')]
            if not stable_installers:
                raise Exception("找不到穩定版的 Fabric 安裝程式")
            installer_version = stable_installers[0]['version']
            
            return f"https://meta.fabricmc.net/v2/versions/loader/{mc_version}/{loader_version}/{installer_version}/server/jar"
        elif core_type == "Forge":
            # Forge downloads are behind an ad-wall, so we can't download directly.
            # Instead, we'll return a special URL to open in the user's browser.
            return f"WEBPAGE::https://files.minecraftforge.net/net/minecraftforge/forge/index_{mc_version}.html"
        elif core_type == "NeoForge":
            # For NeoForge, the mc_version is the full version string
            return f"https://maven.neoforged.net/net/neoforged/neoforge/{mc_version}/neoforge-{mc_version}-installer.jar"

    except (requests.RequestException, StopIteration, KeyError, json.JSONDecodeError) as e:
        print(f"(＃`Д´) 找不到下載連結啦：{e}")
        return None
    return None

def get_required_java_version(mc_version_str):
    try:
        major_version = int(mc_version_str.split('.')[1])
        if major_version >= 21: return 21
        if major_version >= 17: return 17
        if major_version >= 16: return 16
    except (ValueError, IndexError): pass
    return 8

def get_java_download_link(version):
    os_name = "windows" if sys.platform == "win32" else "mac" if sys.platform == "darwin" else "linux"
    arch = "x64" if platform.machine().endswith('64') else "x86"
    api_url = f"https://api.adoptium.net/v3/assets/latest/{version}/hotspot?vendor=eclipse&os={os_name}&architecture={arch}"
    try:
        res = requests.get(api_url)
        res.raise_for_status()
        binary_info = next(pkg for pkg in res.json() if pkg['binary']['image_type'] == 'jdk')
        return binary_info['binary']['package']['link']
    except (requests.RequestException, StopIteration, KeyError) as e:
        print(f"找不到 Java {version} 的下載連結: {e}")
        return None

def manage_java_installation(mc_version, progress_callback):
    java_version = get_required_java_version(mc_version)
    java_install_path = os.path.join(JAVA_DIR, f"jdk-{java_version}")
    java_exe = os.path.join(java_install_path, 'bin', 'java.exe' if sys.platform == "win32" else "java")

    if os.path.exists(java_install_path):
        progress_callback(f"已找到 Java {java_version}！", 0.1)
        return java_exe

    progress_callback(f"需要 Java {java_version}，正在尋找下載連結...", 0.02)
    link = get_java_download_link(java_version)
    if not link: raise Exception(f"無法找到 Java {java_version} 的下載點。")
    
    progress_callback(f"正在下載 Java {java_version}...", 0.05)
    response = requests.get(link, stream=True)
    response.raise_for_status()
    
    zip_bytes = io.BytesIO()
    total_size = int(response.headers.get('content-length', 0))
    bytes_downloaded = 0
    for chunk in response.iter_content(chunk_size=8192):
        bytes_downloaded += len(chunk)
        zip_bytes.write(chunk)
        if total_size > 0:
            progress = (bytes_downloaded / total_size) * 0.3
            progress_callback(f"下載 Java... {bytes_downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB", progress)
    
    progress_callback(f"正在解壓縮 Java {java_version}...", 0.35)
    with zipfile.ZipFile(zip_bytes) as zf:
        extracted_folder_name = zf.namelist()[0].split('/')[0]
        zf.extractall(JAVA_DIR)
    
    os.rename(os.path.join(JAVA_DIR, extracted_folder_name), java_install_path)
    progress_callback(f"Java {java_version} 安裝完成！", 0.4)
    return java_exe

# --- Server Installation System ---
def install_server(core_type, mc_version, path, progress_callback):
    try:
        progress_callback("準備開始...", 0.0)
        settings = load_settings()
        
        java_exe_path = settings['java_executable_path']
        if settings['auto_download_java']:
            java_mc_version = mc_version.split('-')[0]
            java_exe_path = manage_java_installation(java_mc_version, progress_callback)
        else:
            progress_callback("使用系統預設 Java...", 0.4)

        os.makedirs(path, exist_ok=True)
        
        progress_callback(f"正在尋找 {core_type} {mc_version}...", 0.42)
        url = get_download_url(core_type, mc_version)
        if not url: raise Exception("找不到下載連結或對應頁面。")

        INSTALLER_CORES = ["Forge", "NeoForge", "Fabric"]
        is_installer_core = core_type in INSTALLER_CORES
        
        jar_name = "server.jar" # Default
        bat_content = "" # Default empty
        download_target_path = ""

        # --- Download Phase ---
        if url.startswith("WEBPAGE::"):
            page_url = url.replace("WEBPAGE::", "")
            webbrowser.open(page_url)
            proceed = messagebox.askokcancel("需要手動下載", 
                f"""因為 Forge 的下載受廣告保護，無法自動下載。

已經為您打開下載網頁，請按照以下步驟操作：

1. 在網頁上點擊 "Installer" (安裝程式)。
2. 將下載的 .jar 檔案儲存到以下資料夾：
{path}
3. 完成後，點擊「確定」繼續安裝。

如果不想繼續，請點擊「取消」。"""
            )
            if not proceed:
                raise Exception("使用者取消了手動下載。")
            
            # Scan for the downloaded installer
            jars_in_dir = [f for f in os.listdir(path) if f.endswith('.jar')]
            if len(jars_in_dir) == 0:
                raise Exception(f"在 {path} 中找不到任何手動下載的 .jar 安裝檔。")
            if len(jars_in_dir) > 1:
                raise Exception(f"在 {path} 中找到多個 .jar 檔案，無法確定哪一個是安裝檔。")
            download_target_path = os.path.join(path, jars_in_dir[0])
            progress_callback("偵測到手動下載的安裝檔！", 0.85)

        else: # Automatic download for other cores
            download_target_name = "installer.jar" if is_installer_core else "server.jar"
            download_target_path = os.path.join(path, download_target_name)
            
            progress_callback(f"正在下載 {download_target_name}...", 0.45)
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            with open(download_target_path, 'wb') as f:
                bytes_downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    bytes_downloaded += len(chunk)
                    f.write(chunk)
                    if total_size > 0:
                        progress = 0.45 + (bytes_downloaded / total_size) * 0.4
                        progress_callback(f"下載伺服器核心... {bytes_downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB", progress)
            progress_callback("下載完成！", 0.85)

        # --- Installation/Setup Phase ---
        if is_installer_core:
            progress_callback(f"正在執行 {core_type} 安裝程式...", 0.86)
            try:
                result = subprocess.run(
                    [java_exe_path, "-jar", download_target_path, "--installServer"],
                    cwd=path, check=True, capture_output=True, text=True, encoding='utf-8'
                )
            except subprocess.CalledProcessError as e:
                error_message = f"""安裝程式執行失敗！
返回碼: {e.returncode}
輸出: {e.stdout}
錯誤: {e.stderr}"""
                raise Exception(error_message)
            except FileNotFoundError:
                 raise Exception(f"找不到 Java 執行檔 '{java_exe_path}'。請檢查您的 Java 設定或啟用自動下載。")

            # Clean up installer only if it was automatically downloaded
            if not url.startswith("WEBPAGE::"):
                os.remove(download_target_path)
                
            progress_callback("安裝程式執行完畢，正在設定啟動腳本...", 0.9)

            if core_type in ["Forge", "NeoForge"]:
                user_args_file = os.path.join(path, 'user_jvm_args.txt')
                run_bat_file = os.path.join(path, 'run.bat')

                if os.path.exists(run_bat_file):
                    # For modern Forge/NeoForge, write memory settings to user_jvm_args.txt
                    if os.path.exists(user_args_file):
                        with open(user_args_file, 'w', encoding='utf-8') as f:
                            f.write(f'''# Generated by Minecraft Server Tool
-Xmx{settings["max_ram_mb"]}M
-Xms{settings["min_ram_mb"]}M
''')
                    
                    os.rename(run_bat_file, os.path.join(path, 'start.bat'))
                    if os.path.exists(os.path.join(path, 'run.sh')):
                        os.rename(os.path.join(path, 'run.sh'), os.path.join(path, 'start.sh'))
                    
                    bat_content = None  # Signal to skip default bat creation
                    jar_name = "N/A (Installer Core)"
                else:
                    # Fallback for older versions that might not create run.bat
                    raise Exception("安裝後找不到 run.bat。可能是不支援的 Forge/NeoForge 版本。")

            elif core_type == "Fabric":
                jar_name = "fabric-server-launch.jar"
        
        # --- Finalization (for non-installer cores and Fabric) ---
        if bat_content is not None:
            java_args = f"-Xms{settings['min_ram_mb']}M -Xmx{settings['max_ram_mb']}M"
            gui_flag = "" if settings['use_server_gui'] else "nogui"
            
            bat_content = f'''
@echo off
"{java_exe_path}" {java_args} -jar "{jar_name}" {gui_flag}
pause
'''.strip()
            with open(os.path.join(path, 'start.bat'), 'w', encoding='utf-8') as f: f.write(bat_content)
        
        progress_callback("啟動腳本建立完成...", 0.92)
        
        if settings['auto_accept_eula']:
            with open(os.path.join(path, 'eula.txt'), 'w', encoding='utf-8') as f: f.write("eula=true")
            progress_callback("已自動同意 EULA...", 0.95)

        # Create default server.properties if it doesn't exist
        settings = load_settings()
        default_properties = {
            'server-port': settings.get('default_server_port', '25565'),
            'max-players': settings.get('default_max_players', '20'),
            'online-mode': str(settings.get('default_online_mode', True)).lower(),
            'difficulty': settings.get('default_difficulty', 'easy'),
            'gamemode': settings.get('default_gamemode', 'survival'),
            'pvp': str(settings.get('default_pvp', True)).lower()
        }
        
        properties_path = os.path.join(path, 'server.properties')
        if not os.path.exists(properties_path):
            with open(properties_path, 'w', encoding='utf-8') as f:
                f.write("# Minecraft server properties\n")
                for key, value in default_properties.items():
                    f.write(f"{key}={value}\n")
        
        profile = {"core_type": core_type, "version": mc_version, "jar_name": jar_name}
        with open(os.path.join(path, 'installer_profile.json'), 'w', encoding='utf-8') as f: json.dump(profile, f, indent=4)
        progress_callback("伺服器設定檔建立完成！", 1.0)
        
        return f"{core_type} {mc_version}"
    except Exception as e:
        raise e

# --- Server Properties Configuration Handler ---
def read_properties(server_path):
    props = {}
    props_file = os.path.join(server_path, 'server.properties')
    if not os.path.exists(props_file): return None
    with open(props_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                props[key.strip()] = value.strip()
    return props

def write_properties(server_path, new_values):
    props_file = os.path.join(server_path, 'server.properties')
    lines = []
    with open(props_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(props_file, 'w', encoding='utf-8') as f:
        written_keys = set()
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('#'):
                key = line_stripped.split('=', 1)[0].strip()
                if key in new_values:
                    f.write(f"{key}={new_values[key]}\n")
                    written_keys.add(key)
                else:
                    f.write(line)
            else:
                f.write(line)
        for key, value in new_values.items():
            if key not in written_keys:
                f.write(f"{key}={value}\n")

# --- Server Discovery & Management Module ---
def scan_for_servers(path):
    found_servers = []
    if not os.path.isdir(path): return []
    for root, dirs, files in os.walk(path):
        if 'installer_profile.json' in files:
            profile_path = os.path.join(root, 'installer_profile.json')
            try:
                with open(profile_path, 'r') as f:
                    profile_data = json.load(f)
                    profile_data['path'] = root
                    found_servers.append(profile_data)
                dirs[:] = []
            except (json.JSONDecodeError, KeyError): continue
    return found_servers

def run_server(server_path):
    bat_file = os.path.join(server_path, 'start.bat')
    if os.path.exists(bat_file):
        subprocess.Popen([bat_file], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=server_path)
    else:
        raise FileNotFoundError("找不到 start.bat 啟動檔！")

def create_backup(server_path, progress_callback):
    """
    Creates a zip archive of a Minecraft server directory.

    This function intelligently excludes the 'backups' directory itself from the
    archive to prevent a recursive backup issue where each new archive would
    contain all previous ones. It uses the zipfile module for granular control
    over the archive's contents.

    Args:
        server_path (str): The absolute path to the server's root directory.
        progress_callback (callable): A function to be called to report progress
            updates to the UI. It should accept a string message and a float
            value between 0.0 and 1.0.

    Returns:
        str: The filename of the successfully created backup archive.

    Raises:
        Exception: Propagates any exceptions that occur during file I/O or
            the zipping process, allowing the caller to handle them.
    """
    try:
        progress_callback("初始化打包過程...", 0.1)

        # Define the target directory for storing backups.
        backup_dir = os.path.join(server_path, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Generate a timestamped, unique filename for the new archive.
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"backup-{timestamp}"
        backup_zip_path = os.path.join(backup_dir, f"{backup_filename}.zip")

        progress_callback("掃描和打包檔案中...", 0.3)

        # Use the zipfile module for direct control over archive contents.
        # This is necessary to implement the exclusion logic for the backup directory.
        with zipfile.ZipFile(backup_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the entire directory tree of the server.
            for root, dirs, files in os.walk(server_path):

                # --- THE CRITICAL FIX ---
                # By modifying the 'dirs' list in-place, we instruct os.walk()
                # to skip traversing into the 'backups' directory. This elegantly
                # prevents the recursive backup issue.
                if 'backups' in dirs:
                    dirs.remove('backups')

                # Add each file to the zip archive.
                for file in files:
                    file_path = os.path.join(root, file)

                    # Create a relative path for the file within the archive.
                    # This prevents the zip file from storing the full absolute path
                    # (e.g., "C:/Users/...") and maintains a clean server structure.
                    archive_name = os.path.relpath(file_path, server_path)
                    zipf.write(file_path, archive_name)

        progress_callback("備份完成!", 1.0)
        return f"{backup_filename}.zip"

    except Exception as e:
        # Propagate the exception to the caller (e.g., the GUI thread) to handle.
        raise e

# --- Asynchronous Task Management ---
class Worker(threading.Thread):
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func, self.args, self.kwargs = func, args, kwargs
        self.result = None
        self.daemon = True

    def run(self):
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.result = e

# ==============================================================================
# GRAPHICAL USER INTERFACE MODULE - Frontend Components
# ==============================================================================

# --- Server Installation Interface ---
class InstallView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        self.core_label = ctk.CTkLabel(self, text="伺服器核心類型:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold"))
        self.core_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.core_options = ["Paper", "Purpur", "Vanilla", "Forge", "NeoForge", "Fabric"]
        self.core_var = ctk.StringVar(value=self.core_options[0])
        self.core_menu = ctk.CTkOptionMenu(self, values=self.core_options, variable=self.core_var, 
                                         command=lambda _: self.trigger_version_update(),
                                         font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.core_menu.grid(row=0, column=1, columnspan=2, padx=20, pady=10, sticky="ew")

        self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="w")
        ctk.CTkLabel(self.filter_frame, text="版本類型:", font=ctk.CTkFont(family="Microsoft JhengHei")).pack(side="left", padx=(5, 10))
        
        self.filters = {
            "release": ctk.BooleanVar(value=True), "snapshot": ctk.BooleanVar(value=False),
            "old_beta": ctk.BooleanVar(value=False), "old_alpha": ctk.BooleanVar(value=False),
        }
        
        ctk.CTkCheckBox(self.filter_frame, text="正式版", variable=self.filters["release"], 
                       command=self.trigger_version_update, font=ctk.CTkFont(family="Microsoft JhengHei")).pack(side="left", padx=5)
        self.snapshot_check = ctk.CTkCheckBox(self.filter_frame, text="快照版", variable=self.filters["snapshot"], 
                                            command=self.trigger_version_update, font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.snapshot_check.pack(side="left", padx=5)
        self.beta_check = ctk.CTkCheckBox(self.filter_frame, text="Beta", variable=self.filters["old_beta"], 
                                        command=self.trigger_version_update, font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.beta_check.pack(side="left", padx=5)
        self.alpha_check = ctk.CTkCheckBox(self.filter_frame, text="Alpha", variable=self.filters["old_alpha"], 
                                         command=self.trigger_version_update, font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.alpha_check.pack(side="left", padx=5)

        self.version_label = ctk.CTkLabel(self, text="遊戲版本:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold"))
        self.version_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.version_var = ctk.StringVar(value="正在載入...")
        self.version_menu = ctk.CTkOptionMenu(self, variable=self.version_var, values=["請先選擇核心"],
                                            font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.version_menu.grid(row=2, column=1, columnspan=2, padx=20, pady=10, sticky="ew")
        self.version_menu.configure(state="disabled")

        self.path_label = ctk.CTkLabel(self, text="安裝路徑:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold"))
        self.path_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")
        self.path_entry = ctk.CTkEntry(self, placeholder_text="選擇一個 *新的空資料夾* 來安裝伺服器...",
                                     font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.path_entry.grid(row=3, column=1, padx=20, pady=10, sticky="ew")
        self.browse_button = ctk.CTkButton(self, text="瀏覽...", command=self.browse_path,
                                         font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.browse_button.grid(row=3, column=2, padx=10, pady=10)

        self.progress_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.progress_label.grid(row=4, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        self.progressbar = ctk.CTkProgressBar(self)
        self.progressbar.grid(row=5, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        self.progressbar.set(0)

        self.install_button = ctk.CTkButton(self, text="🚀 開始安裝！", command=self.start_installation, height=40,
                                          font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold"))
        self.install_button.grid(row=6, column=1, padx=20, pady=20)

        self.after(100, self.trigger_version_update)

    def browse_path(self):
        path = filedialog.askdirectory()
        if path: self.path_entry.delete(0, "end"); self.path_entry.insert(0, path)

    def trigger_version_update(self):
        self.version_menu.configure(state="disabled")
        self.version_var.set("正在獲取版本...")
        selected_core = self.core_var.get()
        active_filters = {key for key, var in self.filters.items() if var.get()}
        is_vanilla = (selected_core == "Vanilla")
        for check in [self.beta_check, self.alpha_check]: check.configure(state="normal" if is_vanilla else "disabled")
        Worker(lambda: self.after(0, self.update_version_menu, get_versions(selected_core, active_filters))).start()

    def update_version_menu(self, versions):
        if versions:
            self.version_menu.configure(values=versions, state="normal")
            self.version_var.set(versions[0])
        else:
            self.version_menu.configure(values=["沒有找到符合的版本 (つд⊂)"], state="disabled")
            self.version_var.set("沒有找到符合的版本 (つд⊂)")

    def start_installation(self):
        path = self.path_entry.get()
        if not path or "..." in path:
            messagebox.showerror("錯誤", "請選擇一個有效的安裝路徑！ Σ(°Д°)"); return
        if os.listdir(path) and not messagebox.askyesno("警告", "資料夾不是空的！\n檔案可能會被覆蓋，確定要繼續嗎？"): return
        self.install_button.configure(state="disabled", text="安裝中...")
        worker = Worker(install_server, self.core_var.get(), self.version_var.get(), path, self.update_progress)
        worker.start()
        self.after(100, self.check_status, worker, "安裝")

    def update_progress(self, text, value):
        self.progress_label.configure(text=text); self.progressbar.set(value); self.update_idletasks()

    def check_status(self, worker, action_name):
        if worker.is_alive():
            self.after(100, self.check_status, worker, action_name)
        else:
            self.install_button.configure(state="normal", text="🚀 開始安裝！")
            if isinstance(worker.result, Exception):
                messagebox.showerror(f"{action_name}失敗", f"發生錯誤：\n{worker.result}")
                self.update_progress(f"{action_name}失敗 ( TДT)", 0)
            else:
                messagebox.showinfo("成功！", f"伺服器 {worker.result} 已成功{action_name}！🎉")
                self.update_progress(f"{action_name}完成！(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", 1)

# --- Server Properties Editor Window ---
class PropertiesEditor(ctk.CTkToplevel):
    def __init__(self, master, server_path):
        super().__init__(master)
        self.server_path = server_path
        self.title(f"編輯 {os.path.basename(server_path)} 屬性")
        self.geometry("500x400")
        self.grab_set()
        self.grid_columnconfigure(1, weight=1)

        self.properties = read_properties(self.server_path)
        if self.properties is None:
            ctk.CTkLabel(self, text="找不到 server.properties！\n請先啟動一次伺服器以生成檔案。", 
                        font=ctk.CTkFont(family="Microsoft JhengHei")).pack(pady=20)
            return

        # 基本設定
        ctk.CTkLabel(self, text="基本設定", font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")
        
        ctk.CTkLabel(self, text="伺服器連接埠 (Port):", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.port_var = ctk.StringVar(value=self.properties.get('server-port', '25565'))
        ctk.CTkEntry(self, textvariable=self.port_var, font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(self, text="玩家人數上限:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.players_var = ctk.StringVar(value=self.properties.get('max-players', '20'))
        ctk.CTkEntry(self, textvariable=self.players_var, font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(self, text="正版模式:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.online_mode_var = ctk.BooleanVar(value=self.properties.get('online-mode', 'true').lower() == 'true')
        ctk.CTkSwitch(self, text="開啟正版驗證", variable=self.online_mode_var, font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=3, column=1, padx=10, pady=5, sticky="w")
        
        # 遊戲設定
        ctk.CTkLabel(self, text="遊戲設定", font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold")).grid(row=4, column=0, columnspan=2, padx=10, pady=(15, 5), sticky="w")
        
        ctk.CTkLabel(self, text="玩家傷害 (PVP):", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.pvp_var = ctk.BooleanVar(value=self.properties.get('pvp', 'true').lower() == 'true')
        ctk.CTkSwitch(self, text="允許玩家互相攻擊", variable=self.pvp_var, font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=5, column=1, padx=10, pady=5, sticky="w")
        
        ctk.CTkLabel(self, text="遊戲難度:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.difficulty_var = ctk.StringVar(value=self.properties.get('difficulty', 'easy'))
        difficulty_menu = ctk.CTkOptionMenu(self, variable=self.difficulty_var, 
                                          values=["peaceful", "easy", "normal", "hard"],
                                          font=ctk.CTkFont(family="Microsoft JhengHei"))
        difficulty_menu.grid(row=6, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(self, text="遊戲模式:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=7, column=0, padx=10, pady=5, sticky="w")
        self.gamemode_var = ctk.StringVar(value=self.properties.get('gamemode', 'survival'))
        gamemode_menu = ctk.CTkOptionMenu(self, variable=self.gamemode_var,
                                        values=["survival", "creative", "adventure", "spectator"],
                                        font=ctk.CTkFont(family="Microsoft JhengHei"))
        gamemode_menu.grid(row=7, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkButton(self, text="💾 儲存並關閉", command=self.save_and_close, 
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=8, column=1, padx=10, pady=20, sticky="e")
        
    def save_and_close(self):
        new_values = {
            'server-port': self.port_var.get(),
            'max-players': self.players_var.get(),
            'online-mode': str(self.online_mode_var.get()).lower(),
            'pvp': str(self.pvp_var.get()).lower(),
            'difficulty': self.difficulty_var.get(),
            'gamemode': self.gamemode_var.get()
        }
        try:
            write_properties(self.server_path, new_values)
            messagebox.showinfo("成功", "伺服器屬性已儲存！", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗：\n{e}", parent=self)

# --- Server Management Interface ---
class ManageView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.scan_frame = ctk.CTkFrame(self)
        self.scan_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.scan_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.scan_frame, text="伺服器根目錄:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        self.scan_path_entry = ctk.CTkEntry(self.scan_frame, font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.scan_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(self.scan_frame, text="瀏覽", width=80, command=self.browse_scan_path,
                     font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=0, column=2, padx=5, pady=10)
        ctk.CTkButton(self.scan_frame, text="🔍 掃描伺服器", command=self.scan_servers,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=3, padx=10, pady=10)
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="找到的伺服器")
        self.scrollable_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.status_label.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.load_path_and_scan()

    def load_path_and_scan(self):
        settings = load_settings()
        self.scan_path_entry.insert(0, settings.get('scan_path', '')); self.scan_servers()

    def browse_scan_path(self):
        path = filedialog.askdirectory()
        if path:
            self.scan_path_entry.delete(0, "end"); self.scan_path_entry.insert(0, path)
            settings = load_settings(); settings['scan_path'] = path; save_settings(settings)

    def scan_servers(self):
        if not self.scan_path_entry.get(): return
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        servers = scan_for_servers(self.scan_path_entry.get())
        if not servers:
            ctk.CTkLabel(self.scrollable_frame, text="(´・ω・`) 找不到任何由本工具安裝的伺服器...",
                        font=ctk.CTkFont(family="Microsoft JhengHei")).pack(pady=20)
            return
        for server in servers: self.add_server_widget(server)

    def add_server_widget(self, server_info):
        card = ctk.CTkFrame(self.scrollable_frame); card.pack(fill="x", padx=10, pady=5)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=f"類型: {server_info['core_type']} | 版本: {server_info['version']}", anchor="w",
                    font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(card, text=f"路徑: {server_info['path']}", anchor="w", text_color="gray",
                    font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=1, column=0, padx=10, pady=(0, 5), sticky="w")
        
        button_frame = ctk.CTkFrame(card, fg_color="transparent"); button_frame.grid(row=0, column=1, rowspan=2, padx=10, pady=5, sticky="e")
        ctk.CTkButton(button_frame, text="▶ 啟動", width=80, command=lambda p=server_info['path']: self.start_server(p),
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).pack(side="left", padx=5)
        backup_button = ctk.CTkButton(button_frame, text="💾 備份", width=80,
                                    font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold"))
        backup_button.configure(command=lambda p=server_info['path'], b=backup_button: self.backup_server(p, b))
        backup_button.pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="⚙ 屬性", width=80, command=lambda p=server_info['path']: self.open_properties_editor(p),
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).pack(side="left", padx=5)

    def open_properties_editor(self, server_path): PropertiesEditor(self, server_path)

    def start_server(self, path):
        try: run_server(path); self.status_label.configure(text=f"正在啟動 {os.path.basename(path)}...")
        except Exception as e: messagebox.showerror("啟動失敗", f"無法啟動伺服器：\n{e}")

    def backup_server(self, path, button):
        button.configure(state="disabled", text="備份中...")
        self.status_label.configure(text=f"正在備份 {os.path.basename(path)}，請稍候...")
        worker = Worker(create_backup, path, lambda t, v: self.status_label.configure(text=t))
        worker.start()
        self.after(100, self.check_backup_status, worker, button)

    def check_backup_status(self, worker, button):
        if worker.is_alive():
            self.after(100, self.check_backup_status, worker, button)
        else:
            button.configure(state="normal", text="💾 備份")
            if isinstance(worker.result, Exception):
                messagebox.showerror("備份失敗", f"發生錯誤：\n{worker.result}")
                self.status_label.configure(text="備份失敗！ ( TДT)")
            else:
                messagebox.showinfo("備份成功", f"成功建立備份檔案：\n{worker.result}")
                self.status_label.configure(text="備份完成！(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧")

# --- Application Settings Interface ---
class SettingsView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.initial_theme = "" # 用來追蹤主題是否變更

        # --- 外觀設定 ---
        appearance_title = ctk.CTkLabel(self, text="外觀設定", font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold"))
        appearance_title.grid(row=0, column=0, columnspan=3, padx=20, pady=(10, 5), sticky="w")
        
        appearance_frame = ctk.CTkFrame(self, fg_color="transparent")
        appearance_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        appearance_frame.grid_columnconfigure((1, 3), weight=1)

        # 顏色模式選擇
        ctk.CTkLabel(appearance_frame, text="顏色模式:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.mode_var = ctk.StringVar()
        self.mode_menu = ctk.CTkOptionMenu(appearance_frame, variable=self.mode_var,
                                           values=["淺色", "深色", "系統"],
                                           command=self.change_mode, # 顏色模式可以即時改變
                                           font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.mode_menu.grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")

        # 主題選擇
        THEMES_DIR = os.path.join(BUNDLE_DIR, 'themes')
        self.themes = []
        if os.path.isdir(THEMES_DIR):
            self.themes = sorted([f.replace('.json', '') for f in os.listdir(THEMES_DIR) if f.endswith('.json')])
        
        if not self.themes:
            self.themes = ["(找不到主題)"]

        ctk.CTkLabel(appearance_frame, text="應用程式主題:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")
        self.theme_var = ctk.StringVar()
        self.theme_menu = ctk.CTkOptionMenu(appearance_frame, variable=self.theme_var,
                                            values=self.themes,
                                            # 移除 command，因為無法即時生效
                                            font=ctk.CTkFont(family="Microsoft JhengHei"))
        self.theme_menu.grid(row=0, column=3, pady=5, sticky="w")
        if self.themes == "(找不到主題)": self.theme_menu.configure(state="disabled")

        # --- 伺服器啟動設定 ---
        ctk.CTkLabel(self, text="伺服器啟動設定", font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold")).grid(row=2, column=0, columnspan=3, padx=20, pady=(20, 5), sticky="w")
        
        self.total_ram_mb = round(psutil.virtual_memory().total / (1024**2))
        
        ctk.CTkLabel(self, text="最大記憶體 (RAM):", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=3, column=0, padx=20, pady=10, sticky="w")
        max_ram_rounded = (self.total_ram_mb // 256) * 256
        self.max_ram_slider = ctk.CTkSlider(self, from_=512, to=max_ram_rounded, number_of_steps=(max_ram_rounded - 512) // 256, command=self.update_ram_labels)
        self.max_ram_slider.grid(row=3, column=1, padx=10, pady=10, sticky="ew")
        self.max_ram_label = ctk.CTkLabel(self, text="2048 MB", font=ctk.CTkFont(family="Microsoft JhengHei")); self.max_ram_label.grid(row=3, column=2, padx=10)

        ctk.CTkLabel(self, text="最小記憶體 (RAM):", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.min_ram_slider = ctk.CTkSlider(self, from_=512, to=2048, number_of_steps=(2048 - 512) // 256, command=self.update_ram_labels)
        self.min_ram_slider.grid(row=4, column=1, padx=10, pady=10, sticky="ew")
        self.min_ram_label = ctk.CTkLabel(self, text="1024 MB", font=ctk.CTkFont(family="Microsoft JhengHei")); self.min_ram_label.grid(row=4, column=2, padx=10)
        
        self.java_switch_var = ctk.BooleanVar()
        ctk.CTkSwitch(self, text="自動下載並管理 Java 版本", variable=self.java_switch_var,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=5, column=0, columnspan=2, padx=20, pady=15, sticky="w")
        self.gui_switch_var = ctk.BooleanVar()
        ctk.CTkSwitch(self, text="啟動伺服器時顯示圖形化介面 (GUI)", variable=self.gui_switch_var,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=6, column=0, columnspan=2, padx=20, pady=15, sticky="w")

        eula_frame = ctk.CTkFrame(self, fg_color="transparent"); eula_frame.grid(row=7, column=0, columnspan=2, padx=20, pady=15, sticky="w")
        self.eula_switch_var = ctk.BooleanVar()
        ctk.CTkSwitch(eula_frame, text="自動同意 Mojang EULA", variable=self.eula_switch_var,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).pack(side="left")
        
        eula_link = ctk.CTkLabel(eula_frame, text="(閱讀條款)", text_color=("cyan", "#2098D1"), cursor="hand2",
                               font=ctk.CTkFont(family="Microsoft JhengHei"))
        eula_link.pack(side="left", padx=10)
        eula_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.minecraft.net/eula"))
        
        ctk.CTkLabel(self, text="新伺服器預設設定", font=ctk.CTkFont(family="Microsoft JhengHei", size=16, weight="bold")).grid(row=8, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="w")
        
        props_frame1 = ctk.CTkFrame(self, fg_color="transparent")
        props_frame1.grid(row=9, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        props_frame1.grid_columnconfigure((1, 3), weight=1)
        
        ctk.CTkLabel(props_frame1, text="預設連接埠:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.default_port_var = ctk.StringVar(value="25565")
        ctk.CTkEntry(props_frame1, textvariable=self.default_port_var, width=100, font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")
        
        ctk.CTkLabel(props_frame1, text="預設玩家上限:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")
        self.default_players_var = ctk.StringVar(value="20")
        ctk.CTkEntry(props_frame1, textvariable=self.default_players_var, width=100, font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=0, column=3, pady=5, sticky="w")
        
        props_frame2 = ctk.CTkFrame(self, fg_color="transparent")
        props_frame2.grid(row=10, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        props_frame2.grid_columnconfigure((1, 3), weight=1)
        
        ctk.CTkLabel(props_frame2, text="預設遊戲難度:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.default_difficulty_var = ctk.StringVar(value="easy")
        ctk.CTkOptionMenu(props_frame2, variable=self.default_difficulty_var, values=["peaceful", "easy", "normal", "hard"],
                         width=120, font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")
        
        ctk.CTkLabel(props_frame2, text="預設遊戲模式:", font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")
        self.default_gamemode_var = ctk.StringVar(value="survival")
        ctk.CTkOptionMenu(props_frame2, variable=self.default_gamemode_var, values=["survival", "creative", "adventure", "spectator"],
                         width=120, font=ctk.CTkFont(family="Microsoft JhengHei")).grid(row=0, column=3, pady=5, sticky="w")
        
        props_frame3 = ctk.CTkFrame(self, fg_color="transparent")
        props_frame3.grid(row=11, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        
        self.default_online_mode_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(props_frame3, text="預設啟用正版驗證", variable=self.default_online_mode_var,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).pack(side="left", padx=(0, 30))
        
        self.default_pvp_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(props_frame3, text="預設啟用PVP", variable=self.default_pvp_var,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).pack(side="left")
        
        ctk.CTkButton(self, text="💾 儲存設定", command=self.save_all_settings,
                     font=ctk.CTkFont(family="Microsoft JhengHei", weight="bold")).grid(row=12, column=1, columnspan=2, padx=20, pady=20, sticky="e")
        self.load_and_display_settings()

    def change_mode(self, mode_chinese: str):
        mode_map = {"淺色": "light", "深色": "dark", "系統": "system"}
        ctk.set_appearance_mode(mode_map.get(mode_chinese, "system"))

    def update_ram_labels(self, _=None):
        max_val = int(round(self.max_ram_slider.get() / 256) * 256)
        min_val = int(round(self.min_ram_slider.get() / 256) * 256)
        
        if min_val > max_val: 
            min_val = max_val
            self.min_ram_slider.set(min_val)
        
        self.min_ram_slider.configure(to=max_val, number_of_steps=(max_val - 512) // 256 if max_val > 512 else 1)
        
        self.max_ram_label.configure(text=f"{max_val} MB")
        self.min_ram_label.configure(text=f"{min_val} MB")

    def load_and_display_settings(self):
        self.settings = load_settings()
        
        if 'max_ram_gb' in self.settings:
            self.settings['max_ram_mb'] = self.settings.get('max_ram_gb', 2) * 1024
            self.settings['min_ram_mb'] = self.settings.get('min_ram_gb', 1) * 1024
            del self.settings['max_ram_gb']
            del self.settings['min_ram_gb']
            save_settings(self.settings)
        
        mode_map_rev = {"light": "淺色", "dark": "深色", "system": "系統"}
        current_mode = self.settings.get('appearance_mode', 'system').lower()
        self.mode_var.set(mode_map_rev.get(current_mode, "系統"))

        saved_theme = self.settings.get('theme', 'blue')
        if saved_theme in self.themes:
            self.theme_var.set(saved_theme)
        elif self.themes != "(找不到主題)":
            self.theme_var.set(self.themes)
        
        self.initial_theme = self.theme_var.get() # 載入時記錄當前主題

        self.max_ram_slider.set(self.settings.get('max_ram_mb', 2048))
        self.min_ram_slider.set(self.settings.get('min_ram_mb', 1024))
        self.update_ram_labels()
        
        self.java_switch_var.set(self.settings.get('auto_download_java', False))
        self.gui_switch_var.set(self.settings.get('use_server_gui', False))
        self.eula_switch_var.set(self.settings.get('auto_accept_eula', True))
        
        self.default_port_var.set(self.settings.get('default_server_port', '25565'))
        self.default_players_var.set(self.settings.get('default_max_players', '20'))
        self.default_difficulty_var.set(self.settings.get('default_difficulty', 'easy'))
        self.default_gamemode_var.set(self.settings.get('default_gamemode', 'survival'))
        self.default_online_mode_var.set(self.settings.get('default_online_mode', True))
        self.default_pvp_var.set(self.settings.get('default_pvp', True))
    
    def save_all_settings(self):
        new_theme = self.theme_var.get()

        mode_map = {"淺色": "light", "深色": "dark", "系統": "system"}
        self.settings['appearance_mode'] = mode_map.get(self.mode_var.get(), "system")
        self.settings['theme'] = new_theme
        
        self.settings['max_ram_mb'] = int(round(self.max_ram_slider.get() / 256) * 256)
        self.settings['min_ram_mb'] = int(round(self.min_ram_slider.get() / 256) * 256)
        
        self.settings['auto_download_java'] = self.java_switch_var.get()
        self.settings['use_server_gui'] = self.gui_switch_var.get()
        self.settings['auto_accept_eula'] = self.eula_switch_var.get()
        
        self.settings['default_server_port'] = self.default_port_var.get()
        self.settings['default_max_players'] = self.default_players_var.get()
        self.settings['default_difficulty'] = self.default_difficulty_var.get()
        self.settings['default_gamemode'] = self.default_gamemode_var.get()
        self.settings['default_online_mode'] = self.default_online_mode_var.get()
        self.settings['default_pvp'] = self.default_pvp_var.get()
        
        save_settings(self.settings)

        # 檢查主題是否已變更，並給予相應提示
        if self.initial_theme != new_theme:
            messagebox.showinfo("成功", "設定已儲存！ ( ´ ▽ ` )b\n\n新的主題將在您下次啟動應用程式時生效。")
            self.initial_theme = new_theme # 更新初始主題，避免重複提示
        else:
            messagebox.showinfo("成功", "設定已儲存！ ( ´ ▽ ` )b")

# --- About Page Interface ---
class AboutView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.logo_clicks = 0

        # --- Header ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=40, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        logo_image = ctk.CTkImage(Image.open(ICON_PATH), size=(48, 48))
        logo_label = ctk.CTkLabel(header_frame, image=logo_image, text="")
        logo_label.grid(row=0, column=0, rowspan=2, padx=(0, 20))
        logo_label.bind("<Button-1>", self.handle_logo_click)

        app_title = ctk.CTkLabel(header_frame, text="Minecraft Server Management Tool", 
                               font=ctk.CTkFont(size=28, weight="bold"), anchor="w")
        app_title.grid(row=0, column=1, sticky="ew")
        
        # Updated version and build date
        version_label = ctk.CTkLabel(header_frame, text="版本: v0.3.0-beta (構建於2025/11/6)", 
                                   font=ctk.CTkFont(size=14), anchor="w", text_color="gray")
        version_label.grid(row=1, column=1, sticky="ew")

        # --- Developer Info ---
        dev_frame = ctk.CTkFrame(self)
        dev_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        dev_frame.grid_columnconfigure(1, weight=1)

        dev_title = ctk.CTkLabel(dev_frame, text="開發者資訊", 
                               font=ctk.CTkFont(size=18, weight="bold"))
        dev_title.grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 5), sticky="w")

        ctk.CTkLabel(dev_frame, text="👨‍💻 開發者:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, padx=20, pady=2, sticky="w")
        ctk.CTkLabel(dev_frame, text="TNTAPPLE", font=ctk.CTkFont(size=14), anchor="e").grid(row=1, column=1, padx=20, pady=2, sticky="e")

        ctk.CTkLabel(dev_frame, text="🐙 GitHub:", font=ctk.CTkFont(size=14)).grid(row=2, column=0, padx=20, pady=2, sticky="w")
        github_link = ctk.CTkLabel(dev_frame, text="github.com/tntapple219", text_color=("cyan", "#2098D1"), cursor="hand2", font=ctk.CTkFont(size=14, underline=True), anchor="e")
        github_link.grid(row=2, column=1, padx=20, pady=2, sticky="e")
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/tntapple219"))

        ctk.CTkLabel(dev_frame, text="▶ YouTube:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, padx=20, pady=(2, 10), sticky="w")
        youtube_link = ctk.CTkLabel(dev_frame, text="@炸彈蘋果", text_color=("red", "#cc0000"), cursor="hand2", font=ctk.CTkFont(size=14, underline=True), anchor="e")
        youtube_link.grid(row=3, column=1, padx=20, pady=(2, 10), sticky="e")
        youtube_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.youtube.com/@%E7%82%B8%E5%BD%88%E8%98%8B%E6%9E%9C"))

        # --- Description ---
        desc_frame = ctk.CTkFrame(self)
        desc_frame.grid(row=2, column=0, padx=40, pady=10, sticky="nsew")
        self.grid_rowconfigure(2, weight=1) # Allow this frame to expand
        desc_frame.grid_columnconfigure(0, weight=1)

        desc_title = ctk.CTkLabel(desc_frame, text="應用程式說明", 
                                font=ctk.CTkFont(size=18, weight="bold"))
        desc_title.pack(padx=20, pady=(10, 5), anchor="w")
        
        desc_text_content = (
            "這是一個專業的 Minecraft 伺服器管理工具，提供完整的伺服器安裝、管理和配置功能。\n\n"
            "主要功能包括：\n"
            " • 支援 Paper, Purpur, Vanilla, Forge, NeoForge, Fabric 等多種伺服器核心\n"
            " • 自動化 Java 運行環境管理\n"
            " • 智能版本選擇和下載\n"
            " • 伺服器屬性配置編輯器\n"
            " • 自動備份功能\n"
            " • 直觀的圖形化用戶界面"
        )
        desc_text = ctk.CTkTextbox(desc_frame, wrap="word", fg_color="transparent")
        desc_text.pack(padx=20, pady=(0, 15), fill="both", expand=True)
        desc_text.insert("1.0", desc_text_content)
        desc_text.configure(state="disabled")

        # --- NEW: Changelog ---
        changelog_frame = ctk.CTkFrame(self)
        changelog_frame.grid(row=3, column=0, padx=40, pady=10, sticky="ew")
        changelog_frame.grid_columnconfigure(0, weight=1)

        changelog_title = ctk.CTkLabel(changelog_frame, text="更新日誌 (Changelog)", 
                                     font=ctk.CTkFont(size=18, weight="bold"))
        changelog_title.pack(padx=20, pady=(10, 5), anchor="w")

        changelog_content = (
            "v0.3.0-beta- 2025/11/5\n"
            "-------------------------------------\n"
            "• [新增功能] 新增主題和深淺色模式調整。\n"
            "---------------------------------------------------------\n"
            "v0.2.2-beta (hotfix) - 2025/11/5\n"
            "-------------------------------------\n"
            "• [修正] 修正了一個備份機制的嚴重錯誤。該錯誤會導致備份功能將先前的備份檔重複打包，造成備份檔案大小無限增長的問題。"
        )
        changelog_text = ctk.CTkTextbox(changelog_frame, wrap="word", height=80, fg_color="transparent")
        changelog_text.pack(padx=20, pady=(0, 15), fill="x", expand=True)
        changelog_text.insert("1.0", changelog_content)
        changelog_text.configure(state="disabled")

    def handle_logo_click(self, event):
        self.logo_clicks += 1
        if self.logo_clicks >= 7:
            webbrowser.open("https://pbs.twimg.com/media/EUbWQYWXQAAwMMB?format=jpg")
            self.logo_clicks = 0

# ==============================================================================
# MAIN APPLICATION CLASS - Primary Controller
# ==============================================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Server Management Tool v0.3.0-beta")
        self.geometry("900x700")  # Expanded to accommodate new about section
        
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        # 设置默认字体为微软正黑体
        self.default_font = ctk.CTkFont(family="Microsoft JhengHei")

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(padx=10, pady=10, fill="both", expand=True)

        self.tab_view.add("📥 安裝新伺服器")
        self.tab_view.add("🗂 管理現有伺服器")
        self.tab_view.add("⚙ 設定")
        self.tab_view.add("ℹ 關於")
        
        self.install_frame = InstallView(master=self.tab_view.tab("📥 安裝新伺服器"))
        self.install_frame.pack(fill="both", expand=True)
        self.manage_frame = ManageView(master=self.tab_view.tab("🗂 管理現有伺服器"))
        self.manage_frame.pack(fill="both", expand=True)
        self.settings_frame = SettingsView(master=self.tab_view.tab("⚙ 設定"))
        self.settings_frame.pack(fill="both", expand=True)
        self.about_frame = AboutView(master=self.tab_view.tab("ℹ 關於"))
        self.about_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    # 在 App 啟動前，先載入設定並套用外觀
    settings = load_settings()
    
    # 套用顏色模式 (深色/淺色/系統)
    ctk.set_appearance_mode(settings.get('appearance_mode', 'system'))
    
    # 套用主題
    THEMES_DIR = os.path.join(BUNDLE_DIR, 'themes')
    theme_name = settings.get('theme', 'blue')
    theme_path = os.path.join(THEMES_DIR, f"{theme_name}.json")
    
    # 確保主題檔案存在，若不存在則使用預設值，避免程式崩潰
    if os.path.exists(theme_path):
        ctk.set_default_color_theme(theme_path)
    else:
        # 如果找不到指定主題，就退回使用 customtkinter 內建的 blue 主題
        print(f"警告：找不到主題檔案 '{theme_path}'，將使用預設主題。")
        ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()