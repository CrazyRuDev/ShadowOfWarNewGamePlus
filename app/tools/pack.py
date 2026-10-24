"""dist\\SoWNGPlus.zip for players: only what may be given away — not data\\ (files of the game), летопись\\, the ini.

    python pack.py      (build.bat runs it after the folder is built)
"""
import os
import zipfile

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(APP, 'dist', 'SoWNGPlus')
OUT = os.path.join(APP, 'dist', 'SoWNGPlus.zip')
FILES = ('SoWNGPlus.exe', 'SoWNGPlus.ahk', 'README.md', 'LICENSE', 'AutoHotkey-license.txt')
FOLDERS = ('python', 'engine', 'bases')


def main():
    n = 0
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in FILES:
            p = os.path.join(SRC, f)
            if os.path.isfile(p):
                z.write(p, 'SoWNGPlus/' + f)
                n += 1
        for d in FOLDERS:
            for root, dirs, files in os.walk(os.path.join(SRC, d)):
                dirs[:] = [x for x in dirs if x != '__pycache__']
                for f in files:
                    p = os.path.join(root, f)
                    z.write(p, 'SoWNGPlus/' + os.path.relpath(p, SRC).replace('\\', '/'))
                    n += 1
    print('%s: %d файлов, %.1f МБ' % (OUT, n, os.path.getsize(OUT) / 2 ** 20))


if __name__ == '__main__':
    main()
