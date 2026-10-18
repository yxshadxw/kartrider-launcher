from pathlib import Path
import collections, hashlib, json, struct, sys, zlib
from decode_pk import Reader
from read_rho import Rho
from korean_resources import encode_xml, patch_archive, read_game_index, translate_tree
from native_font import font_tree, native_font_payloads
BASE = Path(__file__).resolve().parent
IMAGES = json.loads((BASE / "image-replacements.json").read_text(encoding="utf-8"))
IMAGE_MAP = collections.defaultdict(list)
for row in IMAGES: IMAGE_MAP[row["archive"]].append(row)
def patch(data_dir, output_dir):
    data_dir=Path(data_dir).resolve(); output_dir=Path(output_dir).resolve()
    if not (data_dir/"aaa.pk").is_file(): raise FileNotFoundError(f"Data/aaa.pk not found: {data_dir}")
    if output_dir.exists(): raise FileExistsError(f"Output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    root, rows, pk=read_game_index(data_dir/"aaa.pk")
    archives=[]; resource_rows=[]; errors=[]
    for name,key in rows:
        src=data_dir/name
        if not src.is_file(): continue
        rho=Rho(src,key); replacements={}
        try:
            entries={e["path"]:e for e in rho.entries}
            for e in rho.entries:
                if e["extension"].lower()!="bml": continue
                try:
                    payload=rho.content(e); reader=Reader(payload); tree=reader.node()
                    if reader.p!=len(payload): raise ValueError("Trailing binary XML bytes")
                    count=translate_tree(tree)
                    font=(name=="gui_font.rho" and e["path"].startswith("font@") and e["path"].endswith(".bml"))
                    if font:
                        tree=font_tree()
                    if count or font:
                        replacements[e["path"]]=encode_xml(tree)
                        resource_rows.append({"archive":name,"member":e["path"],"translated_values":count,"font_patch":bool(font)})
                except (ValueError,UnicodeError,struct.error,zlib.error) as ex:
                    errors.append({"archive":name,"member":e["path"],"error":str(ex)})
            for row in IMAGE_MAP.get(name,[]):
                target=entries.get(row["target"]); source=entries.get(row["source"])
                if target is None or source is None: raise ValueError(f"Image pair missing: {name}:{row['target']}")
                replacements[row["target"]]=rho.content(source)
            if name=="gui_font.rho": replacements.update(native_font_payloads(rho))
        finally: rho.f.close()
        if replacements: archives.append(patch_archive(src,output_dir/name,key,replacements))
    by_name={a["file"]:a for a in archives}
    for e in root.iter("RhoFolder"):
        info=by_name.get(e.get("fileName"))
        if info: e.set("mediaSize",str(info["media_size"]));e.set("dataHash",str(info["data_hash"]))
    raw=encode_xml(root)
    packed=b"S\x01"+struct.pack("<II",zlib.adler32(raw,0),len(raw))+zlib.compress(raw,9)
    (output_dir/"aaa.pk").write_bytes(struct.pack("<I",len(packed))+packed)
    manifest={"source_index_sha256":hashlib.sha256(pk).hexdigest(),"archives":archives,"resources":resource_rows,
              "image_replacements":len(IMAGES),"translated_values":sum(x["translated_values"] for x in resource_rows),"parse_errors":errors}
    (output_dir/"translation-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest
def main():
    if len(sys.argv)!=3: raise SystemExit("Usage: python apply_korean_patch.py <game Data folder> <output folder>")
    result=patch(Path(sys.argv[1]),Path(sys.argv[2]))
    print(json.dumps({"archives_repacked":len(result["archives"]),"translated_values":result["translated_values"],
                      "localized_images":result["image_replacements"],"output":str(Path(sys.argv[2]).resolve())},ensure_ascii=False))
if __name__=="__main__": main()
