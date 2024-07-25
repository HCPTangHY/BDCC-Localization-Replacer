import ujson as json
import os
import shutil
from .consts import *
from .log import logger


class Replacer:
    def __init__(self):
        logger.info("Replacer init")
        self.paratranzPath = f"{DIR_TRANS}"
        self.BDCCSourcePath = f"{DIR_SOURCE}"
        self.translationDict = {}
        logger.info(f"Replacer read translate path {self.paratranzPath}")
        logger.info(f"Replacer read BDCC path {self.BDCCSourcePath}")
        logger.info("Replacer read hash_index.json")
        with open(f"{ROOT}\\hash_index.json", "r", encoding="utf-8") as fp:
            self.hashIndex = json.load(fp)
        logger.info("Replacer init done")

    def read_translation_files(self):
        logger.info("Replacer read translation files")
        translation_dict = {}
        root_path = f"{ROOT}"
        for root, _, files in os.walk(DIR_TRANS):
            for file in files:
                with open(f"{root}\\{file}", "r", encoding="utf-8") as fp:
                    logger.info(f"Replacer read {root}\\{file}")
                    # filepath = f"{root.replace(root_path, '')}"
                    # logger.info(f"Replacer read {filepath}\\{file}")
                    key = f"{root}\\{file}"
                    translation_dict[key] = json.load(fp)
                    # logger.info(f"translation: {translation_dict[key]}")
        self.translationDict = translation_dict
        logger.info("Replacer read translation files done")

    def BDCC_replace(self):
        logger.info("Replacer BDCC replace")
        if DIR_OUTPUT.exists():
            shutil.rmtree(DIR_OUTPUT)
        os.makedirs(DIR_OUTPUT, exist_ok=True)
        for root, dirs, files in os.walk(self.BDCCSourcePath):
            for d in dirs:
                os.makedirs(root.replace('source', 'output', 1) + "\\" + d, exist_ok=True)
            for f in files:
                file_path = f"{root}\\{f}"
                output_path = file_path.replace('source', 'output', 1)
                if "DatapackMenu.gd" in f or not (f.endswith(".gd") or f.endswith(".tscn")):
                    shutil.copyfile(file_path, output_path)
                    continue
                with open(file_path, "r", encoding="utf-8") as fp:
                    flines = fp.readlines()
                trans_file_path = file_path.replace('source', 'trans', 1).replace(".gd", ".json")
                logger.info(f"trans_file {trans_file_path} in {file_path}")
                if trans_file_path not in self.translationDict:
                    shutil.copyfile(file_path, output_path)
                    # logger.info(f"trans_file {trans_file_path}")
                    continue
                logger.info(f"trans_file {trans_file_path}")
                file_hash_index = self.hashIndex[file_path.replace(self.BDCCSourcePath + "\\", "", 1)]
                trans_dict = self.translationDict[trans_file_path]
                for i in range(len(trans_dict)):
                    trans_value = trans_dict[i]
                    index = int(trans_value['key'].split("_")[-1])
                    hash = list(file_hash_index['Indexes'].keys())[list(file_hash_index['Indexes'].values()).index(index)]
                    tokenPostion = file_hash_index["TokenPostion"][hash][0]
                    translation = trans_value['translation'] if trans_value['translation'] != "" else trans_value[
                        'original']
                    context = trans_value['context'] if 'context' in trans_value else trans_value['original']
                    targetLine = []
                    lineIndex = tokenPostion["StartLine"]
                    if lineIndex >= len(flines): lineIndex -= 1
                    if context not in flines[lineIndex]:
                        if context in flines[min(lineIndex + 1, len(flines) - 1)]:
                            lineIndex = min(lineIndex + 1, len(flines) - 1)
                        else:
                            if context in flines[lineIndex - 1]: lineIndex -= 1
                    try:
                        targetLine.append(flines[lineIndex][:tokenPostion["StartColumn"]])
                        targetLine.append(translation.replace("\\n", "\\\\n"))
                        targetLine.append(flines[lineIndex][tokenPostion["EndColumn"]:])
                        flines[lineIndex] = "".join(targetLine)
                    except:
                        logger.error(f"{f},{index}")
                with open(output_path, "w", encoding="utf-8") as fp:
                    fp.write("".join(flines))
                logger.info(f"{output_path} output filled")
