"""QReader real sobre imágenes sintéticas: no sustituye una foto física del celular."""

import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import qrcode
    from PIL import Image, ImageEnhance, ImageFilter
    from qr_reader import decode_image, get_reader

    value = "http://192.168.1.20:5001/qr/test-token.synthetic-only"
    qr = qrcode.QRCode(box_size=10, border=6)
    qr.add_data(value)
    qr.make(fit=True)
    original = qr.make_image().convert("RGB")
    fixtures = {
        "foto-jpeg": original,
        "giro-contraste": ImageEnhance.Contrast(original.rotate(27, expand=True, fillcolor="white")).enhance(0.5),
        "inclinacion-desenfoque": original.transform(
            (original.width + 180, original.height), Image.Transform.AFFINE,
            (1, -0.2, 0, 0, 1, 0), resample=Image.Resampling.BICUBIC, fillcolor="white"
        ).filter(ImageFilter.GaussianBlur(0.5)),
    }
    get_reader()  # Descarga inicial solo si no está preparado; sin importar app.py.
    for name, image in fixtures.items():
        content = io.BytesIO()
        image.save(content, format="JPEG", quality=85)
        result = decode_image(content.getvalue())
        assert value in result, (name, result)
        print("OK:", name)
    blank = io.BytesIO()
    Image.new("RGB", (300, 300), "white").save(blank, format="PNG")
    assert decode_image(blank.getvalue()) == ()
    print("OK: imagen sin QR; pendientes foto y cámara físicas.")


if __name__ == "__main__":
    main()
