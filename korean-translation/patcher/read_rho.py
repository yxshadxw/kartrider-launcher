"""Read-only RHO 1.1 inventory reconstructed from launcher C# and validated headers.

Only writes inventories and selected small metadata copies under this analysis directory.
"""
from pathlib import Path
import collections,hashlib,json,re,struct,sys,zlib
from decode_pk import Reader
BASE=Path(__file__).resolve().parent
MASK=0xffffffff
code=(BASE/'decompiled-launcher/KartLibrary.Encrypt/RhoKey.cs').read_text(encoding='utf-8-sig')
table=[int(x) for x in re.findall(r'(\d+)u',code.split('public static uint GetRhoKey')[0])]
if len(table)!=1024:raise ValueError('Unexpected vector table')

def xor_data(data,key):
    n=key^0x8473fbc1
    stream=b''.join(struct.pack('<I',(n-i*2072773695)&MASK) for i in range(16))
    return bytes(c^stream[i&63] for i,c in enumerate(data))

def decrypt_header(data,key):
    result=[];acc=0
    for i,(v,) in enumerate(struct.iter_unpack('<I',data)):
        k=(key+i)&MASK
        vector=0
        for j in range(4):vector^=table[j*256+((k>>(8*j))&255)]
        n=v^vector^acc;result.append(n);acc=(acc+n)&MASK
    return struct.pack('<'+'I'*len(result),*result)

class Rho:
    def __init__(self,path,key):
        self.path=path;self.key=key;self.f=path.open('rb');self.size=path.stat().st_size
        if self.read(0,34).decode('utf-16le')!='Rh layer spec 1.1':raise ValueError('Only RHO 1.1 supported')
        h=decrypt_header(self.read(128,128),key)
        self.header_plain=h
        if zlib.adler32(h[4:],0)!=struct.unpack_from('<I',h)[0]:raise ValueError('Header checksum mismatch')
        version,count,white=struct.unpack_from('<III',h,4)
        if version!=65537 or count>200000:raise ValueError('Header version/count mismatch')
        self.blocks={};self.block_rows={};self.directories={}
        for i in range(count):
            h=decrypt_header(self.read(256+i*32,32),((key^white)+i)&MASK)
            idx,pos,size,usize,flags,checksum=struct.unpack_from('<IIIIII',h)
            self.blocks[idx]=dict(offset=pos<<8,size=size,usize=usize,flags=flags,checksum=checksum)
            self.block_rows[idx]=(256+i*32,((key^white)+i)&MASK)
        self.entries=[];queue=[('',MASK)]
        visited=set()
        while queue:
            prefix,idx=queue.pop(0)
            if idx in visited:raise ValueError('Directory cycle')
            visited.add(idx)
            directory_data=self.block(idx,(key+630434289)&MASK)
            self.directories[idx]=directory_data
            r=Reader(directory_data)
            def nultext():
                out=bytearray()
                while True:
                    b=r.read(2)
                    if b==b'\0\0':return out.decode('utf-16le')
                    out.extend(b)
            dirs=r.u32()
            if dirs>100000:raise ValueError('Directory limit')
            for _ in range(dirs):
                name=nultext();queue.append((prefix+name+'/',r.u32()))
            files=r.u32()
            if files>100000:raise ValueError('File limit')
            for _ in range(files):
                name=nultext();size_offset=r.p+12
                ext,prop,block,size=struct.unpack('<IIII',r.read(16))
                suffix=struct.pack('<I',ext).rstrip(b'\0').decode('ascii')
                filename=name+('.'+suffix if suffix else '')
                self.entries.append(dict(path=prefix+filename,name=name,extension=suffix,ext_num=ext,
                    property=prop,block=block,size=size,directory_block=idx,directory_size_offset=size_offset))
    def read(self,offset,size):
        if offset<0 or size<0 or offset+size>self.size:raise ValueError('File bounds')
        self.f.seek(offset);b=self.f.read(size)
        if len(b)!=size:raise ValueError('Short read')
        return b
    def block(self,idx,key):
        b=self.blocks[idx];payload=self.read(b['offset'],b['size'])
        if b['usize']>32*1024*1024:raise ValueError('Block output cap')
        if b['flags']&2:
            d=zlib.decompressobj();payload=d.decompress(payload,b['usize']+1)
            if not d.eof or len(payload)!=b['usize']:raise ValueError('Block decompression mismatch')
        if b['flags']&4:payload=xor_data(payload,key)
        if b['flags']==4 and idx+1 in self.blocks:
            tail=self.blocks[idx+1];payload+=self.read(b['offset']+b['size'],tail['size'])
        return payload
    def content(self,e):
        key=(zlib.adler32(e['name'].encode('utf-16le'),0)+e['ext_num']+self.key-1970136660)&MASK
        data=self.block(e['block'],key)
        if len(data)!=e['size']:raise ValueError('Directory file length mismatch')
        return data

def main(root):
    index=json.loads((BASE/'aaa-index-evidence.json').read_text(encoding='utf-8'))
    desired=['character_bazzi.rho','track_.rho','zeta_cn_quest.rho','track_beach_R04.rho']
    sources=[]
    for name in desired:
        hit=next((x for x in index['rho_mappings'] if x['fileName']==name),None)
        if not hit:continue
        path=root/name
        rho=Rho(path,int(hit['key']))
        report=dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            logical_mount=hit['logical_path'],header_checksum_verified=True,block_count=len(rho.blocks),
            file_count=len(rho.entries),extensions=dict(collections.Counter(e['extension'] for e in rho.entries)),entries=rho.entries)
        samples=[]
        for e in rho.entries:
            if ((e['extension'] in ['xml','bml'] and e['size']<1024*1024 and len(samples)<3)
                or (name=='track_beach_R04.rho' and e['path']=='xt_minimap.png')):
                payload=rho.content(e)
                target=BASE/'resource-samples'/name/(hashlib.sha256(e['path'].encode()).hexdigest()[:12]+'.'+e['extension'])
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
                sample=dict(logical_path=e['path'],copy=str(target.relative_to(BASE)),sha256=hashlib.sha256(payload).hexdigest(),size=len(payload),block=rho.blocks[e['block']])
                if e['extension']=='png':
                    if payload[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG signature mismatch')
                    sample['png_dimensions']=struct.unpack_from('>II',payload,16)
                if e['extension']=='bml':
                    import xml.etree.ElementTree as ET
                    try:
                        br=Reader(payload);xml_root=br.node()
                        if br.p!=len(payload):raise ValueError('Trailing BML bytes')
                        ET.indent(xml_root);ET.ElementTree(xml_root).write(target.with_suffix('.xml'),encoding='utf-8',xml_declaration=True)
                        sample.update(xml_root=xml_root.tag,xml_nodes=sum(1 for _ in xml_root.iter()),xml_copy=str(target.with_suffix('.xml').relative_to(BASE)))
                    except (ValueError,UnicodeError) as err:sample['xml_decode_error']=str(err)
                samples.append(sample)
        report['samples']=samples;rho.f.close();sources.append(report)
        print(name,'files',report['file_count'],'extensions',report['extensions'],'samples',len(samples))
    (BASE/'rho-inventory.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main(Path(sys.argv[1]))
