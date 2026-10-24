"""The window script of the single-file build: a copy of gui\\SoWNGPlus.ahk with the engine and the bases built in.

    python single_ahk.py <sowtool.exe> <out .ahk>

Ahk2Exe embeds the FileInstall files into the exe; on every start the exe puts them next to itself (so a new exe
always brings its engine). The source script stays one: this adds the block to a copy only. FileInstall must stand at
the start of a line for Ahk2Exe to see it, its source a literal string (absolute paths here).
"""
import os
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    engine, out = (os.path.abspath(a) for a in sys.argv[1:3])
    bases = os.path.join(APP, 'gui', 'bases')
    s = open(os.path.join(APP, 'gui', 'SoWNGPlus.ahk'), encoding='utf-8-sig').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    anchor = 'global DATA_DIR := APP_DIR "\\data"' + nl
    assert s.count(anchor) == 1
    block = [
        '; сборка-файл: движок и опоры внутри exe (FileInstall), при каждом запуске — рядом с exe; движок занят',
        '; (идёт летопись прошлого запуска) — остаётся прежний',
        'if A_IsCompiled {',
        '    DirCreate(APP_DIR "\\engine"), DirCreate(APP_DIR "\\bases")',
        '    try',
        '        FileInstall("%s", APP_DIR "\\engine\\sowtool.exe", 1)' % engine,
    ]
    for f in sorted(os.listdir(bases)):
        if f.endswith('.sav'):
            block.append('    FileInstall("%s", APP_DIR "\\bases\\%s", 1)' % (os.path.join(bases, f), f))
    block.append('}')
    s = s.replace(anchor, anchor + nl.join(block) + nl)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8-sig', newline='').write(s)
    print('скрипт сборки-файла:', out)


if __name__ == '__main__':
    main()
