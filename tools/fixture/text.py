WORDS_PER_LINE = 78
JOINER = " "


class TextCorpus:
    def __init__(self, vocabulary):
        self._vocabulary = list(vocabulary)
        self._alphabet = sorted(
            {character for word in self._vocabulary for character in word} | {JOINER}
        )
        self._code_of = {character: code for code, character in enumerate(self._alphabet, start=1)}

    def cmap_mappings(self):
        return {code: character for character, code in self._code_of.items()}

    def encode(self, text):
        return b"".join(self._two_byte_code(character) for character in text)

    def page_text(self, page_index, characters):
        return "\n".join(self._lines(page_index, characters))

    def _two_byte_code(self, character):
        code = self._code_of[character]
        return bytes((code >> 8, code & 0xFF))

    def _lines(self, page_index, characters):
        lines = []
        total = 0
        current = []
        index = 0
        while total < characters:
            word = self._word(page_index, index)
            index += 1
            if current and len(JOINER.join(current + [word])) > WORDS_PER_LINE:
                lines.append(JOINER.join(current))
                current = []
                total = _joined_length(lines)
                if total >= characters:
                    return _trim_lines(lines, characters)
            current.append(word)
        if current:
            lines.append(JOINER.join(current))
        return _trim_lines(lines, characters)

    def _word(self, page_index, index):
        position = (page_index * 7919 + index * 104729) % len(self._vocabulary)
        return self._vocabulary[position]


def _joined_length(lines):
    return sum(len(line) for line in lines) + max(len(lines) - 1, 0)


def _trim_lines(lines, characters):
    overflow = _joined_length(lines) - characters
    if overflow <= 0:
        return lines
    last = _trim_to(lines[-1], len(lines[-1]) - overflow)
    if last:
        return lines[:-1] + [last]
    return lines[:-1]


def _trim_to(line, budget):
    if len(line) <= budget:
        return line
    cut = line.rfind(JOINER, 0, budget + 1)
    return line[:cut] if cut > 0 else line[:budget]


SYLLABLES = [
    "ba", "be", "bi", "bo", "bu", "ca", "ce", "ci", "co", "cu",
    "da", "de", "di", "do", "du", "fa", "fe", "fi", "fo", "fu",
    "ga", "ge", "gi", "go", "gu", "la", "le", "li", "lo", "lu",
    "ma", "me", "mi", "mo", "mu", "na", "ne", "ni", "no", "nu",
    "pa", "pe", "pi", "po", "pu", "ra", "re", "ri", "ro", "ru",
    "sa", "se", "si", "so", "su", "ta", "te", "ti", "to", "tu",
    "va", "ve", "vi", "vo", "vu", "za", "ze", "zi", "zo", "zu",
]

VOWELS = ["a", "e", "i", "o", "u", "á", "é", "í", "ó", "ú", "ü", "ñ"]


def vocabulary():
    return _spanish_words() + [
        onset + vowel + coda for onset in SYLLABLES for vowel in VOWELS for coda in SYLLABLES
    ]


def _spanish_words():
    return [
        "el", "la", "los", "las", "un", "una", "de", "del", "que", "por",
        "para", "con", "como", "más", "niño", "años", "ciudad", "país",
        "sx", "sy", "día", "semana", "mes", "año", "trabajo", "estudio",
        "casa", "familia", "escuela", "docente", "alumno", "nota", "tema",
        "capítulo", "parte", "ejemplo", "problema", "solución", "dato",
        "número", "letra", "palabra", "texto", "página", "documento",
        "lectura", "escritura", "lenguaje", "español", "inglés", "carácter",
        "acentuación", "tilde", "ñandú", "pingüino", "árbol", "útil",
        "código", "proyecto", "sistema", "servicio", "red", "servidor",
        "procesador", "memoria", "archivo", "formato", "compresión",
        "medición", "resultado", "informe", "gráfico", "tabla", "columna",
        "fila", "error", "acierto", "cálculo", "suma", "resta", "producto",
        "proporción", "distancia", "velocidad", "tiempo", "energía",
        "presente", "ausente", "nuevo", "viejo", "grande", "pequeño",
    ]