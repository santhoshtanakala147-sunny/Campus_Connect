document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const game = btn.dataset.game;
        document.getElementById("tictactoe-panel").style.display = game === "tictactoe" ? "block" : "none";
        document.getElementById("puzzle-panel").style.display = game === "puzzle" ? "block" : "none";
    });
});

/* ---------------- Tic-Tac-Toe (minimax CPU) ---------------- */

let ttt = Array(9).fill(null);
let tttOver = false;
const tttBoard = document.getElementById("ttt-board");
const tttStatus = document.getElementById("ttt-status");

const WIN_LINES = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],
    [0, 3, 6], [1, 4, 7], [2, 5, 8],
    [0, 4, 8], [2, 4, 6],
];

function tttWinner(board) {
    for (const [a, b, c] of WIN_LINES) {
        if (board[a] && board[a] === board[b] && board[b] === board[c]) return board[a];
    }
    if (board.every((cell) => cell)) return "draw";
    return null;
}

function renderTtt() {
    tttBoard.innerHTML = "";
    ttt.forEach((val, i) => {
        const cell = document.createElement("div");
        cell.className = "ttt-cell";
        cell.textContent = val || "";
        if (!val && !tttOver) {
            cell.addEventListener("click", () => playerMove(i));
        }
        tttBoard.appendChild(cell);
    });
}

function playerMove(i) {
    if (ttt[i] || tttOver) return;
    ttt[i] = "X";
    const winner = tttWinner(ttt);
    if (winner) {
        finishTtt(winner);
        return;
    }
    const cpuMove = bestMove(ttt);
    ttt[cpuMove] = "O";
    const winner2 = tttWinner(ttt);
    renderTtt();
    if (winner2) finishTtt(winner2);
}

function finishTtt(winner) {
    tttOver = true;
    renderTtt();
    if (winner === "draw") tttStatus.textContent = "It's a draw.";
    else tttStatus.textContent = winner === "X" ? "You win!" : "CPU wins.";
}

function bestMove(board) {
    let best = -Infinity;
    let move = -1;
    for (let i = 0; i < 9; i++) {
        if (!board[i]) {
            board[i] = "O";
            const score = minimax(board, 0, false);
            board[i] = null;
            if (score > best) {
                best = score;
                move = i;
            }
        }
    }
    return move;
}

function minimax(board, depth, isMaximizing) {
    const winner = tttWinner(board);
    if (winner === "O") return 10 - depth;
    if (winner === "X") return depth - 10;
    if (winner === "draw") return 0;

    if (isMaximizing) {
        let best = -Infinity;
        for (let i = 0; i < 9; i++) {
            if (!board[i]) {
                board[i] = "O";
                best = Math.max(best, minimax(board, depth + 1, false));
                board[i] = null;
            }
        }
        return best;
    } else {
        let best = Infinity;
        for (let i = 0; i < 9; i++) {
            if (!board[i]) {
                board[i] = "X";
                best = Math.min(best, minimax(board, depth + 1, true));
                board[i] = null;
            }
        }
        return best;
    }
}

document.getElementById("ttt-reset").addEventListener("click", () => {
    ttt = Array(9).fill(null);
    tttOver = false;
    tttStatus.textContent = "You are X. Beat the CPU.";
    renderTtt();
});

renderTtt();

/* ---------------- Sliding Puzzle (8-puzzle) ---------------- */

const SIZE = 3;
let tiles = [];
const puzzleBoard = document.getElementById("puzzle-board");
const puzzleStatus = document.getElementById("puzzle-status");

function solvedTiles() {
    const arr = [];
    for (let i = 1; i < SIZE * SIZE; i++) arr.push(i);
    arr.push(null);
    return arr;
}

function isSolved() {
    const solved = solvedTiles();
    return tiles.every((v, i) => v === solved[i]);
}

function shuffle() {
    tiles = solvedTiles();
    let blank = tiles.indexOf(null);
    // Shuffle via random valid moves so the puzzle is always solvable.
    for (let i = 0; i < 200; i++) {
        const neighbors = neighborIndices(blank);
        const swapWith = neighbors[Math.floor(Math.random() * neighbors.length)];
        [tiles[blank], tiles[swapWith]] = [tiles[swapWith], tiles[blank]];
        blank = swapWith;
    }
    puzzleStatus.textContent = "Arrange the tiles in order.";
    renderPuzzle();
}

function neighborIndices(i) {
    const row = Math.floor(i / SIZE);
    const col = i % SIZE;
    const result = [];
    if (row > 0) result.push(i - SIZE);
    if (row < SIZE - 1) result.push(i + SIZE);
    if (col > 0) result.push(i - 1);
    if (col < SIZE - 1) result.push(i + 1);
    return result;
}

function renderPuzzle() {
    puzzleBoard.innerHTML = "";
    tiles.forEach((val, i) => {
        const cell = document.createElement("div");
        cell.className = "puzzle-cell" + (val === null ? " blank" : "");
        cell.textContent = val ?? "";
        if (val !== null) {
            cell.addEventListener("click", () => tryMove(i));
        }
        puzzleBoard.appendChild(cell);
    });
}

function tryMove(i) {
    const blank = tiles.indexOf(null);
    if (neighborIndices(i).includes(blank)) {
        [tiles[i], tiles[blank]] = [tiles[blank], tiles[i]];
        renderPuzzle();
        if (isSolved()) puzzleStatus.textContent = "Solved! Nice work.";
    }
}

document.getElementById("puzzle-reset").addEventListener("click", shuffle);

shuffle();
