# Nova animation assets — provenance & usage

The two VRM files in `../models/` are **rigs with no baked clips** (`animations: 0`).
Motion comes from the retarget-ready clips in this folder or from procedural code.

## Source

All six `.glb` motion clips were downloaded verbatim from:

`https://github.com/Yun-0000/Anima/tree/public-release/frontend/public/motions`

Anima is an MIT-licensed open-source animated-anime-companion project. Its
`ASSET_LICENSE.md` states the motions are **motion-capture exports from Meshy's
animation library** (names are Meshy library IDs), retargeted onto a Meshy rig,
with finger poses set in code. It also explicitly states **no Mixamo animations
are used**. Nod and head-shake in that project are procedural code, not files.

> **Licensing note:** the repository code is MIT, and `ASSET_LICENSE.md` grants
> clear redistribution terms for the *characters* (VRoid sample avatars), but it
> does not spell out redistribution terms for the *motion files* beyond naming
> their Meshy origin. They are fine for Nova's private local use. Verify with
> Meshy before shipping them inside a public redistributable release — or use
> the procedural clip below, which has no such ambiguity.

## The six clips (verified glTF 2.0, 66 anim channels each)

| File | Clip name | Duration | Use in Nova |
| --- | --- | --- | --- |
| `idle_243.glb` | `Idle_3` | 10.00 s | long idle variation |
| `idle_249.glb` | `Idle_9` | 2.03 s | short idle variation |
| `idle_252.glb` | `Idle_12` | 6.03 s | medium idle variation |
| `wave_290.glb` | `Wave_One_Hand` | 4.13 s | greeting / "hello" gesture |
| `explain_314.glb` | `Talk_with_Right_Hand_Open` | 3.77 s | talking-with-hands while explaining |
| `shrug_317.glb` | `Shrug` | 2.03 s | confusion / "I don't know" gesture |

Each file contains exactly one animation with rotation/translation/scale tracks
on a 26-node rig and **no skin** (bone-only tracks — ideal for retargeting).

### Bone-name mapping (clip rig → VRM humanoid)

The clips use Mixamo-style names. The standard three-vrm Mixamo retargeting map
applies directly:

```
Hips→hips        Spine→spine       Spine01→chest     Spine02→upperChest
neck→neck        Head→head
LeftShoulder→leftShoulder   LeftArm→leftUpperArm   LeftForeArm→leftLowerArm   LeftHand→leftHand
RightShoulder→rightShoulder RightArm→rightUpperArm RightForeArm→rightLowerArm RightHand→rightHand
LeftUpLeg→leftUpperLeg  LeftLeg→leftLowerLeg  LeftFoot→leftFoot  LeftToeBase→leftToes
RightUpLeg→rightUpperLeg RightLeg→rightLowerLeg RightFoot→rightFoot RightToeBase→rightToes
```

Retarget by copying each source node's local transform to the matched VRM human
bone, then let three-vrm's spring bones / look-at / expressions layer on top.
Anima's own implementation is `frontend/src/stage/meshyAnimation.ts` in that
repo (MIT); its README says the retargeting follows three-vrm's Mixamo example.

## Zero-dependency fallback: `procedural_idle.json`

Transcribed from `Kirakun0328/text-to-vrma` (`src/idleMotion.js`, MIT). It is a
4-second looping idle: breathing (chest 2.5°, hips −8 mm), gentle head sway,
arms out ~70° from T-pose, and two blinks. No retargeting, no external asset,
no ambiguous asset license. Use this first if you want Nova moving immediately;
swap in the mocap clips when a three-vrm viewer is wired up.

## What this does NOT include

- No walk/run/jump locomotion clips.
- No dance clip. (Music → dancing would need a dedicated dance `.glb`/`.vrma`,
  or a procedural dance built from bone keyframes — not present in these sources.)
- No lip-sync audio-driven shapes. The VRM's existing mouth blendshapes
  (`A I U E O`) plus `Blink`/`Joy`/`Angry` etc. can be driven from code instead.
- Nod / head-shake are procedural in the source project, not bundled files.
