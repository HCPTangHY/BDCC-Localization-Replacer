from src import replacer, consts,log
import re

from src.extract import extract
from src.replace import replace_translation
from src.update import update, update_deprecated
from src.parse import parser_check
from src.consts import DIR_SOURCE, DIR_OUTPUT, DIR_TRANS, DIR_FETCH, DIR_DEPRECATED, DIR_CHANGE

# from src import trans
def main():
    log.logger.info("Translating...")
    rep = replacer.Replacer()
    rep.read_translation_files()
    rep.BDCC_replace()

def translate_new():
    log.logger.info("Extract new translation items...")
    extract(DIR_SOURCE, DIR_TRANS)
    log.logger.info("Migrate old translation items...")
    update(DIR_TRANS, DIR_FETCH, DIR_DEPRECATED, DIR_CHANGE)
    log.logger.info("Replace source code with new translation items...")
    replace_translation(DIR_SOURCE, DIR_TRANS, DIR_OUTPUT)
    log.logger.info("Checking translation files...")
    parser_check(DIR_OUTPUT)
    log.logger.info("Translation complete!")
    
def translate_old():
    log.logger.info("Extract new translation items...")
    extract(DIR_SOURCE, DIR_TRANS)
    log.logger.info("Migrate old translation items...")
    update_deprecated(DIR_TRANS, DIR_FETCH, DIR_DEPRECATED)
    log.logger.info("Replace source code with new translation items...")
    replace_translation(DIR_SOURCE, DIR_TRANS, DIR_OUTPUT)

# trans.trans_main()
if __name__ == '__main__':
    translate_new()
