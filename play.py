"""Games Nova can play WITH the owner — all local, from scratch, no downloads.

Chat-driven games run through GameRoom (rock-paper-scissors, guess-the-number,
hangman, trivia, tic-tac-toe, 20-questions, mini crossword). Two games use the
desktop directly: `snake_window` opens a self-playing Snake board, and hide-and-
seek is handled by the avatar moving itself around (see avatar.py).
"""
import random
import re
import tkinter as tk

WORDS = ["nova", "cyber", "neon", "anime", "pixel", "robot", "galaxy", "kitty",
         "studio", "future", "glitch", "starlight", "phantom", "blossom"]
TRIVIA = [
    ("What is the capital of Japan?", "tokyo"),
    ("How many colors are in a rainbow?", "7"),
    ("What is 9 times 8?", "72"),
    ("Which planet is known as the Red Planet?", "mars"),
    ("What do you call a baby cat?", "kitten"),
    ("What is the largest ocean on Earth?", "pacific"),
    ("How many sides does a hexagon have?", "6"),
    ("What gas do plants absorb from the air?", "co2"),
]
CROSSWORD = [
    ("A cat's soft sound (4)", "purr"),
    ("Opposite of dark (5)", "light"),
    ("A girl's best friend, in games (5)", "sword"),
    ("Where you sleep (4)", "bed"),
    ("Bright streak in the sky (4)", "star"),
]
TWENTY_THINGS = [
    ("cat", {"animal", "pet", "fur", "small", "meow"}),
    ("piano", {"instrument", "music", "keys", "large", "sound"}),
    ("moon", {"space", "sky", "round", "night", "rock"}),
    ("notebook", {"object", "paper", "write", "small", "school"}),
    ("coffee", {"drink", "hot", "brown", "morning", "caffeine"}),
    ("bicycle", {"vehicle", "wheels", "ride", "outside", "pedal"}),
]


def _norm(text):
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()


class GameRoom:
    """One active game at a time; every method returns text for Nova to say."""

    def __init__(self):
        self.key = None
        self.state = {}

    @staticmethod
    def catalogue():
        return [
            ("rps", "Rock Paper Scissors", "beat me at hands"),
            ("number", "Guess my number", "I think of 1-20, you guess"),
            ("hangman", "Hangman", "guess the hidden word"),
            ("trivia", "Trivia", "5 quick questions"),
            ("tictactoe", "Tic Tac Toe", "you vs me on a 3x3 board"),
            ("twenty", "20 Questions", "I think of something, you ask yes/no"),
            ("crossword", "Mini Crossword", "5 tiny clues"),
            ("snake", "Snake", "a self-playing snake on your desktop"),
            ("hide", "Hide and Seek", "I hide, you find me"),
        ]

    def start(self, key):
        key = _norm(key).replace(" ", "_")
        aliases = {
            "rock_paper_scissors": "rps", "rps": "rps",
            "guess_my_number": "number", "number": "number", "guess": "number",
            "hangman": "hangman", "trivia": "trivia", "quiz": "trivia",
            "tic_tac_toe": "tictactoe", "tictactoe": "tictactoe",
            "20_questions": "twenty", "20_questions_game": "twenty", "twenty": "twenty",
            "crossword": "crossword", "snake": "snake", "hide": "hide", "hide_and_seek": "hide",
        }
        key = aliases.get(key, key)
        if key not in {k for k, _, _ in self.catalogue()}:
            names = ", ".join(k for k, _, _ in self.catalogue())
            return "I know these games: " + names + ". Pick one!"
        self.key = key
        if key == "rps":
            self.state = {}
            return "Rock, paper, scissors! Type rock / paper / scissors."
        if key == "number":
            self.state = {"secret": random.randint(1, 20), "tries": 0}
            return "I'm thinking of a number from 1 to 20. Guess it! (6 tries)"
        if key == "hangman":
            self.state = {"word": random.choice(WORDS), "guessed": set(), "wrong": 0}
            return "Hangman! Guess a letter.\n" + self._hangman_board()
        if key == "trivia":
            self.state = {"i": 0, "score": 0}
            return "Trivia time! " + TRIVIA[0][0]
        if key == "tictactoe":
            self.state = {"board": [" "] * 9, "turn": "you"}
            return "Tic Tac Toe — you're X, I'm O. Pick 1-9.\n" + self._ttt_board()
        if key == "twenty":
            thing, _ = random.choice(TWENTY_THINGS)
            self.state = {"thing": thing, "asked": 0}
            return "I've thought of something. Ask me yes/no questions (up to 20), or just guess it!"
        if key == "crossword":
            self.state = {"i": 0, "score": 0}
            return "Mini crossword! #1: " + CROSSWORD[0][0]
        if key == "snake":
            self.key = None
            return "Opening Snake — watch me chase the dots! (arrow keys take over)"
        if key == "hide":
            self.key = None
            return "HIDE AND SEEK! I'm going to hide... type 'found you' when you spot me~"
        return "Let's play!"

    def handle(self, text):
        if not self.key:
            return "Pick a game first — say 'play trivia' or 'what games can we play?'.", True
        handler = getattr(self, "_" + self.key, None)
        if not handler:
            return "That game's handled on the desktop, not in chat.", True
        return handler(_norm(text))

    # ---- individual games ----
    def _rps(self, text):
        if text not in ("rock", "paper", "scissors"):
            return "Say rock, paper, or scissors.", False
        mine = random.choice(("rock", "paper", "scissors"))
        beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        if text == mine:
            out = "We both picked %s — tie! Again?" % mine
        elif beats[text] == mine:
            out = "I picked %s. You win! *salutes*" % mine
        else:
            out = "I picked %s. I win! *smirks* Again?" % mine
        self.key = None
        return out, True

    def _number(self, text):
        try:
            guess = int(text)
        except ValueError:
            return "Just a number from 1 to 20~", False
        s = self.state
        s["tries"] += 1
        secret = s["secret"]
        if guess == secret:
            self.key = None
            return "You got it! %s was my number. *claps*" % secret, True
        hint = "higher" if guess < secret else "lower"
        if s["tries"] >= 6:
            self.key = None
            return "Out of tries! It was %s. Rematch?" % secret, True
        return "%s! Try %s. (%d tries left)" % (
            "Too low, go higher" if guess < secret else "Too high, go lower", hint, 6 - s["tries"]), False

    def _hangman_board(self):
        s = self.state
        shown = "".join(c if c in s["guessed"] else "_" for c in s["word"])
        return "%s   [%d wrong / 6]" % (" ".join(shown), s["wrong"])

    def _hangman(self, text):
        s = self.state
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return "Give me a letter.", False
        letter = letters[0]
        if letter in s["guessed"]:
            return "Already guessed that one~", False
        s["guessed"].add(letter)
        if letter not in s["word"]:
            s["wrong"] += 1
            if s["wrong"] >= 6:
                self.key = None
                return "You ran out! The word was '%s'. Rematch?" % s["word"], True
            return "Nope! " + self._hangman_board(), False
        if all(c in s["guessed"] for c in s["word"]):
            self.key = None
            return "You got it — '%s'! *cheers*" % s["word"], True
        return "Nice! " + self._hangman_board(), False

    def _trivia(self, text):
        s = self.state
        answer = TRIVIA[s["i"]][1]
        if answer in text or (answer == "co2" and "carbon" in text):
            s["score"] += 1
            line = "Correct! "
        else:
            line = "Nope — it was '%s'. " % answer
        s["i"] += 1
        if s["i"] >= len(TRIVIA):
            self.key = None
            return line + "Final score: %d/%d. Wanna go again?" % (s["score"], len(TRIVIA)), True
        return line + "Next: " + TRIVIA[s["i"]][0], False

    @staticmethod
    def _ttt_board(b=None):
        b = b or [" "] * 9
        return "\n".join(" %s | %s | %s " % tuple(b[i:i + 3]) for i in (0, 3, 6))

    @staticmethod
    def _ttt_winner(b):
        for i, j, k in ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
                        (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)):
            if b[i] != " " and b[i] == b[j] == b[k]:
                return b[i]
        return None

    def _ttt_best(self, b):
        for move in range(9):
            if b[move] == " ":
                b[move] = "O"
                win = self._ttt_winner(b)
                b[move] = " "
                if win == "O":
                    return move
        for move in (4, 0, 2, 6, 8, 1, 3, 5, 7):
            if b[move] == " ":
                return move
        return None

    def _tictactoe(self, text):
        b = self.state["board"]
        nums = re.findall(r"\d", text)
        if not nums or not (1 <= int(nums[0]) <= 9) or b[int(nums[0]) - 1] != " ":
            return "Pick an empty square 1-9.\n" + self._ttt_board(b), False
        b[int(nums[0]) - 1] = "X"
        if self._ttt_winner(b) == "X":
            self.key = None
            return "You win! " + self._ttt_board(b), True
        if " " not in b:
            self.key = None
            return "Draw! " + self._ttt_board(b), True
        move = self._ttt_best(b)
        if move is not None:
            b[move] = "O"
        if self._ttt_winner(b) == "O" or " " not in b:
            self.key = None
            return ("I win this one! " if self._ttt_winner(b) == "O" else "Draw! ") + self._ttt_board(b), True
        return "My move:\n" + self._ttt_board(b) + "\nYour turn (1-9).", False

    def _twenty(self, text):
        s = self.state
        if any(w in text for w in ("give up", "i know", "it is", "it's", "is it a", "answer")):
            guess = _norm(text).replace("is it a", "").replace("i know", "").strip()
            self.key = None
            if guess == s["thing"]:
                return "Yes! It was %s. You got me~" % s["thing"], True
            return "Nope, it was %s! Good game." % s["thing"], True
        s["asked"] += 1
        _, feats = next((t, f) for t, f in TWENTY_THINGS if t == s["thing"])
        yes = any(f in text for f in feats)
        if s["asked"] >= 20:
            self.key = None
            return "20 questions! It was %s. You win~" % s["thing"], True
        return ("Yes." if yes else "No.") + " (%d/20)" % s["asked"], False

    def _crossword(self, text):
        s = self.state
        clue, answer = CROSSWORD[s["i"]]
        if answer in text:
            s["score"] += 1
            line = "Correct! "
        else:
            line = "Not quite — it was '%s'. " % answer
        s["i"] += 1
        if s["i"] >= len(CROSSWORD):
            self.key = None
            return line + "Puzzle done: %d/%d." % (s["score"], len(CROSSWORD)), True
        return line + "#%d: %s" % (s["i"] + 1, CROSSWORD[s["i"]][0]), False


def snake_window(parent):
    """Open a small self-playing Snake board. Arrow keys seize control; Esc closes."""
    win = tk.Toplevel(parent)
    win.title("Nova plays Snake")
    win.configure(bg="#0D1420")
    cell, cols, rows = 18, 22, 16
    canvas = tk.Canvas(win, width=cols * cell, height=rows * cell, bg="#08121C",
                       highlightthickness=0)
    canvas.pack(padx=8, pady=8)
    state = {"snake": [(5, 8), (4, 8), (3, 8)], "dir": (1, 0),
             "food": (12, 8), "score": 0, "speed": 110, "manual": False}
    colors = {"head": "#00E5FF", "body": "#7CFFCB", "food": "#FF6B8A"}

    def draw():
        canvas.delete("all")
        fx, fy = state["food"]
        canvas.create_oval(fx * cell + 3, fy * cell + 3, fx * cell + cell - 3, fy * cell + cell - 3,
                           fill=colors["food"], outline="")
        for i, (x, y) in enumerate(state["snake"]):
            color = colors["head"] if i == 0 else colors["body"]
            canvas.create_rectangle(x * cell + 1, y * cell + 1, x * cell + cell - 1,
                                    y * cell + cell - 1, fill=color, outline="")
        canvas.create_text(6, 6, text="score %d  %s" % (
            state["score"], "you're driving" if state["manual"] else "Nova auto-play"),
            fill="#E8F6FF", anchor="nw", font=("Consolas", 9))

    def step():
        if not win.winfo_exists():
            return
        snake, (dx, dy) = state["snake"], state["dir"]
        if not state["manual"]:
            hx, hy = snake[0]
            fx, fy = state["food"]
            # greedy step toward food, avoiding walls and body
            options = []
            for nd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = hx + nd[0], hy + nd[1]
                if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in snake[:-1]:
                    options.append((abs(nx - fx) + abs(ny - fy), nd))
            if options:
                state["dir"] = min(options)[1]
                dx, dy = state["dir"]
        hx, hy = snake[0]
        nx, ny = hx + dx, hy + dy
        if not (0 <= nx < cols and 0 <= ny < rows) or (nx, ny) in snake[:-1]:
            state["snake"] = [(5, 8), (4, 8), (3, 8)]
            state["dir"], state["food"], state["score"] = (1, 0), (12, 8), 0
        else:
            snake.insert(0, (nx, ny))
            if (nx, ny) == state["food"]:
                state["score"] += 1
                state["food"] = (random.randrange(cols), random.randrange(rows))
            else:
                snake.pop()
        draw()
        win.after(state["speed"], step)

    def key(event):
        arrows = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}
        if event.keysym in arrows:
            state["manual"] = True
            state["dir"] = arrows[event.keysym]
        elif event.keysym == "Escape":
            win.destroy()

    win.bind("<Key>", key)
    win.focus_set()
    draw()
    win.after(state["speed"], step)
    return win


if __name__ == "__main__":
    room = GameRoom()
    print(room.start("trivia"))
    for answer in ("tokyo", "7", "72", "mars", "kitten"):
        reply, done = room.handle(answer)
        print(reply)
        if done:
            break
