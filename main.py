from src import replacer,consts
import re
# from src import trans
def main():
    rep = replacer.Replacer("\\trans",".\source")
    rep.read_translation_files()
    rep.BDCC_replace()
# trans.trans_main()
if __name__ == '__main__':
    main()
