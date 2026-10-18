"""Build an English text patch and native bitmap-font repair from a local install."""
from pathlib import Path
import collections, hashlib, json, re, struct, sys, unicodedata, zlib
from unidecode import unidecode

from decode_pk import Reader
from read_rho import Rho
from korean_resources import encode_xml, patch_archive, read_game_index
from native_font import font_tree, native_font_payloads

BASE = Path(__file__).resolve().parent
DISPLAY_KEYS = set("text altText caption stateText value title msg characterName script passMsg EventString challenge userWin userLose retireChallenge retireUserWin retireUserLose motto desc mission missionText rewardMsg subTitle synopsis howToClear prize restrictionMsg string v careerDesc helpString stockCardName mixName q message dialogCaption dialogDesc stockDesc additionalDesc tabTitle seasonTitle baseNotice completeNotice labelText rewardMessage idealType info noticeString cc story skillName skillDesc eventMsg alarmMsgFormat missionTitle addDesc kartString resultMsg missionDesc npcName".split())
NAME_TAGS = {"TierMatching", "gp", "emblem", "mixEntity", "Level", "AiRider", "Tune", "Item", "F1Rider", "rid", "comboItem", "pcCafeBenefit", "exceedType", "Event", "color", "aura"}
MULTI_NAME_TAGS = {"track", "track_crz", "track_rvs", "challenge", "item"}
CJK = re.compile(r"[\u3000-\u9fff\uac00-\ud7af]")
PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[diuoxXfFeEgGaAcsp]|\{\d+(?:[^{}]*)\}")


def load_cache():
    cache = {}
    for line in (BASE / "translations.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            source, target = json.loads(line)
            cache[source] = target
    cache.update(json.loads((BASE / "known.json").read_text(encoding="utf-8")))
    cache.update(json.loads((BASE / "manual.json").read_text(encoding="utf-8")))
    return cache


def clean(value, source=""):
    value = unicodedata.normalize("NFKC", value)
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": "'", "\u201d": "'",
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00d7": "x",
        "\u00f7": "/", "\u2022": "*", "\u203b": "*", "\u2192": "to",
        "\u2190": "back", "\u25b6": ">", "\u25c0": "<", "\u2605": "*",
        "\u2606": "*", "\u300c": "'", "\u300d": "'", "\u300e": "'",
        "\u300f": "'", "\u3001": ",", "\u3002": ".", "\u3010": "[",
        "\u3011": "]", "\u00a0": " ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = unidecode(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.replace('"', "'").replace("&", "and").replace("<", "(").replace(">", ")")
    value = re.sub(r"\b(?:preserved eggs?|Piedan|Pidan)\b", "Dao", value, flags=re.I)
    if "\uc5e0\ube14\ub7fc" in source or "\uc5e0\ube14\ub818" in source:
        value = re.sub(r"\b(?:mblr|mblum|mbrum|mumbler(?:um)?|mbblerum|embrow|emberlum|embow|emma)\b", "Emblem", value, flags=re.I)
    if "\uce74\ud2b8" in source or "\uce74\ud2b8\ub77c\uc774\ub354" in source:
        value = re.sub(r"\bcartrider\b|\bcart rider\b", "KartRider", value, flags=re.I)
        value = re.sub(r"\bcartridges?\b", "kart", value, flags=re.I)
    # Prevent literal percentages such as "100% chance" from resembling a printf token.
    value = re.sub(r"(?<=\d)%\s+(?=[A-Za-z])", " percent ", value)
    return value


def english(source, cache):
    if source not in cache:
        if CJK.search(source):
            raise ValueError(f"Missing English translation: {source[:180]!r}")
        return clean(source, source)
    target = clean(cache[source], source)
    if re.search(r"\.top\b|swarovski|florence-hotels|www\.hide\.com", target, re.I):
        raise ValueError(f"Suspicious translated content for: {source[:180]!r}")
    # The source-side placeholders are authoritative; percentages are normalized above.
    if collections.Counter(PLACEHOLDER.findall(source)) != collections.Counter(PLACEHOLDER.findall(target)):
        raise ValueError(f"Placeholder mismatch for: {source[:180]!r} -> {target[:180]!r}")
    return target


def should_translate(element, key, member):
    if key == "name":
        return element.tag == "Msg" or ("locale" in member.lower() and element.tag in MULTI_NAME_TAGS) or element.tag in NAME_TAGS
    if key == "str":
        return element.tag in ("emo", "macroChat")
    return key in DISPLAY_KEYS


def translate_tree(root, member, cache):
    changed = 0
    for parent in root.iter():
        localized = [child for child in parent if child.tag == "m" and "c" in child.attrib and "v" in child.attrib]
        if localized:
            source = next((child.get("v") for locale in ("cn", "kr", "tw", "jp") for child in localized if child.get("c") == locale and child.get("v")), None)
            if source is None:
                source = next((child.get("v") for child in localized if child.get("v")), None)
            if source:
                target = english(source, cache)
                for child in localized:
                    if child.get("v") != target:
                        child.set("v", target)
                        changed += 1
        for key, value in list(parent.attrib.items()) + [("#text", parent.text or "")]:
            if parent.tag == "m" and key == "v" and "c" in parent.attrib:
                continue
            if not value or not CJK.search(value) or not should_translate(parent, key, member):
                continue
            target = english(value, cache)
            if key == "#text":
                parent.text = target
            else:
                parent.set(key, target)
            changed += 1
    return changed


def patch(data_dir, output_dir):
    data_dir = Path(data_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if not (data_dir / "aaa.pk").is_file():
        raise FileNotFoundError(f"Data/aaa.pk not found: {data_dir}")
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    cache = load_cache()
    root, rows, pk = read_game_index(data_dir / "aaa.pk")
    archives, resources, errors = [], [], []
    for name, key in rows:
        source_path = data_dir / name
        if not source_path.is_file():
            continue
        rho = Rho(source_path, key)
        replacements = {}
        try:
            for entry in rho.entries:
                if entry["extension"].lower() != "bml":
                    continue
                try:
                    payload = rho.content(entry)
                    reader = Reader(payload)
                    tree = reader.node()
                    if reader.p != len(payload):
                        raise ValueError("Trailing binary XML bytes")
                    changed = translate_tree(tree, entry["path"], cache)
                    font = name == "gui_font.rho" and entry["path"].startswith("font@") and entry["path"].endswith(".bml")
                    if font:
                        tree = font_tree()
                    if changed or font:
                        replacements[entry["path"]] = encode_xml(tree)
                        resources.append({"archive": name, "member": entry["path"], "translated_values": changed, "font_patch": bool(font)})
                except (ValueError, UnicodeError, struct.error, zlib.error) as error:
                    errors.append({"archive": name, "member": entry["path"], "error": str(error)})
            if name == "gui_font.rho":
                replacements.update(native_font_payloads(rho))
        finally:
            rho.f.close()
        if replacements:
            archives.append(patch_archive(source_path, output_dir / name, key, replacements))
    if errors:
        raise RuntimeError(f"Could not safely translate {len(errors)} BML resources; no patch package was completed.")
    by_name = {archive["file"]: archive for archive in archives}
    for row in root.iter("RhoFolder"):
        info = by_name.get(row.get("fileName"))
        if info:
            row.set("mediaSize", str(info["media_size"]))
            row.set("dataHash", str(info["data_hash"]))
    raw = encode_xml(root)
    record = b"S\x01" + struct.pack("<II", zlib.adler32(raw, 0), len(raw)) + zlib.compress(raw, 9)
    (output_dir / "aaa.pk").write_bytes(struct.pack("<I", len(record)) + record)

    manifest = {
        "source_index_sha256": hashlib.sha256(pk).hexdigest(),
        "legacy_archives_repacked": len(archives),
        "resources": resources,
        "translated_values": sum(item["translated_values"] for item in resources),
        "native_bitmap_font": True,
        "parse_errors": errors,
        "scope": "English UI and data text in local legacy RHO files, including native bitmap font conversion. RHO5 packs and image-baked text are unchanged.",
    }
    (output_dir / "english-patch-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python apply_english_patch.py <game Data folder> <new output folder>")
    result = patch(sys.argv[1], sys.argv[2])
    print(json.dumps({"legacy_archives": result["legacy_archives_repacked"],
                      "translated_values": result["translated_values"],
                      "native_bitmap_font": result["native_bitmap_font"], "output": str(Path(sys.argv[2]).resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
