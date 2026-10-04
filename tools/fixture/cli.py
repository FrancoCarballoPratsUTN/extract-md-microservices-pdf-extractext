import pathlib
import sys

from tools.fixture.document import REFERENCE_PROFILE, ReferenceDocument

FLAGS = {
    "--pages": "pages",
    "--distinct-images": "distinct_images",
    "--image-draws": "image_draws",
    "--characters-per-page": "characters_per_page",
    "--image-side": "image_side",
}

USAGE = (
    "uso: gen-fixture --out RUTA.pdf [--pages N] [--distinct-images N]\n"
    "          [--image-draws N] [--characters-per-page N] [--image-side N]"
)


def main(argv):
    try:
        options = _parse(argv)
    except ValueError as failure:
        print(failure, file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    if options is None:
        return 2
    document = ReferenceDocument(options)
    path = pathlib.Path(options.pop("out"))
    path.parent.mkdir(parents=True, exist_ok=True)
    written = path.write_bytes(document.write())
    print(f"out={path} bytes={written}")
    print(
        "pages=%d flate_streams=%d image_draws=%d characters=%d decompressed=%d"
        % (
            document.page_count(),
            document.flate_stream_count(),
            document.image_draw_count(),
            document.character_count(),
            document.decompressed_bytes(),
        )
    )
    return 0


def _parse(argv):
    options = dict(REFERENCE_PROFILE)
    output = None
    index = 0
    while index < len(argv):
        flag = argv[index]
        if flag == "--out":
            output = _value(argv, index)
            index += 2
            continue
        if flag not in FLAGS:
            raise ValueError("flag desconocida: %s" % flag)
        key = FLAGS[flag]
        options[key] = _integer(_value(argv, index))
        index += 2
    if output is None:
        raise ValueError("falta --out")
    options["out"] = output
    return options


def _value(argv, index):
    if index + 1 >= len(argv):
        raise ValueError("falta el valor de %s" % argv[index])
    return argv[index + 1]


def _integer(value):
    try:
        return int(value)
    except ValueError:
        raise ValueError("valor no numérico: %s" % value) from None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))