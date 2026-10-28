from collections import deque


class Graph:
    def __init__(self):
        self._adjacency = {}  
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
        if start == goal:
            return [start]
        if start not in self._adjacency or goal not in self._adjacency:
            return None

        parent = {start: None}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in self._adjacency.get(node, ()):
                if neighbor in parent:
                    continue
                parent[neighbor] = node
                if neighbor == goal:
                    path = [goal]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])
                    return path[::-1]
                queue.append(neighbor)
        return None

    def __contains__(self, node):
        return node in self._adjacency

    def suggestions(self, user, limit=10, max_depth=3):
        if user not in self._adjacency:
            return []
        direct = self._adjacency[user]
        dist = {user: 0}
        queue = deque([user])
        while queue:
            node = queue.popleft()
            if dist[node] == max_depth:
                continue
            for nb in self._adjacency.get(node, ()):
                if nb not in dist:
                    dist[nb] = dist[node] + 1
                    queue.append(nb)
        ranked = []
        for cand, d in dist.items():
            if d >= 2:
                mutual = len(self._adjacency[cand] & direct)
                ranked.append((cand, mutual, d))
        ranked.sort(key=lambda t: (-t[1], t[2], t[0]))
        return ranked[:limit]

    def distance(self, a, b):
        path = self.shortest_path(a, b)
        return None if path is None else len(path) - 1
