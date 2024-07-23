import ujson as json
import numpy as np

from .consts import *


def split_main():
    with open(DIR_FETCH / "main.554c4eab.json", "r", encoding="utf-8") as fp:
        data = json.load(fp)

    data = np.array_split(data, 5)
    for idx, d in data:
        with open(f"fetch/main.554c4eab-{idx+1}.json", "w", encoding="utf-8") as fp:
            json.dump(d.tolist(), fp, ensure_ascii=False)


if __name__ == '__main__':
    split_main()
