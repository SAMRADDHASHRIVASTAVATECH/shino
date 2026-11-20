# Nova avatar model assets — provenance & licensing

These are the 3D humanoid avatar models shipped in this folder. Both are genuine
VRM humanoids (54 humanoid bones including fingers and eyes) and are fully
offline assets — no download or network call is made at runtime.

A VRM file is a **rigged, skinned character** ready to be animated. Neither file
bundles animation clips (`animations: 0`). Idle / blink / talk / dance / emotion
motion must be driven by code or by retargeted `.vrma` / mocap clips — the rig,
face blendshapes (mouth shapes A/I/U/E/O, Blink/Angry/Joy/Sorrow/Surprised) and
spring bones are what make that possible.

---

## 1. `victoria-jeans.vrm` — primary local model (personal use only)

| Field | Value |
| --- | --- |
| Source URL | `https://raw.githubusercontent.com/vladmandic/human-three-vrm/main/assets/victoria-jeans.vrm` |
| Upstream repo | `https://github.com/vladmandic/human-three-vrm` (repository **code** is MIT) |
| File size | 12,115,176 bytes |
| Format | VRM 0.x (glTF 2.0, extension key `VRM`) |
| Embedded author | `Cyan` (title also `Cyan`) |
| Embedded license | `Redistribution_Prohibited` |
| Permissions | `allowedUserName=OnlyAuthor`, commercial `Disallow`, violent `Disallow`, sexual `Disallow` |
| Rig | 54 humanoid bones (all fingers, both eyes), 15 blendshape expressions, 8 materials, 3 meshes, 14 images |

**Licensing status:** The MIT license on the *repository code* does **not**
override the model's own embedded VRM license. That metadata explicitly says
`Redistribution_Prohibited` and `OnlyAuthor`.

- ✅ **Allowed here:** using this file locally on this machine as Nova's personal
  avatar. This is a private, offline companion; personal local use is fine.
- ❌ **Do not:** bundle this file in a public/redistributable release of Nova,
  host it for download, or use it commercially, without first obtaining
  permission from the author (Cyan) or swapping in the clean-licensed model below.

---

## 2. `VRM1_Constraint_Twist_Sample.vrm` — clean-licensed fallback (redistributable)

| Field | Value |
| --- | --- |
| Source URL | `https://raw.githubusercontent.com/pixiv/three-vrm/dev/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm` |
| Upstream repo | `https://github.com/pixiv/three-vrm` |
| File size | 10,776,032 bytes |
| Format | VRM 1.0 (glTF 2.0, extension key `VRMC_vrm`) |
| Author | pixiv Inc. — © 2022 pixiv Inc. |
| License | `https://vrm.dev/licenses/1.0/` (VRM License 1.0) |
| Permissions | `avatarPermission=everyone`, `commercialUsage=corporation`, `modification=allowModificationRedistribution`, `creditNotation=unnecessary` |
| Rig | 54 humanoid bones, plus `VRMC_springBone` |

**Licensing status:** Clean. Modification and redistribution are explicitly
permitted, commercial use is allowed, and credit is not required. This is the
model to ship / redistribute if Nova is ever packaged for others. It is a
technical constraint/twist sample, so it is less "character-like" visually than
Victoria — swap models by changing the configured VRM path.

---

## Model provenance summary

- Both files were downloaded verbatim from the source URLs above; bytes were not
  edited. Validated by glTF magic (`glTF` = `103,108,84,70`) and by parsing the
  embedded JSON chunk for humanoid bones and license metadata.
- No proprietary Desktop Mate / paid DLC assets were used. Desktop Mate was not
  installed.
- If in doubt for a public release, use model #2.
- Animation clips (a separate concern from the model rigs) are documented in
  `../motions/ANIMATION_ASSETS.md`.
