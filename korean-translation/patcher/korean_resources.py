"""Korean text patch using translations already shipped in legacy RHO resources."""
from pathlib import Path
import collections,hashlib,json,re,shutil,struct,sys,zlib
import xml.etree.ElementTree as ET
from decode_pk import Reader
from read_rho import Rho,table,MASK,xor_data
BASE=Path(__file__).resolve().parent

def encode_xml(root):
    def text(s):
        raw=(s or '').encode('utf-16le');return struct.pack('<I',len(raw)//2)+raw
    def node(e):
        result=text(e.tag)+text(e.text)+struct.pack('<I',len(e.attrib))
        for k,v in e.attrib.items():result+=text(k)+text(v)
        result+=struct.pack('<I',len(e))
        return result+b''.join(node(c) for c in e)
    return node(root)

def placeholders(s):
    return collections.Counter(re.findall(r'%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[diuoxXfFeEgGaAcsp]|\{\d+(?:[^{}]*)\}',s))

def translate_tree(root):
    changed=0
    for parent in root.iter():
        kr=next((e.get('v') for e in parent if e.tag=='m' and e.get('c')=='kr' and e.get('v')),None)
        if not kr:continue
        for e in parent:
            if e.tag=='m' and e.get('c')=='cn' and e.get('v') is not None and e.get('v')!=kr:
                if placeholders(e.get('v'))!=placeholders(kr):continue
                e.set('v',kr);changed+=1
    return changed

def font_korean(root):
    if root.tag!='Fonts':return False
    seen=set()
    for e in root:
        if e.tag=='BitmapFont':
            e.set('headerFile','nanumgothic_9');e.set('dataFile','nanumgothic_9')
        elif e.tag=='GdiFont':
            # Keep the family name ASCII so it survives every source and console encoding.
            e.set('faceName','Malgun Gothic')
        # FtFont keeps size/stroke and its renderer. Its OTF payload is replaced
        # with the Korean font below; renaming the RHO member is unnecessary.
    for e in list(root):
        if e.get('name') in seen:root.remove(e)
        else:seen.add(e.get('name'))
    return True

def korean_font_payloads():
    return {'SourceHanSansCN-'+weight+'.otf':
            (BASE/'fonts'/('SourceHanSansK-'+weight+'.otf')).read_bytes()
            for weight in ('Medium','Bold')}

def read_game_index(path):
    pk=path.read_bytes()
    if len(pk)<14 or pk[4:6]!=b'S\x01':raise ValueError('Unexpected aaa.pk header')
    expected=struct.unpack_from('<I',pk,10)[0]
    raw=zlib.decompress(pk[14:])
    if len(raw)!=expected:raise ValueError('Unexpected index length')
    root=Reader(raw).node()
    rows=[]
    for e in root.iter('RhoFolder'):
        name=e.get('fileName');key=e.get('key')
        if name and name.lower().endswith('.rho') and key is not None:
            rows.append((name,int(key)))
    return root,rows,pk

def encrypt_header(data,key):
    result=[];acc=0
    for i,(v,) in enumerate(struct.iter_unpack('<I',data)):
        k=(key+i)&MASK;vector=0
        for j in range(4):vector^=table[j*256+((k>>(8*j))&255)]
        result.append(v^vector^acc);acc=(acc+v)&MASK
    return struct.pack('<'+'I'*len(result),*result)

def patch_archive(src,dst,key,replacements):
    rho=Rho(src,key)
    try:
        output=bytearray(src.read_bytes());changed={};dirs={}
        file_refs=collections.Counter(e['block'] for e in rho.entries)
        directory_blocks=set(rho.directories)
        def add_changed_block(idx,plain,data_key):
            block=rho.blocks[idx]
            if idx in changed:raise ValueError(f'Shared RHO block replacement is unsupported: {idx}')
            if block['flags']==4:
                tail_idx=idx+1;tail=rho.blocks.get(tail_idx);head_size=block['size']
                if (tail is None or tail['flags']!=0 or tail['offset']!=block['offset']+head_size
                    or head_size<=0 or head_size%256 or len(plain)<head_size
                    or file_refs[tail_idx] or tail_idx in directory_blocks or tail_idx in changed):
                    raise ValueError(f'Unsafe encrypted continuation block layout: {idx}')
                changed[idx]=(plain[:head_size],data_key,'encrypted_head')
                changed[tail_idx]=(plain[head_size:],None,'raw_tail')
            else:
                changed[idx]=(plain,data_key,'normal')
        for e in rho.entries:
            if e['path'] not in replacements:continue
            payload=replacements[e['path']]
            data_key=(zlib.adler32(e['name'].encode('utf-16le'),0)+e['ext_num']+key-1970136660)&MASK
            add_changed_block(e['block'],payload,data_key)
            d=dirs.setdefault(e['directory_block'],bytearray(rho.directories[e['directory_block']]))
            struct.pack_into('<I',d,e['directory_size_offset'],len(payload))
        if len(replacements)!=sum(e['path'] in replacements for e in rho.entries):raise ValueError('Unknown replacement member')
        for idx,data in dirs.items():add_changed_block(idx,bytes(data),(key+630434289)&MASK)
        new_payloads={}
        for idx,(plain,data_key,mode) in changed.items():
            block=rho.blocks[idx].copy();flags=block['flags']
            if mode=='encrypted_head':
                encoded=xor_data(plain,data_key);flags=4;block.update(flags=flags,size=len(encoded),usize=len(plain),checksum=zlib.adler32(plain,0))
            elif mode=='raw_tail':
                encoded=plain;flags=0;block.update(flags=flags,size=len(encoded),usize=len(plain),checksum=0)
            else:
                encoded=xor_data(plain,data_key) if flags&4 else plain
                if flags&2:encoded=zlib.compress(encoded,9)
                block.update(size=len(encoded),usize=len(plain),checksum=zlib.adler32(plain,0) if flags&4 else 0)
            offset=(len(output)+255)&~255
            output.extend(b'\0'*(offset-len(output)));output.extend(encoded);block.update(offset=offset)
            row,row_key=rho.block_rows[idx]
            header=struct.pack('<IIIIIIII',idx,offset>>8,block['size'],block['usize'],flags,block['checksum'],0,0)
            output[row:row+32]=encrypt_header(header,row_key)
            new_payloads[idx]=encoded
        checksum=0
        for idx,block in rho.blocks.items():
            raw=new_payloads.get(idx)
            if raw is None:raw=rho.read(block['offset'],block['size'])
            checksum=zlib.adler32(raw,checksum)
        h=bytearray(rho.header_plain);struct.pack_into('<I',h,24,checksum)
        struct.pack_into('<I',h,0,zlib.adler32(h[4:],0));output[128:256]=encrypt_header(h,key)
        output.extend(b'\0'*((-len(output))%256))
        dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(output)
    finally:rho.f.close()
    verify=Rho(dst,key)
    try:
        for e in verify.entries:
            if e['path'] in replacements:
                if verify.content(e)!=replacements[e['path']]:raise ValueError('Roundtrip mismatch')
                block=verify.blocks[e['block']]
                if block['flags']==4:
                    expected=zlib.adler32(replacements[e['path']][:block['size']],0)
                    if block['checksum']!=expected:raise ValueError('Encrypted-head checksum mismatch')
                elif block['flags']&4 and block['checksum']!=zlib.adler32(replacements[e['path']],0):
                    raise ValueError('Content checksum mismatch')
    finally:verify.f.close()
    return dict(file=src.name,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        patched_sha256=hashlib.sha256(output).hexdigest(),media_size=len(output),data_hash=checksum,
        replaced_members=list(replacements))

def main(source,out):
    game_index,rho_rows,pk=read_game_index(source/'aaa.pk')
    records=[];files=[];errors=[];scanned=0
    for name,key in rho_rows:
        if not (source/name).exists():continue
        rho=Rho(source/name,key);replacements={}
        try:
            for e in rho.entries:
                if e['extension']!='bml':continue
                scanned+=1
                try:
                    payload=rho.content(e);br=Reader(payload);root=br.node()
                    if br.p!=len(payload):raise ValueError('Trailing binary XML bytes')
                    count=translate_tree(root)
                    font=(name=='gui_font.rho' and e['path'] in ['font@cn.bml','font@kr.bml'] and font_korean(root))
                    if count or font:
                        replacements[e['path']]=encode_xml(root)
                        records.append(dict(archive=name,member=e['path'],translated=count,font_patch=bool(font)))
                except (ValueError,UnicodeError,struct.error,zlib.error) as err:
                    errors.append(dict(archive=name,member=e['path'],error=str(err)))
        finally:rho.f.close()
        if name=='gui_font.rho':replacements.update(korean_font_payloads())
        if replacements:files.append(patch_archive(source/name,out/'Data'/name,key,replacements))
        if len(files)%30==0 and replacements:print('Patched archives',len(files),'scanned BML',scanned,flush=True)
    root=game_index;by_name={x['file']:x for x in files}
    for e in root.iter('RhoFolder'):
        if e.get('fileName') in by_name:
            info=by_name[e.get('fileName')];e.set('mediaSize',str(info['media_size']));e.set('dataHash',str(info['data_hash']))
    raw=encode_xml(root);record=b'S\x01'+struct.pack('<II',zlib.adler32(raw,0),len(raw))+zlib.compress(raw,9)
    (out/'Data/aaa.pk').write_bytes(struct.pack('<I',len(record))+record)
    manifest=dict(source_index_sha256=hashlib.sha256(pk).hexdigest(),scanned_bml=scanned,
        archives=files,resources=records,translated_values=sum(x['translated'] for x in records),parse_errors=errors,
        scope='Existing Korean translations copied into Chinese-locale StringBag entries in legacy RHO; native Nanum bitmap and Korean Source Han Sans OTF fonts preserve font styles. RHO5 and image-baked text excluded.')
    (out/'korean-patch-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(BASE/'fonts/LICENSE.txt',out/'SourceHanSans-LICENSE.txt')
    print(json.dumps(dict(scanned=scanned,archives=len(files),resources=len(records),translated=manifest['translated_values'],parse_errors=len(errors))))

if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))
