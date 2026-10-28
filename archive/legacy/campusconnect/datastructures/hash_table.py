"""
Custom Hash Table (separate chaining) used to index student accounts by
email for O(1) average-case lookup during login/authentication.

This is a from-scratch implementation (no dict under the hood for storage)
so it demonstrates the actual data structure rather than wrapping Python's
built-in dict.
"""

DEFAULT_CAPACITY = 16
LOAD_FACTOR_THRESHOLD = 0.75


class _Entry:
    __slots__ = ("key", "value")

    def __init__(self, key, value):
        self.key = key
        self.value = value


class HashTable:
    def __init__(self, capacity=DEFAULT_CAPACITY):
        self._capacity = capacity
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0

    def _hash(self, key):
        # Normalize email keys so lookups are case-insensitive.
        if isinstance(key, str):
            key = key.strip().lower()
        return hash(key) % self._capacity

    def put(self, key, value):
        if isinstance(key, str):
            key = key.strip().lower()

        idx = self._hash(key)
        bucket = self._buckets[idx]
        for entry in bucket:
            if entry.key == key:
                entry.value = value
                return
        bucket.append(_Entry(key, value))
        self._size += 1

        if self._size / self._capacity > LOAD_FACTOR_THRESHOLD:
            self._resize()

    def get(self, key, default=None):
        if isinstance(key, str):
            key = key.strip().lower()
        idx = self._hash(key)
        for entry in self._buckets[idx]:
            if entry.key == key:
                return entry.value
        return default

    def contains(self, key):
        _MISSING = object()
        return self.get(key, _MISSING) is not _MISSING

    def delete(self, key):
        if isinstance(key, str):
            key = key.strip().lower()
        idx = self._hash(key)
        bucket = self._buckets[idx]
        for i, entry in enumerate(bucket):
            if entry.key == key:
                del bucket[i]
                self._size -= 1
                return True
        return False

    def _resize(self):
        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0
        for bucket in old_buckets:
            for entry in bucket:
                self.put(entry.key, entry.value)

    def __len__(self):
        return self._size

    def __contains__(self, key):
        return self.contains(key)

    def keys(self):
        return [entry.key for bucket in self._buckets for entry in bucket]

    def values(self):
        return [entry.value for bucket in self._buckets for entry in bucket]

    def items(self):
        return [(entry.key, entry.value) for bucket in self._buckets for entry in bucket]
