import ujson as json
import os
from .log import logger
from .consts import *

def str_check(t):
    return t in {"String", "Template"}

def token_sift():
    for file in os.listdir(DIR_TOKENIZES):
        if not file.endswith(".json"):
            continue
        with open(DIR_TOKENIZES / f"{file}",mode="r",encoding="utf-8") as fp:
            token = json.loads(fp.read())
        token = [t for t in token if str_check(t['type'])]
        with open(DIR_NEWTOKENIZES / f"{file}",mode="w",encoding="utf-8") as fp:
            fp.write(json.dumps(token, ensure_ascii=False))
        logger.info(f"token {file} sift done!")

if __name__ == '__main__':
    token_sift()