class Name:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def serialize(self):
        return b"/" + self.value.encode("ascii")

    def __eq__(self, other):
        return isinstance(other, Name) and other.value == self.value

    def __hash__(self):
        return hash(("Name", self.value))


class Ref:
    __slots__ = ("number", "generation")

    def __init__(self, number, generation=0):
        self.number = number
        self.generation = generation

    def serialize(self):
        return b"%d %d R" % (self.number, self.generation)

    def __eq__(self, other):
        return (
            isinstance(other, Ref)
            and other.number == self.number
            and other.generation == self.generation
        )

    def __hash__(self):
        return hash(("Ref", self.number, self.generation))


class Stream:
    __slots__ = ("dictionary", "data")

    def __init__(self, dictionary, data):
        self.data = bytes(data)
        self.dictionary = dict(dictionary)
        self.dictionary[Name("Length")] = len(self.data)

    def serialize(self):
        return serialize(self.dictionary) + b"\nstream\n" + self.data + b"\nendstream"


def serialize(value):
    if value is None:
        return b"null"
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, Name):
        return value.serialize()
    if isinstance(value, Ref):
        return value.serialize()
    if hasattr(value, "serialize"):
        return value.serialize()
    if isinstance(value, (bytes, bytearray)):
        return b"<" + bytes(value).hex().upper().encode("ascii") + b">"
    if isinstance(value, str):
        return b"(" + value.encode("latin-1") + b")"
    if isinstance(value, int):
        return b"%d" % value
    if isinstance(value, float):
        return b"%.6f" % value
    if isinstance(value, (list, tuple)):
        return b"[" + b" ".join(serialize(item) for item in value) + b"]"
    if isinstance(value, dict):
        return b"<< " + b" ".join(_pair(key, item) for key, item in value.items()) + b" >>"
    raise TypeError("tipo PDF no soportado: %s" % type(value).__name__)


def _pair(key, value):
    return serialize(key if isinstance(key, Name) else Name(key)) + b" " + serialize(value)