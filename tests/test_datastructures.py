import random

import pytest

from datastructures import AVLTree, Graph, HashTable, MaxHeap, Trie


# ---------------------------------------------------------------- HashTable
def test_hash_table_basic_and_case_insensitive():
    t = HashTable()
    t.put("A@x.edu", 1)
    assert t.get("a@X.EDU") == 1
    assert "a@x.edu" in t and t.contains(" A@x.edu ")
    assert t.get("missing") is None and t.get("missing", 7) == 7
    t.put("a@x.edu", 2)
    assert len(t) == 1 and t.get("a@x.edu") == 2
    assert t.delete("a@x.edu") and not t.delete("a@x.edu") and len(t) == 0


def test_hash_table_resizes_and_keeps_everything():
    t = HashTable(capacity=4)
    for i in range(500):
        t.put(f"user{i}@x.edu", i)
    assert len(t) == 500 and t._capacity >= 500 / 0.75 / 2
    assert all(t.get(f"user{i}@x.edu") == i for i in range(500))
    assert sorted(t.values()) == list(range(500))


def test_hash_table_stores_falsy_values():
    t = HashTable()
    t.put("k", 0)
    assert t.contains("k") and t.get("k") == 0


# ------------------------------------------------------------------ AVLTree
def _check_avl(node):
    if node is None:
        return 0
    lh, rh = _check_avl(node.left), _check_avl(node.right)
    assert abs(lh - rh) <= 1, "unbalanced"
    assert node.height == 1 + max(lh, rh), "stale height"
    return node.height


def test_avl_sorted_and_balanced_after_sequential_inserts():
    t = AVLTree()
    for i in range(1000):          # worst case for a plain BST
        t.insert(i, i)
    _check_avl(t.root)
    assert t.height() <= 11        # ~1.44*log2(1000)
    assert t.inorder() == list(range(1000))
    assert t.inorder_desc() == list(range(999, -1, -1))
    assert list(t.iter_desc()) == list(range(999, -1, -1))


def test_avl_random_insert_delete_matches_reference():
    rng = random.Random(7)
    t, ref = AVLTree(), {}
    for _ in range(3000):
        k = rng.randint(0, 400)
        if rng.random() < 0.6:
            t.insert(k, k * 2)
            ref[k] = k * 2
        else:
            assert t.delete(k) == (k in ref)
            ref.pop(k, None)
        assert len(t) == len(ref)
    _check_avl(t.root)
    assert t.inorder() == [ref[k] for k in sorted(ref)]


def test_avl_duplicate_key_overwrites_and_tuple_keys():
    t = AVLTree()
    t.insert((1.0, 1), "a")
    t.insert((1.0, 2), "b")      # same timestamp, different id
    t.insert((1.0, 1), "c")
    assert len(t) == 2 and list(t.iter_desc()) == ["b", "c"]


def test_avl_iter_desc_is_lazy():
    t = AVLTree()
    for i in range(10000):
        t.insert(i, i)
    it = t.iter_desc()
    assert [next(it) for _ in range(3)] == [9999, 9998, 9997]


# ------------------------------------------------------------------ MaxHeap
def test_heap_top_k_matches_sorted():
    rng = random.Random(1)
    items = [(rng.randint(0, 50), i) for i in range(300)]
    h = MaxHeap.build(items)
    expected = [v for _, v in sorted(items, key=lambda t: -t[0])][:10]
    got = h.top_k(10)
    # equal scores may come back in any order, so compare scores
    score = dict((v, s) for s, v in items)
    assert [score[v] for v in got] == [score[v] for v in expected]
    assert len(h) == 300            # top_k must not mutate


def test_heap_tuple_scores_break_ties():
    h = MaxHeap.build([((5, 1.0), "old"), ((5, 2.0), "new"), ((9, 0.0), "top")])
    assert h.top_k(3) == ["top", "new", "old"]


def test_heap_push_pop_and_empty():
    h = MaxHeap()
    assert h.pop_max() is None and h.peek() is None
    for s in (3, 1, 4, 1, 5):
        h.push(s, s)
    assert [h.pop_max()[0] for _ in range(5)] == [5, 4, 3, 1, 1]


# --------------------------------------------------------------------- Trie
def test_trie_prefix_search():
    t = Trie()
    t.insert("Alice", 1)
    t.insert("alan", 2)
    t.insert("bob", 3)
    assert t.search_prefix("al") == {1, 2}
    assert t.search_prefix("ALI") == {1}
    assert t.search_prefix("") == {1, 2, 3}
    assert t.search_prefix("z") == set()


def test_trie_remove_prunes():
    t = Trie()
    t.insert("alice", 1)
    t.insert("alan", 2)
    t.remove("alice", 1)
    assert t.search_prefix("ali") == set() and t.search_prefix("al") == {2}
    assert "i" not in t.root.children["a"].children["l"].children


# -------------------------------------------------------------------- Graph
def make_graph():
    g = Graph()
    #  1-2-3-4-5   plus 1-6, 6-3 (so 1 and 3 have mutual friends 2 and 6)
    for a, b in [(1, 2), (2, 3), (3, 4), (4, 5), (1, 6), (6, 3)]:
        g.add_edge(a, b)
    g.add_node(99)
    return g


def test_graph_basics():
    g = make_graph()
    assert g.are_friends(1, 2) and g.are_friends(2, 1) and not g.are_friends(1, 3)
    assert g.mutual_friends(1, 3) == {2, 6}
    assert g.degree(3) == 3
    g.remove_edge(1, 2)
    assert not g.are_friends(1, 2)


def test_graph_shortest_path_and_distance():
    g = make_graph()
    assert g.shortest_path(1, 1) == [1]
    assert g.shortest_path(1, 5) == [1, 2, 3, 4, 5] or g.shortest_path(1, 5) == [1, 6, 3, 4, 5]
    assert g.distance(1, 5) == 4 and g.distance(1, 3) == 2
    assert g.shortest_path(1, 99) is None and g.distance(1, 99) is None
    assert g.shortest_path(1, 12345) is None


def test_graph_suggestions_ranked_by_mutuals():
    g = make_graph()
    ranked = g.suggestions(1)
    # 3 has 2 mutual friends at 2 hops; 4 has none at 3 hops; 5 is 4 hops away
    assert ranked == [(3, 2, 2), (4, 0, 3)]
    assert g.suggestions(1, max_depth=2) == [(3, 2, 2)]
    assert g.suggestions(404) == []
