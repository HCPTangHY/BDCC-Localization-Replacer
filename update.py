import json
from pathlib import Path
from typing import Dict, List

import shutil

new_path = Path("result")
result_path = Path("fill")
old_path = Path("pz")

if not result_path.exists():
    shutil.copytree(new_path, result_path, dirs_exist_ok=True)

for file in old_path.glob("**/*.json"):
    new_file = new_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))
    # print(new_file)
    # print(file)

    if not new_file.exists():
        print(file, "not exist")
        continue

    with open(file, "r", encoding="utf-8") as f:
        old_data = json.load(f)
    with open(new_file, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    old_data_map: Dict[str, List] = {}
    new_data_map: Dict[str, List] = {}

    for item in old_data:
        original = item["original"]
        # original = original.replace("return ", "")
        # item["translation"] = item["translation"].replace("return ", "")
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
            # print(original)
            pass
    
    result_file = result_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
