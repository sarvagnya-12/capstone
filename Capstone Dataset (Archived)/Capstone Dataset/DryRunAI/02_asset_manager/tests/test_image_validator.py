from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_manager.validators import ImageAssetValidator


class ImageAssetValidatorTests(unittest.TestCase):
    def test_validates_supported_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            Image.new("RGB", (10, 5), color="white").save(image_path)
            width, height, image_format = ImageAssetValidator({"PNG"}).validate(image_path)
            self.assertEqual(width, 10)
            self.assertEqual(height, 5)
            self.assertEqual(image_format, "PNG")


if __name__ == "__main__":
    unittest.main()

