from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


def watermark_image(uploaded_file, text="HomeFinder KE"):
    """Takes an uploaded image file, stamps a tiled watermark over it, returns a new uploadable file."""
    if not uploaded_file:
        return uploaded_file

    image = Image.open(uploaded_file).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font_size = max(18, image.width // 20)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    step_x, step_y = text_w + 60, text_h + 60
    for y in range(0, image.height, step_y):
        for x in range(0, image.width, step_x):
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 90))

    watermarked = Image.alpha_composite(image, overlay).convert("RGB")

    buffer = BytesIO()
    watermarked.save(buffer, format="JPEG", quality=88)
    buffer.seek(0)

    return InMemoryUploadedFile(
        buffer, None, uploaded_file.name, "image/jpeg",
        sys.getsizeof(buffer), None
    )