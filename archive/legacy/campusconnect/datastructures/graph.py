"""
Custom Graph (undirected, adjacency list) used to model the student friend
network. Nodes are user ids; an edge means two students are friends.
"""

from collections import deque


class Graph:
    def __init__(self):
        self._adjacency = {}  # user_id -> set(friend_ids)

    def add_node(self, node):
        if node not in self._adjacency:
            self._adjacency[node] = set()

    def add_edge(self, a, b):
        self.add_node(a)
        self.add_node(b)
        self._adjacency[a].add(b)
        self._adjacency[b].add(a)

    def remove_edge(self, a, b):
        self._adjacency.get(a, set()).discard(b)
        self._adjacency.get(b, set()).discard(a)

    def are_friends(self, a, b):
        return b in self._adjacency.get(a, set())

    def neighbors(self, node):
        return set(self._adjacency.get(node, set()))

    def degree(self, node):
        return len(self._adjacency.get(node, set()))

    def mutual_friends(self, a, b):
        return self.neighbors(a) & self.neighbors(b)

    def shortest_path(self, start, goal):
        """BFS shortest path between two students (e.g. 'friends of friends')."""
        if start == goal:
            return [start]
        if start not in self._adjacency or goal not in self._adjacency:
            return None

        visited = {start}
        queue = deque([[start]])
        while queue:
            path = queue.popleft()
            node = path[-1]
            for neighbor in self._adjacency.get(node, set()):
                if neighbor == goal:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def __contains__(self, node):
        return node in self._adjacency
