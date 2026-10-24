import struct
D=open('/tmp/claude-0/-home-user-claude/736d1654-7f66-5b6b-ac74-5dab6060c2ec/scratchpad/ext/hotchunk__database_game_game.gamedb','rb').read()
POOL=0x47; PSIZE=struct.unpack_from('<I',D,8)[0]; PE=POOL+PSIZE
def pstr(o):
    if 0<=o<PSIZE:
        a=POOL+o; e=D.index(b'\0',a); return D[a:e].decode('latin1')
def dump(o,n=128):
    for i in range(o,o+n,4):
        v=struct.unpack_from('<I',D,i)[0]; f=struct.unpack_from('<f',D,i)[0]
        s=pstr(v) if v>0x40 else None
        print(hex(i), D[i:i+4].hex(' '), v, ('"%s"'%s[:60]) if s and (v==0 or D[POOL+v-1]==0) else ('%g'%f if 1e-4<abs(f)<1e7 else ''))
