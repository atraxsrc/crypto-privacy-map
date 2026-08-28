import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import tempfile
import unittest

from protocol_ids import ids_from_index_html

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _write(text):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return tmp.name


class IdsFromIndexHtmlTest(unittest.TestCase):
    def test_extracts_ids_in_document_order(self):
        path = _write('''
          const DATA = [
            { column: "default", id: "monero", name: "Monero" },
            { column: "optin", id: "zcash-shielded", name: "Zcash Shielded" }
          ];
        ''')
        self.assertEqual(ids_from_index_html(path), ["monero", "zcash-shielded"])

    def test_raises_when_no_ids_present(self):
        path = _write("const DATA = [{ name: 'Monero' }];")
        with self.assertRaisesRegex(ValueError, "no protocol ids"):
            ids_from_index_html(path)

    def test_raises_on_duplicate_ids(self):
        path = _write('''
            { id: "monero", name: "Monero" },
            { id: "monero", name: "Monero Again" }
        ''')
        with self.assertRaisesRegex(ValueError, "duplicate protocol ids"):
            ids_from_index_html(path)

    def test_real_index_html_has_ten_unique_ids(self):
        ids = ids_from_index_html(REPO_ROOT / "index.html")
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)
        self.assertIn("monero", ids)
        self.assertIn("zcash-shielded", ids)


if __name__ == "__main__":
    unittest.main()
