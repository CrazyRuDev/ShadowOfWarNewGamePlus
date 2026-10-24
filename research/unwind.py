import struct,sys,bisect
sys.path.insert(0,'.')
import sowpe,pfunc,mdmp
e=sowpe.d
pe=struct.unpack_from('<I',e,0x3c)[0]; opt=pe+24
exc_rva,exc_size=struct.unpack_from('<II',e,opt+112+3*8)
off=sowpe.va2off(sowpe.BASE+exc_rva)
RT=[]
for i in range(exc_size//12): RT.append(struct.unpack_from('<III',e,off+12*i))
RT.sort(); S=[r[0] for r in RT]
def lookup(rva):
    i=bisect.bisect_right(S,rva)-1
    if i<0: return None
    b,en,u=RT[i]
    return (b,en,u) if b<=rva<en else None
REG=['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']+['r%d'%i for i in range(8,16)]
def unwind(md,regs,rip_rva,modbase):
    ent=lookup(rip_rva)
    if not ent:  # leaf
        ret=struct.unpack('<Q',md.read(regs['rsp'],8))[0]; regs['rsp']+=8; return ret
    b,en,u=ent
    while True:
        uo=sowpe.va2off(sowpe.BASE+u)
        verf,prolog,cnt,fr=struct.unpack_from('<BBBB',e,uo)
        flags=verf>>3; frreg=fr&15; froff=(fr>>4)*16
        codes=[struct.unpack_from('<BB',e,uo+4+2*i) for i in range(cnt)]
        off_in=rip_rva-b
        i=0
        if frreg and off_in>=prolog: regs['rsp']=regs[REG[frreg]]-froff  # frame
        while i<cnt:
            co,info=codes[i]; op=info&15; oi=info>>4
            applies = co<=off_in
            if op==0: # push nonvol
                if applies: regs[REG[oi]]=struct.unpack('<Q',md.read(regs['rsp'],8))[0]; regs['rsp']+=8
                i+=1
            elif op==1:
                if oi==0: sz=codes[i+1][0]|codes[i+1][1]<<8; sz*=8; n=2
                else: sz=struct.unpack_from('<I',e,uo+4+2*(i+1))[0]; n=3
                if applies: regs['rsp']+=sz
                i+=n
            elif op==2:
                if applies: regs['rsp']+=oi*8+8
                i+=1
            elif op==3: i+=1
            elif op==4:
                o=(codes[i+1][0]|codes[i+1][1]<<8)*8
                if applies: regs[REG[oi]]=struct.unpack('<Q',md.read(regs['rsp']+o,8))[0]
                i+=2
            elif op==5:
                o=struct.unpack_from('<I',e,uo+4+2*(i+1))[0]
                if applies: regs[REG[oi]]=struct.unpack('<Q',md.read(regs['rsp']+o,8))[0]
                i+=3
            elif op==8: i+=2
            elif op==9: i+=3
            elif op==10: i+=1
            else: raise Exception('op %d'%op)
        if flags&4:  # chained
            ci=4+2*((cnt+1)&~1)
            b,en,u=struct.unpack_from('<III',e,uo+ci); off_in=10**9; rip_rva=b+10**9  # all applies
            # for chained, prologue fully applied
            rip_rva=b+0x7fffffff
            continue
        break
    ret=struct.unpack('<Q',md.read(regs['rsp'],8))[0]; regs['rsp']+=8; return ret
md=mdmp.MD(sys.argv[1])
tid,code,addr,ctx=md.exception()
base=[m for m in md.mods if m[2].lower().endswith('shadowofwar.exe')][0][0]
regs={REG[i]:struct.unpack_from('<Q',ctx,0x78+8*i)[0] for i in range(16)}
rip=struct.unpack_from('<Q',ctx,0xF8)[0]
for k in range(25):
    r=rip-base
    f=pfunc.func(sowpe.BASE+r)
    print(hex(sowpe.BASE+r), f and hex(f[0]), ' '.join('%s=%x'%(n,regs[n]) for n in ('rbx','rsi','rdi','rbp','r14','r15','rsp')))
    if not (0<=r<0x4000000): break
    rip=unwind(md,regs,r,base)
