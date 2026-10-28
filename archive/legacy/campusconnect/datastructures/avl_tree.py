"""
Custom AVL Tree (self-balancing BST) used to keep posts in sorted order
for efficient insertion, deletion, and retrieval — backs the chronological
feed so it doesn't need to re-sort on every read.

Keys must be totally ordered and unique; the posts feed uses
(created_at_epoch, post_id) so ties on timestamp still order deterministically.
"""


class _AVLNode:
    __slots__ = ("key", "value", "left", "right", "height")

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.left = None
        self.right = None
        self.height = 1


class AVLTree:
    def __init__(self):
        self.root = None

    # -- public API ---------------------------------------------------

    def insert(self, key, value):
        self.root = self._insert(self.root, key, value)

    def delete(self, key):
        self.root = self._delete(self.root, key)

    def inorder(self):
        """Ascending-key order."""
        result = []
        self._inorder(self.root, result)
        return result

    def inorder_desc(self):
        """Descending-key order (e.g. newest post first)."""
        result = []
        self._inorder_desc(self.root, result)
        return result

    # -- internals -------------------------------------------------------

    def _height(self, node):
        return node.height if node else 0

    def _balance_factor(self, node):
        return self._height(node.left) - self._height(node.right) if node else 0

    def _update_height(self, node):
        node.height = 1 + max(self._height(node.left), self._height(node.right))

    def _rotate_right(self, y):
        x = y.left
        t2 = x.right
        x.right = y
        y.left = t2
        self._update_height(y)
        self._update_height(x)
        return x

    def _rotate_left(self, x):
        y = x.right
        t2 = y.left
        y.left = x
        x.right = t2
        self._update_height(x)
        self._update_height(y)
        return y

    def _rebalance(self, node):
        self._update_height(node)
        balance = self._balance_factor(node)

        if balance > 1:
            if self._balance_factor(node.left) < 0:
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        if balance < -1:
            if self._balance_factor(node.right) > 0:
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def _insert(self, node, key, value):
        if node is None:
            return _AVLNode(key, value)
        if key < node.key:
            node.left = self._insert(node.left, key, value)
        elif key > node.key:
            node.right = self._insert(node.right, key, value)
        else:
            node.value = value  # overwrite on duplicate key
            return node
        return self._rebalance(node)

    def _min_node(self, node):
        while node.left is not None:
            node = node.left
        return node

    def _delete(self, node, key):
        if node is None:
            return None
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            successor = self._min_node(node.right)
            node.key, node.value = successor.key, successor.value
            node.right = self._delete(node.right, successor.key)
        return self._rebalance(node)

    def _inorder(self, node, result):
        if node is None:
            return
        self._inorder(node.left, result)
        result.append(node.value)
        self._inorder(node.right, result)

    def _inorder_desc(self, node, result):
        if node is None:
            return
        self._inorder_desc(node.right, result)
        result.append(node.value)
        self._inorder_desc(node.left, result)
