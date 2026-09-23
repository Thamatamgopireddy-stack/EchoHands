lucide.createIcons();

const state = {
    camera: false,
    backendCamera: false,
    listening: false,
    lastSign: "",
    queue: [],
    active: false,
    speed: 1
};
let browserRecognition = null;

const get = (id) => document.getElementById(id);
const signs = new Set(["HELLO", "NAMASTE", "THANK_YOU", "YES", "NO", "PLEASE", "HELP"]);

function logMessage(role, text) {
    const item = document.createElement("div");
    item.className = "log-item";
    item.textContent = role + ": " + text;
    const time = document.createElement("time");
    time.textContent = new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });
    item.append(time);
    get("logList").append(item);
}

function updateQueue() {
    get("queueCount").textContent = state.queue.length + " queued";
}

function updateCameraButton(active) {
    const button = get("cameraButton");
    button.innerHTML = active
        ? '<i data-lucide="video-off"></i> Stop camera'
        : '<i data-lucide="video"></i> Start camera';
    lucide.createIcons();
}

function setCameraState(active) {
    state.camera = active;
    state.backendCamera = active;
    get("cameraStatus").textContent = active ? "Camera active" : "Camera idle";
    get("cameraDot").className = active ? "dot active" : "dot";
    updateCameraButton(active);
    if (!active) {
        const canvas = get("landmarkCanvas");
        canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
        get("cameraEmpty").style.display = "grid";
    } else {
        get("cameraEmpty").style.display = "none";
    }
}

function updateMicButton(active) {
    const button = get("micButton");
    button.innerHTML = active
        ? '<i data-lucide="mic-off"></i> Mute microphone'
        : '<i data-lucide="mic"></i> Start listening';
    lucide.createIcons();
    get("micStatus").textContent = active ? "Listening" : "Mic muted";
    get("micDot").className = active ? "dot active" : "dot";
}

function speakText(text) {
    if ("speechSynthesis" in window) {
        speechSynthesis.cancel();
        speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    }
}

function queueText(text) {
    const words = String(text)
        .toUpperCase()
        .replace(/[^A-Z0-9_ ]/g, " ")
        .split(/\s+/)
        .filter(Boolean);
    words.forEach((word) => {
        const name = word === "THANK" || word === "YOU" || word === "THANKYOU"
            ? "THANK_YOU"
            : word;
        if (signs.has(name)) {
            window.playSign(name);
        } else {
            [...name].forEach((letter) => window.playSign(letter));
        }
    });
}

function announce(name) {
    get("currentSign").textContent = name;
    get("detectedSign").textContent = name;
    get("poseLabel").textContent = name;
    state.lastSign = name;
    logMessage("Speaker", name + " - avatar signing");
}

function syncSpeechInput(text) {
    const input = get("speechInput");
    input.value = text;
    input.focus({ preventScroll: true });
    input.classList.add("speech-received");
    window.setTimeout(() => input.classList.remove("speech-received"), 700);
}

window.playSign = function (name) {
    name = String(name || "").trim().toUpperCase();
    if (!name) return false;
    state.queue.push(name);
    updateQueue();
    playNext();
    return true;
};

function playNext() {
    if (state.active || !state.queue.length) return;
    state.active = true;
    const name = state.queue.shift();
    updateQueue();
    announce(name);
    const duration = playAvatarSign(name);
    setTimeout(() => {
        state.active = false;
        returnAvatarToIdle();
        playNext();
    }, duration);
}

function onSpeechRecognized(text) {
    text = String(text || "").trim();
    if (!text) return;
    syncSpeechInput(text);
    get("speechCaption").textContent = text;
    logMessage("Speaker", text);
    queueText(text);
}

window.onBackendSpeech = function (text) {
    text = String(text || "").trim();
    if (!text) return;
    onSpeechRecognized(text);
};

window.onBackendSign = function (gesture, word) {
    get("poseLabel").textContent = gesture;
    get("detectedSign").textContent = word;
    logMessage("Signer", gesture + " -> " + word);
};

window.onBackendStatus = function (message) {
    if (/microphone|listening|calibrating/i.test(message)) {
        state.listening = true;
        get("micStatus").textContent = message;
        get("micDot").className = "dot active";
    } else if (/camera feed active/i.test(message)) {
        setCameraState(true);
    }
};

window.onBackendError = function (message) {
    if (/camera/i.test(message)) {
        setCameraState(false);
    } else {
        state.listening = false;
        updateMicButton(false);
        get("micStatus").textContent = message;
        get("micDot").className = "dot";
    }
    logMessage("System", message);
};

window.onBackendCameraFrame = function (image, gesture) {
    if (!state.camera) return;
    if (gesture) get("poseLabel").textContent = gesture;
    const canvas = get("landmarkCanvas");
    const context = canvas.getContext("2d");
    const source = new Image();
    source.onload = () => {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
        context.drawImage(source, 0, 0, canvas.width, canvas.height);
    };
    source.src = "data:image/jpeg;base64," + image;
};

function backendAvailable() {
    return Boolean(window.pywebview?.api);
}

function createBrowserRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return null;
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onstart = () => updateMicButton(true);
    recognition.onresult = (event) => {
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
            if (event.results[index].isFinal) onSpeechRecognized(event.results[index][0].transcript);
        }
    };
    recognition.onerror = (event) => {
        if (["not-allowed", "service-not-allowed", "network"].includes(event.error)) {
            state.listening = false;
            updateMicButton(false);
            const message = event.error === "network"
                ? "Browser speech needs internet; run the Python app for microphone input"
                : "Microphone permission was denied";
            get("micStatus").textContent = message;
            logMessage("System", message);
        } else {
            logMessage("System", "Browser microphone: " + event.error);
        }
    };
    recognition.onend = () => {
        if (state.listening) {
            try {
                recognition.start();
            } catch (error) {
                state.listening = false;
                updateMicButton(false);
            }
        }
    };
    return recognition;
}

async function toggleCamera() {
    if (backendAvailable()) {
        if (state.camera) {
            const stopped = await window.pywebview.api.stop_camera();
            if (stopped) setCameraState(false);
        } else {
            const started = await window.pywebview.api.start_camera();
            if (started) {
                setCameraState(true);
            } else {
                get("cameraStatus").textContent = "Camera unavailable";
                get("cameraDot").className = "dot";
            }
        }
        return;
    }
    const video = get("webcam");
    if (state.camera) {
        video.srcObject?.getTracks().forEach((track) => track.stop());
        video.srcObject = null;
        video.style.display = "none";
        setCameraState(false);
        return;
    }
    try {
        video.srcObject = await navigator.mediaDevices.getUserMedia({ video: true });
        video.style.display = "block";
        get("cameraEmpty").style.display = "none";
        setCameraState(true);
    } catch (error) {
        get("cameraStatus").textContent = "Camera unavailable";
    }
}

async function toggleMic() {
    if (backendAvailable()) {
        if (state.listening) {
            const stopped = await window.pywebview.api.stop_microphone();
            if (stopped) state.listening = false;
        } else {
            state.listening = await window.pywebview.api.start_microphone();
        }
        updateMicButton(state.listening);
        return;
    }
    if (state.listening) {
        state.listening = false;
        browserRecognition?.stop();
        updateMicButton(false);
        return;
    }
    browserRecognition = browserRecognition || createBrowserRecognition();
    if (!browserRecognition) {
        get("micStatus").textContent = "Python microphone backend required";
        return;
    }
    state.listening = true;
    updateMicButton(true);
    try {
        browserRecognition.start();
    } catch (error) {
        state.listening = false;
        updateMicButton(false);
        logMessage("System", "Browser microphone could not start: " + error.message);
    }
}

get("cameraButton").addEventListener("click", toggleCamera);
get("micButton").addEventListener("click", toggleMic);
get("simulateButton").addEventListener("click", () => {
    get("poseLabel").textContent = "NAMASTE";
    get("detectedSign").textContent = "NAMASTE";
    speakText("Namaste");
    logMessage("Signer", "Namaste - spoken via TTS");
});
get("speakDetectedButton").addEventListener("click", () => {
    speakText(get("detectedSign").textContent);
});
get("translateButton").addEventListener("click", () => {
    const input = get("speechInput");
    onSpeechRecognized(input.value);
    input.value = "";
});
get("speechInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") get("translateButton").click();
});
get("replayButton").addEventListener("click", () => {
    if (state.lastSign) window.playSign(state.lastSign);
});
get("speedSelect").addEventListener("change", (event) => {
    state.speed = Number(event.target.value);
});
get("clearButton").addEventListener("click", () => {
    get("logList").replaceChildren();
});
get("contrastButton").addEventListener("click", () => {
    document.body.classList.toggle("contrast");
});

let avatarScene;
let avatarCamera;
let avatarRenderer;
let avatarMixer;
let activeAction = null;
let idleAction = null;
let avatarModel = null;
let avatarRoot = null;
let avatarReady = false;
let fallbackPose = null;
let avatarRestPose = [];
let proceduralRig = null;
const avatarActions = {};
const avatarLoader = new THREE.GLTFLoader();
const avatarClock = new THREE.Clock();
const avatarModelPaths = ["assets/anime_avatar.glb", "assets/avatar.glb"];

const boneAliases = {
    leftShoulder: ["shoulder.L", "Shoulder_L", "leftShoulder", "LeftShoulder"],
    rightShoulder: ["shoulder.R", "Shoulder_R", "rightShoulder", "RightShoulder"],
    leftUpperArm: ["upperarm.L", "upperarm01.L", "upper_arm.L", "UpperArm_L", "leftUpperArm", "LeftArm"],
    rightUpperArm: ["upperarm.R", "upperarm01.R", "upper_arm.R", "UpperArm_R", "rightUpperArm", "RightArm"],
    leftForearm: ["forearm.L", "lowerarm.L", "lowerarm01.L", "ForeArm_L", "leftForeArm", "LeftForeArm"],
    rightForearm: ["forearm.R", "lowerarm.R", "lowerarm01.R", "ForeArm_R", "rightForeArm", "RightForeArm"],
    leftHand: ["hand.L", "Hand_L", "leftHand", "LeftHand"],
    rightHand: ["hand.R", "Hand_R", "rightHand", "RightHand"]
};

function setAvatarStatus(message) {
    const status = get("avatarStatus");
    if (status) status.textContent = message;
}

function normalizeClipName(name) {
    return String(name || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function findAvatarAction(token) {
    const normalized = normalizeClipName(token);
    return Object.entries(avatarActions).find(([name]) => {
        const clipName = normalizeClipName(name);
        return clipName === normalized || clipName.includes(normalized);
    })?.[1] || null;
}

function findBone(names) {
    if (!avatarModel) return null;
    const wanted = new Set(names.map((name) => name.toLowerCase()));
    let result = null;
    avatarModel.traverse((object) => {
        if (!result && object.isBone && wanted.has(object.name.toLowerCase())) result = object;
    });
    return result;
}

function resolveBones() {
    return Object.fromEntries(Object.entries(boneAliases).map(([key, names]) => [key, findBone(names)]));
}

window.inspectAvatarRig = function () {
    if (!avatarModel) return { loaded: false, bones: [], clips: [] };
    const bones = [];
    avatarModel.traverse((object) => {
        if (object.isBone) bones.push(object.name);
    });
    const result = {
        loaded: true,
        bones,
        clips: Object.keys(avatarActions),
        mappedFallbackBones: resolveBones(),
        proceduralPose: proceduralRig ? {
            leftArmZ: proceduralRig.leftArm.rotation.z,
            rightArmZ: proceduralRig.rightArm.rotation.z,
            active: fallbackPose?.type === "procedural"
        } : null
    };
    console.table(result.mappedFallbackBones);
    console.log("EchoHands avatar rig", result);
    return result;
};

function fitAvatarToView(model) {
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const targetHeight = 1.75;
    const scale = targetHeight / Math.max(size.y, 0.001);
    model.scale.setScalar(scale);

    const fittedBounds = new THREE.Box3().setFromObject(model);
    const fittedCenter = fittedBounds.getCenter(new THREE.Vector3());
    model.position.sub(fittedCenter);

    const fittedSize = fittedBounds.getSize(new THREE.Vector3());
    const height = Math.max(fittedSize.y, targetHeight);
    const box = get("avatarCanvasContainer");
    const aspect = Math.max(box.clientWidth / Math.max(box.clientHeight, 1), 0.5);
    const radius = Math.max(fittedSize.x, fittedSize.y, fittedSize.z) * 0.5;
    avatarCamera.fov = aspect < 0.8 ? 48 : 42;
    avatarCamera.near = Math.max(radius / 100, 0.01);
    avatarCamera.far = Math.max(height * 10, 10);
    const distance = Math.max(radius / Math.tan(THREE.MathUtils.degToRad(avatarCamera.fov / 2)), height * 0.85);
    avatarCamera.position.set(0, height * 0.08, distance * 1.08);
    avatarCamera.lookAt(0, height * 0.08, 0);
    avatarCamera.updateProjectionMatrix();
}

function crossFadeTo(action) {
    action.reset();
    action.setLoop(THREE.LoopOnce, 1);
    action.clampWhenFinished = true;
    if (activeAction && activeAction !== action) action.crossFadeFrom(activeAction, 0.22, true);
    action.play();
    activeAction = action;
}

function beginFallbackGesture(token) {
    const bones = resolveBones();
    const gesture = {
        HELLO: [["rightUpperArm", 0, 0, -0.55], ["rightForearm", 0, 0, 0.75], ["rightHand", 0, 0, -0.45]],
        NAMASTE: [["leftForearm", 0, 0, -0.35], ["rightForearm", 0, 0, 0.35], ["leftHand", 0, 0, -0.2], ["rightHand", 0, 0, 0.2]],
        YES: [["rightUpperArm", -0.25, 0, -0.2], ["rightForearm", 0.8, 0, 0]],
        NO: [["rightUpperArm", -0.25, 0, -0.2], ["rightForearm", 0, 0.65, 0]],
        PLEASE: [["rightUpperArm", -0.35, 0, -0.25], ["rightForearm", 0, 0, 0.65], ["rightHand", 0, 0, -0.35]],
        THANK_YOU: [["rightUpperArm", -0.35, 0, -0.3], ["rightForearm", 0.25, 0, 0.5], ["rightHand", 0, 0, -0.25]]
        , HELP: [["rightUpperArm", -0.4, 0, -0.35], ["rightForearm", 0.45, 0, 0.55], ["rightHand", 0, 0, -0.3]]
    }[token] || [];
    const targets = gesture.map(([boneName, x, y, z]) => {
        const bone = bones[boneName];
        if (!bone) return null;
        return { bone, start: bone.quaternion.clone(), target: new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z)) };
    }).filter(Boolean);
    if (!targets.length && proceduralRig) {
        fallbackPose = { type: "procedural", token, startedAt: performance.now(), duration: 1600 };
        return 1600;
    }
    fallbackPose = { targets, startedAt: performance.now(), duration: 1600 };
    if (!targets.length) setAvatarStatus("Avatar loaded; no matching bones");
    return 850;
}

function restoreAvatarRestPose() {
    if (proceduralRig) {
        fallbackPose = { type: "procedural", token: "REST", startedAt: performance.now(), duration: 220 };
    }
    if (!avatarRestPose.length) return;
    fallbackPose = {
        targets: avatarRestPose.map(({ bone, quaternion }) => ({
            bone,
            start: bone.quaternion.clone(),
            target: quaternion
        })),
        startedAt: performance.now(),
        duration: 220
    };
}

function applyProceduralPose(token, progress, returning) {
    if (!proceduralRig) return;
    const factor = returning ? 1 - progress : Math.min(progress * 3, 1);
    const targets = {
        HELLO: [0, -1.05],
        NAMASTE: [0.7, -0.7],
        YES: [0, -0.8],
        NO: [0, -0.8],
        PLEASE: [0, -0.65],
        THANK_YOU: [0, -0.65],
        HELP: [0, -0.8],
        REST: [0, 0]
    }[token] || [0, 0];
    proceduralRig.leftArm.rotation.z = THREE.MathUtils.lerp(0, targets[0], factor);
    const rightArmAngle = token === "HELLO" ? 2.45 : targets[1];
    proceduralRig.rightArm.rotation.z = THREE.MathUtils.lerp(0, rightArmAngle, factor);
    proceduralRig.rightHand.position.z = THREE.MathUtils.lerp(0, 0.24, factor);
    const wave = !returning && token === "HELLO"
        ? Math.sin((performance.now() - fallbackPose.startedAt) / 85) * 0.32 * factor
        : 0;
    proceduralRig.rightHand.rotation.z = wave;
    proceduralRig.rightHand.rotation.x = token === "HELLO" ? -0.25 * factor : 0;
    proceduralRig.leftHand.rotation.z = 0;
    if (returning) {
        proceduralRig.rightHand.position.z = THREE.MathUtils.lerp(0.24, 0, progress);
        proceduralRig.rightHand.rotation.x = THREE.MathUtils.lerp(-0.25, 0, progress);
    }
}

function playAvatarSign(token) {
    setAvatarStatus("Signing " + token);
    const action = findAvatarAction(token);
    if (action) {
        fallbackPose = null;
        crossFadeTo(action);
        return (action.getClip().duration * 1000 / state.speed) + 250;
    }
    return beginFallbackGesture(token) / state.speed;
}

function returnAvatarToIdle() {
    restoreAvatarRestPose();
    if (idleAction && activeAction !== idleAction) {
        idleAction.reset();
        idleAction.crossFadeFrom(activeAction, 0.22, true);
        idleAction.play();
        activeAction = idleAction;
    }
    setAvatarStatus(avatarReady ? "Avatar ready" : "Avatar loading...");
}

function createProceduralAvatar() {
    const group = new THREE.Group();
    const skin = new THREE.MeshStandardMaterial({ color: 0xf1b7a3, roughness: 0.7 });
    const hair = new THREE.MeshStandardMaterial({ color: 0x243247, roughness: 0.55 });
    const shirt = new THREE.MeshStandardMaterial({ color: 0x18bfa8, roughness: 0.65 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x10232c, roughness: 0.75 });

    const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.31, 0.26, 0.72, 20), shirt);
    torso.position.y = -0.34;
    group.add(torso);
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.11, 0.16, 16), skin);
    neck.position.y = 0.1;
    group.add(neck);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.27, 24, 16), skin);
    head.scale.set(0.9, 1.12, 0.88);
    head.position.y = 0.38;
    group.add(head);
    const hairCap = new THREE.Mesh(new THREE.SphereGeometry(0.285, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.58), hair);
    hairCap.position.y = 0.47;
    group.add(hairCap);
    const eyeGeometry = new THREE.SphereGeometry(0.025, 12, 8);
    [-0.09, 0.09].forEach((x) => {
        const eye = new THREE.Mesh(eyeGeometry, dark);
        eye.position.set(x, 0.4, 0.245);
        group.add(eye);
    });
    const leftArm = new THREE.Group();
    const rightArm = new THREE.Group();
    [[leftArm, -0.38], [rightArm, 0.38]].forEach(([armGroup, x]) => {
        armGroup.position.set(x, -0.02, 0);
        const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.08, 0.52, 12), shirt);
        arm.position.y = -0.26;
        armGroup.add(arm);
        const hand = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), skin);
        hand.position.set(0, -0.55, 0);
        armGroup.add(hand);
        group.add(armGroup);
        armGroup.userData.hand = hand;
    });
    proceduralRig = {
        leftArm,
        rightArm,
        leftHand: leftArm.userData.hand,
        rightHand: rightArm.userData.hand
    };
    group.position.y = 0.1;
    avatarScene.add(group);
    avatarModel = group;
    avatarCamera.position.set(0, 0.15, 2.25);
    avatarCamera.lookAt(0, 0.15, 0);
    avatarCamera.near = 0.01;
    avatarCamera.far = 10;
    avatarCamera.updateProjectionMatrix();
    avatarReady = true;
    setAvatarStatus("Avatar ready (procedural fallback)");
}

function initAvatar() {
    const box = get("avatarCanvasContainer");
    avatarScene = new THREE.Scene();
    avatarScene.background = new THREE.Color(0x071015);
    avatarCamera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);
    avatarRenderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    avatarRenderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    avatarRenderer.outputEncoding = THREE.sRGBEncoding;
    avatarRenderer.setSize(box.clientWidth, box.clientHeight);
    box.appendChild(avatarRenderer.domElement);
    avatarScene.add(new THREE.HemisphereLight(0xffffff, 0x26333b, 1.1));
    const light = new THREE.DirectionalLight(0xffffff, 1.4);
    light.position.set(1, 2, 2);
    avatarScene.add(light);
    setAvatarStatus("Loading anime avatar...");
    const onModelLoaded = (gltf) => {
        avatarModel = gltf.scene;
        avatarRoot = new THREE.Group();
        avatarRoot.add(avatarModel);
        avatarScene.add(avatarRoot);
        fitAvatarToView(avatarModel);
        avatarModel.traverse((object) => {
            if (object.isMesh) {
                object.frustumCulled = true;
                object.castShadow = false;
                object.receiveShadow = false;
                if (object.material) {
                    object.material.needsUpdate = false;
                    if ("roughness" in object.material) object.material.roughness = Math.max(object.material.roughness, 0.55);
                }
            }
        });
        avatarModel.traverse((object) => {
            if (object.isBone) avatarRestPose.push({ bone: object, quaternion: object.quaternion.clone() });
        });
        avatarMixer = new THREE.AnimationMixer(avatarModel);
        (gltf.animations || []).forEach((clip) => {
            avatarActions[clip.name.toUpperCase()] = avatarMixer.clipAction(clip);
        });
        const idleClip = gltf.animations.find((clip) => /idle|rest|stand/i.test(clip.name));
        if (idleClip) {
            idleAction = avatarMixer.clipAction(idleClip);
            idleAction.play();
            activeAction = idleAction;
        }
        avatarReady = true;
        setAvatarStatus(gltf.animations.length ? "Avatar ready" : "Avatar ready; procedural gestures enabled");
    };
    const loadModel = async (pathIndex) => {
        if (pathIndex >= avatarModelPaths.length) {
            createProceduralAvatar();
            return;
        }
        try {
            const response = await fetch(avatarModelPaths[pathIndex]);
            if (!response.ok) {
                await loadModel(pathIndex + 1);
                return;
            }
            setAvatarStatus("Loading anime avatar...");
            const data = await response.arrayBuffer();
            avatarLoader.parse(data, "", onModelLoaded, () => loadModel(pathIndex + 1));
        } catch (error) {
            await loadModel(pathIndex + 1);
        }
    };
    loadModel(0);
    function render() {
        requestAnimationFrame(render);
        if (avatarMixer) avatarMixer.update(avatarClock.getDelta());
        if (fallbackPose?.type === "procedural") {
            const progress = Math.min((performance.now() - fallbackPose.startedAt) / fallbackPose.duration, 1);
            applyProceduralPose(fallbackPose.token, progress, fallbackPose.token === "REST");
        } else if (fallbackPose) {
            const progress = Math.min((performance.now() - fallbackPose.startedAt) / 220, 1);
            fallbackPose.targets.forEach((pose) => pose.bone.quaternion.slerpQuaternions(pose.start, pose.target, progress));
        }
        avatarRenderer.render(avatarScene, avatarCamera);
    }
    render();
}

function resizeAvatar() {
    const box = get("avatarCanvasContainer");
    if (!avatarRenderer) return;
    const width = Math.max(box.clientWidth, 1);
    const height = Math.max(box.clientHeight, 1);
    avatarCamera.aspect = width / height;
    avatarCamera.updateProjectionMatrix();
    avatarRenderer.setSize(width, height, false);
}

addEventListener("resize", resizeAvatar);
if (window.ResizeObserver) new ResizeObserver(resizeAvatar).observe(get("avatarCanvasContainer"));
addEventListener("pywebviewready", () => {
    get("micStatus").textContent = "Mic muted - backend ready";
});
if (!backendAvailable()) {
    get("micStatus").textContent = "Browser speech requires internet";
}
initAvatar();
