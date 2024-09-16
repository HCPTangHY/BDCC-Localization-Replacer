import json
import shutil
from pathlib import Path
from typing import Dict, List, Union

from .log import logger

def update_data(old_data: List, new_data: List) -> Union[List, List]:
    old_data_map: Dict[str, List] = {}
    new_data_map: Dict[str, List] = {}
    
    deprecated_data = []

    for item in old_data:
        original = item["original"]
        if '"' in original:
            original = original.strip()
            item["translation"] = item["translation"].strip()
        if original not in old_data_map:
            old_data_map[original] = []
        old_data_map[original].append(item)
    for item in new_data:
        original = item["original"]
        if original not in new_data_map:
            new_data_map[original] = []
        new_data_map[original].append(item)

    for original, items in old_data_map.items():
        valid_items = list(filter(lambda x: x["stage"] == 1 or x["stage"] == 2, items))
        if original in new_data_map:
            new_items = new_data_map[original]
            if len(valid_items) <= 0:
                continue
            elif len(new_data_map[original]) != len(valid_items):
                for idx, new_item in enumerate(new_items):
                    if idx >= len(valid_items):
                        idx = len(valid_items) - 1
                    new_item["translation"] = valid_items[idx]["translation"]
                    new_item["stage"] = 2 # questionable
            else:
                for idx, item in enumerate(valid_items):
                    new_items[idx]["translation"] = item["translation"]
                    new_items[idx]["stage"] = item["stage"]
        else:
            deprecated_data += valid_items
    
    return new_data, deprecated_data

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
        if "deprecated" in file.as_posix():
            continue

        new_file = new_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))

        if not new_file.exists():
            logger.warning(f"{file} has no corresponding new dict file")
            continue

        with open(file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)

        new_data, deprecated_data = update_data(old_data, new_data)
        
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        
        deprecated_file = deprecated_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))
        if not deprecated_file.parent.exists():
            deprecated_file.parent.mkdir(parents=True)

        if len(deprecated_data) > 0:
            with open(deprecated_file, "w", encoding="utf-8") as f:
                json.dump(deprecated_data, f, ensure_ascii=False, indent=2)

def update(new_path: Union[Path, str], old_path: Union[Path, str], deprecated_path: Union[Path, str]):
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
        if "deprecated" in file.as_posix():
            continue

        new_file = new_path.joinpath(file.relative_to(old_path))

        if not new_file.exists():
            logger.warning(f"{file} has no corresponding new dict file")
            continue

        with open(file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)

        new_data, deprecated_data = update_data(old_data, new_data)
        
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        
        deprecated_file = deprecated_path.joinpath(file.relative_to(old_path))
        if not deprecated_file.parent.exists():
            deprecated_file.parent.mkdir(parents=True)
        
        if len(deprecated_data) > 0:
            with open(deprecated_file, "w", encoding="utf-8") as f:
                json.dump(deprecated_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    new_path = Path("result")
    result_path = Path("fill")
    old_path = Path("pz")
    
    update_deprecated(new_path, result_path, old_path)
