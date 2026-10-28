"""Curated content for the Reels page.

Everything here was checked against its source page:
  * MIT OpenCourseWare lectures: IDs and the CC BY-NC-SA 4.0 licence were read from each OCW lecture page.
  * Open textbooks/tools: licences read from the project pages.
Pre-built animations are original work made for CampusConnect (see frontend/reels.js).

Videos are *embedded* from YouTube (click-to-play, youtube-nocookie.com); nothing is copied or re-hosted,
and every card shows its licence, credit and a link back to the source.
"""

TOPICS = ["Data Structures", "Algorithms", "AI & ML", "Math", "Quantum", "Web Dev", "AI & Safety", "Study Tips", "Other"]

OCW = "MIT OpenCourseWare · 6.006 Introduction to Algorithms (Fall 2011)"
CC_NC_SA = "CC BY-NC-SA 4.0"

REELS = [
    # ---- Pre-built: short animated explainers drawn in the browser (original) -------------------------
    dict(slug="anim-hash", kind="prebuilt", media="animation", media_ref="hash", topic="Data Structures",
         title="Hash table in 30s: how login finds you instantly",
         description="Buckets, collisions and rehashing, the idea behind our email → user lookup.",
         license="Original · made for CampusConnect", credit="CampusConnect", source_url="",
         code="datastructures/hash_table.py"),
    dict(slug="anim-bfs", kind="prebuilt", media="animation", media_ref="bfs", topic="Algorithms",
         title="BFS: how \"People you may know\" works",
         description="Level-by-level search over the friend graph, ranked by mutual friends.",
         license="Original · made for CampusConnect", credit="CampusConnect", source_url="",
         code="datastructures/graph.py (suggestions, shortest_path)"),
    dict(slug="anim-trie", kind="prebuilt", media="animation", media_ref="trie", topic="Data Structures",
         title="Trie: search-as-you-type",
         description="Why typing 'al' finds Alan without scanning every student.",
         license="Original · made for CampusConnect", credit="CampusConnect", source_url="",
         code="datastructures/trie.py"),
    dict(slug="anim-avl", kind="prebuilt", media="animation", media_ref="avl", topic="Data Structures",
         title="AVL rotations keep the feed balanced",
         description="Insert 10, 20, 30... and watch the tree fix itself with rotations.",
         license="Original · made for CampusConnect", credit="CampusConnect", source_url="",
         code="datastructures/avl_tree.py (_rotate_left, _rebalance)"),
    dict(slug="anim-heap", kind="prebuilt", media="animation", media_ref="heap", topic="Data Structures",
         title="Max heap: crowning the #1 trending post",
         description="Sift-up in action: a new post with score 60 climbs to the top.",
         license="Original · made for CampusConnect", credit="CampusConnect", source_url="",
         code="datastructures/max_heap.py"),
    dict(slug="anim-safety", kind="prebuilt", media="animation", media_ref="safety", topic="AI & Safety",
         title="How every post is safety-checked",
         description="Local rules first, then a Gemini classifier, then allow, block, or support.",
         license="Original · made for CampusConnect", credit="CampusConnect", source_url="",
         code="ai/moderation.py"),

    # ---- Open-licensed lectures (embedded from the course's own YouTube uploads) ----------------------
    dict(slug="ocw-avl", kind="open", media="youtube", media_ref="FNeL18KsWPc", topic="Data Structures",
         title="AVL Trees & AVL Sort (full lecture)",
         description="Why balanced trees keep search, insert and delete at O(log n). The idea behind our feed.",
         license=CC_NC_SA, credit=OCW, source_url="https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/6-006-introduction-to-algorithms-fall-2011/lecture-videos/lecture-6-avl-trees-avl-sort/"),
    dict(slug="ocw-heaps", kind="open", media="youtube", media_ref="B7hVxCmfPtM", topic="Data Structures",
         title="Heaps and Heap Sort (full lecture)",
         description="Priority queues and the array-based heap, the structure behind our trending tab.",
         license=CC_NC_SA, credit=OCW, source_url="https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-4-heaps-and-heap-sort/"),
    dict(slug="ocw-hashing", kind="open", media="youtube", media_ref="0M_kIqhwbFo", topic="Data Structures",
         title="Hashing with Chaining (full lecture)",
         description="Hash functions, collisions and chaining, as used in our login table.",
         license=CC_NC_SA, credit=OCW, source_url="https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-8-hashing-with-chaining/"),
    dict(slug="ocw-bst", kind="open", media="youtube", media_ref="9Jry5-82I68", topic="Data Structures",
         title="Binary Search Trees, BST Sort (full lecture)",
         description="The starting point for AVL trees: ordered insertion, search and why balance matters.",
         license=CC_NC_SA, credit=OCW, source_url="https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-5-binary-search-trees-bst-sort/"),
    dict(slug="ocw-bfs", kind="open", media="youtube", media_ref="s-CYnVz-uh4", topic="Algorithms",
         title="Breadth-First Search (full lecture)",
         description="BFS on graphs: shortest paths in unweighted networks like a friend graph.",
         license=CC_NC_SA, credit=OCW, source_url="https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-13-breadth-first-search-bfs/"),
    dict(slug="ocw-linalg", kind="open", media="youtube", media_ref="J7DzL2_Na80", topic="Math",
         title="The Geometry of Linear Equations (Gilbert Strang)",
         description="Lecture 1 of MIT's 18.06 Linear Algebra, a foundation for machine learning and quantum computing.",
         license=CC_NC_SA, credit="MIT OpenCourseWare · 18.06 Linear Algebra (Spring 2010) · Prof. Gilbert Strang",
         source_url="https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/resources/lecture-1-the-geometry-of-linear-equations/"),
]

# Reference library: (group, title, by, licence, url, note)
REFERENCES = [
    dict(group="Open textbooks", title="Open Data Structures", by="Pat Morin",
         license="CC BY 2.5 (Canada)", url="https://opendatastructures.org/",
         note="Free HTML/PDF with Python, Java and C++ editions. Covers hash tables, AVL-style trees and heaps."),
    dict(group="Open textbooks", title="Algorithms", by="Jeff Erickson",
         license="CC BY 4.0", url="https://jeffe.cs.illinois.edu/teaching/algorithms/",
         note="Free PDF. Great for graph search (BFS/DFS), recursion and dynamic programming."),
    dict(group="Free courses", title="MIT 6.006 Introduction to Algorithms (Fall 2011)", by="MIT OpenCourseWare",
         license="CC BY-NC-SA 4.0", url="https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/",
         note="24 lecture videos, notes and problem sets. The lectures in the Reels tab come from here."),
    dict(group="Free courses", title="MIT 18.06 Linear Algebra (Spring 2010)", by="MIT OpenCourseWare · Gilbert Strang",
         license="CC BY-NC-SA 4.0", url="https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
         note="The classic linear algebra course, useful for ML and quantum computing."),
    dict(group="Free courses", title="CS50x: Introduction to Computer Science", by="Harvard",
         license="Free to take as OpenCourseWare (see the course's licence page)", url="https://cs50.harvard.edu/x/",
         note="Beginner-friendly; Week 5 covers data structures (hash tables, tries, linked lists)."),
    dict(group="Docs used in this project", title="Flask documentation", by="Pallets",
         license="BSD-3-Clause (Flask)", url="https://flask.palletsprojects.com/",
         note="The web framework behind the CampusConnect API."),
    dict(group="Docs used in this project", title="SQLite documentation", by="SQLite developers",
         license="Public domain", url="https://www.sqlite.org/docs.html",
         note="The database. The software and its docs are dedicated to the public domain."),
    dict(group="Docs used in this project", title="Gemini API documentation", by="Google",
         license="Google API docs (the API itself is not open source)", url="https://ai.google.dev/gemini-api/docs",
         note="Used for safety checks and the Mochi pet chatbot."),
    dict(group="Related papers (from our project deck)", title="ViSSR: A Visual Analytics System for Student High-Order Social Relationships at Campus",
         by="X. Li, H. Cheng, S. An, Y. Zhang, Y. Zhang · Intelligent Data Analysis, 2025", license="See publisher",
         url="https://journals.sagepub.com/doi/10.3233/IDA-230263",
         note="Graph-based modelling of student relationships on campus."),
    dict(group="Related papers (from our project deck)", title="Friends Recommendation in Dynamic Social Networks Using Breadth-First Search Algorithm",
         by="R. Pira, J. Domi, B. Qehaja, E. Hajrizi · UBT International Conference, 2025", license="See publisher",
         url="https://knowledgecenter.ubt-uni.net/conference/2025UBTIC/CS/42",
         note="BFS-based friend recommendation, which is the approach behind our \"People you may know\"."),
    dict(group="Related papers (from our project deck)", title="A Case Study of University Student Networks and the COVID-19 Pandemic Using a Social Network Analysis Approach in Halls of Residence",
         by="J. A. Benítez-Andrades et al. · Scientific Reports, 2021", license="Open access (see article)",
         url="https://www.nature.com/articles/s41598-021-94383-2",
         note="Social network analysis of university student networks."),
]
