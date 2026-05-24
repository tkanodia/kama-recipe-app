"""Generate WebP thumbnails from image bytes using Pillow."""

import io

from PIL import Image


async def generate_thumbnail(image_bytes: bytes, max_width: int = 400) -> bytes:
    """Resize an image to *max_width* while maintaining aspect ratio and
    return the result encoded as WebP."""
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=80)
    return buf.getvalue()
