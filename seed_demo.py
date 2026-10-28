"""Fill CampusConnect with sample classmates, friendships, groups, posts and events.

    python seed_demo.py              # add demo data, befriend every real account
    python seed_demo.py --reset      # remove the demo data again
    python seed_demo.py --db path    # use a different SQLite file

Run it while the server is stopped, then start the server again (the in-memory
graph, trie and AVL tree are rebuilt from SQLite at startup).

Demo students get a first.last address on their own college's domain (for example amrita.edu) and
get a random password, so nobody can log in as them. Everything is written
straight to the database, so it skips the safety checks on purpose.
"""

import argparse
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEMO_DOMAIN = "demo.campusconnect.edu"

# name, major, year, interests, bio
STUDENTS = [
    ("Aarav Menon", "Computer Science", "3rd year", "graphs, competitive programming, Python", "Solving one graph problem a day. Ask me about BFS vs DFS."),
    ("Diya Nair", "Information Science", "3rd year", "databases, SQL, system design", "Normalisation fan. I explain DBMS with chai analogies."),
    ("Rohan Iyer", "Computer Science", "2nd year", "operating systems, C, Linux", "Writing a tiny shell for the OS lab."),
    ("Meera Krishnan", "Electronics", "4th year", "signals, embedded systems, MATLAB", "Placement season survivor. Happy to share notes."),
    ("Kabir Shetty", "Computer Science", "3rd year", "machine learning, statistics", "Currently stuck on gradient descent intuition."),
    ("Ananya Rao", "Mathematics", "2nd year", "linear algebra, proofs, LaTeX", "Linear algebra is secretly geometry."),
    ("Vikram Hegde", "Mechanical", "4th year", "thermodynamics, CAD, GATE prep", "GATE 2027 aspirant. Study group organiser."),
    ("Sneha Patil", "Information Science", "1st year", "web development, JavaScript", "New here. Learning HTML, CSS and a bit of JS."),
    ("Arjun Reddy", "Computer Science", "4th year", "placements, aptitude, interviews", "Mock interview buddy. DM me for practice slots."),
    ("Ishita Bhat", "Biotechnology", "3rd year", "genetics, python for biology", "Bringing Python to the wet lab."),
    ("Dev Kulkarni", "Computer Science", "2nd year", "algorithms, trees, recursion", "AVL rotations finally clicked for me last night."),
    ("Nandini Gowda", "Civil", "3rd year", "structural analysis, AutoCAD", "Beams, loads and way too many diagrams."),
    ("Tanvi Joshi", "Electronics", "2nd year", "digital logic, Verilog", "Karnaugh maps are my happy place."),
    ("Harsh Vardhan", "Computer Science", "1st year", "C programming, pointers", "Pointers are scary. Help appreciated."),
    ("Pooja Shenoy", "Information Science", "4th year", "cloud, networking, DevOps", "Preparing for a cloud certification."),
    ("Siddharth Nambiar", "Mathematics", "3rd year", "probability, statistics, R", "Probability puzzles over coffee."),
]

# Friendships between demo students (indices into STUDENTS).
EDGES = [
    (0, 1), (0, 2), (0, 4), (1, 2), (1, 8), (2, 10), (3, 8), (3, 14), (4, 5), (4, 15),
    (5, 15), (5, 10), (6, 11), (6, 12), (7, 13), (7, 10), (8, 9), (9, 15), (10, 13),
    (11, 12), (12, 3), (13, 14), (14, 8), (2, 13), (0, 10),
]
# Demo students who become friends of every real account (level 1 in the graph).
DIRECT = [0, 1, 2, 3, 4]

GROUPS = [
    ("DSA Study Circle", "Data Structures and Algorithms", 0, [0, 1, 2, 4, 8, 10, 13]),
    ("DBMS Doubts", "Databases and SQL", 1, [1, 2, 7, 9, 14]),
    ("Placement Prep 2027", "Aptitude and interviews", 8, [0, 3, 8, 14, 6]),
    ("OS Lab Helpers", "Operating Systems", 2, [2, 10, 13, 0]),
    ("Maths for ML", "Linear algebra and probability", 5, [4, 5, 15, 9]),
]

# author, group index or None, text, hours ago, liked-by, comments [(author, text)]
POSTS = [
    (0, None, "BFS explores level by level using a queue, DFS dives deep using a stack. For shortest paths in an unweighted graph, BFS is the one that guarantees the answer. Here is how I remember it: a queue is fair, a stack is greedy.",
     3, [1, 2, 4, 10, 13, 8], [(10, "This helped. I was mixing up which one uses the queue."), (2, "Add that DFS can be recursive, so the call stack is the stack.")]),
    (1, None, "Quick revision for the DBMS test: 1NF means atomic values, 2NF removes partial dependency, 3NF removes transitive dependency. Which normal form did you find hardest?",
     6, [0, 2, 7, 9], [(7, "3NF. Transitive dependency never sticks in my head."), (1, "Try this: every non-key attribute depends on the key, the whole key and nothing but the key.")]),
    (10, 0, "AVL rotations finally clicked. A left-left imbalance needs one right rotation. A left-right imbalance needs a left rotation on the child first, then a right rotation on the node. Drawing the three nodes on paper makes it obvious.",
     9, [0, 1, 2, 4, 8], [(0, "Our project uses an AVL tree for the chronological feed, so this is useful for the viva too.")]),
    (4, None, "Can someone explain why we subtract the gradient in gradient descent? I understand the update rule but not the intuition.",
     11, [5, 15], [(5, "The gradient points uphill, so moving the opposite way takes you downhill on the loss surface."), (15, "Think of a ball rolling down a bowl. The gradient is the slope under the ball.")]),
    (8, None, "Placement tip: for aptitude, practise time and work and percentages first. They carry the most marks for the least effort. For interviews, explain your approach out loud before writing code.",
     14, [0, 3, 14, 6, 9], [(3, "Adding probability and permutations to this list. They show up in almost every test.")]),
    (2, 3, "Operating Systems lab: my shell now runs commands with fork and exec. Next I am adding pipes. If you have a clean way to explain file descriptors, please share.",
     20, [10, 13, 0], [(10, "dup2 is the key function for pipes. Draw the descriptor table before and after."), (13, "Would love a walkthrough of this in the group.")]),
    (5, 4, "Linear algebra tip: an eigenvector is a direction that a matrix only stretches or flips, never rotates. The eigenvalue tells you by how much.",
     26, [4, 15, 9, 0], [(4, "Why does this matter for PCA?"), (5, "PCA keeps the eigenvectors of the covariance matrix with the biggest eigenvalues, the directions with the most variance.")]),
    (12, None, "Digital logic revision: a Karnaugh map groups adjacent ones in powers of two. Larger groups give simpler expressions. Do not forget that the edges wrap around.",
     30, [3, 6, 11], [(3, "Wrap-around groups are the ones everyone misses in exams.")]),
    (13, None, "Why does a C pointer to an int move by 4 bytes when I add 1? Is that always the case?",
     34, [7, 10], [(2, "Pointer arithmetic scales by the size of the type, so it is sizeof(int) bytes, usually 4 but not guaranteed."), (10, "Try printing the addresses before and after. Seeing it helps.")]),
    (14, None, "Cloud certification study plan: week one for networking basics, week two for compute and storage, week three for security and billing, week four for practice exams. Anyone want to join?",
     41, [3, 8, 13], []),
    (9, None, "Using Python to count GC content in a DNA sequence took five lines with a dictionary. Biology students, give it a try, it is a gentle way into programming.",
     48, [15, 7, 10, 4], [(15, "Nice. Next try finding the reverse complement.")]),
    (15, 4, "Probability puzzle for the group: you roll two fair dice. What is the probability that the sum is at least 10? Post your working, not just the answer.",
     52, [5, 4, 9], [(5, "6 favourable outcomes out of 36, so 1/6."), (4, "Agreed. Outcomes are (4,6), (5,5), (5,6), (6,4), (6,5), (6,6).")]),
    (6, 2, "GATE preparation: solve previous year questions by topic, not by year. It shows you which topics repeat and where you are weak.",
     60, [11, 3, 8], []),
    (7, None, "First week of web development: I built a page with HTML and a bit of CSS. How do you decide between flexbox and grid for layouts?",
     70, [10, 13], [(10, "Flexbox for one direction, a row or a column. Grid when you need rows and columns together.")]),
]

EVENTS = [
    ("Data Structures Revision Workshop", "Trees, graphs and heaps with worked examples. Bring your doubts.", 2),
    ("Mock Technical Interview Day", "One-on-one practice interviews with seniors from the placement cell.", 5),
    ("SQL and Database Design Lab", "Hands-on session on joins, indexes and ER diagrams.", 9),
    ("Aptitude Test Series: Round 1", "A timed quantitative and logical reasoning test with solutions.", 14),
    ("Research Paper Reading Club", "We read and discuss one paper each month. This month: graph algorithms.", 21),
]

ANNOUNCEMENTS = [
    ("Library hours extended for exam week", "The central library stays open until 10 pm from Monday until the end of the internal assessments. Bring your ID card."),
    ("Project review schedule released", "Departments have published the mini-project review slots. Check your department notice board and confirm your team's slot."),
]

RESOURCES = [
    ("VisuAlgo: visualising algorithms", "https://visualgo.net", "Step-by-step animations for sorting, trees, graphs and more.", 0),
    ("NPTEL courses", "https://nptel.ac.in", "Free lectures from the IITs and IISc across engineering subjects.", 3),
    ("CSES Problem Set", "https://cses.fi/problemset/", "A well-ordered set of algorithm problems for practice.", 8),
    ("CS50: Introduction to Computer Science", "https://cs50.harvard.edu/x/", "A friendly open course covering C, Python, SQL and web basics.", 7),
]


# ---------------------------------------------------------------------------
# More variety: extra students, groups, posts (some with YouTube lectures), events, links and reel comments.
# Appended after the lists above so earlier indices stay valid.
# ---------------------------------------------------------------------------
STUDENTS += [
    ("Kavya Subramaniam", "Chemical", "2nd year", "process control, thermodynamics, MATLAB", "Learning to model reactors in MATLAB."),
    ("Aditya Rao", "Computer Science", "3rd year", "web development, React, APIs", "Building one small full-stack project every month."),
    ("Nisha Pillai", "Economics", "3rd year", "econometrics, statistics, R", "Regression is my favourite tool."),
    ("Ravi Teja", "Civil", "2nd year", "surveying, structural analysis, AutoCAD", "Sharing my surveying lab notes."),
]
EDGES += [(16, 3), (16, 11), (17, 7), (17, 0), (17, 10), (18, 15), (18, 5), (19, 11), (19, 6)]
GROUPS += [
    ("Web Dev Builders", "HTML, CSS, JavaScript and Flask projects", 17, [17, 7, 0, 10, 13]),
    ("Research Paper Club", "Reading and summarising one paper a week", 5, [5, 4, 15, 18, 9]),
    ("Competitive Programming", "Contest problems and editorial discussions", 10, [10, 0, 1, 13, 17]),
]
# (author, group, text, hours ago, liked-by, comments, optional (youtube id, title))
POSTS += [
    (0, None, "Watch this before the graph quiz: a full MIT lecture on breadth-first search. The way it builds shortest paths level by level is exactly what our friend suggestions use.",
     4, [1, 2, 4, 10, 13, 17], [(13, "Watched the first twenty minutes. The queue walkthrough is very clear."), (4, "Is the shortest path proof in this one?")],
     ("s-CYnVz-uh4", "Breadth-First Search (full lecture)")),
    (10, None, "AVL trees explained properly in this lecture. Watch the part about balance factors and then try the rotations on paper yourself.",
     10, [0, 1, 2, 8], [(1, "Pausing at each insertion and drawing the tree helped me a lot.")],
     ("FNeL18KsWPc", "AVL Trees & AVL Sort (full lecture)")),
    (1, None, "Hash tables lecture recommendation. Chaining, load factor and resizing are all covered, and it matches how our login lookup works.",
     16, [0, 2, 7, 13], [(7, "Thanks! The collision section finally made load factor make sense.")],
     ("0M_kIqhwbFo", "Hashing with Chaining (full lecture)")),
    (13, None, "Heaps and heap sort in one lecture. Good revision for the priority queue topic, and it explains why the trending posts list is built with a heap.",
     22, [10, 0, 17], [], ("B7hVxCmfPtM", "Heaps and Heap Sort (full lecture)")),
    (5, 4, "Linear algebra lecture to start the week. If vectors and matrices still feel abstract, this one builds the intuition step by step.",
     28, [4, 15, 9, 18], [(15, "Adding this to our reading list for the group.")],
     ("J7DzL2_Na80", "Linear Algebra lecture")),
    (3, None, "Signals revision: the Fourier transform tells you which frequencies a signal contains. Plot a square wave and its first five harmonics and the idea becomes visual.",
     8, [8, 6, 16], [(16, "Can this be used to filter noise in a sensor reading?"), (3, "Yes, remove the frequencies that are mostly noise and transform back.")]),
    (17, 5, "Web development tip: build the layout with plain HTML first, then add CSS, then JavaScript. Each layer should still work if the next one fails.",
     5, [7, 0, 10, 13], [(7, "This progressive approach saved my first project."), (0, "Also validate input on the server, not only in the browser.")]),
    (17, 5, "Flask mini project idea: a timetable clash checker. Model classes as nodes, shared students as edges, and colour the graph so no two clashing classes share a slot.",
     12, [0, 10, 7], []),
    (18, None, "Statistics reminder: correlation does not imply causation. Before you trust a regression result, check for a hidden variable that affects both sides.",
     18, [15, 5, 9], [(15, "A good example is ice cream sales and sunburn, both driven by hot weather.")]),
    (16, None, "Chemical engineering study tip: write the mass balance first, always. Input minus output plus generation equals accumulation, and most process problems start from it.",
     24, [11, 3], [(11, "This is how I start every thermodynamics problem too.")]),
    (19, None, "Surveying lab notes: always do a closing check on a traverse. The misclosure tells you whether to trust your readings before you start the calculations.",
     32, [11, 6, 16], []),
    (4, 6, "Paper for this week: Attention Is All You Need. Read the abstract and the section on scaled dot-product attention first, then the rest. We discuss on Sunday.",
     7, [5, 15, 18, 9], [(5, "I will bring a worked example with a three-word sentence."), (18, "Is the positional encoding section in scope?")]),
    (15, 6, "Reading tip for research papers: read the abstract, then the conclusion, then the figures, and only then the method. You will know early whether the paper is worth your time.",
     36, [4, 5, 9], [(9, "Adding: keep a one-line summary of each paper in a notebook.")]),
    (10, 7, "Contest lesson: when a problem has n up to 100000, an O(n squared) solution will time out. Look for sorting, a hash map or two pointers first.",
     13, [0, 1, 13, 17], [(1, "Prefix sums also solve a surprising number of these."), (13, "Remember to test the edge cases: n equal to 1 and all equal values.")]),
    (8, None, "Exam strategy: do a timed practice paper every Sunday, then spend double the time reviewing mistakes. The review is where the marks come from.",
     44, [0, 3, 14, 6, 16], [(14, "Keeping an error log by topic made my revision much more focused.")]),
    (14, None, "Networking revision: TCP gives reliable ordered delivery with a handshake, UDP trades reliability for speed. Which one would you use for a live lecture stream, and why?",
     50, [3, 8, 13], [(13, "UDP-based protocols, since a late packet is useless in a live stream."), (3, "But recorded lectures usually use TCP so nothing is lost.")]),
    (11, None, "Structural analysis reminder: draw the free body diagram before writing any equation. Most sign errors disappear once the forces are on the paper.",
     56, [19, 12, 16], []),
    (9, None, "Scholarship reminder for final years: check the eligibility criteria, prepare your documents early, and ask your department for the recommendation letters well before the deadline.",
     62, [15, 7, 10], [(15, "Thanks for the reminder, the deadline is closer than I thought.")]),
    (2, 3, "Linux lab tip: use man and the help flag before searching the web. Reading the manual page for grep and sed once saved me hours across the semester.",
     66, [10, 13, 0], []),
]
EVENTS += [
    ("Intro to Web Development Bootcamp", "Two-day hands-on workshop: HTML, CSS, JavaScript and a small Flask backend.", 4),
    ("Machine Learning Reading Group", "We discuss one paper on attention models. Bring your questions and notes.", 7),
    ("Competitive Programming Contest", "Two-hour team contest with problems on graphs, greedy and dynamic programming.", 11),
    ("Scholarship Information Session", "How to find scholarships, prepare documents and write a strong application.", 17),
    ("Research Methods Seminar", "Choosing a topic, reading papers efficiently and writing a short literature review.", 24),
]
ANNOUNCEMENTS += [
    ("Lab record submission dates", "Submit your completed lab records to the department office before the internal viva. Late submissions are not evaluated."),
    ("Guest lecture on cloud computing", "An industry speaker will talk about cloud architecture and careers in the seminar hall on Friday. Attendance counts for the seminar credit."),
]
RESOURCES += [
    ("Khan Academy: Linear algebra", "https://www.khanacademy.org/math/linear-algebra", "Free video lessons and practice for vectors, matrices and transformations.", 5),
    ("MIT OpenCourseWare", "https://ocw.mit.edu", "Lecture notes, assignments and exams from real MIT courses.", 10),
    ("CP-Algorithms", "https://cp-algorithms.com", "Clear articles on algorithms and data structures with code.", 13),
    ("MDN Web Docs", "https://developer.mozilla.org", "The reference for HTML, CSS and JavaScript with tutorials.", 17),
    ("scikit-learn user guide", "https://scikit-learn.org/stable/user_guide.html", "Practical machine learning in Python with worked examples.", 4),
    ("arXiv: computer science papers", "https://arxiv.org/list/cs/recent", "Recent research papers, free to read, for your paper-reading practice.", 15),
    ("Developer roadmaps", "https://roadmap.sh", "Step-by-step learning paths for web, data and systems careers.", 7),
]
# (reel slug, author index, comment)
REEL_COMMENTS = [
    ("ocw-bfs", 13, "The queue trace at the start makes the level-by-level idea very clear."),
    ("ocw-bfs", 4, "Does the lecture prove why BFS gives the shortest path in unweighted graphs?"),
    ("ocw-avl", 1, "Pause at each insertion and draw the rotation yourself. It sticks better."),
    ("ocw-hashing", 7, "Great for understanding load factor before the DBMS indexing chapter."),
    ("ocw-linalg", 15, "Watch this before the eigenvalue topic. Strongly recommended."),
]


# Sample classmates study at different well-known Indian institutions (index matches STUDENTS).
AMRITA = "Amrita Vishwa Vidyapeetham"
SRM = "SRM Institute of Science and Technology"
VIT = "Vellore Institute of Technology"
IITM = "IIT Madras"
IITB = "IIT Bombay"
NITT = "NIT Tiruchirappalli"
BITS = "BITS Pilani"
IIITH = "IIIT Hyderabad"
PSG = "PSG College of Technology"
ANNA = "Anna University"
IISC = "Indian Institute of Science, Bangalore"
DU = "University of Delhi"
COLLEGE_OF = [AMRITA, AMRITA, SRM, VIT, IITM, IISC, NITT, AMRITA, BITS, VIT,
              IITB, ANNA, SRM, IIITH, PSG, IITM, AMRITA, SRM, DU, VIT]
DEFAULT_COLLEGE = AMRITA      # its sample events/announcements are copied to colleges that have none
# college for each of the 10 events and 4 announcements, in list order
EVENT_COLLEGES = [AMRITA, SRM, VIT, IITM, AMRITA, IITB, BITS, AMRITA, NITT, IIITH]
ANNOUNCEMENT_COLLEGES = [AMRITA, SRM, VIT, IITM]


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Each sample student gets an address on their own college's domain (fictional people; nobody can log in as them).
COLLEGE_DOMAIN = {
    AMRITA: "amrita.edu", SRM: "srmist.edu.in", VIT: "vit.ac.in", IITM: "smail.iitm.ac.in", IITB: "iitb.ac.in",
    NITT: "nitt.edu", BITS: "pilani.bits-pilani.ac.in", IIITH: "students.iiit.ac.in", PSG: "psgtech.ac.in",
    ANNA: "annauniv.edu", IISC: "iisc.ac.in", DU: "du.ac.in",
}


def demo_email(name):
    college = COLLEGE_OF[[s[0] for s in STUDENTS].index(name)]
    return name.lower().replace(" ", ".") + "@" + COLLEGE_DOMAIN[college]


IS_DEMO = "(SELECT user_id FROM demo_users)"      # demo students are tracked in a table, not by e-mail address


def reset(conn):
    ensure_tables(conn)
    conn.execute(f"DELETE FROM users WHERE id IN {IS_DEMO}")
    conn.execute("DELETE FROM demo_users")
    conn.commit()
    conn.execute("DELETE FROM demo_welcome")
    conn.execute("INSERT OR IGNORE INTO demo_state (key) VALUES ('seeded')")   # stay removed on the next start
    conn.commit()
    print("Removed all demo students and everything they created.")


def has_demo(conn):
    return conn.execute("SELECT 1 FROM demo_users").fetchone() is not None


def ensure_tables(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS demo_state (key TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS demo_welcome (user_id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS demo_users (user_id INTEGER PRIMARY KEY)")
    # Databases seeded by an earlier version used @demo.campusconnect.edu addresses and one college: upgrade them.
    for i, (name, *_rest) in enumerate(STUDENTS):
        old = conn.execute("SELECT id FROM users WHERE email = ?", (name.lower().replace(" ", ".") + "@" + DEMO_DOMAIN,)).fetchone()
        if old:
            conn.execute("UPDATE users SET email = ?, college = ? WHERE id = ?", (demo_email(name), COLLEGE_OF[i], old["id"]))
            conn.execute("INSERT OR IGNORE INTO demo_users (user_id) VALUES (?)", (old["id"],))


def auto_seed(conn):
    """Called when the app starts (unless CC_DEMO_DATA=0): add the sample data once. Running
    `python seed_demo.py --reset` removes it for good; it is not re-added on the next start."""
    ensure_tables(conn)
    if conn.execute("SELECT 1 FROM demo_state WHERE key = 'seeded'").fetchone():
        conn.commit()           # keeps the e-mail/college upgrade done by ensure_tables
        return False
    if not has_demo(conn):
        seed(conn, quiet=True)
    conn.execute("INSERT OR IGNORE INTO demo_state (key) VALUES ('seeded')")
    conn.commit()
    return True


def copy_samples_to_college(conn, college):
    """Events and announcements are per college. If this college has no sample ones, copy the default college's."""
    demo_where = f"created_by IN {IS_DEMO}"
    if conn.execute(f"SELECT 1 FROM events WHERE college = ? AND {demo_where}", (college,)).fetchone():
        return
    for r in conn.execute(f"SELECT * FROM events WHERE college = ? AND {demo_where}", (DEFAULT_COLLEGE,)).fetchall():
        conn.execute("INSERT INTO events (title, description, college, event_date, created_by) VALUES (?, ?, ?, ?, ?)",
                     (r["title"], r["description"], college, r["event_date"], r["created_by"]))
    for r in conn.execute(f"SELECT * FROM announcements WHERE college = ? AND {demo_where}", (DEFAULT_COLLEGE,)).fetchall():
        conn.execute("INSERT INTO announcements (title, body, college, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                     (r["title"], r["body"], college, r["created_by"], r["created_at"]))


def introduce(conn, user_id):
    """Once per real student: make the first few sample classmates their friends, put them in the first two
    groups, and make sure their college has sample events and announcements. Returns the new friend ids."""
    ensure_tables(conn)
    if conn.execute("SELECT 1 FROM demo_welcome WHERE user_id = ?", (user_id,)).fetchone() or not has_demo(conn):
        return []
    me = conn.execute("SELECT email, college FROM users WHERE id = ?", (user_id,)).fetchone()
    if me is None or conn.execute("SELECT 1 FROM demo_users WHERE user_id = ?", (user_id,)).fetchone():
        return []
    hubs = [conn.execute("SELECT id FROM users WHERE email = ?", (demo_email(STUDENTS[i][0]),)).fetchone() for i in DIRECT]
    hubs = [h["id"] for h in hubs if h]
    for h in hubs:
        conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)", (user_id, h))
        conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)", (h, user_id))
    for g in conn.execute(f"SELECT id FROM groups WHERE created_by IN {IS_DEMO} ORDER BY id LIMIT 2").fetchall():
        conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)", (g["id"], user_id))
    copy_samples_to_college(conn, me["college"])
    conn.execute("INSERT OR IGNORE INTO demo_welcome (user_id) VALUES (?)", (user_id,))
    conn.commit()
    return hubs


def seed(conn, quiet=False):
    ensure_tables(conn)
    if has_demo(conn):
        if not quiet:
            print("Demo data is already there. Run with --reset first to rebuild it.")
        return
    real = conn.execute(f"SELECT id, full_name, college FROM users WHERE id NOT IN {IS_DEMO} ORDER BY id").fetchall()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    ids = []
    for name, major, year, interests, bio in STUDENTS:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, full_name, college, verified, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (demo_email(name), generate_password_hash(secrets.token_hex(16)), name, COLLEGE_OF[len(ids)], ts(now - timedelta(days=30))))
        ids.append(cur.lastrowid)
        conn.execute("INSERT INTO demo_users (user_id) VALUES (?)", (cur.lastrowid,))
        conn.execute("INSERT INTO profiles (user_id, bio, major, year, interests) VALUES (?, ?, ?, ?, ?)",
                     (cur.lastrowid, bio, major, year, interests))

    def befriend(a, b):
        conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)", (a, b))
        conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)", (b, a))

    for a, b in EDGES:
        befriend(ids[a], ids[b])
    for user in real:
        for i in DIRECT:
            befriend(user["id"], ids[i])

    group_ids = []
    for name, topic, owner, members in GROUPS:
        cur = conn.execute("INSERT INTO groups (name, topic, created_by, created_at) VALUES (?, ?, ?, ?)",
                           (name, topic, ids[owner], ts(now - timedelta(days=20))))
        gid = cur.lastrowid
        group_ids.append(gid)
        for m in set(members) | {owner}:
            conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)", (gid, ids[m]))
    for user in real:                      # real accounts start in the first two groups
        for gid in group_ids[:2]:
            conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)", (gid, user["id"]))

    for author, group, text, hours, likers, comments, *rest in POSTS:
        created = now - timedelta(hours=hours)
        vid, vtitle = rest[0] if rest else ("", "")
        cur = conn.execute("INSERT INTO posts (author_id, group_id, content, likes, created_at, video, video_title) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (ids[author], group_ids[group] if group is not None else None, text, len(likers), ts(created), vid, vtitle))
        pid = cur.lastrowid
        for liker in likers:
            conn.execute("INSERT OR IGNORE INTO post_likes (post_id, user_id) VALUES (?, ?)", (pid, ids[liker]))
        for n, (c_author, c_text) in enumerate(comments, start=1):
            conn.execute("INSERT INTO comments (post_id, author_id, content, created_at) VALUES (?, ?, ?, ?)",
                         (pid, ids[c_author], c_text, ts(created + timedelta(minutes=12 * n))))

    def organiser(college):                # first sample student at that college
        return ids[COLLEGE_OF.index(college)]

    for (title, desc, days), college in zip(EVENTS, EVENT_COLLEGES):
        conn.execute("INSERT INTO events (title, description, college, event_date, created_by) VALUES (?, ?, ?, ?, ?)",
                     (title, desc, college, (now + timedelta(days=days)).date().isoformat(), organiser(college)))
    for n, ((title, body), college) in enumerate(zip(ANNOUNCEMENTS, ANNOUNCEMENT_COLLEGES)):
        conn.execute("INSERT INTO announcements (title, body, college, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                     (title, body, college, organiser(college), ts(now - timedelta(hours=5 + 20 * n))))
    for college in {r["college"] for r in real}:      # students already signed up get samples for their college too
        copy_samples_to_college(conn, college)
    for title, url, desc, who in RESOURCES:
        conn.execute("INSERT INTO resources (title, url, description, added_by, created_at) VALUES (?, ?, ?, ?, ?)",
                     (title, url, desc, ids[who], ts(now - timedelta(hours=8 + who))))
    reel_ids = {r["slug"]: r["id"] for r in conn.execute("SELECT id, slug FROM reels")}
    for n, (slug, author, text) in enumerate(REEL_COMMENTS):
        if slug in reel_ids:
            conn.execute("INSERT INTO reel_comments (reel_id, author_id, content, created_at) VALUES (?, ?, ?, ?)",
                         (reel_ids[slug], ids[author], text, ts(now - timedelta(hours=3 + 5 * n))))
    for user in real:
        conn.execute("INSERT OR IGNORE INTO demo_welcome (user_id) VALUES (?)", (user["id"],))
    conn.execute("INSERT OR IGNORE INTO demo_state (key) VALUES ('seeded')")
    conn.commit()
    if quiet:
        return
    who = ", ".join(r["full_name"] for r in real) or "nobody yet"
    print(f"Added {len(ids)} students across {len(set(COLLEGE_OF))} colleges, {len(GROUPS)} groups, {len(POSTS)} posts, "
          f"{len(EVENTS)} events and {len(RESOURCES)} shared links.")
    print(f"Befriended real accounts: {who}. Restart the server to see it.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="remove demo data instead of adding it")
    ap.add_argument("--db", default=os.environ.get("CC_DATABASE_PATH") or os.path.join(BASE_DIR, "instance", "campusconnect.db"))
    args = ap.parse_args()
    if not os.path.exists(args.db):
        raise SystemExit(f"No database at {args.db}. Start the app once (python run.py) and sign up, then run this.")
    db = connect(args.db)
    try:
        reset(db) if args.reset else seed(db)
    finally:
        db.close()
