import re
import string
import unicodedata


def numf(num: int) -> str:
    if num < 10000:
        return str(num)
    if num < 100000000:
        return ("%.2f" % (num / 10000)) + "万"
    return ("%.2f" % (num / 100000000)) + "亿"


def get_cut_str(input_str: str, cut: int) -> list[str]:
    """
    自动断行, 用于 Pillow 等不会自动换行的场景
    """
    punc = """，,、。.？?）》】“"‘'；;：:！!·`~%^& """  # noqa: RUF001
    si = 0
    i = 0
    next_str = input_str
    str_list = []

    while re.search(r"\n\n\n\n\n", next_str):
        next_str = re.sub(r"\n\n\n\n\n", "\n", next_str)
    for s in next_str:
        si += 1 if s in string.printable else 2
        i += 1
        if not next_str:
            break
        if next_str[0] == "\n":
            next_str = next_str[1:]
        elif s == "\n":
            str_list.append(next_str[: i - 1])
            next_str = next_str[i - 1 :]
            si = 0
            i = 0
            continue
        if si > cut:
            try:
                if next_str[i] in punc:
                    i += 1
            except IndexError:
                str_list.append(next_str)
                return str_list
            str_list.append(next_str[:i])
            next_str = next_str[i:]
            si = 0
            i = 0
    str_list.append(next_str)
    i = 0
    non_wrap_str = []
    for p in str_list:
        if not p:
            break
        if p[-1] == "\n":
            p = p[:-1]  # noqa: PLW2901
        non_wrap_str.append(p)
        i += 1
    return non_wrap_str


def get_str_width(input_str: str) -> int:
    """
    获取字符串的宽度, 中文字符算两个字符, 全角标点也算两个字符
    """
    return sum(2 if unicodedata.east_asian_width(s) in {"F", "W"} else 1 for s in input_str)
