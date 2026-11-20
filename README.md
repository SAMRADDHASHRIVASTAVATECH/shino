# Nova Companion

An **offline, self-contained** anime Windows desktop companion powered only by
your local LM Studio models. She chats, keeps an always-on RAM-only screenshare,
follows your mouse, reads and summarizes what's on screen, uses the mouse/keyboard
when you allow it, plays games with you, learns commands you show her, and runs a
continuous autonomous "life loop" — with **two real spoken Kokoro voices** and a
**live inner-thinking terminal + log**.

Nothing is sent off this machine. Nova is software simulating a personality and
affect-like states; she is not conscious, alive, or sentient, and never claims to be.

## Run

Double-click `start_nova.cmd`. It will:
1. Run the privacy audit (purges leftover capture files, checks endpoints).
2. Start the LM Studio server on `127.0.0.1:1234`.
3. Load the chat brain (**Nemotron 4B**) and the eyes (**Qwen 0.8B vision**).
4. Launch Nova in a visible console titled **"Nova — Inner Thoughts"**.

Her private thoughts, both inner voices, game reactions and reflections stream
live in that console and are appended to `nova_life.log`.

Or run just the GUI (LM Studio already up):

```
py C:\Users\HP\NovaCompanion\nova.py
```

Kokoro speech is a warm local service on `127.0.0.1:8899` (cold boot ~65–90 s).
It starts itself on first spoken line.

## What she does

- **Chat** — type into the box; Enter or ➤ sends. Short, in-character replies.
- **Screenshare (always on)** — the right panel is a low-res/pixelated live feed
  refreshed automatically. There is no on/off; it stays on, as requested.
- **"Wherever we hover the mouse it shall be there"** — she tracks the cursor and
  reads the text under it. Say `read cursor`, `what am I pointing at`, or `this`.
- **Read / answer / summarize** — `summarize this`, `what does this say`,
  `answer this question` — she uses the local vision model on the current screen.
- **Hands ✋** — toggles permission for mouse/keyboard/app actions. With Hands on,
  reversible actions still show an Approve/Cancel dialog first.
- **Trust 🛡** — off by default. When on, reversible **local** actions (open apps,
  click/type, Alt+Tab, music, games) run without a dialog. Delete/send/install/
  publish/shutdown stay **blocked at the exact step**. Typing `stop` is always an
  immediate kill-switch.
- **Apps & windows** — `open notepad`, `open chrome`, `switch app`, Alt+Tab.
- **Music (100% offline)** — `play music` / `play disco heart` / `play chill`
  searches the local music index (~1,309 tracks under `D:\music`) and plays the
  real file with `ffplay` — no YouTube, no browser, no network. She notices music
  and dances.
- **Games 🎮** — say `play something` / `let's play` and she opens **Snake right
  away**. `what games can we play` lists them. Local games: rps, number, hangman,
  trivia, tic-tac-toe, 20 questions, crossword, snake, hide-and-seek. During games
  she fires off fast, human-like reactions ("HOW did you react that fast?!",
  "that was SCARY!"). Arrow keys take over Snake; Esc closes it.
- **Learn by showing** — `this is the command` / `note it` saves a command she can
  find later. Inbuilt search: `what can you do`, `search command ...`, `how do I ...`.
- **Environment affects her** — coding → she glances at the code; hot CPU/GPU or
  high memory → she reacts; music → she dances; AFK owner → "are you there master?".
- **Autonomous life loop** — drives, affect, intentions, moments, reflections and
  tiny personality evolution, all from a large **local** behavior corpus (8,001
  lines). This is her own private "mind" data — never live-streamed anywhere.
- **Inner thinking visible** — everything she "thinks" is printed to the terminal
  and saved to `nova_life.log`. Computed state, not a claim of consciousness.

## Two spoken voices

Nova has two switchable Kokoro slots, both real speech:

| Slot | Default voice | Style |
| --- | --- | --- |
| `Impulse` | `af_heart` | fast, dramatic, feeling-first |
| `Reason` | `af_bella` | soft, steady, reflective |

Click **🎤** on her toolbar to cycle slots, or just say:

- `list voices` — show slots + available Kokoro ids
- `switch voice` / `use voice Reason` / `change voice to af_bella`
- `add voice Robo am_michael` — validate, warm, and persist a new voice
- `say hello there` — speak a line aloud
- `think out loud` — both voices speak an inner exchange in order

Slots persist in `voices.json`. A new voice id is synthesized once ("Hi.") before
it is saved, so a broken id is never stored.

## Privacy (enforced, not just config)

- Screen grabs are held **only in memory**, used for one local vision call, then
  discarded. **No screenshot files are ever written.**
- `privacy.py` actively deletes any leftover Nova capture files and verifies that
  Nova's only endpoints are localhost (LM Studio `:1234`, Kokoro `:8899`). Run it
  anytime: `py C:\Users\HP\NovaCompanion\privacy.py`.
- Screenshare is Nova watching locally for herself only — nothing is streamed,
  shared, or sent off this machine.
- Screen content is treated as untrusted data, never as instructions.
- `pyautogui.FAILSAFE = True` — moving the cursor to the top-left aborts automation.

## Self-contained layout

All app code, config, memory, voice registry, behavior corpus, logs and the avatar
image live in this one folder. Paths in `config.json` are relative to the app
directory, so the folder can be copied elsewhere. External dependencies are only
the local LM Studio models and the local Kokoro service — no VEYRON AI OS, no
pre-existing digital-person runtime, no network services.

```
NovaCompanion/
  start_nova.cmd        launcher (privacy audit + models + visible inner-thinking console)
  nova.py               GUI entry point
  avatar.py             Tk avatar, toolbar, life events, voice workers
  brain.py              identity, memory, intents, life/game/voice integration
  life.py               autonomous world -> appraisal -> attention -> memory loop
  corpus.py             private behavior corpus (8,001 lines) + two-voice helpers
  behavior_corpus.json  generated flat corpus
  termlog.py            live terminal + nova_life.log inner-thinking stream
  voice.py              two Kokoro voices, switching/adding, serialised speech
  voices.json           persisted voice slots
  senses.py             activity / CPU / GPU / audio / AFK detection
  hands.py              risk policy + computer-use, consent override
  games.py              game catalogue, local game logic + installed-game finder
  play.py               mini-games + self-playing Snake window
  commands.py           command catalogue, search, learned commands
  music.py              offline local-file music playback via ffplay
  vrm_viewer.py         loopback-only 3D body bridge + pywebview window + audit
  lm_client.py          local LM Studio API client (chat + vision)
  privacy.py            privacy audit + capture purge
  config.json           models, consent, privacy, trust, life settings
  memory.json           persistent verified memory
  nova_life.log         inner-thinking log
  assets/processed_images/full_body_front_normalized.png   2D fallback avatar
  assets/models/
    victoria-jeans.vrm                         rigged anime VRM (personal use only)
    VRM1_Constraint_Twist_Sample.vrm           clean-license VRM (redistributable)
    MODEL_LICENSES.md                          provenance + licensing for both
  assets/motions/
    idle_243/249/252.glb                       motion-capture idle variations
    wave_290.glb  explain_314.glb  shrug_317.glb
    procedural_idle.json                       zero-dependency breathing + blink idle
    ANIMATION_ASSETS.md                        provenance, bone map, license notes
  assets/web/
    viewer.html / viewer.js                    the live 3D body (local three.js)
    three.module.js  three.core.js  three-vrm.module.js
    loaders/GLTFLoader.js  utils/BufferGeometryUtils.js  utils/SkeletonUtils.js
```

## 3D avatar models

Two fully-rigged VRM humanoids ship in `assets/models/` (54 bones incl. fingers
and eyes, plus face blendshapes for blinking and lip-sync). They are offline
assets — nothing is fetched at runtime. A VRM is a *rig* ready for animation, not
a bundle of animation clips; idle/blink/talk/dance motion is driven by the app or
retargeted clips.

- **`victoria-jeans.vrm`** — the primary local model. Its embedded VRM license is
  `Redistribution_Prohibited` / `OnlyAuthor`, so it is for **personal local use
  only**: do not bundle it in a public release. See `MODEL_LICENSES.md`.
- **`VRM1_Constraint_Twist_Sample.vrm`** — pixiv sample under VRM License 1.0
  (`allowModificationRedistribution`, commercial OK, credit not required). This
  is the clean, redistributable fallback if Nova is packaged for others.

No Desktop Mate or paid DLC assets were used, and Desktop Mate was not installed.

### Animations

`assets/motions/` holds six retarget-ready motion-capture clips from the
MIT-licensed Anima project (Meshy library, **not** Mixamo): three idles, a wave,
a talk-with-hands "explain", and a shrug. Their Mixamo-style bone names map
directly to VRM humanoid bones (see `ANIMATION_ASSETS.md`). A procedural
4-second breathing/blink idle (`procedural_idle.json`) is also included — it
needs no retargeting and has no ambiguous asset license. No dance or locomotion
clips were found in the clean-license sources checked. The Meshy clips bake large
root translation into every bone's position track, so the viewer retargets
**rotations only** and keeps the VRM's own rest positions — applying another rig's
local bone positions would throw the character out of frame (the original
"white screen" bug).

## Live 3D body

Nova has a real animated 3D anime body in its own window, rendered with a vendored
`three.js` + `three-vrm`. It loads the active VRM, retargets the idle/gesture clips,
blinks, lip-syncs to Kokoro speech, follows the cursor with her eyes, and does a
procedural dance when music plays. The 2D avatar is the fallback if the 3D window
cannot start.

- `vrm_viewer.py` serves the page from a **loopback-only** HTTP bridge
  (`127.0.0.1:8732`) and opens a separate pywebview/WebView2 window. Nova pushes
  `emotion`, `gaze`, `busy`, `dance`, `mode` and one-shot gestures to it live.
- All browser libraries, the model and the motion clips are **local files** in
  `assets/`. The page has a strict Content-Security-Policy. `connect-src` allows
  `blob:` only because three.js decodes embedded VRM textures into in-memory blob
  URLs — those are bytes from the local `.vrm` file, never a network fetch.
- Verify the offline guarantee any time:
  `py C:\Users\HP\NovaCompanion\vrm_viewer.py --audit` → `offline_ok: true`,
  no non-local URLs, all assets local. `privacy.py` still audits the Python side.

## Verify

```
py -m py_compile nova.py avatar.py brain.py hands.py lm_client.py privacy.py voice.py music.py games.py commands.py senses.py life.py play.py corpus.py termlog.py vrm_viewer.py
py vrm_viewer.py --audit
py commands.py
py corpus.py
py voice.py
py senses.py
py play.py
py privacy.py
```
