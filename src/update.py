import json
import shutil
from pathlib import Path
from typing import Dict, List, Union

from .log import logger
from .consts import DIR_TRANS, DIR_FETCH, DIR_DEPRECATED, DIR_CHANGE

def update_data(old_data: List, new_data: List) -> Union[List, List]:
    old_data_map: Dict[str, List] = {}
    new_data_map: Dict[str, List] = {}
    
    deprecated_data = []
    is_diff = False

    for item in old_data:
        original = item["original"]
        if '"' in original:
            original = original.strip(" ")
            item["translation"] = item["translation"].strip(" ")
        if original not in old_data_map:
            old_data_map[original] = []
        old_data_map[original].append(item)
    for item in new_data:
        original = item["original"]
        if original not in new_data_map:
            new_data_map[original] = []
        new_data_map[original].append(item)

    for original, items in old_data_map.items():
        valid_items = list(filter(lambda x: x["stage"] != 0 and len(x["translation"]) > 0, items))
        if original in new_data_map:
            new_items = new_data_map[original]
            if len(new_data_map[original]) != len(items):
                is_diff = True
                if len(valid_items) <= 0:
                    continue
                for idx, new_item in enumerate(new_items):
                    if idx >= len(valid_items):
                        idx = len(valid_items) - 1
                    new_item["translation"] = valid_items[idx]["translation"]
                    new_item["stage"] = 1
            else:
                for idx, item in enumerate(items):
                    new_items[idx]["translation"] = item["translation"]
                    new_items[idx]["stage"] = item["stage"]
        else:
            deprecated_data += valid_items
            is_diff = True
    
    return new_data, deprecated_data, is_diff

def update_deprecated(new_path: Union[Path, str], old_path: Union[Path, str], deprecated_path: Union[Path, str]):
    if isinstance(new_path, str):
        new_path = Path(new_path)

    if isinstance(old_path, str):
        old_path = Path(old_path)
    
    if isinstance(deprecated_path, str):
        deprecated_path = Path(deprecated_path)

    if deprecated_path.exists():
        shutil.rmtree(deprecated_path)
    deprecated_path.mkdir(parents=True, exist_ok=True)
    
    for file in old_path.glob("**/*.json"):
        if "过时" in file.as_posix():
            continue

        new_file = new_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))

        if not new_file.exists():
            logger.warning(f"{file} has no corresponding new dict file")
            continue

        with open(file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)

        new_data, deprecated_data, _ = update_data(old_data, new_data)
        
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        
        deprecated_file = deprecated_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))

        if len(deprecated_data) > 0:
            if not deprecated_file.parent.exists():
                deprecated_file.parent.mkdir(parents=True)
            with open(deprecated_file, "w", encoding="utf-8") as f:
                json.dump(deprecated_data, f, ensure_ascii=False, indent=2)

def update(new_path: Union[Path, str], old_path: Union[Path, str], deprecated_path: Union[Path, str], change_path: Union[Path, str]):
    if isinstance(new_path, str):
        new_path = Path(new_path)

    if isinstance(old_path, str):
        old_path = Path(old_path)
        
    if isinstance(deprecated_path, str):
        deprecated_path = Path(deprecated_path)
    
    if deprecated_path.exists():
        shutil.rmtree(deprecated_path)
    deprecated_path.mkdir(parents=True, exist_ok=True)
    
    for file in old_path.glob("**/*.json"):
        if "过时" in file.as_posix():
            continue

        new_file = new_path.joinpath(file.relative_to(old_path))

        if not new_file.exists():
            logger.warning(f"{file} has no corresponding new dict file")
            continue

        with open(file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)
        
        for item in old_data:
            item["original"] = item["original"].replace("\\n", "\n")
            item["translation"] = item["translation"].replace("\\n", "\n")

        new_data, deprecated_data, is_diff = update_data(old_data, new_data)

        # put original text for text with '_'
        for item in new_data:
            if item["translation"] == "" and "_" in item["original"] and "say=" not in item["original"]:
                item["translation"] = item["original"]
                item["stage"] = 1
                is_diff = True
        
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        
        deprecated_file = deprecated_path.joinpath(file.relative_to(old_path))
        change_file = change_path.joinpath(file.relative_to(old_path))
        
        if len(deprecated_data) > 0:
            if not deprecated_file.parent.exists():
                deprecated_file.parent.mkdir(parents=True)
            with open(deprecated_file, "w", encoding="utf-8") as f:
                json.dump(deprecated_data, f, ensure_ascii=False, indent=2)
        if is_diff:
            if not change_file.parent.exists():
                change_file.parent.mkdir(parents=True)
            shutil.copyfile(new_file, change_file)
        else:
            old_key_set = set(item["key"] for item in old_data)
            new_key_set = set(item["key"] for item in new_data)
            old_ori_set = set(item["original"] for item in old_data)
            new_ori_set = set(item["original"] for item in new_data)
            if old_key_set != new_key_set or old_ori_set != new_ori_set:
                if not change_file.parent.exists():
                    change_file.parent.mkdir(parents=True)
                shutil.copyfile(new_file, change_file)

if __name__ == "__main__":
    update(DIR_TRANS, DIR_FETCH, DIR_DEPRECATED, DIR_CHANGE)
