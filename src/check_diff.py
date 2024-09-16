import shutil

from pathlib import Path
from typing import Dict, List, Union
from hashlib import md5

from .consts import DIR_TRANS, DIR_FETCH, DIR_DIFF

###################
# NOT FUNCTIONING
###################
def check_diff(
    old_path: Union[Path, str],
    new_path: Union[Path, str],
    diff_path: Union[Path, str],
):
    if isinstance(old_path, str):
        old_path = Path(old_path)

    if isinstance(new_path, str):
        new_path = Path(new_path)

    if isinstance(diff_path, str):
        diff_path = Path(diff_path)

    if diff_path.exists():
        shutil.rmtree(diff_path)

    diff_path.mkdir(parents=True, exist_ok=True)

    for file in new_path.glob("**/*.json"):
        old_file = old_path.joinpath(file.relative_to(new_path))
        diff_file = diff_path.joinpath(file.relative_to(new_path))
        if not old_file.exists():
            if not diff_file.parent.exists():
                diff_file.parent.mkdir(parents=True)
            shutil.copyfile(file, diff_file)
        else:
            with open(old_file, "r", encoding="utf-8") as f:
                text = f.read().encode("utf-8")
                if old_file.name.endswith(".tscn.json"):
                    text = text.replace(rb"\\n", rb"\n")
                old_md5 = md5(text).hexdigest()
            with open(file, "r", encoding="utf-8") as f:
                new_md5 = md5(f.read().encode("utf-8")).hexdigest()
            if old_md5 != new_md5:
                if not diff_file.parent.exists():
                    diff_file.parent.mkdir(parents=True)
                shutil.copyfile(file, diff_file)

if __name__ == "__main__":
    check_diff(DIR_FETCH, DIR_TRANS, DIR_DIFF)