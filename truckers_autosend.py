"""
Atlas AutoSend TMP — Dear PyGui edition
pip install dearpygui pyautogui pyperclip keyboard psutil
"""

import dearpygui.dearpygui as dpg
import threading
import time
import random
import json
import os
import subprocess
import sys
import shutil
import urllib.request
from datetime import datetime

# Version actuelle du logiciel (mettez à jour manuellement)
VERSION = "1.2.6"

# URL brut où se trouve la dernière version du script.
# Exemple : "https://raw.githubusercontent.com/<user>/<repo>/main/truckers_autosend.py"
UPDATE_URL = "https://raw.githubusercontent.com/Atlas-dev-py/AutoSend/refs/heads/main/truckers_autosend.py"

# URL d'un fichier JSON contenant les infos de version et changelog.
# Exemple : "https://raw.githubusercontent.com/<user>/<repo>/main/version.json"
VERSION_INFO_URL = "https://raw.githubusercontent.com/Atlas-dev-py/AutoSendVersion/refs/heads/main/version.json"


try:
    import pyautogui
    import pyperclip
    import keyboard
    DEPS_OK = True
except ImportError:
    DEPS_OK = False

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    from win10toast import ToastNotifier
    NOTIF_OK = True
except ImportError:
    NOTIF_OK = False


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
CONFIG_FILE = "truckers_config.json"

def _download_remote_script():
    """Télécharge le contenu du script distant (texte brut)."""
    if not UPDATE_URL:
        return None
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=10) as r:
            return r.read().decode("utf-8")
    except Exception:
        return None


def _fetch_version_info():
    """Télécharge les infos de version (JSON avec version et changelog)."""
    if not VERSION_INFO_URL:
        return None
    try:
        with urllib.request.urlopen(VERSION_INFO_URL, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data
    except Exception:
        return None


def _parse_script_version(script_text: str) -> str | None:
    import re
    # Recherche plus souple
    match = re.search(r'VERSION\s*=\s*["\']?([^"\']+)["\']?', script_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Ancienne méthode en secours
    for line in script_text.splitlines():
        line = line.strip()
        if line.startswith("VERSION") and "=" in line:
            parts = line.split("=", 1)
            if len(parts) == 2:
                val = parts[1].strip().strip('"\'')
                if val:
                    return val
    return None


def _auto_update(show_status=True):
    """Vérifie la version et applique la mise à jour si nécessaire."""
    try:
        if show_status:
            queue_status("Vérification mise à jour…", (180, 200, 255, 255))

        # Récupérer les infos de version
        info = _fetch_version_info()
        if not info:
            if show_status:
                queue_status("Impossible de vérifier les mises à jour.", (220, 120, 120, 255))
            return

        latest_version = info.get("version", "")
        changelog = info.get("changelog", "")

        if not latest_version or latest_version == VERSION:
            if show_status:
                queue_status("Aucune mise à jour disponible.", (140, 140, 160, 255))
            return

        # Télécharger le script mis à jour
        remote_script = _download_remote_script()
        if not remote_script:
            if show_status:
                queue_status("Échec du téléchargement de la mise à jour.", (220, 120, 120, 255))
            return

        remote_script_version = _parse_script_version(remote_script)
        if remote_script_version and remote_script_version != latest_version:
            # Si le script distant ne correspond pas à la version annoncée, on ne l'applique pas.
            if show_status:
                queue_status("La version du script distant ne correspond pas à la version annoncée.", (220, 120, 120, 255))
                add_log(f"Version attendue : {latest_version}, version trouvée : {remote_script_version}", (220, 220, 150, 255))
            return

        # Corriger localement les versions distantes qui utilisent os.execv() de façon instable
        remote_script = remote_script.replace(
            "        os.execv(sys.executable, [sys.executable] + sys.argv)\n",
            "        # Redémarrer de manière fiable (utilise le python du venv si présent)\n"
            "        venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')\n"
            "        python_exec = venv_python if os.path.isfile(venv_python) else sys.executable\n"
            "        subprocess.Popen([python_exec, os.path.abspath(__file__)], cwd=os.path.dirname(os.path.abspath(__file__)))\n"
            "        sys.exit(0)\n"
        )

        local_path = os.path.abspath(__file__)

        # Appliquer la mise à jour
        if os.path.exists("updating.flag"):
            os.remove("updating.flag")
        add_log("Redémarrage après MAJ détecté – on continue normalement.", (160, 230, 180, 255))

        # Afficher le changelog si disponible
        if show_status:
            if changelog:
                add_log(f"Mise à jour {VERSION} → {latest_version} appliquée.", (160, 230, 180, 255))
                add_log(f"Changelog : {changelog}", (200, 220, 255, 255))
            queue_status("Mise à jour appliquée, redémarrage…", (160, 230, 180, 255))

        queue_status("Mise à jour appliquée — redémarrage annulé (manuel requis).", (160, 230, 180, 255))
        # Pas de redémarrage auto pour éviter les problèmes d'os.execv, l'utilisateur doit relancer manuellement après la mise à jour.
    except Exception as e:
        if show_status:
            queue_status("Échec de la mise à jour.", (220, 120, 120, 255))
        pass


def _start_update_thread():
    """Lance la vérification de mise à jour en arrière-plan."""
    try:
        t = threading.Thread(target=_auto_update, daemon=True)
        t.start()
    except Exception:
        pass


def cb_check_updates(sender, app_data):
    """Bouton UI : vérifie les mises à jour maintenant."""
    try:
        t = threading.Thread(target=_check_updates_interactive, daemon=True)
        t.start()
    except Exception:
        pass


def _check_updates_interactive():
    """Vérifie les mises à jour et affiche une modale si disponible."""
    try:
        queue_status("Vérification mise à jour…", (180, 200, 255, 255))

        info = _fetch_version_info()
        if not info:
            queue_status("Impossible de vérifier les mises à jour.", (220, 120, 120, 255))
            return

        latest_version = info.get("version", "")
        changelog = info.get("changelog", "")

        if not latest_version or latest_version == VERSION:
            queue_status("Aucune mise à jour disponible.", (140, 140, 160, 255))
            return

        # Afficher la modale de mise à jour
        dpg.set_value("update_version_text", f"Nouvelle version disponible : {latest_version} (actuelle : {VERSION})")
        dpg.set_value("update_changelog_text", changelog or "Aucun changelog fourni.")
        dpg.configure_item("modal_update", show=True)
        queue_status("Mise à jour disponible !", (255, 200, 100, 255))

    except Exception:
        queue_status("Échec de la vérification.", (220, 120, 120, 255))


def cb_apply_update(sender, app_data):
    """Applique la mise à jour depuis la modale."""
    dpg.configure_item("modal_update", show=False)
    try:
        t = threading.Thread(target=lambda: _auto_update(show_status=True), daemon=True)
        t.start()
    except Exception:
        pass


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data.get("messages"), list):
                data["messages"] = "\n".join(data["messages"])
            return data
        except Exception:
            pass
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
#  ETS2
# ─────────────────────────────────────────────
ETS2_STEAM_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Euro Truck Simulator 2\bin\win_x64\eurotrucks2.exe",
    r"C:\Program Files\Steam\steamapps\common\Euro Truck Simulator 2\bin\win_x64\eurotrucks2.exe",
    r"D:\Steam\steamapps\common\Euro Truck Simulator 2\bin\win_x64\eurotrucks2.exe",
    r"D:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\bin\win_x64\eurotrucks2.exe",
    r"E:\Steam\steamapps\common\Euro Truck Simulator 2\bin\win_x64\eurotrucks2.exe",
    r"E:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\bin\win_x64\eurotrucks2.exe",
]

def auto_detect_ets2():
    for p in ETS2_STEAM_PATHS:
        if os.path.isfile(p):
            return p
    return None

def is_ets2_running():
    if not PSUTIL_OK:
        return None
    for p in psutil.process_iter(["name"]):
        try:
            if p.info["name"] and p.info["name"].lower() == "eurotrucks2.exe":
                return True
        except Exception:
            pass
    return False

# ─────────────────────────────────────────────
#  THEMES — 6 thèmes
# ─────────────────────────────────────────────
# Chaque thème = dict avec toutes les clés nécessaires
THEMES = {

    # ── 1. Violet ETS (style référence) ──────────────────────────────
    "Violet ETS": {
        "WindowBg":    ( 13,  11,  20, 255),   # fond quasi-noir légèrement violacé
        "ChildBg":     ( 19,  16,  30, 255),
        "PopupBg":     ( 19,  16,  30, 248),
        "TitleBg":     ( 10,   8,  16, 255),
        "TitleBgA":    ( 16,  12,  28, 255),
        "TitleBgC":    ( 10,   8,  16, 255),
        "Header":      ( 45,  30,  80, 200),
        "HeaderH":     (120,  80, 200,  90),
        "HeaderA":     (140, 100, 220, 140),
        "Text":        (220, 215, 235, 255),   # blanc légèrement violacé
        "TextDis":     ( 90,  80, 120, 255),
        "Border":      ( 70,  45, 120, 200),   # bordure violette visible
        "FrameBg":     ( 22,  18,  36, 255),   # input sombre
        "FrameBgH":    ( 40,  28,  68, 255),
        "FrameBgA":    ( 90,  55, 160,  80),
        "Button":      ( 38,  26,  68, 255),   # bouton violet foncé
        "ButtonH":     ( 65,  42, 110, 255),
        "ButtonA":     ( 90,  55, 150, 255),
        "CheckMark":   (160, 110, 255, 255),
        "ScrollBg":    ( 13,  11,  20, 255),
        "ScrollGrab":  ( 45,  30,  80, 255),
        "ScrollGrabH": (100,  65, 170, 200),
        "ScrollGrabA": (130,  85, 210, 255),
        "Separator":   ( 50,  35,  85, 180),
        "Tab":         ( 22,  16,  36, 255),
        "TabH":        ( 65,  42, 110, 180),
        "TabA":        ( 48,  32,  88, 255),
        "SliderGrab":  (140,  95, 230, 255),
        "SliderGrabA": (170, 120, 255, 255),
        "PlotHisto":   (130,  85, 210, 255),
        "BtnStart":    ( 28, 120,  60, 255),
        "BtnStartH":   ( 40, 165,  80, 255),
        "BtnStartA":   (100, 220, 130, 255),
        "BtnStartTxt": (200, 255, 215, 255),
        "BtnStop":     (130,  30,  55, 255),
        "BtnStopH":    (185,  45,  75, 255),
        "BtnStopA":    (230,  80, 110, 255),
        "ProgBar":     (120,  75, 210, 255),
        "ProgBg":      ( 22,  16,  36, 255),
        "SubText":     ( 90,  80, 120, 255),
        "WarnText":    (200,  60,  90, 255),
        "TitleText":   (200, 185, 240, 255),
        "icon":        "💜",
    },

    # ── 2. Clair ─────────────────────────────────────────────────────
    "Clair": {
        "WindowBg":    (240, 242, 248, 255),
        "ChildBg":     (228, 232, 245, 255),
        "PopupBg":     (235, 238, 248, 245),
        "TitleBg":     (210, 215, 235, 255),
        "TitleBgA":    (195, 205, 230, 255),
        "TitleBgC":    (210, 215, 235, 255),
        "Header":      (180, 200, 240, 150),
        "HeaderH":     ( 79, 158, 255, 100),
        "HeaderA":     ( 79, 158, 255, 180),
        "Text":        ( 30,  35,  60, 255),
        "TextDis":     (130, 140, 170, 255),
        "Border":      (190, 200, 225, 255),
        "FrameBg":     (255, 255, 255, 255),
        "FrameBgH":    (210, 220, 245, 255),
        "FrameBgA":    ( 79, 158, 255,  80),
        "Button":      (200, 210, 235, 255),
        "ButtonH":     ( 79, 158, 255, 180),
        "ButtonA":     ( 50, 130, 220, 255),
        "CheckMark":   ( 50, 130, 220, 255),
        "ScrollBg":    (225, 228, 242, 255),
        "ScrollGrab":  (180, 195, 225, 255),
        "ScrollGrabH": ( 79, 158, 255, 180),
        "ScrollGrabA": ( 50, 130, 220, 255),
        "Separator":   (190, 200, 225, 255),
        "Tab":         (215, 222, 240, 255),
        "TabH":        ( 79, 158, 255, 120),
        "TabA":        (195, 210, 238, 255),
        "SliderGrab":  ( 50, 130, 220, 255),
        "SliderGrabA": ( 30, 100, 200, 255),
        "PlotHisto":   ( 50, 130, 220, 255),
        "BtnStart":    ( 34, 160,  74, 255),
        "BtnStartH":   ( 46, 190,  90, 255),
        "BtnStartA":   ( 20, 130,  55, 255),
        "BtnStartTxt": (255, 255, 255, 255),
        "BtnStop":     (200,  50,  70, 255),
        "BtnStopH":    (230,  70,  90, 255),
        "BtnStopA":    (170,  30,  50, 255),
        "ProgBar":     ( 50, 130, 220, 255),
        "ProgBg":      (210, 215, 235, 255),
        "SubText":     (100, 110, 150, 255),
        "WarnText":    (180,  40,  60, 255),
        "TitleText":   ( 30,  35,  60, 255),
        "icon":        "☀",
    },

    # ── 3. Vert Camionneur ────────────────────────────────────────────
    "Vert Camionneur": {
        "WindowBg":    ( 10,  18,  12, 255),
        "ChildBg":     ( 14,  24,  16, 255),
        "PopupBg":     ( 14,  24,  16, 245),
        "TitleBg":     (  8,  14,  10, 255),
        "TitleBgA":    ( 12,  22,  14, 255),
        "TitleBgC":    (  8,  14,  10, 255),
        "Header":      ( 20,  60,  28, 200),
        "HeaderH":     ( 50, 200,  80,  80),
        "HeaderA":     ( 50, 200,  80, 120),
        "Text":        (180, 240, 190, 255),
        "TextDis":     ( 80, 130,  90, 255),
        "Border":      ( 20,  60,  28, 255),
        "FrameBg":     ( 10,  20,  12, 255),
        "FrameBgH":    ( 20,  55,  28, 255),
        "FrameBgA":    ( 50, 200,  80,  60),
        "Button":      ( 20,  55,  28, 255),
        "ButtonH":     ( 50, 200,  80, 160),
        "ButtonA":     ( 50, 200,  80, 255),
        "CheckMark":   ( 80, 230, 100, 255),
        "ScrollBg":    ( 10,  18,  12, 255),
        "ScrollGrab":  ( 20,  55,  28, 255),
        "ScrollGrabH": ( 50, 200,  80, 160),
        "ScrollGrabA": ( 50, 200,  80, 255),
        "Separator":   ( 20,  55,  28, 255),
        "Tab":         ( 14,  24,  16, 255),
        "TabH":        ( 50, 200,  80, 120),
        "TabA":        ( 20,  55,  28, 255),
        "SliderGrab":  ( 80, 230, 100, 255),
        "SliderGrabA": (130, 255, 140, 255),
        "PlotHisto":   ( 80, 230, 100, 255),
        "BtnStart":    ( 30, 160,  55, 255),
        "BtnStartH":   ( 50, 210,  75, 255),
        "BtnStartA":   (120, 255, 140, 255),
        "BtnStartTxt": (  8,  18,  10, 255),
        "BtnStop":     (160,  40,  40, 255),
        "BtnStopH":    (210,  60,  60, 255),
        "BtnStopA":    (255, 100, 100, 255),
        "ProgBar":     ( 60, 210,  90, 255),
        "ProgBg":      ( 10,  22,  14, 255),
        "SubText":     ( 80, 130,  90, 255),
        "WarnText":    (220,  80,  60, 255),
        "TitleText":   (140, 230, 160, 255),
        "icon":        "🚚",
    },

    # ── 4. Rouge Turbo ────────────────────────────────────────────────
    "Rouge Turbo": {
        "WindowBg":    ( 18,   8,   8, 255),
        "ChildBg":     ( 26,  12,  12, 255),
        "PopupBg":     ( 26,  12,  12, 245),
        "TitleBg":     ( 14,   6,   6, 255),
        "TitleBgA":    ( 22,  10,  10, 255),
        "TitleBgC":    ( 14,   6,   6, 255),
        "Header":      ( 70,  18,  18, 200),
        "HeaderH":     (220,  50,  60,  80),
        "HeaderA":     (220,  50,  60, 120),
        "Text":        (245, 200, 200, 255),
        "TextDis":     (130,  80,  80, 255),
        "Border":      ( 70,  18,  18, 255),
        "FrameBg":     ( 20,   8,   8, 255),
        "FrameBgH":    ( 65,  18,  18, 255),
        "FrameBgA":    (220,  50,  60,  60),
        "Button":      ( 65,  18,  18, 255),
        "ButtonH":     (220,  50,  60, 160),
        "ButtonA":     (220,  50,  60, 255),
        "CheckMark":   (255,  80,  90, 255),
        "ScrollBg":    ( 18,   8,   8, 255),
        "ScrollGrab":  ( 65,  18,  18, 255),
        "ScrollGrabH": (220,  50,  60, 160),
        "ScrollGrabA": (220,  50,  60, 255),
        "Separator":   ( 70,  18,  18, 255),
        "Tab":         ( 26,  12,  12, 255),
        "TabH":        (220,  50,  60, 120),
        "TabA":        ( 65,  18,  18, 255),
        "SliderGrab":  (255,  80,  90, 255),
        "SliderGrabA": (255, 140, 140, 255),
        "PlotHisto":   (255,  80,  90, 255),
        "BtnStart":    ( 50, 140,  60, 255),
        "BtnStartH":   ( 70, 190,  80, 255),
        "BtnStartA":   (130, 255, 140, 255),
        "BtnStartTxt": ( 10,  18,  10, 255),
        "BtnStop":     (200,  30,  40, 255),
        "BtnStopH":    (255,  55,  65, 255),
        "BtnStopA":    (255, 120, 120, 255),
        "ProgBar":     (220,  60,  70, 255),
        "ProgBg":      ( 22,   8,   8, 255),
        "SubText":     (130,  80,  80, 255),
        "WarnText":    (255, 120,  60, 255),
        "TitleText":   (255, 180, 180, 255),
        "icon":        "🔴",
    },

    # ── 5. Cyberpunk Violet ───────────────────────────────────────────
    "Cyberpunk": {
        "WindowBg":    (  8,   4,  18, 255),
        "ChildBg":     ( 14,   8,  28, 255),
        "PopupBg":     ( 14,   8,  28, 245),
        "TitleBg":     (  6,   3,  14, 255),
        "TitleBgA":    ( 10,   6,  22, 255),
        "TitleBgC":    (  6,   3,  14, 255),
        "Header":      ( 50,  10,  90, 200),
        "HeaderH":     (180,  50, 255,  80),
        "HeaderA":     (180,  50, 255, 120),
        "Text":        (230, 200, 255, 255),
        "TextDis":     (100,  70, 140, 255),
        "Border":      ( 60,  15, 100, 255),
        "FrameBg":     ( 10,   5,  20, 255),
        "FrameBgH":    ( 50,  10,  90, 255),
        "FrameBgA":    (180,  50, 255,  60),
        "Button":      ( 50,  10,  90, 255),
        "ButtonH":     (180,  50, 255, 160),
        "ButtonA":     (200,  80, 255, 255),
        "CheckMark":   (200,  80, 255, 255),
        "ScrollBg":    (  8,   4,  18, 255),
        "ScrollGrab":  ( 50,  10,  90, 255),
        "ScrollGrabH": (180,  50, 255, 160),
        "ScrollGrabA": (200,  80, 255, 255),
        "Separator":   ( 60,  15, 100, 255),
        "Tab":         ( 14,   8,  28, 255),
        "TabH":        (180,  50, 255, 120),
        "TabA":        ( 50,  10,  90, 255),
        "SliderGrab":  (200,  80, 255, 255),
        "SliderGrabA": (230, 140, 255, 255),
        "PlotHisto":   (200,  80, 255, 255),
        "BtnStart":    ( 20, 180, 120, 255),
        "BtnStartH":   ( 30, 220, 150, 255),
        "BtnStartA":   (100, 255, 200, 255),
        "BtnStartTxt": (  6,  14,  10, 255),
        "BtnStop":     (180,  20, 120, 255),
        "BtnStopH":    (230,  40, 160, 255),
        "BtnStopA":    (255, 100, 200, 255),
        "ProgBar":     (180,  50, 255, 255),
        "ProgBg":      ( 10,   5,  20, 255),
        "SubText":     (100,  70, 140, 255),
        "WarnText":    (255,  80, 180, 255),
        "TitleText":   (220, 180, 255, 255),
        "icon":        "💜",
    },

    # ── 6. Désert (Sépia chaud) ───────────────────────────────────────
    "Désert": {
        "WindowBg":    ( 28,  20,  10, 255),
        "ChildBg":     ( 38,  28,  14, 255),
        "PopupBg":     ( 38,  28,  14, 245),
        "TitleBg":     ( 22,  16,   8, 255),
        "TitleBgA":    ( 32,  24,  12, 255),
        "TitleBgC":    ( 22,  16,   8, 255),
        "Header":      ( 80,  55,  20, 200),
        "HeaderH":     (220, 160,  40,  80),
        "HeaderA":     (220, 160,  40, 120),
        "Text":        (245, 220, 170, 255),
        "TextDis":     (140, 110,  65, 255),
        "Border":      ( 80,  55,  20, 255),
        "FrameBg":     ( 32,  22,  10, 255),
        "FrameBgH":    ( 75,  52,  18, 255),
        "FrameBgA":    (220, 160,  40,  60),
        "Button":      ( 75,  52,  18, 255),
        "ButtonH":     (220, 160,  40, 160),
        "ButtonA":     (240, 180,  50, 255),
        "CheckMark":   (240, 180,  50, 255),
        "ScrollBg":    ( 28,  20,  10, 255),
        "ScrollGrab":  ( 75,  52,  18, 255),
        "ScrollGrabH": (220, 160,  40, 160),
        "ScrollGrabA": (240, 180,  50, 255),
        "Separator":   ( 80,  55,  20, 255),
        "Tab":         ( 38,  28,  14, 255),
        "TabH":        (220, 160,  40, 120),
        "TabA":        ( 75,  52,  18, 255),
        "SliderGrab":  (240, 180,  50, 255),
        "SliderGrabA": (255, 210,  80, 255),
        "PlotHisto":   (240, 180,  50, 255),
        "BtnStart":    ( 50, 140,  55, 255),
        "BtnStartH":   ( 70, 185,  75, 255),
        "BtnStartA":   (140, 240, 150, 255),
        "BtnStartTxt": ( 10,  20,  10, 255),
        "BtnStop":     (180,  55,  30, 255),
        "BtnStopH":    (230,  75,  40, 255),
        "BtnStopA":    (255, 130,  80, 255),
        "ProgBar":     (220, 160,  40, 255),
        "ProgBg":      ( 32,  22,  10, 255),
        "SubText":     (140, 110,  65, 255),
        "WarnText":    (255, 100,  40, 255),
        "TitleText":   (245, 210, 140, 255),
        "icon":        "🏜",
    },
}

THEME_NAMES = list(THEMES.keys())

# ─────────────────────────────────────────────
#  GLOBAL STATE
# ─────────────────────────────────────────────
g_running      = False
g_count        = 0
g_thread       = None
g_log_lines    = []
g_current_theme = "Violet ETS"
LOG_MAX        = 200
_theme_objs    = {}   # cache des objets thème DPG

# Statut de la vérification de mise à jour (thread-safe via file state)
g_pending_status = None
g_pending_color = None

def add_log(msg, color=(180, 220, 180, 255)):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}]  {msg}"
    g_log_lines.append((line, color))
    if len(g_log_lines) > LOG_MAX:
        g_log_lines.pop(0)
    if dpg.does_item_exist("log_group"):
        dpg.delete_item("log_group", children_only=True)
        for l, c in g_log_lines[-40:]:
            dpg.add_text(l, color=c, parent="log_group")

def set_status(msg, color=(140, 140, 160, 255)):
    if dpg.does_item_exist("status_text"):
        dpg.set_value("status_text", msg)
        dpg.configure_item("status_text", color=color)


def queue_status(msg, color=(140, 140, 160, 255)):
    """Enfile un statut pour l'appliquer depuis la boucle principale (thread-safe)."""
    global g_pending_status, g_pending_color
    g_pending_status = msg
    g_pending_color = color


# ─────────────────────────────────────────────
#  WORKER
# ─────────────────────────────────────────────
def worker_thread(msgs, interval, duration, delay_ms, open_key, start_delay):
    global g_running, g_count

    for i in range(start_delay, 0, -1):
        if not g_running: return
        set_status(f"  Démarrage dans {i}s — bascule sur TruckersMP !", (249, 226, 175, 255))
        time.sleep(1)

    if not g_running: return

    start_time = time.time()
    add_log(f"Démarré  ·  {len(msgs)} msg  ·  intervalle {interval}s  ·  durée {int(duration/60)}min",
            (249, 226, 175, 255))

    while g_running:
        elapsed = time.time() - start_time
        if elapsed >= duration: break

        msg = random.choice(msgs)
        try:
            pyperclip.copy(msg)
            pyautogui.press(open_key)
            time.sleep(delay_ms / 1000.0)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.08)
            pyautogui.press("enter")
            g_count += 1

            pct = min(elapsed / duration * 100, 100)
            rem = duration - elapsed

            if dpg.does_item_exist("progress_bar"):
                dpg.set_value("progress_bar", pct / 100.0)

            label = msg[:50] + ("..." if len(msg) > 50 else "")
            set_status(f"  #{g_count} envoyé  ·  Restant : {int(rem/60)}m {int(rem%60):02d}s",
                       (166, 227, 161, 255))
            add_log(f"#{g_count}  {label}", (166, 227, 161, 255))

        except Exception as e:
            add_log(f"Erreur : {e}", (243, 139, 168, 255))

        wait = max(1.0, interval)
        deadline = time.time() + wait
        while g_running and time.time() < deadline:
            time.sleep(0.1)

    if g_running:
        g_running = False
        n = g_count
        set_status(f"  Terminé — {n} message(s) envoyé(s).", (166, 227, 161, 255))
        add_log(f"Terminé. Total : {n} messages.", (249, 226, 175, 255))
        if dpg.does_item_exist("progress_bar"):
            dpg.set_value("progress_bar", 1.0)
        if dpg.does_item_exist("btn_start"):
            dpg.enable_item("btn_start")
        if dpg.does_item_exist("btn_stop"):
            dpg.disable_item("btn_stop")

# ─────────────────────────────────────────────
#  THEME ENGINE
# ─────────────────────────────────────────────
def _build_theme_obj(t):
    """Construit et retourne un objet thème DPG complet."""
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg,             t["WindowBg"])
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg,              t["ChildBg"])
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg,              t["PopupBg"])
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg,              t["TitleBg"])
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive,        t["TitleBgA"])
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed,     t["TitleBgC"])
            dpg.add_theme_color(dpg.mvThemeCol_Header,               t["Header"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered,        t["HeaderH"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive,         t["HeaderA"])
            dpg.add_theme_color(dpg.mvThemeCol_Text,                 t["Text"])
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled,         t["TextDis"])
            dpg.add_theme_color(dpg.mvThemeCol_Border,               t["Border"])
            dpg.add_theme_color(dpg.mvThemeCol_BorderShadow,         (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg,              t["FrameBg"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered,       t["FrameBgH"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive,        t["FrameBgA"])
            dpg.add_theme_color(dpg.mvThemeCol_Button,               t["Button"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,        t["ButtonH"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,         t["ButtonA"])
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark,            t["CheckMark"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,          t["ScrollBg"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,        t["ScrollGrab"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, t["ScrollGrabH"])
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive,  t["ScrollGrabA"])
            dpg.add_theme_color(dpg.mvThemeCol_Separator,            t["Separator"])
            dpg.add_theme_color(dpg.mvThemeCol_Tab,                  t["Tab"])
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered,           t["TabH"])
            dpg.add_theme_color(dpg.mvThemeCol_TabActive,            t["TabA"])
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab,           t["SliderGrab"])
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive,     t["SliderGrabA"])
            dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram,        t["PlotHisto"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding,   10)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding,     8)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding,    10)   # inputs & checkboxes très arrondis
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding,      8)
            dpg.add_theme_style(dpg.mvStyleVar_PopupRounding,    10)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding,  8)
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding,       8)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding,    14, 10)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding,     10,  6)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing,      10,  7)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing,  7,  5)
            dpg.add_theme_style(dpg.mvStyleVar_IndentSpacing,    22)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize,    10)
            dpg.add_theme_style(dpg.mvStyleVar_GrabMinSize,       8)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize,  1)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize,   1)
    return th

def _build_btn_start_theme(t):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button,        t["BtnStart"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, t["BtnStartH"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,  t["BtnStartA"])
            dpg.add_theme_color(dpg.mvThemeCol_Text,          t["BtnStartTxt"])
    return th

def _build_btn_stop_theme(t):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button,        t["BtnStop"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, t["BtnStopH"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,  t["BtnStopA"])
    return th

def _build_prog_theme(t):
    with dpg.theme() as th:
        with dpg.theme_component(dpg.mvProgressBar):
            dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram, t["ProgBar"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg,       t["ProgBg"])
    return th

def apply_theme_by_name(name):
    """Applique un thème par son nom."""
    global g_current_theme, _theme_objs
    if name not in THEMES:
        return
    g_current_theme = name
    t = THEMES[name]

    # Recréer les objets thème (on supprime les anciens si existants)
    for key in ("global", "btn_start", "btn_stop", "prog"):
        if key in _theme_objs and dpg.does_item_exist(_theme_objs[key]):
            dpg.delete_item(_theme_objs[key])

    _theme_objs["global"]    = _build_theme_obj(t)
    _theme_objs["btn_start"] = _build_btn_start_theme(t)
    _theme_objs["btn_stop"]  = _build_btn_stop_theme(t)
    _theme_objs["prog"]      = _build_prog_theme(t)

    dpg.bind_theme(_theme_objs["global"])
    if dpg.does_item_exist("btn_start"):
        dpg.bind_item_theme("btn_start", _theme_objs["btn_start"])
    if dpg.does_item_exist("btn_stop"):
        dpg.bind_item_theme("btn_stop",  _theme_objs["btn_stop"])
    if dpg.does_item_exist("progress_bar"):
        dpg.bind_item_theme("progress_bar", _theme_objs["prog"])

    # Mettre à jour les textes colorés
    if dpg.does_item_exist("hdr_title"):
        dpg.configure_item("hdr_title", color=t["TitleText"])
    if dpg.does_item_exist("hdr_sep1"):
        dpg.configure_item("hdr_sep1", color=t["Border"])
    if dpg.does_item_exist("hdr_sep2"):
        dpg.configure_item("hdr_sep2", color=t["Border"])
    if dpg.does_item_exist("hdr_f10"):
        dpg.configure_item("hdr_f10", color=t["WarnText"])
    if dpg.does_item_exist("status_text"):
        dpg.configure_item("status_text", color=t["SubText"])

    # Mettre à jour les boutons du sélecteur de thème
    for n in THEME_NAMES:
        tag = f"theme_btn_{n}"
        if dpg.does_item_exist(tag):
            is_active = (n == name)
            checkmark = "  ✔" if is_active else "     "
            label = f"  {THEMES[n]['icon']}  {n}{checkmark}"
            dpg.set_item_label(tag, label)

    # Mettre à jour le label "Thème actif" dans l'onglet Thème
    if dpg.does_item_exist("theme_active_label"):
        dpg.set_value("theme_active_label", f"  {t['icon']}  {name}")
        dpg.configure_item("theme_active_label", color=t["TitleText"])

    # Sauvegarder le choix
    cfg = load_config()
    cfg["theme"] = name
    save_config(cfg)

# ─────────────────────────────────────────────
#  CALLBACKS
# ─────────────────────────────────────────────
def cb_start(sender, app_data):
    global g_running, g_count, g_thread
    if not DEPS_OK:
        dpg.configure_item("modal_err", show=True)
        dpg.set_value("modal_err_msg", "Installe les dépendances :\npip install pyautogui pyperclip keyboard")
        return
    raw = dpg.get_value("input_messages")
    msgs = [l.strip() for l in raw.splitlines() if l.strip()]
    if not msgs:
        dpg.configure_item("modal_err", show=True)
        dpg.set_value("modal_err_msg", "Entrez au moins un message !")
        return
    ets2 = is_ets2_running()
    if ets2 is False:
        dpg.configure_item("modal_warn_ets2", show=True)
        return
    _do_start(msgs)

def _do_start(msgs):
    global g_running, g_count, g_thread
    try:
        interval    = float(dpg.get_value("spin_interval"))
        duration    = float(dpg.get_value("spin_duration")) * 60
        delay_ms    = int(dpg.get_value("spin_delay"))
        open_key    = dpg.get_value("input_openkey").strip() or "y"
        start_delay = int(dpg.get_value("spin_startdelay"))
    except Exception:
        return
    g_running = True
    g_count   = 0
    dpg.disable_item("btn_start")
    dpg.enable_item("btn_stop")
    dpg.set_value("progress_bar", 0.0)
    g_thread = threading.Thread(
        target=worker_thread,
        args=(msgs, interval, duration, delay_ms, open_key, start_delay),
        daemon=True)
    g_thread.start()

def cb_stop(sender, app_data):
    global g_running
    g_running = False
    set_status("Arrêté.", (243, 139, 168, 255))
    add_log("Arrêté manuellement.", (243, 139, 168, 255))
    dpg.enable_item("btn_start")
    dpg.disable_item("btn_stop")
    dpg.set_value("progress_bar", 0.0)

def cb_save(sender, app_data):
    cfg = {
        "messages":    dpg.get_value("input_messages"),
        "interval":    dpg.get_value("spin_interval"),
        "duration":    dpg.get_value("spin_duration"),
        "open_key":    dpg.get_value("input_openkey").strip(),
        "delay_ms":    dpg.get_value("spin_delay"),
        "start_delay": dpg.get_value("spin_startdelay"),
    }
    save_config(cfg)
    add_log("Configuration sauvegardée (partage)  ✓", (249, 226, 175, 255))

def cb_save_local(sender, app_data):
    cfg = load_config()
    cfg.update({
        "messages":    dpg.get_value("input_messages"),
        "interval":    dpg.get_value("spin_interval"),
        "duration":    dpg.get_value("spin_duration"),
        "open_key":    dpg.get_value("input_openkey").strip(),
        "delay_ms":    dpg.get_value("spin_delay"),
        "start_delay": dpg.get_value("spin_startdelay"),
        "ets2_path":   dpg.get_value("input_ets2path").strip(),
    })
    save_config(cfg)
    add_log("Config complète sauvegardée (local)  ✓", (249, 226, 175, 255))

def cb_save_quick(sender, app_data):
    """Sauvegarde les messages rapides et leurs raccourcis."""
    cfg = load_config()
    cfg["quick_msgs"]    = [dpg.get_value(f"quick_msg_{i}") for i in range(QUICK_SLOTS)]
    cfg["quick_hotkeys"] = list(g_quick_hotkeys)
    save_config(cfg)
    add_log("Messages rapides sauvegardés  ✓", (137, 180, 250, 255))

def cb_autodetect(sender, app_data):
    found = auto_detect_ets2()
    if found:
        dpg.set_value("input_ets2path", found)
        add_log(f"ETS2 détecté : {found}", (249, 226, 175, 255))
    else:
        add_log("ETS2 introuvable. Renseignez le chemin manuellement.", (243, 139, 168, 255))

def cb_launch_exe(sender, app_data):
    path = dpg.get_value("input_ets2path").strip()
    if not path or not os.path.isfile(path):
        add_log("Chemin ETS2 invalide.", (243, 139, 168, 255))
        return
    subprocess.Popen([path], cwd=os.path.dirname(path))
    add_log("ETS2 lancé via l'exécutable.", (249, 226, 175, 255))

def cb_launch_steam(sender, app_data):
    subprocess.Popen("steam://rungameid/227300", shell=True)
    add_log("ETS2 lancé via Steam.", (249, 226, 175, 255))

def cb_ets2_confirm_start(sender, app_data):
    dpg.configure_item("modal_warn_ets2", show=False)
    raw = dpg.get_value("input_messages")
    msgs = [l.strip() for l in raw.splitlines() if l.strip()]
    _do_start(msgs)

def poll_ets2():
    if not dpg.does_item_exist("ets2_status"): return
    status = is_ets2_running()
    if status is True:
        dpg.set_value("ets2_status", "  ETS2 : actif  ✓")
        dpg.configure_item("ets2_status", color=(166, 227, 161, 255))
    elif status is False:
        dpg.set_value("ets2_status", "  ETS2 : non détecté")
        dpg.configure_item("ets2_status", color=(243, 139, 168, 255))
    else:
        dpg.set_value("ets2_status", "  ETS2 : psutil manquant")
        dpg.configure_item("ets2_status", color=(108, 115, 149, 255))

# ─────────────────────────────────────────────
#  KEYBINDING SYSTEM
# ─────────────────────────────────────────────
g_hotkey_start  = "F8"
g_hotkey_stop   = "F10"
g_hotkey_hooks  = []
g_listening_for = None   # "start" | "stop" | "quick_0" … "quick_5"

# Envoi rapide — 6 slots
QUICK_SLOTS     = 6
g_quick_hotkeys = ["F1", "F2", "F3", "F4", "F5", "F6"]   # valeurs par défaut

def _remove_all_hooks():
    global g_hotkey_hooks
    for h in g_hotkey_hooks:
        try: keyboard.remove_hotkey(h)
        except Exception: pass
    g_hotkey_hooks = []

def _send_quick(idx):
    """Envoie immédiatement le message rapide du slot idx."""
    if not DEPS_OK: return
    try:
        open_key = dpg.get_value("input_openkey").strip() or "y"
        delay_ms = int(dpg.get_value("spin_delay"))
        msg = dpg.get_value(f"quick_msg_{idx}").strip()
        if not msg: return
        pyperclip.copy(msg)
        pyautogui.press(open_key)
        time.sleep(delay_ms / 1000.0)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)
        pyautogui.press("enter")
        label = msg[:50] + ("..." if len(msg) > 50 else "")
        add_log(f"[Rapide #{idx+1}]  {label}", (137, 180, 250, 255))
    except Exception as ex:
        add_log(f"[Rapide #{idx+1}] Erreur : {ex}", (243, 139, 168, 255))

def _register_hotkeys():
    global g_hotkey_hooks
    _remove_all_hooks()
    if not DEPS_OK: return
    try:
        hooks = []
        hooks.append(keyboard.add_hotkey(g_hotkey_start,
            lambda: cb_start(None, None) if not g_running else None))
        hooks.append(keyboard.add_hotkey(g_hotkey_stop,
            lambda: cb_stop(None, None)  if g_running     else None))
        # Raccourcis envoi rapide
        for i, hk in enumerate(g_quick_hotkeys):
            if hk:
                idx = i  # capture par valeur
                try:
                    hooks.append(keyboard.add_hotkey(hk, lambda x=idx: _send_quick(x)))
                except Exception:
                    pass
        g_hotkey_hooks = hooks
    except Exception:
        pass

def cb_capture_key(sender, app_data, user_data):
    """user_data = "start" | "stop" | "quick_0" … "quick_5" """
    global g_listening_for
    g_listening_for = user_data
    _remove_all_hooks()
    # Mise à jour du label "en attente"
    tag = _listening_label_tag(user_data)
    if dpg.does_item_exist(tag):
        dpg.set_value(tag, "Appuie…")

def _listening_label_tag(which):
    if which == "start":   return "kb_start_label"
    if which == "stop":    return "kb_stop_label"
    # quick_0 … quick_5
    try:
        idx = int(which.split("_")[1])
        return f"kb_quick_label_{idx}"
    except Exception:
        return ""

def _on_key_press(e):
    global g_listening_for, g_hotkey_start, g_hotkey_stop, g_quick_hotkeys
    if g_listening_for is None: return
    key = e.name.upper()

    tag = _listening_label_tag(g_listening_for)

    if key in ("ESC", "ESCAPE"):
        # Restaurer l'ancien label
        if g_listening_for == "start":
            if dpg.does_item_exist("kb_start_label"):
                dpg.set_value("kb_start_label", g_hotkey_start)
        elif g_listening_for == "stop":
            if dpg.does_item_exist("kb_stop_label"):
                dpg.set_value("kb_stop_label", g_hotkey_stop)
        else:
            try:
                idx = int(g_listening_for.split("_")[1])
                if dpg.does_item_exist(f"kb_quick_label_{idx}"):
                    dpg.set_value(f"kb_quick_label_{idx}", g_quick_hotkeys[idx])
            except Exception: pass
        g_listening_for = None
        _register_hotkeys()
        return

    # Affecter la touche
    if g_listening_for == "start":
        g_hotkey_start = key
        if dpg.does_item_exist("kb_start_label"):
            dpg.set_value("kb_start_label", key)
    elif g_listening_for == "stop":
        g_hotkey_stop = key
        if dpg.does_item_exist("kb_stop_label"):
            dpg.set_value("kb_stop_label", key)
    else:
        try:
            idx = int(g_listening_for.split("_")[1])
            g_quick_hotkeys[idx] = key
            if dpg.does_item_exist(f"kb_quick_label_{idx}"):
                dpg.set_value(f"kb_quick_label_{idx}", key)
        except Exception: pass

    g_listening_for = None
    _register_hotkeys()

    # Sauvegarder
    cfg = load_config()
    cfg["hotkey_start"]  = g_hotkey_start
    cfg["hotkey_stop"]   = g_hotkey_stop
    cfg["quick_hotkeys"] = g_quick_hotkeys
    save_config(cfg)
    add_log(f"Raccourci mis à jour.", (249, 226, 175, 255))

# ─────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────
def build_ui():
    cfg = load_config()

    raw_msg = cfg.get("messages", "")
    if isinstance(raw_msg, list):
        raw_msg = "\n".join(raw_msg)

    def cfg_int(key, default):
        try: return int(cfg[key])
        except: return default
    def cfg_str(key, default):
        v = cfg.get(key, default)
        return str(v) if v is not None else default
    def cfg_bool(key, default):
        v = cfg.get(key, default)
        if isinstance(v, bool): return v
        return default

    v_interval   = cfg_int("interval",    30)
    v_duration   = cfg_int("duration",    10)
    v_delay      = cfg_int("delay_ms",   300)
    v_startdelay = cfg_int("start_delay",  5)
    v_openkey    = cfg_str("open_key",    "y")
    v_ets2       = cfg_str("ets2_path", "") or auto_detect_ets2() or ""

    # Messages rapides
    v_quick_msgs    = cfg.get("quick_msgs",    [""] * QUICK_SLOTS)
    v_quick_hotkeys = cfg.get("quick_hotkeys", list(g_quick_hotkeys))
    # S'assurer que les listes font bien QUICK_SLOTS éléments
    while len(v_quick_msgs)    < QUICK_SLOTS: v_quick_msgs.append("")
    while len(v_quick_hotkeys) < QUICK_SLOTS: v_quick_hotkeys.append("")

    # ── Modales ──
    with dpg.window(label="Erreur", modal=True, show=False, tag="modal_err",
                    no_resize=True, width=340, height=120):
        dpg.add_text("", tag="modal_err_msg", wrap=300)
        dpg.add_separator()
        dpg.add_button(label="OK", width=80,
                       callback=lambda: dpg.configure_item("modal_err", show=False))

    with dpg.window(label="ETS2 non détecté", modal=True, show=False,
                    tag="modal_warn_ets2", no_resize=True, width=380, height=140):
        dpg.add_text("Euro Truck Simulator 2 ne semble pas lancé.\nContinuer quand même ?", wrap=340)
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(label="Oui, continuer", width=130, callback=cb_ets2_confirm_start)
            dpg.add_button(label="Annuler", width=100,
                           callback=lambda: dpg.configure_item("modal_warn_ets2", show=False))

    # Modale pour afficher le changelog de mise à jour
    with dpg.window(label="Mise à jour disponible", modal=True, show=False,
                    tag="modal_update", no_resize=True, width=500, height=300):
        dpg.add_text("", tag="update_version_text", color=(220, 200, 255, 255))
        dpg.add_spacer(height=8)
        dpg.add_text("Changelog :", color=(180, 200, 255, 255))
        dpg.add_spacer(height=4)
        dpg.add_text("", tag="update_changelog_text", wrap=480)
        dpg.add_spacer(height=16)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Mettre à jour maintenant", width=180,
                           callback=cb_apply_update)
            dpg.add_button(label="Plus tard", width=100,
                           callback=lambda: dpg.configure_item("modal_update", show=False))

    # ── Fenêtre principale ──
    with dpg.window(label="Atlas AutoSend TMP", tag="main_window",
                    no_close=True, no_collapse=True):

        # ── Header fixe (hors onglets) ──
        with dpg.group(horizontal=True):
            dpg.add_text("Atlas AutoSend TMP", tag="hdr_title")
            dpg.add_text("  |", tag="hdr_sep1")
            dpg.add_text("", tag="ets2_status")
            dpg.add_text("  |", tag="hdr_sep2")
            dpg.add_text("F10 = STOP", tag="hdr_f10")

        dpg.add_separator()
        dpg.add_spacer(height=2)

        # ══════════════════════════════════════════
        #  BARRE D'ONGLETS
        # ══════════════════════════════════════════
        with dpg.tab_bar(tag="main_tab_bar"):

            # ╔══════════════════════════════╗
            # ║  Onglet 1 — AutoSend         ║
            # ╚══════════════════════════════╝
            with dpg.tab(label="  🚛  AutoSend  ", tag="tab_autosend"):
                dpg.add_spacer(height=6)

                with dpg.collapsing_header(label="  Messages", default_open=True):
                    dpg.add_text("Un message par ligne  —  sélection aléatoire à chaque envoi",
                                 color=(108, 115, 149, 255))
                    dpg.add_spacer(height=2)
                    dpg.add_input_text(tag="input_messages", multiline=True,
                                       height=110, width=-1, default_value=raw_msg,
                                       hint="Salut tout le monde !\nJe suis en convoi...")
                    with dpg.popup(parent="input_messages", mousebutton=dpg.mvMouseButton_Right):
                        dpg.add_text("Edition", color=(108, 115, 149, 255))
                        dpg.add_separator()
                        dpg.add_menu_item(label="  Copier tout",
                            callback=lambda: __import__('pyperclip').copy(dpg.get_value("input_messages"))
                            if DEPS_OK else None)
                        dpg.add_menu_item(label="  Coller",
                            callback=lambda: dpg.set_value("input_messages",
                                dpg.get_value("input_messages") + (__import__('pyperclip').paste() if DEPS_OK else "")))
                        dpg.add_menu_item(label="  Effacer tout",
                            callback=lambda: dpg.set_value("input_messages", ""))

                dpg.add_spacer(height=4)

                with dpg.collapsing_header(label="  Timing", default_open=True):
                    with dpg.group(horizontal=True):
                        dpg.add_text("Intervalle (sec) :", color=(108, 115, 149, 255))
                        dpg.add_input_int(tag="spin_interval", default_value=v_interval,
                                          min_value=1, max_value=9999, width=150,
                                          min_clamped=True, max_clamped=True)
                        dpg.add_spacer(width=20)
                        dpg.add_text("Durée totale (min) :", color=(108, 115, 149, 255))
                        dpg.add_input_int(tag="spin_duration", default_value=v_duration,
                                          min_value=1, max_value=9999, width=150,
                                          min_clamped=True, max_clamped=True)
                    dpg.add_spacer(height=4)
                dpg.add_spacer(height=4)

                with dpg.collapsing_header(label="  Touches Chat", default_open=True):
                    with dpg.group(horizontal=True):
                        dpg.add_text("Touche ouvrir chat :", color=(108, 115, 149, 255))
                        dpg.add_input_text(tag="input_openkey", width=50, default_value=v_openkey)
                        dpg.add_spacer(width=20)
                        dpg.add_text("Délai avant envoi (ms) :", color=(108, 115, 149, 255))
                        dpg.add_input_int(tag="spin_delay", default_value=v_delay,
                                          min_value=50, max_value=3000, width=150,
                                          min_clamped=True, max_clamped=True)

                dpg.add_spacer(height=4)

                with dpg.collapsing_header(label="  Démarrage AutoSend", default_open=True):
                    with dpg.group(horizontal=True):
                        dpg.add_text("Délai avant démarrage (sec) :", color=(108, 115, 149, 255))
                        dpg.add_input_int(tag="spin_startdelay", default_value=v_startdelay,
                                          min_value=1, max_value=30, width=150,
                                          min_clamped=True, max_clamped=True)
                        dpg.add_text("← Basculez sur TruckersMP avant la fin",
                                     color=(108, 115, 149, 255))

                dpg.add_spacer(height=4)

                with dpg.collapsing_header(label="  Raccourcis clavier", default_open=True):
                    dpg.add_text("Clique sur un bouton puis appuie sur la touche souhaitée  ·  ESC pour annuler",
                                 color=(108, 115, 149, 255))
                    dpg.add_spacer(height=6)
                    with dpg.group(horizontal=True):
                        dpg.add_text("Démarrer :", color=(108, 115, 149, 255))
                        dpg.add_spacer(width=6)
                        dpg.add_text(g_hotkey_start, tag="kb_start_label", color=(166, 227, 161, 255))
                        dpg.add_spacer(width=10)
                        dpg.add_button(label="  Changer", width=100,
                                       callback=cb_capture_key, user_data="start")
                        dpg.add_spacer(width=30)
                        dpg.add_text("Arrêter :", color=(108, 115, 149, 255))
                        dpg.add_spacer(width=6)
                        dpg.add_text(g_hotkey_stop, tag="kb_stop_label", color=(243, 139, 168, 255))
                        dpg.add_spacer(width=10)
                        dpg.add_button(label="  Changer", width=100,
                                       callback=cb_capture_key, user_data="stop")

                dpg.add_spacer(height=4)

                with dpg.collapsing_header(label="  Euro Truck Simulator 2", default_open=True):
                    with dpg.group(horizontal=True):
                        dpg.add_text("Chemin ETS2 :", color=(108, 115, 149, 255))
                        dpg.add_input_text(tag="input_ets2path", width=-200,
                                           default_value=v_ets2, hint="C:\\...\\eurotrucks2.exe")
                        dpg.add_button(label="Auto", width=90, callback=cb_autodetect)
                    dpg.add_spacer(height=6)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="  Lancer ETS2", width=150, callback=cb_launch_exe)
                        dpg.add_button(label="  Via Steam",   width=120, callback=cb_launch_steam)

                dpg.add_spacer(height=4)

                # ── Envoi Rapide ─────────────────────────────────────
                with dpg.collapsing_header(label="  Envoi Rapide", default_open=True):
                    dpg.add_text(
                        "Envoie un message instantané via un bouton ou un raccourci clavier.",
                        color=(108, 115, 149, 255))
                    dpg.add_text(
                        "Clique sur [Changer] puis appuie sur la touche voulue  ·  ESC pour annuler.",
                        color=(108, 115, 149, 255))
                    dpg.add_spacer(height=8)

                    for i in range(QUICK_SLOTS):
                        with dpg.group(horizontal=True):
                            # Numéro de slot
                            dpg.add_text(f"#{i+1}", color=(108, 115, 149, 255))
                            dpg.add_spacer(width=4)
                            # Champ message
                            dpg.add_input_text(
                                tag=f"quick_msg_{i}",
                                default_value=v_quick_msgs[i],
                                hint=f"Message rapide #{i+1}…",
                                width=-260,
                            )
                            dpg.add_spacer(width=6)
                            # Touche actuelle
                            hk = v_quick_hotkeys[i] if v_quick_hotkeys[i] else "—"
                            dpg.add_text(hk, tag=f"kb_quick_label_{i}",
                                         color=(137, 180, 250, 255))
                            dpg.add_spacer(width=6)
                            # Bouton changer touche
                            dpg.add_button(label="Touche", width=60,
                                           callback=cb_capture_key,
                                           user_data=f"quick_{i}")
                            dpg.add_spacer(width=4)
                            # Bouton envoyer maintenant
                            dpg.add_button(label="  Envoyer", tag=f"btn_quick_{i}", width=80,
                                           callback=lambda s, a, u: _send_quick(u),
                                           user_data=i)
                        dpg.add_spacer(height=4)

                    dpg.add_spacer(height=4)
                    dpg.add_button(label="  Sauvegarder les messages rapides", width=260, height=28,
                                   callback=cb_save_quick)
                # ─────────────────────────────────────────────────────

                dpg.add_spacer(height=8)
                dpg.add_separator()
                dpg.add_spacer(height=6)

                # Boutons principaux
                with dpg.group(horizontal=True):
                    dpg.add_button(label="  Démarrer", tag="btn_start", width=140, height=36,
                                   callback=cb_start)
                    dpg.add_button(label="  Arrêter",  tag="btn_stop",  width=120, height=36,
                                   callback=cb_stop, enabled=False)
                    dpg.add_spacer(width=8)
                    dpg.add_button(label="  Sauvegarder", width=180, height=36,
                                   callback=cb_save_local)

                dpg.add_spacer(height=4)
                dpg.add_text("  Sauvegarde locale (tout le contenu).",
                             color=(108, 115, 149, 255))
                dpg.add_spacer(height=8)

                with dpg.group(horizontal=True):
                    dpg.add_text("En attente…", tag="status_text", color=(108, 115, 149, 255))
                    dpg.add_spacer(width=16)
                    dpg.add_button(label=f"Vérifier les mises à jour (v{VERSION})", width=250,
                                   callback=cb_check_updates)
                dpg.add_progress_bar(tag="progress_bar", default_value=0.0, width=-1, height=8)

                dpg.add_spacer(height=6)
                dpg.add_separator()
                dpg.add_text("Journal d'activité", color=(108, 115, 149, 255))
                dpg.add_spacer(height=2)
                with dpg.child_window(height=160, width=-1, border=True, tag="log_window"):
                    with dpg.group(tag="log_group"):
                        pass

            # ╔══════════════════════════════╗
            # ║  Onglet 2 — Thème            ║
            # ╚══════════════════════════════╝
            with dpg.tab(label="  🎨  Thème  ", tag="tab_theme"):
                dpg.add_spacer(height=14)
                dpg.add_text("  Choisissez votre thème", color=(108, 115, 149, 255))
                dpg.add_text("  Le choix est sauvegardé automatiquement.",
                             color=(108, 115, 149, 255))
                dpg.add_spacer(height=16)

                # Grille de boutons de thème — 2 colonnes
                for row_start in range(0, len(THEME_NAMES), 2):
                    with dpg.group(horizontal=True):
                        for n in THEME_NAMES[row_start:row_start + 2]:
                            t = THEMES[n]
                            is_active = (n == g_current_theme)
                            checkmark = "  ✔" if is_active else "     "
                            label = f"  {t['icon']}  {n}{checkmark}"
                            dpg.add_button(
                                label=label,
                                tag=f"theme_btn_{n}",
                                width=345, height=52,
                                callback=lambda s, a, u: apply_theme_by_name(u),
                                user_data=n,
                            )
                            dpg.add_spacer(width=6)
                    dpg.add_spacer(height=6)

                dpg.add_spacer(height=20)
                dpg.add_separator()
                dpg.add_spacer(height=10)

                dpg.add_text("  Thème actif :", color=(108, 115, 149, 255))
                dpg.add_spacer(height=4)
                active_t = THEMES.get(g_current_theme, THEMES["Violet ETS"])
                dpg.add_text(
                    f"  {active_t['icon']}  {g_current_theme}",
                    tag="theme_active_label",
                    color=active_t["TitleText"],
                )

def _load_font():
    """
    Charge une police personnalisée si disponible.
    Cherche Carlito (clone de Calibri, fin & moderne) puis d'autres alternatives.
    Retourne True si une police a été chargée.
    """
    candidates = [
        # Windows — polices installées par défaut
        r"C:\Windows\Fonts\calibril.ttf",     # Calibri Light
        r"C:\Windows\Fonts\calibri.ttf",      # Calibri
        r"C:\Windows\Fonts\segoeui.ttf",      # Segoe UI
        r"C:\Windows\Fonts\tahoma.ttf",       # Tahoma
        # Linux / macOS
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with dpg.font_registry():
                    dpg.add_font(path, 15, tag="app_font")
                dpg.bind_font("app_font")
                return True
            except Exception:
                pass
    return False


def _show_welcome_animation(duration=1.2):
    """Affiche une courte animation de bienvenue au démarrage."""
    try:
        # Création rapide d'une fenêtre modale avec texte + barre de progression
        with dpg.window(label="", tag="welcome_win", no_title_bar=True, no_resize=True,
                        no_move=True, no_close=True, no_background=False, modal=True,
                        width=420, height=160):
            dpg.add_spacer(height=10)
            dpg.add_text("Bienvenue dans Atlas AutoSend TMP", tag="welcome_text",
                         color=(220, 200, 255, 255))
            dpg.add_spacer(height=12)
            dpg.add_progress_bar(tag="welcome_progress", default_value=0.0, width=-1, height=18)
            dpg.add_spacer(height=10)
            dpg.add_text("Chargement en cours...", tag="welcome_label",
                         color=(200, 200, 240, 255))

        # Centrer la fenêtre
        try:
            vw = dpg.get_viewport_width()
            vh = dpg.get_viewport_height()
            dpg.set_item_pos("welcome_win", ((vw - 420) // 2, (vh - 160) // 2))
        except Exception:
            pass

        start = time.time()
        while time.time() - start < duration and dpg.is_dearpygui_running():
            t = (time.time() - start) / duration
            dpg.set_value("welcome_progress", min(max(t, 0.0), 1.0))
            dpg.render_dearpygui_frame()
        dpg.delete_item("welcome_win")
    except Exception:
        pass


def main():
    global g_hotkey_start, g_hotkey_stop, g_current_theme, g_quick_hotkeys

    dpg.create_context()
    dpg.create_viewport(title="Atlas AutoSend TMP",
                        width=760, height=960,
                        min_width=500, min_height=600,
                        resizable=True)
    dpg.setup_dearpygui()

    # ── Police personnalisée ──
    _load_font()

    saved_cfg = load_config()
    saved_theme     = saved_cfg.get("theme", "Violet ETS")
    g_current_theme = saved_theme if saved_theme in THEMES else "Violet ETS"
    g_hotkey_start  = saved_cfg.get("hotkey_start", "F8").upper()
    g_hotkey_stop   = saved_cfg.get("hotkey_stop",  "F10").upper()

    # Charger les raccourcis rapides
    saved_quick = saved_cfg.get("quick_hotkeys", ["F1","F2","F3","F4","F5","F6"])
    while len(saved_quick) < QUICK_SLOTS: saved_quick.append("")
    g_quick_hotkeys = [k.upper() if k else "" for k in saved_quick[:QUICK_SLOTS]]

    build_ui()
    apply_theme_by_name(g_current_theme)

    if dpg.does_item_exist("kb_start_label"):
        dpg.set_value("kb_start_label", g_hotkey_start)
    if dpg.does_item_exist("kb_stop_label"):
        dpg.set_value("kb_stop_label",  g_hotkey_stop)
    for i, hk in enumerate(g_quick_hotkeys):
        tag = f"kb_quick_label_{i}"
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, hk if hk else "—")

    dpg.set_primary_window("main_window", True)

    if DEPS_OK:
        _register_hotkeys()
        keyboard.on_press(_on_key_press)

    last_poll      = [0.0]
    dpg.show_viewport()

    # Animer + vérifier mise à jour en arrière-plan
    _show_welcome_animation(duration=1.2)
    _start_update_thread()

    while dpg.is_dearpygui_running():
        now = time.time()
        if now - last_poll[0] > 2.0:
            poll_ets2()
            last_poll[0] = now

        # Appliquer les mises à jour de statut provenant d'autres threads
        global g_pending_status, g_pending_color
        if g_pending_status is not None:
            set_status(g_pending_status, g_pending_color or (140, 140, 160, 255))
            g_pending_status = None
            g_pending_color = None

        dpg.render_dearpygui_frame()

    dpg.destroy_context()

if __name__ == "__main__":
    main()
