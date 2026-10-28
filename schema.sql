-- CampusConnect database schema

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    college         TEXT NOT NULL,
    verified        INTEGER NOT NULL DEFAULT 0,   -- 1 once the college email is confirmed
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id         INTEGER PRIMARY KEY,
    bio             TEXT DEFAULT '',
    major           TEXT DEFAULT '',
    year            TEXT DEFAULT '',
    interests       TEXT DEFAULT '',
    avatar_path     TEXT DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Friend network (undirected graph, stored as directed edges both ways
-- once a request is accepted; pending requests are one direction only).
CREATE TABLE IF NOT EXISTS friend_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id       INTEGER NOT NULL,
    receiver_id     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending, accepted, rejected
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (sender_id, receiver_id)
);

CREATE TABLE IF NOT EXISTS friendships (
    user_id         INTEGER NOT NULL,
    friend_id       INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, friend_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (friend_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS groups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    topic           TEXT NOT NULL,
    created_by      INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id        INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    joined_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id       INTEGER NOT NULL,
    group_id        INTEGER,
    content         TEXT NOT NULL,
    likes           INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         INTEGER NOT NULL,
    author_id       INTEGER NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    college         TEXT NOT NULL,
    event_date      TEXT NOT NULL,
    created_by      INTEGER NOT NULL,
    image           TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Shared links: study notes, articles, tools, past papers, etc.
CREATE TABLE IF NOT EXISTS resources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    description     TEXT DEFAULT '',
    added_by        INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_resources_created_at ON resources(created_at);

-- One row per (post, user) so a student can like a post only once.
CREATE TABLE IF NOT EXISTS post_likes (
    post_id         INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    PRIMARY KEY (post_id, user_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- College-scoped announcements (separate from event listings and shared links).
CREATE TABLE IF NOT EXISTS announcements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    college         TEXT NOT NULL,
    created_by      INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Email verification tokens (stored hashed; single use; expire after 24h).
CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash      TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    expires_at      TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_announcements_college ON announcements(college, created_at);
CREATE INDEX IF NOT EXISTS idx_events_college_date ON events(college, event_date);

-- Audit trail of safety checks. Text is only kept (first 120 chars) for blocked/flagged items.
CREATE TABLE IF NOT EXISTS moderation_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    verdict         TEXT NOT NULL,          -- allow, block, support
    categories      TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL,          -- local, gemini, unavailable
    excerpt         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_modlog_user_time ON moderation_log(user_id, created_at);

-- Reels: short educational videos. kind = prebuilt (animated in-browser), open (open-licensed lecture
-- embedded from its source) or community (a YouTube link a student shared). created_by is NULL for seeded rows.
CREATE TABLE IF NOT EXISTS reels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT UNIQUE,                       -- stable key for seeded reels
    kind            TEXT NOT NULL CHECK (kind IN ('prebuilt', 'open', 'community')),
    media           TEXT NOT NULL CHECK (media IN ('youtube', 'animation')),
    media_ref       TEXT NOT NULL,                     -- YouTube video id, or the animation's scene key
    start_seconds   INTEGER NOT NULL DEFAULT 0,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    topic           TEXT NOT NULL DEFAULT 'Other',
    license         TEXT NOT NULL DEFAULT '',
    credit          TEXT NOT NULL DEFAULT '',
    source_url      TEXT NOT NULL DEFAULT '',
    code_ref        TEXT NOT NULL DEFAULT '',          -- where this idea lives in the project (prebuilt only)
    created_by      INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS reel_likes (
    reel_id         INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    PRIMARY KEY (reel_id, user_id),
    FOREIGN KEY (reel_id) REFERENCES reels(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_reels_community_video ON reels(media_ref) WHERE kind = 'community';
CREATE INDEX IF NOT EXISTS idx_reels_kind_topic ON reels(kind, topic);

-- Saved ("bookmarked") posts, private to each student.
CREATE TABLE IF NOT EXISTS post_saves (
    post_id         INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (post_id, user_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Discussion under a reel (video / animation).
CREATE TABLE IF NOT EXISTS reel_comments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_id         INTEGER NOT NULL,
    author_id       INTEGER NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (reel_id) REFERENCES reels(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reel_comments ON reel_comments(reel_id, id);

-- Direct messages between friends (1:1 chat). read_at is NULL until the receiver opens the conversation.
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id       INTEGER NOT NULL,
    receiver_id     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    read_at         TEXT,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id, receiver_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(receiver_id, read_at);
