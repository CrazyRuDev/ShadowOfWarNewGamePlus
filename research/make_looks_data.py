"""Writes app/engine/sowtool/looks_data.py: the item slots (17 tokens each) the "came back beforehand" looks put into
an orc's record, taken once from the saves where the game itself made them — a player's finished game may lack
them (a sack, a metal jaw, an Olog plate are rare).

    python research/make_looks_data.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import returned, save as sv          # noqa: E402
from sowtool.gamedata import GameData             # noqa: E402

SAMPLES = ['096c2a9f_ShadowOfWarОРИГ.sav',
           os.path.join('история', '096c2a9f_ShadowOfWar_20261020-085254.sav'),   # Bolg «Железная Челюсть»
           os.path.join('история', '096c2a9f_ShadowOfWar_20261022-171608.sav'),   # Ar-Baruk, the Olog plate
           os.path.join('история', '096c2a9f_ShadowOfWar_20261022-154946.sav')]   # Khoglik, the leg claw


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    found = returned.samples([sv.load(os.path.join(ROOT, 'game files', f))[0] for f in SAMPLES], gd)
    need = returned.needed()
    missing = [k for k in need if k not in found]
    assert not missing, missing
    out = os.path.join(ROOT, 'app', 'engine', 'sowtool', 'looks_data.py')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('"""Item slots of the looks of a return from the dead (research/make_looks_data.py writes this file):\n'
                '(item, AD_) -> the 17 tokens of a slot, hex. The guids in them are replaced on use."""\n')
        f.write('SLOTS = {\n')
        for k in sorted(need):
            f.write('    %r: %r,\n' % (k, found[k].hex()))
        f.write('}\n')
    print('Записано %d образцов: %s' % (len(need), out))


if __name__ == '__main__':
    main()
