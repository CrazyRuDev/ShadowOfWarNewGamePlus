"""Finds Shadow of War (Steam app 356190) and its newest save in a Steam installation."""
import glob
import os
import re

APP_ID = '356190'


def steam_dirs():
    out = []
    if os.name == 'nt':
        import winreg
        for root, key, value in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
                                 (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(root, key) as k:
                    out.append(os.path.normpath(winreg.QueryValueEx(k, value)[0]))
            except OSError:
                pass
    else:
        out.append(os.path.expanduser('~/.steam/steam'))
    return [d for i, d in enumerate(out) if os.path.isdir(d) and d.lower() not in (x.lower() for x in out[:i])]


def libraries(steam):
    libs = [steam]
    vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
    if os.path.exists(vdf):
        text = open(vdf, encoding='utf-8', errors='replace').read()
        for p in re.findall(r'"path"\s+"([^"]+)"', text):
            p = os.path.normpath(p.replace('\\\\', '\\'))
            if p not in libs:
                libs.append(p)
    return libs


def find_game():
    for steam in steam_dirs():
        for lib in libraries(steam):
            acf = os.path.join(lib, 'steamapps', 'appmanifest_%s.acf' % APP_ID)
            if os.path.exists(acf):
                m = re.search(r'"installdir"\s+"([^"]+)"', open(acf, encoding='utf-8', errors='replace').read())
                if m:
                    d = os.path.join(lib, 'steamapps', 'common', m.group(1))
                    if os.path.isdir(d):
                        return d
    return None


def find_save():
    """Newest <id>_ShadowOfWar.sav under Steam\\userdata\\<account>\\356190\\remote."""
    saves = []
    for steam in steam_dirs():
        saves += glob.glob(os.path.join(steam, 'userdata', '*', APP_ID, 'remote', '*_ShadowOfWar.sav'))
    return max(saves, key=os.path.getmtime) if saves else None
