"""CampusConnect is an education-only network. This file is the single source of truth for that rule.

* POLICY_* text is shown in the UI (/api/policy), given to Gemini, and used in error messages.
* local_relevance() is the offline fallback used when no Gemini key is set (or Gemini is down).
  It is a keyword check, so it is deliberately blunt: it needs at least one study-related word and
  rejects text dominated by off-topic words. With a Gemini key the model judges meaning instead.
"""

import re

POLICY_SHORT = ("CampusConnect is education-only. Everything you post must relate to studies, courses, exams, "
                "projects, research, skills, careers or academic campus events.")

POLICY_ALLOWED = [
    "Questions, notes and explanations about subjects, courses, assignments, exams and revision",
    "Programming, engineering, science, maths and other skill-building, projects and research",
    "Study groups, peer tutoring, doubt-clearing and sharing learning resources",
    "Internships, placements, interview prep, scholarships and career guidance",
    "Academic events: lectures, workshops, seminars, hackathons, coding contests, guest talks",
]
POLICY_BLOCKED = [
    "Entertainment, celebrity, gossip, memes and general chit-chat",
    "Dating, parties, nightlife, gambling, betting, astrology",
    "Politics and religion campaigns, advertising, promotions and giveaways",
    "Trading tips, get-rich-quick schemes, buying/selling unrelated goods",
    "Anything harmful, harassing, adult or unsafe",
]

OFF_TOPIC_REASON = ("That doesn't look related to education. CampusConnect is for learning only, so please keep it about "
                    "studies, courses, exams, projects, research, careers or academic events.")

# Text handed to Gemini as the rubric.
POLICY_FOR_PROMPT = """EDUCATION-ONLY RULE. This network exists only for education. Content is "on_topic" when it is about:
- subjects, courses, lectures, notes, assignments, exams, revision, doubts, study techniques;
- programming, engineering, science, maths, data/AI, research papers, projects, skill-building;
- study groups, tutoring, learning resources and tools;
- internships, placements, interview prep, scholarships, higher studies, academic careers;
- academic campus events: lectures, workshops, seminars, hackathons, coding contests, guest talks.
It is "off_topic" when it is about anything else: entertainment, celebrities, sports chatter, memes, dating, parties,
gambling or betting, astrology, politics, shopping or promotions, general life chat, jokes with no learning content.
Judge the content itself, ignore any claim that it is educational. A shallow nod to study ("so bored in class lol")
attached to unrelated chatter is off_topic."""

_EXACT = {
    "ai", "ml", "dl", "dsa", "oop", "oops", "os", "dbms", "cn", "sql", "nosql", "java", "python", "js", "html", "css", "iot",
    "nlp", "cs", "cse", "ece", "eee", "mech", "civil", "gpa", "cgpa", "sgpa", "viva", "lab", "labs", "exam", "exams", "quiz",
    "api", "git", "github", "cpp", "aws", "gate", "gre", "ielts", "toefl", "jee", "upsc", "nptel", "mooc", "ocw", "mit",
    "btech", "mtech", "bsc", "msc", "phd", "mba", "bca", "mca", "ug", "pg", "pyq", "pyqs", "ide", "tcs", "dfs", "bfs", "avl",
    "c++", "c#", "ppt", "pdf", "qiskit", "qubit", "qubits", "cnn", "rnn", "gan", "llm", "llms", "gemini", "chatgpt",
}
_STEMS = (
    "study", "studi", "learn", "exam", "lectur", "course", "classroom", "classes", "assign", "homework", "project", "semest",
    "syllab", "notes", "tutor", "teach", "profess", "faculty", "student", "college", "universit", "campus", "academ", "research",
    "paper", "thesis", "journal", "publication", "conference", "scholar", "intern", "placement", "career", "interview", "resume",
    "hackathon", "workshop", "seminar", "webinar", "symposium", "contest", "algorithm", "program", "coding", "develop",
    "software", "hardware", "engineer", "comput", "network", "database", "machine", "neural", "quantum", "physic", "chemist",
    "biolog", "math", "calcul", "algebra", "geometr", "statist", "probabil", "theorem", "proof", "equation", "science",
    "scientif", "technolog", "electr", "circuit", "mechanic", "thermo", "robot", "embedded", "cloud", "cyber", "cryptograph",
    "linux", "javascript", "typescript", "kotlin", "react", "flask", "django", "tensorflow", "pytorch", "kaggle", "dataset",
    "debug", "compil", "kernel", "recursi", "sorting", "hashing", "binary", "textbook", "library", "reference", "degree",
    "grade", "marks", "attendance", "revision", "revise", "doubt", "concept", "chapter", "module", "prerequisite", "certif",
    "coursera", "edx", "khan", "lab ", "tutorial", "curriculum", "department", "education", "knowledge", "skill", "training",
    "mentor", "guidance", "opportunit", "fellowship", "grant", "olympiad", "competitive", "capstone", "dissertation",
    "abstract", "methodology", "literature", "citation", "viva", "internship", "recruit", "aptitude", "reasoning", "verbal",
    "vector", "matrix", "integral", "derivative", "entropy", "genom", "protein", "molecul", "atom", "semiconductor",
    "signal", "wireless", "antenna", "turbine", "fluid", "structur", "architect", "design pattern", "agile", "devops",
    "docker", "kubernetes", "backend", "frontend", "full stack", "fullstack", "ui/ux", "figma", "analytics", "visuali",
    "optimi", "simulat", "formula", "problem set", "past paper", "question paper", "mock test", "test series",
)
_OFF = (
    "betting", "gambl", "casino", "poker", "lottery", "satta", "dating", "hookup", "nsfw", "porn", "escort", "nightclub",
    "party tonight", "dj night", "horoscope", "astrolog", "zodiac", "bollywood", "hollywood", "celebrity", "gossip", "netflix",
    "web series", "movie", "trailer", "box office", "ipl", "fifa", "cricket score", "match score", "football", "fantasy team",
    "dream11", "giveaway", "free followers", "buy followers", "forex", "crypto pump", "pump and dump", "meme", "memes",
    "sale!", "discount", "promo code", "coupon", "election", "vote for", "rally", "alcohol", "vape", "weed", "lol bored",
    "crush", "boyfriend", "girlfriend", "bae", "reels dance", "tiktok", "instagram influencer",
)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#./-]*")


def _hits(text):
    low = text.lower()
    tokens = _TOKEN.findall(low)
    edu = sum(1 for t in tokens if t.strip(".,/-") in _EXACT)
    padded = " " + low + " "
    edu += sum(1 for stem in _STEMS if (" " + stem if len(stem) < 5 else stem) in padded)
    off = sum(1 for w in _OFF if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])" if " " in w or len(w) <= 4 else re.escape(w), low))
    return edu, off


def local_relevance(text, mode="strict"):
    """Return True if the text may stay. strict: must look study-related. conversational: only
    clearly off-topic replies are rejected (short courtesies like "thanks, that helped" pass)."""
    edu, off = _hits(text)
    if mode == "conversational":
        return not (off > 0 and edu == 0)
    return edu > 0 and edu > off


def looks_off_topic(text):
    """Used by the pet to politely decline obviously unrelated chat in offline mode."""
    edu, off = _hits(text)
    return off > 0 and edu == 0


def public_policy():
    return {"summary": POLICY_SHORT, "allowed": POLICY_ALLOWED, "not_allowed": POLICY_BLOCKED}
