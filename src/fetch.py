import esprima
import ujson as json
import json5
import os
import shutil
import asyncio

from .consts import *
from .log import logger

async def tokenize():
    if DIR_FETCH.exists():
        shutil.rmtree(DIR_FETCH)
    os.makedirs(DIR_FETCH, exist_ok=True)
    os.makedirs(DIR_TOKENIZES, exist_ok=True)

    datas = {}
    tasks = set()
    for file in os.listdir(DIR_SOURCE):
        if not file.endswith(".js"):
            continue

        filename = file[:-3]  # remove '.js'
        logger.info(f"Reading {filename} ...")
        with open(DIR_SOURCE / f"{filename}.js", "r", encoding="utf-8") as fp:
            content = fp.read()

        # 异步
        tasks.add(_tokenize(filename, content, datas))

    await asyncio.gather(*tasks)
    return datas


async def _tokenize(filename: str, content: str, datas: dict):
    """异步用"""
    if not (DIR_TOKENIZES / f"{filename}.json").exists():
        tokens = esprima.tokenize(content, {"range": True})
        data = json5.loads(tokens.__str__().replace("False", "false").replace("True", "true"))

        with open(DIR_TOKENIZES / f"{filename}.json", "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False)
        logger.info(f"Tokenized {filename} written successfully!")

    else:
        with open(DIR_TOKENIZES / f"{filename}.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)
        logger.info(f"Tokenized {filename} read successfully!")
    datas[filename] = data


async def fetch(datas: dict):
    for filename, data in datas.items():
        result = []
        idx = 0
        for d in data:
            if d["type"] not in {"String", "Template"}:
                continue

            idx += 1
            result.append({
                "key": f"{filename}_{idx}",
                "original": d["value"],
                "translation": ""
            })

        with open(DIR_FETCH / f"{filename}.json", "w", encoding="utf-8") as fp:
            json.dump(result, fp, ensure_ascii=False)
        logger.info(f"Fetched {filename} successfully!")


if __name__ == '__main__':
    datas = asyncio.run(tokenize())
    asyncio.run(fetch(datas))
