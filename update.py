import json
from pathlib import Path
from typing import Dict, List

new_path = Path("result")
result_path = Path("fill")
old_path = Path("pz")

result_path.mkdir(exist_ok=True)

for file in old_path.glob("**/*.json"):
    new_file = new_path.joinpath(file.relative_to(old_path).with_suffix(".gd.json"))
    print(new_file)
    print(file)

    if not new_file.exists():
        print(file, "not exist")
        continue

    with open(file, "r") as f:
        old_data = json.load(f)
    with open(new_file, "r") as f:
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
    total = 0
    match = 0

    for original, items in old_data_map.items():
        if original in new_data_map:
            match += len(items)
            new_items = new_data_map[original]
            if len(new_data_map[original]) != len(items):
                print(len(new_data_map[original]), len(items))
                for idx, new_item in enumerate(new_items):
                    if idx >= len(items):
                        idx = len(items) - 1
                    new_item["translation"] = items[idx]["translations"]
                    new_item["stage"] = 9
            else:
                for idx, item in enumerate(items):
                    new_items[idx]["translation"] = item["translation"]
                    new_items[idx]["stage"] = item["stage"]
        else:
            # print(original)
            pass
        total += len(items)
    print(match / total)
