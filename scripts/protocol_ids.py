"""Read the protocol roster out of index.html.

The page owns the roster. The pipeline parses ids from it rather than keeping a
second list, so the two can never drift apart.
"""

import re
from pathlib import Path

# Matches an id in either layout: on its own line, or inline after another
# property. Anchoring to a preceding { or , keeps it from matching text that
# merely looks like an id inside a card's prose.
ID_RE = re.compile(r'[{,]\s*id:\s*"([a-z0-9-]+)"\s*,')


def ids_from_index_html(path):
    """Return protocol ids in document order.

    Raises ValueError if the file contains no ids or any duplicates, both of
    which mean the roster is broken rather than empty.
    """
    text = Path(path).read_text(encoding="utf-8")
    ids = ID_RE.findall(text)
    if not ids:
        raise ValueError(f"no protocol ids found in {path}")
    seen, dupes = set(), set()
    for pid in ids:
        if pid in seen:
            dupes.add(pid)
        seen.add(pid)
    if dupes:
        raise ValueError(f"duplicate protocol ids in {path}: {sorted(dupes)}")
    return ids
