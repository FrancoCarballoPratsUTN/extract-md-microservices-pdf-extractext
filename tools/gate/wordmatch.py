import re
from collections import Counter

WORD = re.compile(r"[^\W\d_]+")
DEFAULT_MINIMUM = 0.70


def words(text):
    return [match.lower() for match in WORD.findall(text)]


def match_ratio(expected, actual):
    expected_words = Counter(words(expected))
    if not expected_words:
        return 1.0
    shared = expected_words & Counter(words(actual))
    return sum(shared.values()) / sum(expected_words.values())


def main(argv):
    if len(argv) < 3:
        raise SystemExit("uso: wordmatch EXPECTED ACTUAL [--min 0.70]")
    minimum = DEFAULT_MINIMUM
    if "--min" in argv:
        minimum = float(argv[argv.index("--min") + 1])
    with open(argv[1], encoding="utf-8") as handle:
        expected = handle.read()
    with open(argv[2], encoding="utf-8") as handle:
        actual = handle.read()
    ratio = match_ratio(expected, actual)
    print("gate de coincidencia de palabras: %.2f %% (minimo %.2f %%)" % (ratio * 100, minimum * 100))
    return 0 if ratio >= minimum else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))