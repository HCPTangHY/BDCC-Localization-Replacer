from pathlib import Path
from typing import Dict, Tuple, Union
from .log import logger

from gdtoolkit.parser import parser

def parser_check(output_path: Union[Path, str]):
    if isinstance(output_path, str):
        output_path = Path(output_path)

        is_error = False
        for file in output_path.glob("**/*.gd"):
            with open(file, "r", encoding="utf-8") as f:
                code = f.read()

            try:
                parser.parse(code)
            except Exception as e:
                is_error = True
                logger.error(f"{file} parse error: {e}")

        if is_error:
            raise Exception("parse error")
        else:
            logger.info("parse success")
