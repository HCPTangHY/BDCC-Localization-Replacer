import ujson as json
import json5
import os,re,difflib
import shutil

from .consts import *
from .log import logger

class Replacer:
    def __init__(self,paratranzPath,BDCCSourcePath):
        self.paratranzPath = paratranzPath
        self.BDCCSourcePath = BDCCSourcePath
        self.translationDict = {}
        with open(ROOT.__str__()+"\\hash_index.json","r",encoding="utf-8") as fp:
            jsondata = json.loads(fp.read())
        self.hashIndex = jsondata

    def read_translation_files(self):
        translationDict = {}
        files = os.walk(DIR_TRANS)
        for root, dirs, file in files:
            for f in file:
                with open(f"{root}\{f}","r",encoding="utf-8") as fp:
                    jsondata = json.loads(fp.read())
                translationDict[root.replace(ROOT.__str__()+'\\','')+'\\'+f] = jsondata
                # logger.info(f"{root.replace(ROOT.__str__(),'')}\{f} readed")
        self.translationDict =translationDict

    def BDCC_replace(self):
        if DIR_OUTPUT.exists():
            shutil.rmtree(DIR_OUTPUT)
        os.makedirs(DIR_OUTPUT, exist_ok=True)
        files = os.walk(Path(self.BDCCSourcePath))
        for root, dirs, file in files:
            for d in dirs:
                if not os.path.exists(root.replace('source','output',1)+"\\"+d):
                    os.makedirs(root.replace('source','output',1)+"\\"+d)
            for f in file:
                filePath = root+"\\"+f
                if "DatapackMenu.gd" in f:continue
                if not (f.endswith(".gd") or f.endswith(".tscn")):
                    shutil.copyfile(filePath, filePath.replace('source','output',1))
                    continue
                with open(filePath,"r",encoding="utf-8") as fp:
                    flines = fp.readlines()
                if (filePath.replace('source','trans',1).replace(".gd",".json") not in self.translationDict.keys()):
                    # logger.error(root.replace('source','trans',1)+"\\"+f.replace(".gd",".json")+" not in trans file")
                    shutil.copyfile(root+"\\"+f, root.replace('source','output',1)+"\\"+f)
                    continue
                fileHashIndex = self.hashIndex[filePath.replace(ROOT.__str__(),"").replace("source\\","",1)]
                transDict = self.translationDict[filePath.replace('source','trans',1).replace(".gd",".json")]
                for i in range(len(transDict)):
                    index = int(transDict[i]['key'].split("_")[-1])
                    hash = list(fileHashIndex['Indexes'].keys())[list(fileHashIndex['Indexes'].values()).index(index)]
                    tokenPostion = fileHashIndex["TokenPostion"][hash][0]
                    translation = transDict[i]['translation'] if transDict[i]['translation']!= "" else transDict[i]['original']
                    context = transDict[i]['context'] if 'context' in transDict[i] else transDict[i]['original']
                    targetLine = []
                    lineIndex = tokenPostion["StartLine"]
                    if lineIndex>=len(flines):lineIndex-=1
                    if context not in flines[lineIndex]:
                        if context in flines[min(lineIndex+1,len(flines)-1)]:lineIndex=min(lineIndex+1,len(flines)-1)
                        else:
                            if context in flines[lineIndex-1]:lineIndex-=1
                    try:
                        targetLine.append(flines[lineIndex][:tokenPostion["StartColumn"]])
                        targetLine.append(translation.replace("\\n","\\\\n"))
                        targetLine.append(flines[lineIndex][tokenPostion["EndColumn"]:])
                        flines[lineIndex] = "".join(targetLine)
                    except:
                        logger.error(f"{f},{index}")
                with open(root.replace('source','output',1)+"\\"+f, "w", encoding="utf-8") as fp:
                    fp.write("".join(flines))
                # logger.info(root.replace('\source','\output',1)+"\\"+f+" output filled")

if __name__ == '__main__':
    pass
