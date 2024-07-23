import ujson as json
import os
from .log import logger
from .consts import *

def strip():
    for file in os.listdir(DIR_TRANS):
        if not file.endswith(".json"):
            continue
        with open(DIR_TRANS / f"{file}",mode="r",encoding="utf-8") as fp:
            trans = json.loads(fp.read())
        for i in range(len(trans)):
            if trans[i]["original"]=="":
                trans[i]["original"]="\"\""
                trans[i]["translation"]="\"\""
                trans[i]["stage"]=1
                continue
            if trans[i]["original"]=="\"\"":continue
            if trans[i]["translation"]=="":continue
            if trans[i]["original"][0]=="\"":
                trans[i]["original"] = trans[i]["original"].strip("\"")
                trans[i]["translation"] = trans[i]["translation"].strip("\"")
                trans[i]["stage"]=1;continue
            if trans[i]["original"][0]=="'":
                trans[i]["original"] = trans[i]["original"].strip("'")
                trans[i]["translation"] = trans[i]["translation"].strip("'")
                trans[i]["stage"]=1;continue
            if trans[i]["original"][0]=="`":
                trans[i]["original"] = trans[i]["original"].strip("`")
                trans[i]["translation"] = trans[i]["translation"].strip("`")
                trans[i]["stage"]=1;continue
            trans[i]["stage"]=1
        with open(DIR_TRANS / f"{file}",mode="w",encoding="utf-8") as fp:
            fp.write(json.dumps(trans, ensure_ascii=False))
        logger.info(f"{file} strip done!")

if __name__ == '__main__':
    strip()