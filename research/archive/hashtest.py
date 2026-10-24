import re,zlib,sys; sys.path.insert(0,'../tools'); import strdb
d=open('hotchunk__database_game_game.gamedb','rb').read()
names=set(m.group() for m in re.finditer(rb'[\x21-\x7e][\x20-\x7e]{2,}',d))
ru=strdb.load('hotchunk__database_string_ruru_string.strdb'); keys=set(ru)
def fnv1a(b):
    h=0x811c9dc5
    for c in b: h=((h^c)*0x01000193)&0xffffffff
    return h
def fnv1(b):
    h=0x811c9dc5
    for c in b: h=((h*0x01000193)&0xffffffff)^c
    return h
def djb(b):
    h=5381
    for c in b: h=(h*33+c)&0xffffffff
    return h
def sdbm(b):
    h=0
    for c in b: h=(c+(h<<6)+(h<<16)-h)&0xffffffff
    return h
def x31(b):
    h=0
    for c in b: h=(h*31+c)&0xffffffff
    return h
fs={'crc':zlib.crc32,'fnv1a':fnv1a,'fnv1':fnv1,'djb':djb,'sdbm':sdbm,'x31':x31}
for k,f in fs.items():
  for case in ['as','low','up']:
    tot=0; ex=None
    for n in names:
        b=n if case=='as' else (n.lower() if case=='low' else n.upper())
        h=f(b); c=sum(1 for i in range(16) if ((h+i)&0xffffffff) in keys)
        h2=h^0xffffffff; c+=sum(1 for i in range(16) if ((h2+i)&0xffffffff) in keys) if k=='crc' else 0
        if c>=2: tot+=1; ex=n
    print(k,case,tot,ex)
