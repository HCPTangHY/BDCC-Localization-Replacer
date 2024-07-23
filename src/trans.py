import ujson as json
import os,shutil
from .log import logger
from .consts import *


def trans_main():
    allFile = {}
    shutil.rmtree(".\\transoutput")
    files = os.walk(DIR_TRANS)
    for root, dirs, file in files:
        for d in dirs:
            if not os.path.exists(root.replace('\\trans','\\transoutput')+"\\"+d):
                os.makedirs(root.replace('\\trans','\\transoutput')+"\\"+d)
        for f in file:
            with open(f"{root}\{f}","r",encoding="utf-8") as fp:
                jsondata = json.loads(fp.read())
            allFile[f"{root}\{f}"] = jsondata
            logger.info(f"{root}\{f} readed")
    files = os.walk(DIR_SOURCE)
    for root, dirs, file in files:
        for d in dirs:
            if not os.path.exists(root.replace('\source','\\transoutput')+"\\"+d):
                os.makedirs(root.replace('\source','\\transoutput')+"\\"+d)
        for f in file:
            with open(f"{root}\{f}","r",encoding="utf-8") as fp:
                jsondata = json.loads(fp.read())
            if root.replace('\source','\\trans')+"\\"+f not in allFile:
                logger.error(root.replace('\source','\\trans')+"\\"+f+" not include")
                with open(root.replace('\source','\\transoutput')+"\\"+f, "w", encoding="utf-8") as fp:
                    json.dump(jsondata, fp, ensure_ascii=False)
                continue
            transFile = allFile[root.replace('\source','\\trans')+"\\"+f]
            for i in range(len(jsondata)):
                source = jsondata[i]['original']
                for j in range(len(transFile)):
                    if source == transFile[j]['original']:
                        jsondata[i]['translation'] = transFile[j]["translation"]
                        if jsondata[i]['translation']!= "" :jsondata[i]["stage"] = 1
            logger.info(root.replace('\source','\\trans')+"\\"+f+" trans filled")
            with open(root.replace('\source','\\transoutput')+"\\"+f, "w", encoding="utf-8") as fp:
                json.dump(jsondata, fp, ensure_ascii=False)


if __name__ == '__main__':
    trans_main()