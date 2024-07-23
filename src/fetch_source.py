import ujson as json
import os,re,shutil
from .log import logger
from .consts import *

def fetch():
    shutil.rmtree(".\\fetchoutput")
    files = os.walk(DIR_SOURCE)
    for root, dirs, file in files:
        for d in dirs:
            if not os.path.exists(root.replace('\source','\\fetchoutput')+"\\"+d):
                os.makedirs(root.replace('\source','\\fetchoutput')+"\\"+d)
        for f in file:
            out = []
            with open(f"{root}\{f}","r",encoding="utf-8") as fp:
                jsondata = json.loads(fp.read())
            for jd in jsondata:
                sour = jd['original']
                ori = re.findall(r'"([^"]*)"',sour)
                if len(ori)==0:
                    outjd = jd.copy()
                    outjd['original'] = sour
                    out.append(outjd)
                elif len(ori)==1:
                    outjd = jd.copy()
                    if ('\" +'in sour) or ('\"+' in sour) or ('+\"' in sour) or ('+ \"' in sour) :
                        outjd['original'] = sour
                    else:
                        outjd['original'] = ori[0]
                        outjd["context"] = sour
                    out.append(outjd)
                else:
                    idx=0
                    if ('" +'in sour) or ('"+' in sour) or ('+"' in sour) or ('+ "' in sour) :
                        outjd = jd.copy()
                        outjd['original'] = sour
                        out.append(outjd)
                        continue
                    for split in ori:
                        outjd = jd.copy()
                        outjd["key"] = f"{jd['key']}_{idx}"
                        outjd["original"] = split
                        outjd["context"] = sour
                        out.append(outjd)
                        idx+=1
            with open(root.replace('\source','\\fetchoutput')+"\\"+f, "w", encoding="utf-8") as fp:
                json.dump(out, fp, ensure_ascii=False)




if __name__ == '__main__':
    fetch()