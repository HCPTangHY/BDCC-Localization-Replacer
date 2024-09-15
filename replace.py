import json

from pathlib import Path
from ast import literal_eval

trans_path = Path("fill")
target_path = Path("../BDCC")

for file in trans_path.glob("**/*.json"):
    target_file = target_path.joinpath(file.relative_to(trans_path)).with_suffix("")
    with open(file, "r", encoding="utf-8") as f:
        trans_data = json.load(f)
    
    if target_file.suffix == ".gd":
        with open(target_file, "r", encoding="utf-8") as f:
            # read code as a string
            gd_code = f.read()
        new_code = ""
        prev_end = 0
        for item in trans_data:
            line = literal_eval(item["key"])
            start = line[0]
            end = line[1]
            if "translation" not in item:
                new_code += gd_code[prev_end:end]
            else:
                translation = item["translation"]
                new_code += gd_code[prev_end:start] + translation
            prev_end = end
        new_code += gd_code[prev_end:]
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(new_code)
    elif target_file.suffix == ".tscn":
        with open(target_file, "r", encoding="utf-8") as f:
            tscn_code = f.readlines()
        for item in trans_data:
            if "translation" not in item:
                continue
            line = int(item["key"])
            translation = item["translation"]
            tscn_code[line] = translation
        with open(target_file, "w", encoding="utf-8") as f:
            f.writelines(tscn_code)
    else:
        raise ValueError
    

