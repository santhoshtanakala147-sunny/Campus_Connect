"""
Custom Trie (prefix tree) used to power fast student/college search with
autocomplete. Each node caches the set of ids reachable under it, so a
prefix lookup is O(len(prefix)) instead of a subtree walk.
"""


class TrieNode:
    __slots__ = ("children", "ids")

    def __init__(self):
        self.children = {}
        self.ids = set()


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word, item_id):
        """Index `word` (e.g. a name token or college token) under `item_id`."""
        word = word.strip().lower()
        if not word:
            return
        node = self.root
        node.ids.add(item_id)
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
            node.ids.add(item_id)

    def search_prefix(self, prefix):
        """Return the set of ids indexed under any word starting with `prefix`."""
        prefix = prefix.strip().lower()
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return set()
            node = node.children[ch]
        return set(node.ids)
