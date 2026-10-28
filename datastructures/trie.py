class TrieNode:
    __slots__ = ("children", "ids")

    def __init__(self):
        self.children = {}
        self.ids = set()


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word, item_id):
        word = word.strip().lower()
        if not word:
            return
        node = self.root
        node.ids.add(item_id)
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
            node.ids.add(item_id)

    def search_prefix(self, prefix):
        prefix = prefix.strip().lower()
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return set()
            node = node.children[ch]
        return set(node.ids)

    def remove(self, word, item_id):
        word = word.strip().lower()
        path = [self.root]
        for ch in word:
            nxt = path[-1].children.get(ch)
            if nxt is None:
                return
            path.append(nxt)
        for node in path:
            node.ids.discard(item_id)
        for i in range(len(word), 0, -1):
            node = path[i]
            if not node.ids and not node.children:
                del path[i - 1].children[word[i - 1]]
