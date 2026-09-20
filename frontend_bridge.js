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
            state.queue.push(name);
        } else {
            [...name].forEach((letter) => state.queue.push(letter));
        }
    });
    updateQueue();
    playNext();
}

function announce(name) {
    get("currentSign").textContent = name;
    get("detectedSign").textContent = name;
    get("poseLabel").textContent = name;
    state.lastSign = name;
    logMessage("Speaker", name + " - avatar signing");
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
    get("avatarStatus").textContent = "Signing " + name;
    const action = avatarActions[name];
    if (action) {
        action.reset();
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
        if (activeAction && activeAction !== action) {
            action.crossFadeFrom(activeAction, 0.2, true);
        }
        action.play();
        activeAction = action;
    }
    const duration = ((action ? action.getClip().duration * 1000 : 700) / state.speed) + 250;
    setTimeout(() => {
        state.active = false;
        get("avatarStatus").textContent = "Avatar ready";
        playNext();
    }, duration);
}

function onSpeechRecognized(text) {
    text = String(text || "").trim();
    if (!text) return;
    get("speechCaption").textContent = text;
    logMessage("Speaker", text);
    queueText(text);
}

window.onBackendSpeech = onSpeechRecognized;

window.onBackendSign = function (gesture, word) {
    get("poseLabel").textContent = gesture;
    get("detectedSign").textContent = word;
    logMessage("Signer", gesture + " -> " + word);
};

window.onBackendStatus = function (message) {
    get("micStatus").textContent = message;
    get("micDot").className = "dot active";
};

window.onBackendError = function (message) {
    get("micStatus").textContent = message;
    get("micDot").className = "dot";
    logMessage("System", message);
};

window.onBackendCameraFrame = function (image, gesture) {
    state.backendCamera = true;
    state.camera = true;
    get("cameraEmpty").style.display = "none";
    get("cameraStatus").textContent = "Camera active";
    get("cameraDot").className = "dot active";
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
    return window.pywebview && window.pywebview.api;
}

async function toggleCamera() {
    if (backendAvailable()) {
        if (state.camera) {
            await window.pywebview.api.stop_camera();
            state.camera = false;
            get("cameraStatus").textContent = "Camera idle";
            get("cameraDot").className = "dot";
            get("cameraEmpty").style.display = "grid";
        } else {
            const started = await window.pywebview.api.start_camera();
            get("cameraStatus").textContent = started ? "Starting camera" : "Camera unavailable";
        }
        return;
    }
    const video = get("webcam");
    try {
        video.srcObject = await navigator.mediaDevices.getUserMedia({ video: true });
        video.style.display = "block";
        get("cameraEmpty").style.display = "none";
        state.camera = true;
        get("cameraStatus").textContent = "Camera active";
    } catch (error) {
        get("cameraStatus").textContent = "Camera unavailable";
    }
}

async function toggleMic() {
    if (backendAvailable()) {
        if (state.listening) {
            await window.pywebview.api.stop_microphone();
            state.listening = false;
        } else {
            state.listening = await window.pywebview.api.start_microphone();
        }
        get("micStatus").textContent = state.listening ? "Listening" : "Mic muted";
        get("micDot").className = state.listening ? "dot active" : "dot";
        return;
    }
    state.listening = !state.listening;
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
const avatarActions = {};
const avatarLoader = new THREE.GLTFLoader();
const avatarClock = new THREE.Clock();

function initAvatar() {
    const box = get("avatarCanvasContainer");
    avatarScene = new THREE.Scene();
    avatarScene.background = new THREE.Color(0x071015);
    avatarCamera = new THREE.PerspectiveCamera(
        42,
        box.clientWidth / box.clientHeight,
        0.1,
        100
    );
    avatarCamera.position.set(0, 1.35, 1.55);
    avatarRenderer = new THREE.WebGLRenderer({ antialias: true });
    avatarRenderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    avatarRenderer.setSize(box.clientWidth, box.clientHeight);
    box.appendChild(avatarRenderer.domElement);
    avatarScene.add(new THREE.HemisphereLight(0xffffff, 0x26333b, 1.1));
    const light = new THREE.DirectionalLight(0xffffff, 1.4);
    light.position.set(1, 2, 2);
    avatarScene.add(light);
    avatarLoader.load("assets/avatar.glb", (gltf) => {
        avatarScene.add(gltf.scene);
        avatarMixer = new THREE.AnimationMixer(gltf.scene);
        (gltf.animations || []).forEach((clip) => {
            avatarActions[clip.name.toUpperCase()] = avatarMixer.clipAction(clip);
        });
        get("avatarStatus").textContent = "Avatar ready";
    }, undefined, () => {
        get("avatarStatus").textContent = "Add assets/avatar.glb to enable the rig";
    });
    function render() {
        requestAnimationFrame(render);
        if (avatarMixer) avatarMixer.update(avatarClock.getDelta());
        avatarRenderer.render(avatarScene, avatarCamera);
    }
    render();
}

function resizeAvatar() {
    const box = get("avatarCanvasContainer");
    if (!avatarRenderer) return;
    avatarCamera.aspect = box.clientWidth / box.clientHeight;
    avatarCamera.updateProjectionMatrix();
    avatarRenderer.setSize(box.clientWidth, box.clientHeight);
}

addEventListener("resize", resizeAvatar);
addEventListener("pywebviewready", () => {
    get("micStatus").textContent = "Mic muted - backend ready";
});
initAvatar();
