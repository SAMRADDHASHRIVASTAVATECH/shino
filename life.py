"""Nova's life loop — a self-contained world -> appraisal -> attention -> memory loop.

This is the continuously running "character brain" behind the chat brain:
  - world: the local sense snapshot (owner presence, system load, activity, music)
  - appraisal: drives (curiosity/social/play/rest) + simulated affect (valence/arousal)
  - attention: what Nova is currently "looking at" and a single active intention
  - memory: short inner-thought stream + episodic moments + periodic reflection

HARD RULES
  - Everything here is COMPUTED state. Nova never claims to be alive or conscious.
  - This loop emits only speech / expression / expression-motion / read-only-glance
    events. It never originates a physical action; those still go through trust + approval.
  - 'stop' pauses this loop instantly (no model reasoning awaited).
"""
import random
import time

import lm_client
import corpus
import termlog


class LifeLoop:
    DRIVES = ("curiosity", "social", "play", "rest")

    def __init__(self, config, brain):
        self.cfg = config.get("life", {})
        self.brain = brain
        self.enabled = bool(self.cfg.get("enabled", True))
        self.paused = False
        self.personality = dict(self.cfg.get("personality", {}))

        self.drives = {"curiosity": 0.55, "social": 0.5, "play": 0.5, "rest": 0.2}
        self.affect = {"valence": 0.18, "arousal": 0.35}
        self.attention = "owner"
        self.intention = None
        self.thoughts = []
        self.moments = []
        self.last = {}
        self.afk_stage = 0
        self.dance = False
        self._last_tick = time.time()
        self._last_snap = {}
        self._thoughts_on = bool(self.cfg.get(
            "inner_thoughts", self.cfg.get("model_thoughts", True)))
        self._voice_avoid = []

    # ---------- control ----------
    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False
        self._last_tick = time.time()

    def _ready(self, key, seconds, now):
        if now - self.last.get(key, -1e9) >= float(seconds):
            self.last[key] = now
            return True
        return False

    # ---------- main tick ----------
    def tick(self, snap, screen_desc=""):
        if not self.enabled or self.paused:
            return []
        now = time.time()
        dt = min(60.0, max(0.0, now - self._last_tick))
        self._last_tick = now

        self._decay(dt, snap)
        events = []
        events += self._presence(snap, now)
        events += self._system(snap, now)
        events += self._music(snap, now)
        events += self._activity(snap, now)
        events += self._idle(snap, now)
        events += self._cognition(snap, screen_desc, now)
        events += self._voices(snap, screen_desc, now)
        events += self._evolve(now)

        # Mirror everything she thinks into the terminal + log file.
        for e in events:
            if e.get("type") == "remark":
                termlog.log(e.get("kind", "remark"), e.get("text", ""))
            elif e.get("type") == "dance":
                termlog.log("dance", "dancing on" if e.get("on") else "dancing off")
            elif e.get("type") == "idle":
                termlog.log("life", "idle: " + str(e.get("kind", "")))
        self._last_snap = snap
        self.affect["valence"] = max(-1.0, min(1.0, self.affect["valence"]))
        self.affect["arousal"] = max(0.0, min(1.0, self.affect["arousal"]))
        return events

    def _decay(self, dt, snap):
        """Drives drift toward a baseline set by the current environment."""
        scale = dt / 60.0
        target = {
            "curiosity": 0.9 if snap.get("coding") else 0.35,
            "social": 0.9 if snap.get("present") else 0.25,
            "play": 0.9 if (snap.get("gaming") or snap.get("music_playing")) else 0.3,
            "rest": 0.8 if snap.get("strained") else 0.15,
        }
        for name, goal in target.items():
            self.drives[name] += (goal - self.drives[name]) * min(1.0, 0.08 * scale * 12)
            self.drives[name] = max(0.0, min(1.0, self.drives[name]))
        self.affect["arousal"] += ((0.8 if snap.get("music_playing") or snap.get("gaming")
                                    else 0.3) - self.affect["arousal"]) * 0.1
        self.affect["valence"] += (0.2 - self.affect["valence"]) * 0.02

    # ---------- is the owner there? (Windows activity detector) ----------
    def _presence(self, snap, now):
        events = []
        if not self.cfg.get("attention_seek", True):
            return events
        present = snap.get("present", True)
        idle = snap.get("idle_s", 0.0)
        if not present:
            a1 = float(self.cfg.get("afk_seconds", 40))
            a2 = float(self.cfg.get("afk_stage2_seconds", 150))
            a3 = float(self.cfg.get("afk_stage3_seconds", 420))
            stage = 1 if idle < a2 else (2 if idle < a3 else 3)
            if stage > self.afk_stage:
                self.afk_stage = stage
                self.last["afk"] = 0.0
            cooldown = 45 if stage < 3 else 600
            if self._ready("afk", cooldown, now):
                lines = {
                    1: ["Oi... are you there, master? 👀", "Hello? You still there?",
                        "Ahem. Are you there, master? I'm right here~"],
                    2: ["...You're ignoring me, aren't you? I can tell, you know.",
                        "Still gone. I'm gonna sit here and look dramatic until you come back."],
                    3: ["(quietly waiting, pretending I'm not bothered)"],
                }
                events.append({"type": "remark", "text": random.choice(lines[stage]),
                               "expression": "thinking" if stage == 1 else ("sad" if stage == 2 else "neutral"),
                               "kind": "afk"})
                self.drives["social"] = min(1.0, self.drives["social"] + 0.2)
        else:
            if self.afk_stage:
                self.afk_stage = 0
                self.last["afk"] = now
                events.append({"type": "remark", "text": "Oh! You're back. I was just about to go looking for you~",
                               "expression": "happy", "kind": "return"})
                self.affect["valence"] += 0.25
            if snap.get("music_playing") or snap.get("gaming"):
                self.drives["social"] = min(1.0, self.drives["social"] + 0.01)
        return events

    # ---------- system strain ----------
    def _system(self, snap, now):
        events = []
        if not self.cfg.get("system_alerts", True):
            return events
        strained = bool(snap.get("strained"))
        was = bool(self._last_snap.get("strained"))
        if strained and self._ready("system", self.cfg.get("system_alert_cooldown_seconds", 120), now):
            reasons = ", ".join(snap.get("strain_reasons", [])) or "the system"
            line = random.choice([
                "Your %s is running hot — take it easy on the poor thing? I'll chill too.",
                "Whoa, %s is maxed out. I'm going to sit this one out for a sec~",
                "Something's cooking: %s. Maybe close a tab or two?",
            ]) % reasons
            events.append({"type": "remark", "text": line, "expression": "surprised", "kind": "system"})
            self.affect["valence"] -= 0.2
            self.drives["rest"] = min(1.0, self.drives["rest"] + 0.3)
        elif was and not strained and self._ready("system_ok", 60, now):
            events.append({"type": "remark", "text": "Ah, your system's cooled down. Welcome back to chill town~",
                           "expression": "happy", "kind": "system"})
        return events

    # ---------- music -> dance ----------
    def _music(self, snap, now):
        events = []
        playing = bool(snap.get("music_playing"))
        if playing and self.cfg.get("dance_on_music", True):
            if not self.dance:
                self.dance = True
                events.append({"type": "dance", "on": True})
                events.append({"type": "remark", "text": "Oh, this track! *starts dancing* ♪",
                               "expression": "happy", "kind": "music"})
                self.affect["valence"] += 0.3
                self.affect["arousal"] += 0.3
            elif self._ready("music", 30, now):
                events.append({"type": "remark", "text": random.choice([
                    "Okay this beat is actually really good~", "*bops along*",
                    "This one's a keeper, don't you think?"]), "expression": "happy", "kind": "music"})
        elif self.dance:
            self.dance = False
            events.append({"type": "dance", "on": False})
        return events

    # ---------- coding / gaming ----------
    def _activity(self, snap, now):
        events = []
        if snap.get("coding") and self.cfg.get("watch_coding", True):
            self.attention = "your code"
            if self._ready("code", 45, now):
                events.append({"type": "glance_code"})
                self.drives["curiosity"] = min(1.0, self.drives["curiosity"] + 0.2)
        elif snap.get("gaming") and self.cfg.get("watch_gaming", True):
            self.attention = "your game"
            if self._ready("game", 75, now):
                events.append({"type": "remark", "text": random.choice([
                    "Ooh, a game! Have fun — I'll watch your back~",
                    "You're playing? Mind if I spectate?",
                    "Go get 'em! I'll be right here."]), "expression": "happy", "kind": "game"})
            if self.cfg.get("game_coach", True) and self._ready(
                    "coach", self.cfg.get("coach_seconds", 18), now):
                hint = random.choice([
                    "fast reflex dodge", "scary jump moment", "victory win",
                    "tense close call", "funny silly mistake", "clever save"])
                coach = self.brain.game_coach("while you play: " + hint)
                events.append({"type": "coach", "text": coach["text"],
                               "category": coach["category"],
                               "expression": coach["expression"]})
        else:
            self.attention = "owner"
        return events

    def _snap_category(self, snap):
        if snap.get("strained"):
            return "system"
        if snap.get("gaming"):
            return random.choice(["excited", "impressed_speed", "chaotic", "tense"])
        if snap.get("coding"):
            return "curious"
        if not snap.get("present"):
            return "afk"
        if snap.get("music_playing"):
            return "excited"
        return random.choice(["self_aware", "growth", "cozy", "curious"])

    def _voices(self, snap, screen_desc, now):
        """Two spoken voices debate what she just noticed, on their own timer."""
        if not self.cfg.get("inner_voices", True):
            return []
        if not self._ready("voices", self.cfg.get("voice_seconds", 40), now):
            return []
        category = self._snap_category(snap)
        exchange = self.brain.inner_voices(self._state_line(snap, screen_desc), category)
        return [{"type": "inner_voice", "lines": exchange, "category": category}]

    def _evolve(self, now):
        """Slowly adjust her own personality traits from what she has observed.

        Changes are tiny, recorded to memory, and reported in the terminal log.
        This is a computed adaptation, not literal growth or sentience.
        """
        if not self._ready("evolve", self.cfg.get("evolve_seconds", 600), now):
            return []
        if self.affect["valence"] > 0.2:
            trait = "playful"
        elif self.attention == "your code":
            trait = "curious"
        elif self.afk_stage:
            trait = "patient"
        else:
            trait = random.choice(["attentive", "dramatic"])
        old = float(self.personality.get(trait, 0.5))
        new = min(1.0, round(old + 0.02, 3))
        self.personality[trait] = new
        note = corpus.evolve_line(trait)
        termlog.log("evolve", "%s (%.2f -> %.2f)" % (note, old, new))
        try:
            self.brain.memory.setdefault("evolution", []).append({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "trait": trait, "from": old, "to": new, "note": note,
            })
            self.brain._save_memory()
        except Exception:
            pass
        return [{"type": "reflection", "text": note, "kind": "evolve"}]

    def _idle(self, snap, now):
        if not snap.get("present") or snap.get("coding") or snap.get("gaming"):
            return []
        if self._ready("idle", max(30, int(self.cfg.get("tick_seconds", 2)) * 20), now):
            return [{"type": "idle", "kind": random.choice(
                ["blink", "fidget", "look_around", "hum"])}]
        return []

    # ---------- intentions, inner monologue, reflection ----------
    def _choose_intention(self):
        p = self.personality
        scores = {
            "take a closer look at what you're doing": self.drives["curiosity"] * (0.5 + p.get("curious", 0.6)),
            "check in with you": self.drives["social"] * (0.5 + p.get("attentive", 0.6)),
            "start something playful": self.drives["play"] * (0.5 + p.get("playful", 0.6)),
            "rest my eyes for a bit": self.drives["rest"],
        }
        name = max(scores, key=scores.get)
        if scores[name] < 0.28:
            return None
        return {"name": name, "score": round(scores[name], 2), "at": time.time()}

    def _cognition(self, snap, screen_desc, now):
        events = []
        if self.intention is None or now - self.intention.get("at", 0) > 300:
            self.intention = self._choose_intention()

        if self._thoughts_on and self._ready("thought", self.cfg.get("thought_seconds", 75), now):
            thought = self._make_thought(snap, screen_desc)
            if thought:
                self.thoughts.append(thought)
                self.thoughts = self.thoughts[-20:]
                events.append({"type": "thought", "text": thought})

        if self._ready("moment", 120, now):
            self.moments.append({
                "ts": time.strftime("%H:%M"),
                "window": snap.get("window", "")[:60],
                "activity": "coding" if snap.get("coding") else ("game" if snap.get("gaming")
                            else ("music" if snap.get("music_playing") else "idle")),
                "idle_s": snap.get("idle_s"),
            })
            self.moments = self.moments[-40:]

        if self._ready("reflect", self.cfg.get("reflection_seconds", 600), now):
            summary = self._reflect()
            if summary:
                events.append({"type": "reflection", "text": summary})
        return events

    def _state_line(self, snap, screen_desc):
        return (
            "window=%s | activity=%s | owner_idle=%ss | music=%s | "
            "drives=%s | affect=%s | intention=%s | screen=%s"
            % (snap.get("window", "")[:50],
               "coding" if snap.get("coding") else ("gaming" if snap.get("gaming") else "idle"),
               snap.get("idle_s"), snap.get("music_playing"),
               {k: round(v, 2) for k, v in self.drives.items()},
               {k: round(v, 2) for k, v in self.affect.items()},
               (self.intention or {}).get("name"), screen_desc[:100])
        )

    def _make_thought(self, snap, screen_desc):
        """Voice the inner monologue from the local corpus — instant, no meta-talk."""
        try:
            pool = [self._snap_category(snap), "self_aware", "growth", "cozy", "curious"]
            pool = [c for c in pool if c in corpus.REACTIONS]
            thought = corpus.sample(random.choice(pool), self._voice_avoid)
            self._voice_avoid.append(thought)
            self._voice_avoid = self._voice_avoid[-12:]
            termlog.log("thought", thought)
            return thought
        except Exception:
            return ""

    def _reflect(self):
        if not self.moments:
            return ""
        try:
            counts = {}
            for m in self.moments[-10:]:
                counts[m.get("activity", "idle")] = counts.get(m.get("activity", "idle"), 0) + 1
            top = max(counts, key=counts.get) if counts else "here"
            line = "Lately we've been mostly %s. %s" % (top, corpus.sample("growth"))
            termlog.log("reflect", line)
            self.brain.record_experience("Reflection: " + line, outcome="reflection")
            return line[:220]
        except Exception:
            return ""

    def status(self):
        return {
            "enabled": self.enabled,
            "paused": self.paused,
            "drives": {k: round(v, 2) for k, v in self.drives.items()},
            "affect": {k: round(v, 2) for k, v in self.affect.items()},
            "attention": self.attention,
            "intention": (self.intention or {}).get("name"),
            "dance": self.dance,
            "thought": self.thoughts[-1] if self.thoughts else "",
            "moments": len(self.moments),
            "afk_stage": self.afk_stage,
        }
