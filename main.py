from src import replacer, consts,log
import re


# from src import trans
def main():
    log.logger.info("Translating...")
    rep = replacer.Replacer()
    rep.read_translation_files()
    rep.BDCC_replace()


# trans.trans_main()
if __name__ == '__main__':
    main()
