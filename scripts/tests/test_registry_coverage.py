import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import unittest

from protocol_ids import ids_from_index_html
from sources import REGISTRY, UNSOURCED

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class RegistryCoverageTest(unittest.TestCase):
    def setUp(self):
        self.page_ids = set(ids_from_index_html(REPO_ROOT / "index.html"))
        self.source_ids = {s.id for s in REGISTRY}

    def test_no_id_is_both_sourced_and_unsourced(self):
        self.assertEqual(self.source_ids & set(UNSOURCED), set())

    def test_every_page_protocol_is_classified(self):
        # Adding a protocol to index.html must force a deliberate decision about
        # whether it has a keyless data source. Silence is not an answer.
        missing = self.page_ids - self.source_ids - set(UNSOURCED)
        self.assertEqual(missing, set(),
                         f"protocols in index.html with no source and no UNSOURCED entry: {sorted(missing)}")

    def test_registry_has_no_ids_the_page_does_not_have(self):
        extra = (self.source_ids | set(UNSOURCED)) - self.page_ids
        self.assertEqual(extra, set(),
                         f"classified ids that no longer exist in index.html: {sorted(extra)}")

    def test_every_unsourced_entry_states_a_reason(self):
        for pid, reason in UNSOURCED.items():
            self.assertTrue(reason and len(reason) > 10,
                            f"{pid}: UNSOURCED needs a real reason, got {reason!r}")

    def test_source_ids_are_unique(self):
        self.assertEqual(len(self.source_ids), len(REGISTRY))


if __name__ == "__main__":
    unittest.main()
