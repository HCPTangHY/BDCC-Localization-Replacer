import ujson as json
import json5
import os,re,difflib
import shutil

from .consts import *
from .log import logger

def replace_main():
    if DIR_OUTPUT.exists():
        shutil.rmtree(DIR_OUTPUT)
    os.makedirs(DIR_OUTPUT, exist_ok=True)

    translation_files = {}
    files = os.walk(DIR_TRANS)
    for root, dirs, file in files:
        for d in dirs:
            if not os.path.exists(root.replace('\\trans','\output')+"\\"+d):
                os.makedirs(root.replace('\\trans','\output')+"\\"+d)
        for f in file:
            with open(f"{root}\{f}","r",encoding="utf-8") as fp:
                jsondata = json.loads(fp.read())
            translation_files[f"{root}\{f}"] = jsondata
            # logger.info(f"{root}\{f} readed")
    files = os.walk(DIR_SOURCE)
    for root, dirs, file in files:
        for d in dirs:
            if not os.path.exists(root.replace('\source','\output')+"\\"+d):
                os.makedirs(root.replace('\source','\output')+"\\"+d)
        for f in file:
            if not (f.endswith(".gd") or f.endswith(".tscn")):
                shutil.copyfile(root+"\\"+f, root.replace('\source','\output')+"\\"+f)
                continue
            with open(f"{root}\{f}","r",encoding="utf-8") as fp:
                flines = fp.readlines()
            if (root.replace('\source','\\trans')+"\\"+f.replace(".gd",".json") not in translation_files):
                logger.error(root.replace('\source','\\trans')+"\\"+f.replace(".gd",".json")+" not in trans file")
                shutil.copyfile(root+"\\"+f, root.replace('\source','\output')+"\\"+f)
                continue
            transFile = translation_files[root.replace('\source','\\trans')+"\\"+f.replace(".gd",".json")]
            newlines = []
            for l in flines:
                if re.search(r'"([^"]*)"',l):
                    replaceTag = False
                    for i in range(len(transFile)):
                        if transFile[i]['original'] in l:
                            translation = transFile[i]['translation'] if transFile[i]['translation']!= "" else transFile[i]['original']
                            context = transFile[i]['context'] if 'context' in transFile[i] else transFile[i]['original']
                            if difflib.SequenceMatcher(None,l,context).ratio()>=0.7 and len(translation)>3:
                                newl = l.replace(transFile[i]['original'],translation).replace("​","")
                                replaceTag = True
                                newlines.append(newl)
                                transFile.pop(i)
                            else:
                                newl = l.replace(f"\"{transFile[i]['original']}\"",f"\"{translation}\"").replace("​","")
                                replaceTag = True
                                newlines.append(newl)
                                transFile.pop(i)
                            break
                    if not replaceTag:
                        newlines.append(l)
                else:
                    newlines.append(l)
            with open(root.replace('\source','\output')+"\\"+f, "w", encoding="utf-8") as fp:
                fp.write("".join(newlines))
            # logger.info(root.replace('\source','\output')+"\\"+f+" output filled")

if __name__ == '__main__':
    replace_main()
