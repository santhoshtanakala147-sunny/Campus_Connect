"""
Custom array-based Max Heap used to rank trending posts by engagement
(likes + weighted comments). Built from scratch (sift-up/sift-down,
heapify) rather than wrapping Python's heapq.
"""


class MaxHeap:
    def __init__(self):
        self._items = []  # list of (score, value)

    @classmethod
    def build(cls, scored_items):
        """Build a heap in O(n) from an iterable of (score, value) pairs."""
        heap = cls()
        heap._items = list(scored_items)
        for i in range(len(heap._items) // 2 - 1, -1, -1):
            heap._sift_down(i)
        return heap

    def push(self, score, value):
        self._items.append((score, value))
        self._sift_up(len(self._items) - 1)

    def peek(self):
        return self._items[0] if self._items else None

    def pop_max(self):
        if not self._items:
            return None
        top = self._items[0]
        last = self._items.pop()
        if self._items:
            self._items[0] = last
            self._sift_down(0)
        return top

    def top_k(self, k):
        """Return the k highest-scoring values without mutating this heap."""
        clone = MaxHeap.build(list(self._items))
        results = []
        for _ in range(min(k, len(clone._items))):
            score, value = clone.pop_max()
            results.append(value)
        return results

    def __len__(self):
        return len(self._items)

    # -- internals ---------------------------------------------------

    def _sift_up(self, i):
        while i > 0:
            parent = (i - 1) // 2
            if self._items[i][0] > self._items[parent][0]:
                self._items[i], self._items[parent] = self._items[parent], self._items[i]
                i = parent
            else:
                break

    def _sift_down(self, i):
        n = len(self._items)
        while True:
            left, right = 2 * i + 1, 2 * i + 2
            largest = i
            if left < n and self._items[left][0] > self._items[largest][0]:
                largest = left
            if right < n and self._items[right][0] > self._items[largest][0]:
                largest = right
            if largest == i:
                break
            self._items[i], self._items[largest] = self._items[largest], self._items[i]
            i = largest
