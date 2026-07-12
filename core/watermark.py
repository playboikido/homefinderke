from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


def watermark_image(uploaded_file, text="HomeFinder KE"):
    """Takes an uploaded image file, stamps ONE diagonal watermark line across
    the center, returns a new uploadable file."""
    if not uploaded_file:
        return uploaded_file

    image = Image.open(uploaded_file).convert("RGBA")

    # Draw the text on its own transparent layer first, so we can rotate it cleanly
    font_size = max(28, image.width // 12)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    txt_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    text_img = Image.new("RGBA", (text_w + 20, text_h + 20), (255, 255, 255, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((10, 10), text, font=font, fill=(255, 255, 255, 130))

    rotated = text_img.rotate(30, expand=True, resample=Image.BICUBIC)

    paste_x = (image.width - rotated.width) // 2
    paste_y = (image.height - rotated.height) // 2

    combined = image.copy()
    combined.paste(rotated, (paste_x, paste_y), rotated)

    final_img = combined.convert("RGB")
    buffer = BytesIO()
    final_img.save(buffer, format="JPEG", quality=88)
    buffer.seek(0)

    return InMemoryUploadedFile(
        buffer, None, uploaded_file.name, "image/jpeg",
        sys.getsizeof(buffer), None
    )