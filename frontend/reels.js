/* ============================================================
   Reels: animated explainers (original), embedded open lectures,
   community videos and a reference library.
   Depends on helpers from index.html: apiFetch, escapeHtml, showFlash,
   showToast, showAuth, ICONS, emptyState.
   ============================================================ */

/* ---------- tiny DOM helper (data never goes through innerHTML) ---------- */
function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
        if (v === false || v == null) continue;
        if (k === "class") el.className = v;
        else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v === true ? "" : v);
    }
    kids.flat().forEach((c) => { if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c))); });
    return el;
}
const SVGNS = "http://www.w3.org/2000/svg";
function s(tag, attrs, ...kids) {
    const el = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
    kids.forEach((c) => el.append(c.nodeType ? c : document.createTextNode(String(c))));
    return el;
}

/* ============================================================
   Animation scenes. Each frame is a full picture; the player tweens
   nodes with the same id from one frame to the next.
     node:  {id, x, y, t, s:"c"|"r", w, h, r, c:"hot|good|warn|gold|dim"}
     edge:  [fromId, toId, cls?]     label: {x, y, t, c?}
   Canvas is 360 x 360.
   ============================================================ */
const N = (id, x, y, t, o = {}) => ({ id, x, y, t, ...o });

/* --- Hash table (chaining) --- */
function hashFrame(caption, buckets, items, o = {}) {
    const nodes = [], edges = [], gap = buckets === 4 ? 66 : 38, y0 = buckets === 4 ? 78 : 44;
    const bh = buckets === 4 ? 44 : 28, ih = buckets === 4 ? 34 : 24;
    for (let i = 0; i < buckets; i++) nodes.push(N("b" + i, 44, y0 + i * gap, String(i), { s: "r", w: 46, h: bh, c: (o.cb || {})[i] }));
    const count = {};
    items.forEach((it) => {
        const k = count[it.b] = (count[it.b] ?? -1) + 1;
        nodes.push(N(it.id, 140 + k * 140, y0 + it.b * gap, it.t, { s: "r", w: 124, h: ih, c: (o.ci || {})[it.id], sm: true }));
        edges.push(k === 0 ? ["b" + it.b, it.id] : [it.prev, it.id, (o.ci || {})[it.id] === "hot" ? "hot" : ""]);
    });
    return { caption, nodes, edges, labels: o.labels || [] };
}
const S1 = { id: "sunny", t: "sunny@amrita.edu" }, P1 = { id: "priya", t: "priya@vit.ac.in" }, R1 = { id: "ravi", t: "ravi@nitt.edu" };
const HASH = [
    hashFrame("Our login table maps email → user. Start with 4 buckets.", 4, []),
    hashFrame("hash(email) % 4 picks a bucket. Here: bucket 2.", 4, [], { cb: { 2: "hot" }, labels: [{ x: 180, y: 30, t: 'hash("sunny@amrita.edu") % 4 = 2', c: "hot" }] }),
    hashFrame("The account is stored in bucket 2.", 4, [{ ...S1, b: 2 }], { cb: { 2: "good" }, ci: { sunny: "good" } }),
    hashFrame("Another student hashes to bucket 0.", 4, [{ ...S1, b: 2 }], { cb: { 0: "hot" }, labels: [{ x: 180, y: 30, t: 'hash("priya@vit.ac.in") % 4 = 0', c: "hot" }] }),
    hashFrame("Stored in bucket 0.", 4, [{ ...P1, b: 0 }, { ...S1, b: 2 }], { cb: { 0: "good" }, ci: { priya: "good" } }),
    hashFrame("Uh-oh: a third email also lands in bucket 2. A collision!", 4, [{ ...P1, b: 0 }, { ...S1, b: 2 }], { cb: { 2: "warn" }, ci: { sunny: "warn" }, labels: [{ x: 180, y: 30, t: 'hash("ravi@nitt.edu") % 4 = 2', c: "warn" }] }),
    hashFrame("Chaining: both emails share bucket 2 as a short list.", 4, [{ ...P1, b: 0 }, { ...S1, b: 2 }, { ...R1, b: 2, prev: "sunny" }], { cb: { 2: "hot" }, ci: { ravi: "hot" } }),
    hashFrame("Login = hash, then compare along a tiny chain. O(1) on average.", 4, [{ ...P1, b: 0 }, { ...S1, b: 2 }, { ...R1, b: 2, prev: "sunny" }], { cb: { 2: "hot" }, ci: { sunny: "dim", ravi: "good" }, labels: [{ x: 180, y: 30, t: "login: ravi@nitt.edu → bucket 2 → found", c: "good" }] }),
    hashFrame("Too full (load > 0.75)? Double the buckets and re-spread. Chains stay short. (Illustrative.)", 8, [{ ...P1, b: 0 }, { ...R1, b: 2 }, { ...S1, b: 5 }], { ci: { sunny: "good", priya: "good", ravi: "good" }, labels: [{ x: 230, y: 22, t: "capacity 4 → 8, rehash all keys", c: "hot" }] }),
];

/* --- BFS on the friend graph --- */
const G = {
    you: [180, 50], a: [90, 135], b: [270, 135], c: [40, 230], d: [140, 230], e: [250, 230], f: [320, 300], g: [140, 315],
};
const GE = [["you", "a"], ["you", "b"], ["a", "c"], ["a", "d"], ["b", "d"], ["b", "e"], ["e", "f"], ["d", "g"]];
const GN = { you: "You", a: "Amy", b: "Ben", c: "Cara", d: "Dev", e: "Eli", f: "Fay", g: "Gus" };
function bfsFrame(caption, cls = {}, labels = [], edgeCls = {}) {
    return {
        caption, labels,
        nodes: Object.entries(G).map(([id, [x, y]]) => N(id, x, y, GN[id], { r: 22, c: cls[id] })),
        edges: GE.map(([p, q]) => [p, q, edgeCls[p + q] || ""]),
    };
}
const BFS = [
    bfsFrame("Friendships form a graph. You are the start node.", { you: "gold" }),
    bfsFrame("BFS level 1: your friends, found first.", { you: "gold", a: "good", b: "good" }, [], { youa: "good", youb: "good" }),
    bfsFrame("Level 2: friends of friends are the suggestion candidates.", { you: "gold", a: "good", b: "good", c: "hot", d: "hot", e: "hot" }, [], { youa: "good", youb: "good", ac: "hot", ad: "hot", bd: "hot", be: "hot" }),
    bfsFrame("Rank by mutual friends: Dev knows both Amy and Ben.", { you: "gold", a: "good", b: "good", c: "dim", d: "hot", e: "dim" },
        [{ x: 140, y: 262, t: "2 mutual", c: "hot" }, { x: 40, y: 262, t: "1", c: "" }, { x: 250, y: 262, t: "1", c: "" }], { youa: "good", youb: "good", ad: "hot", bd: "hot" }),
    bfsFrame("Top suggestion: Dev. Each person is visited once: O(V + E).", { you: "gold", a: "good", b: "good", c: "dim", d: "gold", e: "dim" },
        [{ x: 222, y: 276, t: "People you may know!", c: "good" }], { youa: "good", youb: "good", ad: "good", bd: "good" }),
    bfsFrame("We stop at 3 hops, so far-away people (Fay, Gus) stay out.", { you: "gold", a: "good", b: "good", c: "dim", d: "dim", e: "dim", f: "warn", g: "warn" },
        [{ x: 180, y: 346, t: "max_depth = 3", c: "warn" }]),
];

/* --- Trie --- */
const TW = ["amy", "ann", "alan", "bob"], TP = { "": [180, 40], a: [120, 105], b: [290, 105], am: [50, 175], an: [120, 175], al: [190, 175], bo: [290, 175], amy: [50, 245], ann: [120, 245], ala: [190, 245], bob: [290, 245], alan: [190, 315] };
function trieFrame(caption, prefix, results, note) {
    const ids = Object.keys(TP), nodes = [], edges = [];
    ids.forEach((id) => {
        const inSub = id.startsWith(prefix), onPath = prefix.startsWith(id) && id !== prefix;
        let c = prefix === "" ? "" : id === prefix ? "hot" : inSub ? "good" : onPath ? "gold" : "dim";
        if (prefix && !(prefix in TP)) c = id === "" ? "warn" : "dim";
        nodes.push(N("t" + id, TP[id][0], TP[id][1], id === "" ? "•" : id.slice(-1).toUpperCase(), { r: 19, c }));
        if (id) edges.push(["t" + id.slice(0, -1), "t" + id, c === "dim" ? "" : "good"]);
    });
    const labels = [{ x: 180, y: 12, t: `search: "${prefix}"▮`, c: "hot" }];
    labels.push({ x: 180, y: 348, t: results, c: results.startsWith("no ") ? "warn" : "good" });
    if (note) labels.push({ x: 180, y: 330, t: note, c: "" });
    return { caption, nodes, edges, labels };
}
const TRIE = [
    { ...trieFrame("A trie stores words letter by letter: amy, ann, alan, bob.", "", "4 students indexed"), labels: [{ x: 180, y: 348, t: "words: amy · ann · alan · bob", c: "" }] },
    trieFrame("Type \"a\": jump straight to node A.", "a", "results: Amy, Ann, Alan"),
    trieFrame("Type \"al\": the search narrows with each letter.", "al", "results: Alan"),
    trieFrame("Type \"an\": a different branch, a different answer.", "an", "results: Ann"),
    trieFrame("\"z\": no such branch, so no results, instantly.", "z", "no matches"),
    { ...trieFrame("Each node remembers the student ids below it, so results cost O(length of prefix).", "a", "ids cached at every node"), labels: [{ x: 180, y: 12, t: "search: \"a\"▮", c: "hot" }, { x: 180, y: 348, t: "no walking the whole subtree", c: "good" }] },
];

/* --- AVL rotation --- */
const AE = (list) => list.map(([p, q]) => [String(p), String(q)]);
function avlFrame(caption, pos, links, cls = {}, labels = [], edgeCls = {}) {
    return {
        caption, labels,
        nodes: Object.entries(pos).map(([id, [x, y]]) => N(id, x, y, id, { r: 22, c: cls[id] })),
        edges: links.map(([p, q]) => [String(p), String(q), edgeCls[p + "" + q] || ""]),
    };
}
const AVL = [
    avlFrame("Insert 10: the first node is the root.", { 10: [180, 60] }, [], { 10: "good" }),
    avlFrame("Insert 20: it goes to the right of 10.", { 10: [180, 60], 20: [240, 140] }, [[10, 20]], { 20: "hot" }),
    avlFrame("Insert 30: now the tree leans hard to the right.", { 10: [180, 60], 20: [240, 140], 30: [300, 220] }, [[10, 20], [20, 30]], { 10: "warn", 30: "hot" }, [{ x: 100, y: 60, t: "balance −2", c: "warn" }]),
    avlFrame("Right-heavy, so rotate left around 10.", { 10: [180, 60], 20: [240, 140], 30: [300, 220] }, [[10, 20, "hot"], [20, 30]], { 10: "warn", 20: "hot" }, [{ x: 130, y: 330, t: "rotate_left(10)", c: "hot" }], { 1020: "hot" }),
    avlFrame("Balanced again: 20 is the new root. Height stays O(log n).", { 20: [180, 60], 10: [100, 150], 30: [260, 150] }, [[20, 10], [20, 30]], { 20: "good", 10: "good", 30: "good" }),
    avlFrame("Insert 40, then 50 goes below it: the right side is too deep.", { 20: [180, 60], 10: [100, 140], 30: [250, 140], 40: [300, 220], 50: [330, 300] }, [[20, 10], [20, 30], [30, 40], [40, 50]], { 30: "warn", 50: "hot" }, [{ x: 322, y: 128, t: "balance −2", c: "warn" }]),
    avlFrame("Rotate left around 30. One small move, balanced again.", { 20: [180, 60], 10: [100, 140], 40: [250, 140], 30: [190, 225], 50: [310, 225] }, [[20, 10], [20, 40], [40, 30], [40, 50]], { 40: "good", 30: "good", 50: "good", 20: "good", 10: "good" }, [{ x: 180, y: 330, t: "in code: _rebalance() → _rotate_left()", c: "good" }]),
];

/* --- Max heap --- */
const HP = [[180, 45], [100, 120], [260, 120], [60, 200], [140, 200], [220, 200], [300, 200]];
function heapFrame(caption, arr, cls = {}, labels = []) {
    const nodes = [], edges = [];
    arr.forEach((v, i) => {
        nodes.push(N("v" + v, HP[i][0], HP[i][1], String(v), { r: 21, c: cls[v] }));
        nodes.push(N("a" + v, 38 + i * 48, 300, String(v), { s: "r", w: 42, h: 34, c: cls[v], sm: true }));
        if (i > 0) edges.push(["v" + arr[(i - 1) >> 1], "v" + v, cls[v] === "hot" ? "hot" : ""]);
    });
    labels = [...labels, { x: 180, y: 338, t: "array: parent of i is (i − 1) // 2", c: "" }];
    return { caption, nodes, edges, labels };
}
const HEAP = [
    heapFrame("Trending = a max-heap of scores (likes + 2 × comments). Biggest on top.", [50, 30, 40, 10, 20]),
    heapFrame("A new post scores 60. Add it at the end of the array.", [50, 30, 40, 10, 20, 60], { 60: "hot" }, [{ x: 180, y: 262, t: "new post: score 60", c: "hot" }]),
    heapFrame("60 beats its parent 40, so swap them (sift-up).", [50, 30, 60, 10, 20, 40], { 60: "hot", 40: "gold" }),
    heapFrame("60 beats the root 50 too. Swap again.", [60, 30, 50, 10, 20, 40], { 60: "hot", 50: "gold" }),
    heapFrame("Done: the top of the heap is the #1 trending post.", [60, 30, 50, 10, 20, 40], { 60: "good" }, [{ x: 180, y: 262, t: "#1 trending → top_k(10) for the tab", c: "good" }]),
];

/* --- Safety pipeline --- */
function pipeFrame(caption, cls = {}, o = {}) {
    const nodes = [
        N("post", 180, 50, "Student posts", { s: "r", w: 150, h: 38, c: cls.post }),
        N("local", 180, 130, "Local rules", { s: "r", w: 150, h: 38, c: cls.local }),
        N("ai", 180, 210, "Gemini check", { s: "r", w: 150, h: 38, c: cls.ai }),
        N("ok", 90, 300, "Posted ✓", { s: "r", w: 120, h: 38, c: cls.ok }),
        N("no", 270, 300, "Blocked ✗", { s: "r", w: 120, h: 38, c: cls.no }),
    ];
    const edges = [["post", "local", o.e1 || ""], ["local", "ai", o.e2 || ""], ["ai", "ok", o.e3 || ""], ["ai", "no", ""], ["local", "no", o.e4 || ""]];
    if (o.log) { nodes.push(N("log", 300, 210, "Audit log", { s: "r", w: 84, h: 32, c: "gold", sm: true })); edges.push(["ai", "log", "hot"]); }
    return { caption, nodes, edges, labels: o.labels || [] };
}
const SAFETY = [
    pipeFrame("A student posts or comments.", { post: "hot" }),
    pipeFrame("Step 1: fast local rules. No network needed.", { post: "good", local: "hot" }, { e1: "good", labels: [{ x: 180, y: 160, t: "links · OTPs · card numbers · spam", c: "" }] }),
    pipeFrame("A shortened link? Blocked on the spot, with a clear reason.", { post: "good", local: "warn", no: "warn" }, { e1: "good", e4: "warn", labels: [{ x: 90, y: 100, t: "bit.ly/…", c: "warn" }] }),
    pipeFrame("Step 2: Gemini reads the text for harassment, scams, hate and more.", { post: "good", local: "good", ai: "hot" }, { e1: "good", e2: "good", labels: [{ x: 180, y: 240, t: "verdict: allow · block · support", c: "" }] }),
    pipeFrame("Safe: it's posted. Possible self-harm is never blocked: the post goes up with a supportive note.", { post: "good", local: "good", ai: "good", ok: "good" }, { e1: "good", e2: "good", e3: "good" }),
    pipeFrame("Every check is logged. Three blocks in 10 minutes triggers a short cooldown.", { post: "good", local: "good", ai: "good", ok: "good" }, { e1: "good", e2: "good", e3: "good", log: true, labels: [{ x: 180, y: 346, t: "3 blocks / 10 min → cooldown", c: "gold" }] }),
];

const REEL_SCENES = { hash: HASH, bfs: BFS, trie: TRIE, avl: AVL, heap: HEAP, safety: SAFETY };
const reelPlayers = [];

/* ============================================================
   Player: tweens nodes between frames, autoplays only while visible
   ============================================================ */
class ReelPlayer {
    constructor(frames, title) {
        this.frames = frames; this.i = 0; this.playing = true; this.visible = false; this.timer = null; this.raf = null;
        this.pos = new Map(); this.from = new Map(); this.target = new Map(); this.els = new Map(); this.lineEls = [];
        this.reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (this.reduce) this.playing = false;
        this.svg = s("svg", { viewBox: "0 0 360 360", role: "img", "aria-label": `Animated explainer: ${title}` });
        this.gEdges = s("g"); this.gNodes = s("g"); this.gLabels = s("g");
        this.svg.append(this.gEdges, this.gNodes, this.gLabels);
        this.caption = h("div", { class: "reel-caption", "aria-live": "polite" });
        this.playBtn = h("button", { type: "button", onclick: () => this.toggle() }, this.playing ? "Pause" : "Play");
        this.dots = frames.map((_, k) => h("button", { type: "button", class: "dot", "aria-label": `Step ${k + 1}`, onclick: () => { this.pause(); this.show(k); } }));
        this.root = h("div", { class: "reel-anim" }, this.svg, this.caption,
            h("div", { class: "reel-ctrl" },
                h("button", { type: "button", "aria-label": "Previous step", onclick: () => { this.pause(); this.show((this.i - 1 + frames.length) % frames.length); } }, "◀"),
                this.playBtn,
                h("button", { type: "button", "aria-label": "Next step", onclick: () => { this.pause(); this.show((this.i + 1) % frames.length); } }, "▶"),
                h("div", { class: "dots" }, this.dots)));
        this.show(0, true);
        this.io = new IntersectionObserver((e) => { this.visible = e[0].isIntersecting && e[0].intersectionRatio > 0.55; this.schedule(); }, { threshold: [0, 0.55, 1] });
        this.io.observe(this.root);
    }
    destroy() { clearTimeout(this.timer); cancelAnimationFrame(this.raf); this.io.disconnect(); }
    toggle() { this.playing ? this.pause() : (this.playing = true, this.playBtn.textContent = "Pause", this.schedule()); }
    pause() { this.playing = false; this.playBtn.textContent = "Play"; clearTimeout(this.timer); }
    schedule() {
        clearTimeout(this.timer);
        if (!this.playing || !this.visible || document.hidden) return;
        this.timer = setTimeout(() => { this.show((this.i + 1) % this.frames.length); this.schedule(); }, 3200);
    }
    show(k, instant) {
        this.i = k;
        const f = this.frames[k];
        this.caption.textContent = f.caption;
        this.dots.forEach((d, j) => d.classList.toggle("on", j === k));
        // targets
        this.from = new Map([...this.pos].map(([id, p]) => [id, { ...p }]));
        this.target = new Map(f.nodes.map((n) => [n.id, { x: n.x, y: n.y, a: n.c === "dim" ? 0.3 : 1 }]));
        f.nodes.forEach((n) => {
            if (!this.pos.has(n.id)) { this.pos.set(n.id, { x: n.x, y: n.y, a: 0 }); this.from.set(n.id, { x: n.x, y: n.y, a: 0 }); }
            this.ensureNode(n);
        });
        for (const id of this.pos.keys()) if (!this.target.has(id)) this.target.set(id, { ...this.pos.get(id), a: 0 });
        // edges + labels are rebuilt per frame
        this.edges = f.edges;
        this.gEdges.textContent = "";
        this.lineEls = f.edges.map(([a, b, cls]) => { const l = s("line", { class: `edge ${cls || ""}` }); this.gEdges.append(l); return l; });
        this.gLabels.textContent = "";
        (f.labels || []).forEach((l) => this.gLabels.append(s("g", { class: `lbl ${l.c || ""}` }, s("text", { x: l.x, y: l.y }, l.t))));
        this.t0 = performance.now(); this.dur = instant || this.reduce ? 0 : 650;
        cancelAnimationFrame(this.raf);
        this.tick(this.t0);
    }
    ensureNode(n) {
        let el = this.els.get(n.id);
        if (!el) {
            const shape = n.s === "r" ? s("rect", { class: "shape", x: -n.w / 2, y: -n.h / 2, width: n.w, height: n.h, rx: 9 }) : s("circle", { class: "shape", r: n.r || 20 });
            el = s("g", {}, shape, s("text", {}, n.t));
            this.gNodes.append(el); this.els.set(n.id, el);
        }
        el.setAttribute("class", `rn ${n.c || ""} ${n.sm ? "sm" : ""}`);
        el.querySelector("text").textContent = n.t;
        const shape = el.firstChild;
        if (n.s === "r") { shape.setAttribute("width", n.w); shape.setAttribute("height", n.h); shape.setAttribute("x", -n.w / 2); shape.setAttribute("y", -n.h / 2); }
    }
    tick(now) {
        const p = this.dur ? Math.min(1, (now - this.t0) / this.dur) : 1, e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        for (const [id, t] of this.target) {
            const f = this.from.get(id) || t, cur = this.pos.get(id) || { ...t };
            cur.x = f.x + (t.x - f.x) * e; cur.y = f.y + (t.y - f.y) * e; cur.a = f.a + (t.a - f.a) * e;
            this.pos.set(id, cur);
            const el = this.els.get(id);
            if (el) { el.setAttribute("transform", `translate(${cur.x.toFixed(1)} ${cur.y.toFixed(1)})`); el.style.opacity = cur.a.toFixed(2); }
        }
        this.edges.forEach(([a, b], k) => {
            const pa = this.pos.get(a), pb = this.pos.get(b), l = this.lineEls[k];
            if (!pa || !pb) { l.style.display = "none"; return; }
            l.style.display = ""; l.setAttribute("x1", pa.x); l.setAttribute("y1", pa.y); l.setAttribute("x2", pb.x); l.setAttribute("y2", pb.y);
            l.style.opacity = Math.min(pa.a, pb.a).toFixed(2);
        });
        if (p < 1) this.raf = requestAnimationFrame((t) => this.tick(t));
        else for (const [id, t] of this.target) if (t.a === 0) { this.els.get(id)?.remove(); this.els.delete(id); this.pos.delete(id); }
    }
}

/* ============================================================
   Reels page
   ============================================================ */
const reelState = { kind: "all", topic: "", sort: "curated", tab: "reels" };
const PLAY_SVG = `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>`;

function kindTag(kind) {
    return { prebuilt: h("span", { class: "tag gold" }, "Pre-built animation"), open: h("span", { class: "tag" }, "Open-licensed lecture"), community: h("span", { class: "tag" }, "Shared by a student") }[kind];
}

function youtubeMedia(r) {
    const ok = /^[A-Za-z0-9_-]{11}$/.test(r.media_ref);
    if (!ok) return h("div", { class: "reel-empty" }, "Video unavailable");
    const box = h("div", { class: "reel-yt" });
    const img = h("img", { loading: "lazy", alt: "", src: `https://i.ytimg.com/vi/${r.media_ref}/hqdefault.jpg`, referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => img.remove());   // offline or blocked: fall back to the plain dark card
    const play = h("button", { type: "button", class: "reel-play", "aria-label": `Play: ${r.title}`, onclick: () => {
        const start = Number.isInteger(r.start) && r.start > 0 ? `&start=${r.start}` : "";
        box.textContent = "";
        box.append(h("iframe", {
            src: `https://www.youtube-nocookie.com/embed/${r.media_ref}?autoplay=1&rel=0&modestbranding=1${start}`,
            title: r.title, allow: "autoplay; encrypted-media; picture-in-picture; fullscreen", allowfullscreen: true,
            referrerpolicy: "strict-origin-when-cross-origin", sandbox: "allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox",
        }));
    } });
    play.innerHTML = PLAY_SVG;          // constant markup only
    box.append(img, play);
    if (r.kind === "open") box.append(h("span", { class: "badge-len" }, "Full lecture"));
    return box;
}

function renderReel(r) {
    let media;
    if (r.media === "animation" && REEL_SCENES[r.media_ref]) {
        const player = new ReelPlayer(REEL_SCENES[r.media_ref], r.title);
        reelPlayers.push(player); media = player.root;
    } else if (r.media === "youtube") media = youtubeMedia(r);
    else media = h("div", { class: "reel-empty" }, "Preview unavailable");

    const likeBtn = h("button", { type: "button", class: `small-btn icon-btn like-btn${r.liked ? " liked" : ""}`, onclick: async (e) => {
        const btn = e.currentTarget; btn.disabled = true;
        try {
            const d = await apiFetch(`/reels/${r.id}/like`, { method: "POST" });
            btn.classList.toggle("liked", d.reel.liked);
            btn.lastChild.textContent = `${d.reel.liked ? "Liked" : "Like"} (${d.reel.likes})`;
        } catch (err) { showToast(err.message, "error"); } finally { btn.disabled = false; }
    } });
    likeBtn.innerHTML = ICONS.heart; likeBtn.append(h("span", {}, `${r.liked ? "Liked" : "Like"} (${r.likes})`));

    const credit = h("div", { class: "reel-credit" },
        h("strong", {}, r.license), " · ", r.credit, r.added_by ? ` (${r.added_by})` : "",
        r.source_url ? [" · ", h("a", { href: r.source_url, target: "_blank", rel: "noopener noreferrer" }, r.kind === "open" ? "Source ↗" : "Watch on YouTube ↗")] : null);

    // Comments: a small panel that opens under the buttons and loads on first open.
    const commentLabel = h("span", {}, `Comments (${r.comment_count || 0})`);
    const commentBtn = h("button", { type: "button", class: "small-btn icon-btn secondary", "aria-expanded": "false" });
    commentBtn.innerHTML = ICONS.chat; commentBtn.append(commentLabel);
    const panel = buildReelComments(r, commentLabel);
    panel.hidden = true;
    commentBtn.onclick = async () => {
        panel.hidden = !panel.hidden;
        commentBtn.setAttribute("aria-expanded", String(!panel.hidden));
        if (!panel.hidden) { panel.loadOnce(); panel.querySelector("input").focus({ preventScroll: true }); panel.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
    };

    const actions = h("div", { class: "reel-actions" }, likeBtn, commentBtn,
        r.can_delete ? h("button", { type: "button", class: "small-btn danger", onclick: async () => {
            if (!confirm("Delete this reel?")) return;
            try { await apiFetch(`/reels/${r.id}`, { method: "DELETE" }); loadReelsView(); } catch (err) { showToast(err.message, "error"); }
        } }, "Delete") : null);

    return h("article", { class: "reel" },
        h("div", { class: "reel-media" }, media),
        h("div", { class: "reel-info" },
            h("div", { class: "reel-tags" }, kindTag(r.kind), h("span", { class: "tag" }, r.topic)),
            h("h3", {}, r.title), r.description ? h("p", {}, r.description) : null,
            r.code_ref ? h("div", { class: "reel-code", title: "Where this idea lives in the CampusConnect code" }, `📁 ${r.code_ref}`) : null,
            credit, actions, panel));
}

function buildReelComments(r, label) {
    const list = h("div", { class: "reel-comment-list", "aria-live": "polite" });
    const input = h("input", { type: "text", maxlength: "500", placeholder: "Ask a doubt or add a tip about this video...", "aria-label": "Add a comment" });
    const send = h("button", { type: "submit", class: "small-btn" }, "Send");
    const form = h("form", { class: "comment-form" }, input, send);
    const panel = h("div", { class: "reel-comments" }, list, form);
    let loaded = false, count = r.comment_count || 0;
    const setCount = (n) => { count = n; label.textContent = `Comments (${n})`; };

    function row(c) {
        const el = h("div", { class: "comment-row" },
            h("span", { class: "comment-author" }, c.author_name || "Student"), c.content);
        if (c.can_delete) {
            el.append(h("button", { type: "button", class: "reel-comment-del", title: "Delete your comment", "aria-label": "Delete your comment", onclick: async () => {
                try {
                    const d = await apiFetch(`/reels/${r.id}/comments/${c.id}`, { method: "DELETE" });
                    el.remove(); setCount(d.comment_count);
                    if (!list.children.length) list.append(h("p", { class: "empty-note" }, "No comments yet. Start the discussion!"));
                } catch (err) { showToast(err.message, "error"); }
            } }, "\u00d7"));
        }
        return el;
    }

    panel.loadOnce = async () => {
        if (loaded) return;
        list.textContent = ""; list.append(h("p", { class: "loading-note" }, "Loading comments..."));
        try {
            const d = await apiFetch(`/reels/${r.id}/comments`);
            loaded = true; list.textContent = "";
            if (!d.comments.length) list.append(h("p", { class: "empty-note" }, "No comments yet. Start the discussion!"));
            d.comments.forEach((c) => list.append(row(c)));
            setCount(d.comments.length);
        } catch (err) { list.textContent = ""; list.append(h("p", { class: "empty-note" }, err.message)); }
    };

    form.onsubmit = async (e) => {
        e.preventDefault();
        const content = input.value.trim();
        if (!content) return;
        send.disabled = true;
        try {
            const d = await apiFetch(`/reels/${r.id}/comments`, { method: "POST", body: JSON.stringify({ content }) });
            if (d.notice) showToast(d.notice);
            if (!loaded) await panel.loadOnce();
            else { list.querySelector(".empty-note")?.remove(); list.append(row(d.comment)); }
            if (loaded) setCount(d.comment_count);
            input.value = ""; list.scrollTop = list.scrollHeight;
        } catch (err) { showToast(err.message, "error"); } finally { send.disabled = false; }
    };
    return panel;
}

function setReelTab(tab) {
    reelState.tab = tab;
    document.querySelectorAll("#reel-tabs .tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    const refs = tab === "reference";
    document.getElementById("reels-feed-wrap").style.display = refs ? "none" : "block";
    document.getElementById("reels-ref").style.display = refs ? "block" : "none";
    document.getElementById("reels-filters").style.display = refs ? "none" : "flex";
    if (refs) document.getElementById("reel-form-wrap").hidden = true;
    if (!refs) reelState.kind = tab === "reels" ? "all" : tab;
    loadReelsView();
}

async function loadReelsView() {
    reelPlayers.splice(0).forEach((p) => p.destroy());
    if (reelState.tab === "reference") return loadReference();
    const feed = document.getElementById("reels-feed");
    feed.textContent = "";
    feed.append(h("div", { class: "reel-empty" }, "Loading..."));
    try {
        const q = new URLSearchParams({ kind: reelState.kind, sort: reelState.sort });
        if (reelState.topic) q.set("topic", reelState.topic);
        const data = await apiFetch(`/reels?${q}`);
        const sel = document.getElementById("reel-topic"), cur = reelState.topic;
        if (sel.options.length <= 1) data.topics.forEach((t) => sel.append(h("option", { value: t }, t)));
        const formSel = document.getElementById("reel-new-topic");
        if (!formSel.options.length) data.topics.forEach((t) => formSel.append(h("option", { value: t }, t)));
        sel.value = cur;
        feed.textContent = "";
        if (!data.reels.length) feed.append(h("div", { class: "reel-empty" }, "Nothing here yet. Be the first to share a video!"));
        data.reels.forEach((r) => feed.append(renderReel(r)));
        feed.scrollTop = 0;
    } catch (err) {
        if (err.status === 401) { showAuth("login"); return; }
        feed.textContent = ""; feed.append(h("div", { class: "reel-empty" }, err.message));
    }
}

async function loadReference() {
    const box = document.getElementById("reels-ref");
    box.textContent = "";
    try {
        const data = await apiFetch("/reference");
        const groups = new Map();
        data.items.forEach((it) => groups.set(it.group, [...(groups.get(it.group) || []), it]));
        box.append(h("p", { class: "subtitle" }, "Free, openly licensed or official sources behind this project, with the licence of each."));
        groups.forEach((items, name) => box.append(h("section", { class: "ref-group" }, h("h2", {}, name),
            items.map((it) => h("div", { class: "ref-item" },
                h("a", { class: "t", href: it.url, target: "_blank", rel: "noopener noreferrer" }, it.title, " ↗"),
                h("div", { class: "ref-meta" }, `${it.by} · `, h("strong", {}, it.license)),
                h("div", { class: "ref-note" }, it.note))))));
    } catch (err) {
        if (err.status === 401) showAuth("login"); else box.append(h("div", { class: "reel-empty" }, err.message));
    }
}

async function onShareReel(e) {
    e.preventDefault();
    const flash = document.getElementById("reel-new-flash");
    const body = {
        url: document.getElementById("reel-new-url").value.trim(), title: document.getElementById("reel-new-title").value.trim(),
        description: document.getElementById("reel-new-desc").value.trim(), topic: document.getElementById("reel-new-topic").value,
    };
    try {
        const d = await apiFetch("/reels", { method: "POST", body: JSON.stringify(body) });
        document.getElementById("reel-new-form").reset();
        document.getElementById("reel-form-wrap").hidden = true;
        if (d.notice) showToast(d.notice); else showToast("Reel shared. Thanks!");
        flash.className = "flash";
        reelState.sort = "new"; document.getElementById("reel-sort").value = "new";
        setReelTab("community");
    } catch (err) {
        showFlash(flash, err.message, "error");
    }
}

function initReels() {
    document.querySelectorAll("#reel-tabs .tab-btn").forEach((b) => b.addEventListener("click", () => setReelTab(b.dataset.tab)));
    document.getElementById("reel-topic").addEventListener("change", (e) => { reelState.topic = e.target.value; loadReelsView(); });
    document.getElementById("reel-sort").addEventListener("change", (e) => { reelState.sort = e.target.value; loadReelsView(); });
    document.getElementById("reel-share-toggle").addEventListener("click", () => {
        const w = document.getElementById("reel-form-wrap"); w.hidden = !w.hidden;
        if (!w.hidden) document.getElementById("reel-new-url").focus();
    });
    document.getElementById("reel-new-form").addEventListener("submit", onShareReel);
    document.addEventListener("visibilitychange", () => reelPlayers.forEach((p) => p.schedule()));
}
initReels();
