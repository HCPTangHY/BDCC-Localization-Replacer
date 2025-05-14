from pathlib import Path
from typing import Dict, Tuple, Union
from .log import logger

from gdtoolkit.linter import lint_code
from lark.exceptions import UnexpectedInput

def lint_check(output_path: Union[Path, str]):
    if isinstance(output_path, str):
        output_path = Path(output_path)

    is_error = False
    for file in output_path.glob("**/*.gd"):
        with open(file, "r", encoding="utf-8") as f:
            code = f.read()

        try:
            lint_code(code)
        except UnexpectedInput as e:
            is_error = True
            logger.error(f"{file}\nContext:\n{e.get_context(code)}\nparse error: {e}")

    if is_error:
        raise Exception("parse error")
    else:
        logger.info("parse success")

if __name__ == "__main__":
    pass
