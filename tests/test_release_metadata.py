import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    def test_addon_version_is_0_1_17(self):
        addon = ET.parse(ROOT / "addon.xml").getroot()
        self.assertEqual(addon.attrib["version"], "0.1.17")


if __name__ == "__main__":
    unittest.main()
