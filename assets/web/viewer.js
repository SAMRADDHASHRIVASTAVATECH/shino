/* Nova's offline 3D body — three.js + three-vrm, all assets from this PC. */
import * as THREE from 'three';
import { GLTFLoader } from '/web/loaders/GLTFLoader.js';
import { VRM, VRMLoaderPlugin, VRMUtils } from '/web/three-vrm.module.js';

// Pet mode (?pet=1): transparent window, the girl is the only visible UI.
const PET = new URLSearchParams(location.search).get('pet') === '1';
if (PET) document.body.classList.add('pet');

const errBox = document.getElementById('err');
function report(message) {
  if (PET) errBox.style.display = 'none';   // never show debug text to the user
  errBox.textContent = message;
  fetch('/event', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message})
  }).catch(() => {});
}
window.addEventListener('error', e => report('viewer error: ' + e.message));

/* ---------- renderer / scene ---------- */
const renderer = new THREE.WebGLRenderer({antialias: true, alpha: PET,
                                           preserveDrawingBuffer: true,
                                           powerPreference: 'high-performance'});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5)); // small GPU: cap it
renderer.setSize(innerWidth, innerHeight);
renderer.setClearColor(PET ? 0x000000 : 0x0D1420, PET ? 0 : 1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 0.01, 100);
camera.position.set(0, 1.15, 2.6);
camera.lookAt(0, 1.05, 0);

scene.add(new THREE.HemisphereLight(0xd9e7ff, 0x2a2233, 1.15));
const key = new THREE.DirectionalLight(0xffffff, 1.25);
key.position.set(2.5, 4, 3);
scene.add(key);
const rim = new THREE.DirectionalLight(0x66ccff, 0.6);
rim.position.set(-2.5, 2.5, -2);
scene.add(rim);
const fill = new THREE.DirectionalLight(0xff99cc, 0.3);
fill.position.set(-1.5, 1, 3);
scene.add(fill);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

/* ---------- bone map: mocap rig (Mixamo-style) -> VRM humanoid ---------- */
const BONE_MAP = {
  Hips:'hips', Spine:'spine', Spine01:'chest', Spine02:'upperChest',
  neck:'neck', Head:'head',
  LeftShoulder:'leftShoulder', LeftArm:'leftUpperArm',
  LeftForeArm:'leftLowerArm', LeftHand:'leftHand',
  RightShoulder:'rightShoulder', RightArm:'rightUpperArm',
  RightForeArm:'rightLowerArm', RightHand:'rightHand',
  LeftUpLeg:'leftUpperLeg', LeftLeg:'leftLowerLeg',
  LeftFoot:'leftFoot', LeftToeBase:'leftToes',
  RightUpLeg:'rightUpperLeg', RightLeg:'rightLowerLeg',
  RightFoot:'rightFoot', RightToeBase:'rightToes'
};

const IDLE_FILES = ['idle_243.glb', 'idle_249.glb', 'idle_252.glb'];
const GESTURE_FILES = {wave:'wave_290.glb', explain:'explain_314.glb', shrug:'shrug_317.glb'};

let vrm = null, mixer = null, nodes = {}, rest = {};
let idleActions = [], gestureActions = {}, currentIdle = null;
let targetNodes = {};
let state = {emotion:'neutral', speaking:false, dance:false, busy:false,
             mode:'IDLE', gaze:{x:0,y:0}, gesture:{name:'', nonce:0},
             bubble:'', bubble_nonce:0, version:-1};
let loaded = false;
const clock = new THREE.Clock();

/* ---------- helpers ---------- */
function captureRest() {
  rest = {};
  for (const [src, bone] of Object.entries(BONE_MAP)) {
    const node = nodes[src];
    if (node) rest[src] = {q: node.quaternion.clone(), p: node.position.clone(),
                           s: node.scale.clone()};
  }
}

function remapClip(clip, srcRest) {
  const tracks = [];
  for (const track of clip.tracks) {
    const dot = track.name.lastIndexOf('.');
    const srcName = track.name.slice(0, dot);
    const prop = track.name.slice(dot + 1);
    const node = nodes[srcName], src = srcRest[srcName];
    if (!node || !src) continue;
    // IMPORTANT: retarget ROTATIONS only. These Meshy mocap clips bake large
    // root translation into every bone's position track (e.g. Hips Y = -2.4),
    // which shoved the VRM out of frame. Applying a different rig's local bone
    // positions is never valid — keep the VRM's own rest positions instead.
    if (prop !== 'quaternion') continue;
    const v = track.values, out = new Float32Array(v.length);
    for (let i = 0; i < v.length; i += 4) {
      const q = new THREE.Quaternion(v[i], v[i+1], v[i+2], v[i+3]);
      const delta = src.q.clone().invert().multiply(q);
      const result = rest[srcName].q.clone().multiply(delta);
      out[i] = result.x; out[i+1] = result.y;
      out[i+2] = result.z; out[i+3] = result.w;
    }
    tracks.push(new THREE.QuaternionKeyframeTrack(node.name + '.quaternion',
                                                  track.times, out));
  }
  return new THREE.AnimationClip(clip.name, clip.duration, tracks);
}

function loadMotion(path, cb) {
  new GLTFLoader().load(path, gltf => {
    const srcRest = {};
    gltf.scene.traverse(o => {
      if (nodes[o.name] && !srcRest[o.name]) {
        srcRest[o.name] = {q:o.quaternion.clone(), p:o.position.clone(),
                           s:o.scale.clone()};
      }
    });
    if (!gltf.animations.length) { cb(null); return; }
    cb(remapClip(gltf.animations[0], srcRest));
  }, undefined, () => cb(null));
}

/* ---------- load the VRM ---------- */
const loader = new GLTFLoader();
loader.register(parser => new VRMLoaderPlugin(parser));
// The local bridge resolves this alias to whatever model Nova selected.
loader.load('/models/active.vrm', gltf => {
  vrm = gltf.userData.vrm;
  if (!vrm) { report('no VRM data in model'); return; }
  VRMUtils.removeUnnecessaryVertices(gltf.scene);
  VRMUtils.combineSkeletons(gltf.scene);
  if (String(vrm.meta.metaVersion) === '0') VRMUtils.rotateVRM0(vrm);
  scene.add(vrm.scene);

  // Give each human bone a unique name so AnimationMixer can bind to it.
  for (const [src, bone] of Object.entries(BONE_MAP)) {
    const node = vrm.humanoid.getRawBoneNode(bone);
    if (node) {
      node.name = 'nova_' + bone;
      nodes[src] = node;
      targetNodes[src] = node;
    }
  }
  captureRest();
  const count = Object.keys(nodes).length;
  mixer = new THREE.AnimationMixer(vrm.scene);

  // face / look-at target
  const look = new THREE.Object3D();
  look.position.set(0, 1.35, 1.6);
  scene.add(look);
  if (vrm.lookAt) vrm.lookAt.target = look;

  // frame the character
  const box = new THREE.Box3().setFromObject(vrm.scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const dist = Math.max(size.y * 0.95, size.x * 1.1) /
               (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.34;
  camera.position.set(center.x, center.y, center.z + dist);
  camera.lookAt(center.x, center.y, center.z);
  camera.updateProjectionMatrix();

  // motion clips
  let remaining = IDLE_FILES.length + Object.keys(GESTURE_FILES).length;
  const done = () => {
    remaining--;
    if (remaining === 0) {
      loaded = true;
      if (idleActions.length) {
        currentIdle = idleActions[0];
        currentIdle.reset().fadeIn(0.6).play();
      }
      report(`ready: ${count} humanoid bones, ${idleActions.length} idles, ` +
             `${Object.keys(gestureActions).length} gestures — fully offline`);
    }
  };
  IDLE_FILES.forEach(path => loadMotion('/motions/' + path, clip => {
    if (clip) {
      const a = mixer.clipAction(clip);
      a.setLoop(THREE.LoopRepeat, Infinity);
      idleActions.push(a);
    }
    done();
  }));
  Object.entries(GESTURE_FILES).forEach(([name, path]) =>
    loadMotion('/motions/' + path, clip => {
      if (clip) {
        const a = mixer.clipAction(clip);
        a.setLoop(THREE.LoopOnce, 1);
        a.clampWhenFinished = true;
        gestureActions[name] = a;
      }
      done();
    }));

  // idle variation swap every ~18 s
  setInterval(() => {
    if (!loaded || !idleActions.length || state.dance) return;
    const next = idleActions[Math.floor(Math.random() * idleActions.length)];
    if (next === currentIdle) return;
    next.reset().fadeIn(0.9).play();
    if (currentIdle) currentIdle.fadeOut(0.9);
    currentIdle = next;
  }, 18000);
}, undefined, err => report('model load failed: ' + (err?.message || err)));

/* ---------- state -> body ---------- */
const EXPR = {happy:'joy', sad:'sorrow', angry:'angry', surprised:'surprised',
              thinking:'neutral', neutral:'neutral'};
const MOUTHS = ['aa', 'ih', 'uu', 'ee', 'oh'];
let blinkClock = 2.0, blinkPhase = -1, mouthClock = 0;

function setExpression(name) {
  if (!vrm?.expressionManager) return;
  const em = vrm.expressionManager;
  ['joy','sorrow','angry','surprised','neutral'].forEach(k => em.setValue(k, 0));
  const key = EXPR[name] || 'neutral';
  em.setValue(key, key === 'neutral' ? 0.3 : 0.85);
}

function playGesture(name) {
  const a = gestureActions[name];
  if (!a || !mixer) return;
  a.reset(); a.setEffectiveWeight(1); a.enabled = true; a.fadeIn(0.18).play();
  setTimeout(() => a.fadeOut(0.45), Math.max(600, a.getClip().duration * 1000 - 450));
}

function applyState(s) {
  if (s.emotion !== undefined && s.emotion !== state.emotion) setExpression(s.emotion);
  if (s.gesture && s.gesture.nonce !== state.gesture?.nonce && s.gesture.name)
    playGesture(s.gesture.name);
  state = {...state, ...s};
}

/* ---------- pet bubble + typing ---------- */
const bubbleEl = document.getElementById('bubble');
const chatbarEl = document.getElementById('chatbar');
const chatInput = document.getElementById('chatinput');
let lastBubbleNonce = 0, bubbleTimer = null;

function showBubble(text, ms = 7000) {
  if (!PET || !bubbleEl) return;
  bubbleEl.textContent = String(text || '').trim();
  if (!bubbleEl.textContent) return;
  bubbleEl.classList.add('show');
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => bubbleEl.classList.remove('show'), ms);
}

function applyBubble(s) {
  if (!PET || typeof s.bubble_nonce !== 'number') return;
  if (s.bubble_nonce !== lastBubbleNonce) {
    lastBubbleNonce = s.bubble_nonce;
    showBubble(s.bubble);
  }
}

if (PET && chatbarEl && chatInput) {
  // Double-click anywhere on the girl to reveal the tiny input.
  document.addEventListener('dblclick', () => {
    chatbarEl.classList.add('show');
    chatInput.focus();
  });
  chatInput.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      chatbarEl.classList.remove('show');
      chatInput.blur();
    }
  });
  chatbarEl.addEventListener('submit', async e => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
    showBubble('…', 0);
    try {
      const r = await fetch('/chat', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      const j = await r.json();
      showBubble(j.text || '(no reply)', 9000);
    } catch (err) {
      showBubble('offline error: ' + err.message, 6000);
    }
    chatbarEl.classList.remove('show');
    chatInput.blur();
  });
}

async function pollState() {
  try {
    const r = await fetch('/state', {cache: 'no-store'});
    const s = await r.json();
    applyBubble(s);
    if (s.version !== state.version) applyState(s);
  } catch (_) {}
}

/* ---------- frame loop ---------- */
function animate() {
  requestAnimationFrame(animate);
  const now = performance.now();
  if (now - lastFrame < 32) return;           // ~30 fps to spare the GPU
  const dt = Math.min(clock.getDelta(), 0.1);
  lastFrame = now;
  if (!loaded || !mixer) { renderer.render(scene, camera); return; }

  mixer.update(dt);

  // procedural blink (the mocap clips carry no face tracks)
  blinkClock -= dt;
  if (blinkClock <= 0 && blinkPhase < 0) blinkPhase = 0;
  if (blinkPhase >= 0) {
    blinkPhase += dt;
    const w = blinkPhase < 0.07 ? blinkPhase / 0.07
            : blinkPhase < 0.15 ? 1 - (blinkPhase - 0.07) / 0.08 : 0;
    vrm.expressionManager?.setValue('blink', Math.max(0, w));
    if (blinkPhase > 0.15) { blinkPhase = -1; blinkClock = 2.4 + Math.random() * 2.6; }
  }

  // mouth shapes while she is actually speaking
  mouthClock -= dt;
  if (state.speaking && mouthClock <= 0) {
    const m = MOUTHS[Math.floor(Math.random() * MOUTHS.length)];
    MOUTHS.forEach(x => vrm.expressionManager?.setValue(x, 0));
    vrm.expressionManager?.setValue(m, 0.45 + Math.random() * 0.4);
    mouthClock = 0.075 + Math.random() * 0.07;
  } else if (!state.speaking && mouthClock <= 0) {
    MOUTHS.forEach(x => vrm.expressionManager?.setValue(x, 0));
  }

  // eyes / head follow the cursor
  if (vrm.lookAt?.target) {
    const gx = THREE.MathUtils.clamp(state.gaze?.x || 0, -1, 1);
    const gy = THREE.MathUtils.clamp(state.gaze?.y || 0, -1, 1);
    vrm.lookAt.target.position.set(gx * 1.7, 1.35 + gy * 0.8, 1.7);
  }

  // dancing procedural overlay (applied after the mixer so it wins)
  if (state.dance) {
    const t = performance.now() * 0.001;
    const hips = nodes['Hips'], chest = nodes['Spine01'], head = nodes['Head'];
    const la = nodes['LeftArm'], ra = nodes['RightArm'];
    if (hips) { hips.rotation.z = Math.sin(t * 6) * 0.14; hips.rotation.y = Math.sin(t * 3) * 0.18; }
    if (chest) chest.rotation.z = Math.sin(t * 6 + 0.6) * 0.09;
    if (head) head.rotation.z = Math.sin(t * 6 + 1.2) * 0.12;
    if (la) la.rotation.z = -0.5 + Math.sin(t * 6) * 0.45;
    if (ra) ra.rotation.z = 0.5 - Math.sin(t * 6) * 0.45;
    vrm.expressionManager?.setValue('joy', 0.9);
  } else {
    // listening / thinking pose: slight forward lean, no big gestures
    if (state.busy) vrm.expressionManager?.setValue('neutral', 0.5);
  }

  renderer.render(scene, camera);
}
let lastFrame = 0;

// Diagnostic internals (for pixel-isolation tests only).
window.__novaInternals = {scene, camera, renderer, getVrm: () => vrm,
                          getMixer: () => mixer, nodes, rest, THREE};

// Diagnostic hook (read-only) — lets us prove what is actually rendered.
window.__novaDiag = () => {
  let meshCount = 0;
  const mats = [];
  if (vrm) vrm.scene.traverse(o => {
    if (o.isMesh) {
      meshCount++;
      if (mats.length < 6) mats.push({
        name: o.name, visible: o.visible,
        color: o.material?.color?.getHexString?.() || null,
        map: !!o.material?.map,
        opacity: o.material?.opacity,
      });
    }
  });
  const box = new THREE.Box3().setFromObject(vrm ? vrm.scene : scene);
  return {
    ready: loaded, meshes: meshCount,
    box: { min: box.min.toArray().map(n => +n.toFixed(2)),
           max: box.max.toArray().map(n => +n.toFixed(2)) },
    camera: camera.position.toArray().map(n => +n.toFixed(2)),
    calls: renderer.info.render.calls, tris: renderer.info.render.triangles,
    materials: mats, err: errBox.textContent,
  };
};

setInterval(pollState, 220);
pollState();
animate();
