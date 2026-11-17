"""Lectura de imágenes QR, con QReader local y fallback OpenCV para la nube."""

from functools import lru_cache
import io
import os
from pathlib import Path
import threading

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 32_000_000
_inference_lock = threading.Lock()


class InvalidQRImage(ValueError):
    pass


class QRReaderUnavailable(RuntimeError):
    pass


class QRReaderBusy(RuntimeError):
    pass


class _OpenCVReader:
    """Fallback ligero cuando torch/qreader no están instalados (Vercel)."""

    backend = "opencv"

    def __init__(self):
        import cv2

        self._cv2 = cv2
        self._detector = cv2.QRCodeDetector()

    def detect_and_decode(self, image):
        import numpy as np

        arr = image if isinstance(image, np.ndarray) else np.asarray(image)
        if arr.ndim == 2:
            variants = [arr]
        else:
            rgb = arr[:, :, :3]
            variants = [
                rgb,
                self._cv2.cvtColor(rgb, self._cv2.COLOR_RGB2BGR),
                self._cv2.cvtColor(rgb, self._cv2.COLOR_RGB2GRAY),
            ]
        results = []
        for variant in variants:
            for rotation in range(4):
                current = variant if rotation == 0 else self._cv2.rotate(variant, self._cv2.ROTATE_90_CLOCKWISE)
                try:
                    data, _, _ = self._detector.detectAndDecode(current)
                    if data:
                        results.append(data)
                    if hasattr(self._detector, "detectAndDecodeMulti"):
                        ok, decoded, _, _ = self._detector.detectAndDecodeMulti(current)
                        if ok:
                            results.extend(value for value in decoded if value)
                except self._cv2.error:
                    continue
        return tuple(dict.fromkeys(results))


def _qreader():
    import torch
    from qreader import QReader

    torch.set_num_threads(2)
    folder = Path(os.environ.get("QREADER_WEIGHTS_DIR", Path.home() / ".cache" / "scoreup" / "qreader"))
    folder.mkdir(parents=True, exist_ok=True)
    return QReader(model_size="s", reencode_to=None, weights_folder=str(folder))


@lru_cache(maxsize=1)
def get_reader():
    mode = os.environ.get("SCOREUP_QR_BACKEND", "auto").strip().lower()
    if mode == "opencv":
        try:
            return _OpenCVReader()
        except Exception as error:
            raise QRReaderUnavailable("OpenCV no está disponible para leer QR.") from error
    if mode != "qreader":
        try:
            return _qreader()
        except Exception:
            pass
    try:
        return _OpenCVReader()
    except Exception as error:
        raise QRReaderUnavailable("No hay un lector QR disponible en este servidor.") from error


def reader_name():
    return getattr(get_reader(), "backend", "qreader")


def decode_image(content):
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise InvalidQRImage("Adjunta una imagen de hasta 8 MB.")
    try:
        with Image.open(io.BytesIO(content)) as original:
            if original.format not in {"PNG", "JPEG", "WEBP", "GIF"}:
                raise InvalidQRImage("Usa una fotografía JPG, PNG o WebP.")
            if original.width * original.height > MAX_PIXELS:
                raise InvalidQRImage("La imagen es demasiado grande. Reduce su resolución.")
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((2560, 2560))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        if isinstance(error, InvalidQRImage):
            raise
        raise InvalidQRImage("El archivo no contiene una imagen válida.") from error
    if not _inference_lock.acquire(blocking=False):
        raise QRReaderBusy("El lector está ocupado. Reintenta en unos segundos.")
    try:
        import numpy as np

        reader = get_reader()
        return tuple(value for value in reader.detect_and_decode(image=np.asarray(image)) if isinstance(value, str) and value)
    except (QRReaderUnavailable, QRReaderBusy):
        raise
    except Exception as error:
        raise QRReaderUnavailable("No se pudo procesar la imagen con el lector QR.") from error
    finally:
        _inference_lock.release()
