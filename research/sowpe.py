import struct
d=open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))), 'game files', 'ShadowOfWar.exe'),'rb').read()
pe=struct.unpack_from('<I',d,0x3c)[0]; n=struct.unpack_from('<H',d,pe+6)[0]; opt=struct.unpack_from('<H',d,pe+20)[0]
BASE=0x140000000
secs=[]
for i in range(n):
    o=pe+24+opt+i*40; name=d[o:o+8].rstrip(b'\0').decode(errors='replace'); vs,va,rs,ro=struct.unpack_from('<IIII',d,o+8); secs.append((name,va,vs,ro,rs))
def off2va(off):
    for nm,va,vs,ro,rs in secs:
        if ro<=off<ro+rs: return BASE+va+off-ro, nm
def va2off(v):
    r=v-BASE
    for nm,va,vs,ro,rs in secs:
        if va<=r<va+rs: return ro+r-va
