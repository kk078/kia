"""OCR processor for text extraction from images."""

from pathlib import Path
from typing import Any

from PIL import Image


class OCRProcessor:
    """Extract text from images using OCR."""

    def __init__(self, lang: str = "eng") -> None:
        """Initialize OCR processor.

        Args:
            lang: Tesseract language code (default: English)
        """
        self.lang = lang

    async def process_image(self, image_path: str) -> dict[str, Any]:
        """Extract text from an image.

        Args:
            image_path: Path to image file

        Returns:
            Dict with extracted text and metadata
        """
        try:
            import pytesseract

            path = Path(image_path)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            # Open and process image
            with Image.open(path) as img:
                if img.mode != "RGB":
                    img_rgb = img.convert("RGB")
                else:
                    img_rgb = img

                text = pytesseract.image_to_string(img_rgb, lang=self.lang)

                metadata = {
                    "format": img_rgb.format,
                    "size": img_rgb.size,
                    "mode": img_rgb.mode,
                }

            return {
                "text": text.strip(),
                "source": str(path),
                "metadata": metadata,
                "word_count": len(text.split()),
                "char_count": len(text),
            }
        except ImportError:
            return {
                "text": "",
                "source": image_path,
                "error": "pytesseract not installed or Tesseract OCR not available",
                "metadata": {},
                "word_count": 0,
                "char_count": 0,
            }

    async def process_batch(self, image_paths: list[str]) -> list[dict[str, Any]]:
        """Process multiple images.

        Args:
            image_paths: List of image paths

        Returns:
            List of extraction results
        """
        results = []
        for path in image_paths:
            result = await self.process_image(path)
            results.append(result)
        return results
