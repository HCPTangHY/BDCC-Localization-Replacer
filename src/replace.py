import json
import shutil
import re

from pathlib import Path
from ast import literal_eval
from typing import Union

from .consts import ROOT, DIR_SOURCE, DIR_TRANS, DIR_OUTPUT
from .log import logger

BOLD_RE = re.compile(r"custom_fonts/bold_font = (.*)")
BOLD_ITALIC_RE = re.compile(r"(custom_fonts/bold_italics_font = ).*")
REGULAR_ITALIC_RE = re.compile(r"(custom_fonts/italics_font = ).*")

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

        if not source_file.exists():
            logger.warning(f"{file} not exist")

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
                if item["stage"] == 0 or item["translation"] == "":
                    new_code += gd_code[prev_end:end]
                else:
                    translation = item["translation"]
                    translation = translation.replace("__NEWLINE__", "\\n")
                    new_code += gd_code[prev_end:start] + translation
                prev_end = end
            new_code += gd_code[prev_end:]
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(new_code)
        elif source_file.suffix == ".tscn":
            with open(source_file, "r", encoding="utf-8") as f:
                tscn_code = f.readlines()
            new_tscn_code = []
            prev_end = 0
            for item in trans_data:
                line = literal_eval(item["key"])
                start = line[0]
                end = line[1] + 1
                if item["stage"] == 0 or item["translation"] == "":
                    new_tscn_code.extend(tscn_code[prev_end: end])
                else:
                    translation = item["translation"].replace("\\n", "\n")
                    new_tscn_code.extend(tscn_code[prev_end: start])
                    new_tscn_code.append(translation)
                prev_end = end
            new_tscn_code.extend(tscn_code[prev_end:])
            
            new_tscn_code = "".join(new_tscn_code)

            # the italic Chinese charactes do not display in Godot 3.5
            if source_file.stem == "GameUI":
                # get bold font
                bold_font = re.search(BOLD_RE, new_tscn_code)
                # replace bold_italic and regular_italic with bold_font
                new_tscn_code = re.sub(BOLD_ITALIC_RE, rf"\g<1>{bold_font.group(1)}", new_tscn_code)
                new_tscn_code = re.sub(REGULAR_ITALIC_RE, rf"\g<1>{bold_font.group(1)}", new_tscn_code)

            with open(output_file, "w", encoding="utf-8") as f:
                f.writelines(new_tscn_code)
        else:
            raise ValueError

if __name__ == '__main__':
    replace_translation(DIR_SOURCE, DIR_TRANS, DIR_OUTPUT)
