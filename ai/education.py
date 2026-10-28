"""Education-only gate.

CampusConnect is for learning, so everything students write must relate to
education: coursework, studying, exams, research, projects, skills, learning
resources, careers/placements, academic clubs and events, college academic notices.

Two layers (this module is the offline one):
  * `assess()` is a fast, deterministic word-list check. It returns
      "edu"     at least one education term and no stronger off-topic signal
      "mixed"   education AND off-topic terms (a human or Gemini should look)
      "off"     clearly off-topic (more off-topic terms than education terms)
      "unclear" no education term at all
  * ai/moderation.py then asks Gemini to judge "mixed"/"unclear" text strictly
    when a key is configured. Without a key, "unclear" is rejected (strict).

A word list can't understand context, so it is deliberately a first filter
rather than the only one: it lets obviously educational text through cheaply and
rejects obvious chit-chat, ads, memes and entertainment without any network call.
"""

import re
from dataclasses import dataclass, field

# --- education vocabulary --------------------------------------------------------------
# Prefix stems (matched at the start of a word; all >= 4 letters).
EDU_STEMS = """
stud learn teach educat lectur exam assign semest cours syllab curricul tutor quiz internship placement academ scholar
thesis disserta research journal paper publica conferenc workshop seminar webinar symposium hackath bootcamp certif
diploma degree graduat attendan timetabl homework textbook library revis algorithm data program coding softwar hardwar
comput cyber neural tensor pytorch tensorflow sklearn numpy pandas python java javascript typescript html react flask
django sqlite mongodb linux github compiler debug recursi graph sorting complexity leetcode codeforces hackerrank
mathemat calculus algebra geometr trigonomet statistic probabil physic quantum mechanic thermo optics electr circuit
signal semiconductor chemi biolog biotech genetic anatom physiolog pharma medic clinical nursing patholog econom
financ account commerce legal constitution psycholog sociolog philosoph histor geograph literature grammar english
linguist essay engineer robotic embedded arduino raspberry vlsi matlab simulink autocad solidworks faculty professor
depart laborator practical presentation capstone project scholarship fellowship citation plagiari bibliograph latex
overleaf zotero moodle coursera udemy nptel swayam recruit interview resume career aptitude upskill olympiad
doubt concept theory theorem proof formula equation marks grades classroom classes lecture ocw machine learning
neural vector matrix matrices binary array stack queue hashing recursion pointer database sql network protocol
cryptograph blockchain automata compiler operating kernel cloud devops docker kubernetes api framework
test rotat validat notebook mock node subtree traversal topic problem pattern explain revision exercise worksheet
""".split()
# Short or ambiguous terms matched as whole words only.
EDU_EXACT = set("""
ml ai dsa cn os dbms oop cgpa gpa sgpa ug pg btech mtech bsc msc mba phd bca mca iit nit iiit cse ece eee mech civil
it gate jee neet upsc gre toefl ielts cat gmat sat code coder css git sql api iot nlp cv ocr gan cnn rnn lstm bert llm
tree trie heap hash graph bfs dfs avl bst note notes class lab labs viva ppt abstract report poster review oral
college university school tuition prof dept hod syllabus quiz mit cs50 tutorial tutorials study studying learn
algo algos dp oops pyq pyqs ta ra internal practicals
""".split())

# --- off-topic vocabulary ---------------------------------------------------------------
OFF_STEMS = """
movie netflix anime manga meme prank celebrit bollywood hollywood kdrama kpop lyrics playlist concert singer
crush dating boyfriend girlfriend breakup hookup tinder gossip rumour rumor roast
party partying nightclub booze alcohol vodka whisky weed ganja vape cigarette
betting casino poker rummy lottery dream11 satta jackpot
discount coupon promo giveaway cashback dropship forex airdrop
followers instagram insta snapchat tiktok youtuber
cricket football soccer fifa kabaddi scorecard
pubg bgmi valorant fortnite minecraft freefire ludo
election horoscope astrolog temple church mosque
porn nsfw xxx
biryani pizza recipe swiggy zomato fashion outfit makeup skincare shopping vacation
""".split()
OFF_EXACT = set("""
bae song songs lol lmao rofl funny joke jokes sale buy sell selling offer offers ipl nba gta vote voting politics
political modi trump bjp rally dj pub beer bet dating date outing trip tour holiday party gym
""".split()) - {"date"}   # "date" appears in academic text ("date of exam")
OFF_PHRASES = [
    "web series", "k pop", "movie night", "good morning", "good night", "happy birthday", "dm me", "follow me",
    "link in bio", "check my insta", "subscribe to my", "free money", "earn money", "click here to win",
]

# Distress language gets a supportive note instead of an education rejection
# (a student in trouble shouldn't be told "that's off-topic").
DISTRESS = re.compile(r"(?i)\b(kill myself|end my life|want to die|suicid\w*|self[- ]?harm|hurt myself|no reason to live)\b")

URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-']*")

POLITE = re.compile(r"(?i)\b(thanks?|thank you|thx|great|nice|awesome|helpful|helped|got it|understood|clear|"
                    r"good point|well explained|appreciate\w*|useful|congrats?|well done|same here|agreed?|"
                    r"\+1|me too|please|pls|sure|ok(ay)?)\b")


@dataclass
class Assessment:
    label: str                       # edu | mixed | off | unclear
    edu_terms: list = field(default_factory=list)
    off_terms: list = field(default_factory=list)
    words: int = 0
    distress: bool = False


def _tokens(text):
    text = URL.sub(" ", text.lower())
    return [w.strip(".-'") for w in WORD.findall(text)], text


def assess(text):
    words, lowered = _tokens(text or "")
    words = [w for w in words if w]
    edu = [w for w in words if w in EDU_EXACT or any(w.startswith(s) for s in EDU_STEMS)]
    off = [w for w in words if w in OFF_EXACT or any(w.startswith(s) for s in OFF_STEMS)]
    off += [p for p in OFF_PHRASES if p in lowered]
    distress = bool(DISTRESS.search(text or ""))
    if off and len(off) > len(edu):
        label = "off"
    elif off:
        label = "mixed"
    elif edu:
        label = "edu"
    else:
        label = "unclear"
    return Assessment(label, edu[:6], off[:6], len(words), distress)


def is_polite_reply(text, max_words=12):
    """Short courtesy replies ("thanks, this helped!") are fine under an educational post."""
    a = assess(text)
    return a.label != "off" and not a.off_terms and a.words <= max_words and bool(POLITE.search(text))


OFF_TOPIC_MESSAGE = ("CampusConnect is for education only. Share something about your studies, courses, exams, "
                     "projects, research, skills or career preparation.")
