"""Source registry.

REGISTRY holds one Source per protocol that has a keyless public endpoint.
UNSOURCED maps the remaining protocol ids to the reason no source exists, so
the page can say "not measured" instead of silently omitting the card.
"""

REGISTRY = []
UNSOURCED = {}
