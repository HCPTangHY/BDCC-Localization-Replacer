import json
import shutil

from pathlib import Path
from ast import literal_eval
from typing import Union

from .consts import ROOT

def replace_translation(source_path: Union[Path, str], translation_path: Union[Path, str], output_path: Union[Path, str]):
    if isinstance(source_path, str):
        source_path = Path(source_path)

    if isinstance(translation_path, str):
        translation_path = Path(translation_path)
    
    if isinstance(output_path, str):
        output_path = Path(output_path)
    
    if output_path.exists():
        shutil.rmtree(output_path)
    
    shutil.copytree(source_path, output_path)
    
    shutil.copyfile(ROOT / "SourceHanSansCN-Regular.otf", output_path / "Fonts" / "Titillium-Regular.otf")
    shutil.copyfile(ROOT / "SourceHanSansCN-Bold.otf", output_path / "Fonts" / "Titillium-Bold.otf")

    for file in translation_path.glob("**/*.json"):
        source_file = source_path.joinpath(file.relative_to(translation_path)).with_suffix("")
        output_file = output_path.joinpath(file.relative_to(translation_path)).with_suffix("")
        with open(file, "r", encoding="utf-8") as f:
            trans_data = json.load(f)
        
        if source_file.suffix == ".gd":
            with open(source_file, "r", encoding="utf-8") as f:
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
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(new_code)
        elif source_file.suffix == ".tscn":
            with open(source_file, "r", encoding="utf-8") as f:
                tscn_code = f.readlines()
            for item in trans_data:
                if "translation" not in item:
                    continue
                line = int(item["key"])
                translation = item["translation"]
                tscn_code[line] = translation
            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(tscn_code)
        else:
            raise ValueError

if __name__ == '__main__':
    translation_path = Path("fill")
    source_path = Path("../BDCC")

    replace_translation(source_path, translation_path)
