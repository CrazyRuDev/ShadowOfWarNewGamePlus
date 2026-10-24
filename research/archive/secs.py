import struct
def sections(b):
    out=[];i=b.find(b'SAVE',4)
    while i>=0:
        L=struct.unpack_from('<I',b,i-8)[0]; out.append((i,L)); i=b.find(b'SAVE',i+L) if b.find(b'SAVE',i+4)>=0 else -1
        if i>=0 and struct.unpack_from('<I',b,i-8)[0]==0: i=b.find(b'SAVE',i+4)
    return out
def blocks(b,sec):
    s,L=sec; inner=struct.unpack_from('<I',b,s+0x43)[0]; p=s+0x47; end=p+inner; out=[]
    while p<end:
        tag=b[p:p+4].decode('latin1'); ver,sz=struct.unpack_from('<II',b,p+4); out.append((tag,ver,p,sz)); p+=sz+16
    assert p==end,(hex(p),hex(end))
    return out
