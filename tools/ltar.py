import struct, sys
def parse(path):
    d=open(path,'rb').read()
    _,ver,nt,nfold,nfile,_a,_b,_c=struct.unpack_from('<4s7I',d,0)
    names=d[0x30:0x30+nt]
    def nm(o): return names[o:names.index(b'\0',o)].decode()
    p=0x30+nt; files=[]
    for i in range(nfile):
        no,off,cs,us,fl=struct.unpack_from('<IQQQH',d,p); p+=30
        files.append(dict(name=nm(no),off=off,cs=cs,us=us,fl=fl))
    folders=[]
    for i in range(nfold):
        folders.append(struct.unpack_from('<IIII',d,p)); p+=16
    # attach folder names to files
    return d,files,folders,nm
if __name__=='__main__':
    d,files,folders,nm=parse(sys.argv[1])
    for f in files: print(hex(f['fl']),f['off'],f['cs'],f['us'],f['name'])
    for fo in folders: print(nm(fo[0]),fo[1:])

def chunks(d,f):
    o=f['off']; end=o+f['cs']; out=[]
    while o<end:
        cs,us=struct.unpack_from('<II',d,o)
        out.append((o+8,cs,us)); o+=8+cs
        o=f['off']+((o-f['off']+3)&~3)
    return out

import ctypes, os
_lib=ctypes.CDLL(os.environ.get('OOZ_LIB','libooz.so'))
def extract(d,f):
    if f['cs']==f['us']: return d[f['off']:f['off']+f['us']]
    out=bytearray()
    for o,cs,us in chunks(d,f):
        if cs==us: out+=d[o:o+cs]; continue
        buf=ctypes.create_string_buffer(us+64)
        n=_lib.ooz_decompress(d[o:o+cs],cs,buf,us)
        if n!=us: raise ValueError('chunk %s type %s failed'%(hex(o),d[o:o+2].hex()))
        out+=buf.raw[:us]
    return bytes(out)
