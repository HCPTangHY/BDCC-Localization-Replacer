import ujson as json

from .consts import *


def join_main():
    data = []
    for filename in {
        "main.554c4eab-1.json",
        "main.554c4eab-2.json",
        "main.554c4eab-3.json",
        "main.554c4eab-4.json",
        "main.554c4eab-5.json"
    }:
        with open(DIR_TRANS / filename, "r", encoding="utf-8") as fp:
            data.extend(json.load(fp))

    with open(DIR_TRANS / "main.554c4eab.json", "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False)


if __name__ == '__main__':
    join_main()
