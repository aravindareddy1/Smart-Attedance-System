/**
 * Smart Attendance System - Live Attendance & WebRTC Recognition Pipeline
 * Integrates: CameraService, Frame Capture, Canvas Face Bounding Boxes,
 * Real-time FPS, Session Countdown Timer, and Dual-List Roster Sync.
 */

if (typeof window.CameraService === 'undefined') {
    class CameraService {
        static checkSecureContext() {
            const isLocalhost = Boolean(
                window.location.hostname === 'localhost' ||
                window.location.hostname === '127.0.0.1' ||
                window.location.hostname === '[::1]'
            );
            const isHttps = window.location.protocol === 'https:';
            const isSecure = window.isSecureContext || isHttps || isLocalhost;

            return {
                isSecure: isSecure,
                isLocalhost: isLocalhost,
                protocol: window.location.protocol,
                hostname: window.location.hostname,
                port: window.location.port || '5000',
                hasMediaDevices: Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
            };
        }

        static mapCameraError(err) {
            const secInfo = CameraService.checkSecureContext();

            if (!secInfo.hasMediaDevices) {
                if (!secInfo.isSecure) {
                    const localUrl = `http://localhost:${secInfo.port}${window.location.pathname}${window.location.search}`;
                    return {
                        type: 'INSECURE_CONTEXT',
                        title: 'Camera Insecure Context Blocked',
                        message: `Browsers block camera access over insecure HTTP (${window.location.hostname}).`,
                        actionable: `Please access this page via localhost (${localUrl}) or launch with HTTPS.`,
                        isLocalUrl: localUrl
                    };
                }
                return {
                    type: 'NO_MEDIA_DEVICES',
                    title: 'Camera API Not Supported',
                    message: 'Your browser does not support navigator.mediaDevices.getUserMedia.',
                    actionable: 'Please use a modern Chromium, Firefox, or Safari browser.'
                };
            }

            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                return {
                    type: 'PERMISSION_DENIED',
                    title: 'Camera Permission Denied',
                    message: 'Camera permission was denied.',
                    actionable: 'Click the camera/lock icon in your address bar and set Camera permissions to "Allow".'
                };
            }

            if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                return {
                    type: 'NO_HARDWARE',
                    title: 'No Camera Detected',
                    message: 'No video capture hardware was found on this system.',
                    actionable: 'Ensure your webcam is connected and recognized.'
                };
            }

            if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
                return {
                    type: 'HARDWARE_LOCKED',
                    title: 'Camera Busy / In Use',
                    message: 'The camera is currently in use by another program (Zoom, Teams, or another tab).',
                    actionable: 'Close other applications using the webcam and refresh.'
                };
            }

            return {
                type: 'UNKNOWN',
                title: 'Camera Error',
                message: err.message || 'An unknown error occurred while initializing the camera.',
                actionable: 'Check browser permissions and console logs for details.'
            };
        }

        static async startCamera(videoElement, callbacks = {}, options = {}) {
            const {
                onStateChange = () => {},
                onReady = () => {},
                onError = () => {}
            } = callbacks;

            if (!videoElement) {
                const err = {
                    type: 'NO_ELEMENT',
                    title: 'Video Element Missing',
                    message: 'Target video element was not found in the DOM.',
                    actionable: 'Verify DOM element IDs.'
                };
                onError(err);
                return null;
            }

            console.log('[CAMERA] Requesting camera');
            onStateChange('INITIALIZING', 'Requesting camera access...');

            const secInfo = CameraService.checkSecureContext();
            if (!secInfo.hasMediaDevices) {
                const errDetails = CameraService.mapCameraError(new Error('MediaDevices unavailable'));
                console.error('[CAMERA] Error:', errDetails.title);
                onStateChange('ERROR', errDetails.title);
                onError(errDetails);
                return null;
            }

            const constraints = {
                video: {
                    width: { ideal: options.width || 640 },
                    height: { ideal: options.height || 480 },
                    facingMode: options.facingMode || 'user'
                },
                audio: false
            };

            try {
                CameraService.stopCamera(videoElement);

                const stream = await navigator.mediaDevices.getUserMedia(constraints);
                console.log('[CAMERA] Permission granted');
                videoElement.srcObject = stream;

                onStateChange('CONNECTING', 'Attaching video stream...');

                await new Promise((resolve) => {
                    if (videoElement.readyState >= 2) {
                        resolve();
                    } else {
                        videoElement.onloadedmetadata = () => {
                            console.log('[CAMERA] Video metadata loaded');
                            resolve();
                        };
                    }
                });

                await videoElement.play();

                const videoWidth = videoElement.videoWidth || 640;
                const videoHeight = videoElement.videoHeight || 480;
                console.log(`[CAMERA] Resolution: ${videoWidth} x ${videoHeight}`);

                onStateChange('READY', 'Camera Active • Scanning Faces');
                onReady({ stream, videoWidth, videoHeight });
                return stream;
            } catch (err) {
                console.error('[CAMERA] Failed to initialize camera:', err);
                const errDetails = CameraService.mapCameraError(err);
                onStateChange('ERROR', errDetails.title);
                onError(errDetails);
                return null;
            }
        }

        static stopCamera(videoElement) {
            if (!videoElement) return;
            if (videoElement.srcObject) {
                const stream = videoElement.srcObject;
                if (stream.getTracks) {
                    stream.getTracks().forEach(track => track.stop());
                }
                videoElement.srcObject = null;
                console.log('[CAMERA] Camera tracks stopped');
            }
        }

        static captureFrame(videoElement, quality = 0.85) {
            if (!videoElement || !videoElement.videoWidth || videoElement.videoWidth === 0) {
                return null;
            }
            const canvas = document.createElement('canvas');
            canvas.width = videoElement.videoWidth;
            canvas.height = videoElement.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', quality);
            return {
                dataUrl,
                width: canvas.width,
                height: canvas.height
            };
        }
    }

    window.CameraService = CameraService;
}

/**
 * LiveAttendanceManager
 */
class LiveAttendanceManager {
    constructor(config = {}) {
        this.config = config;
        this.sessionId = config.sessionId || this.extractSessionId();
        this.markedIds = new Set(config.initialMarkedIds || []);

        // Element bindings matching live_session.html
        this.video = document.getElementById('webcam-video')
            || document.getElementById('live-video')
            || document.querySelector('video');

        this.canvas = document.getElementById('webcam-canvas');

        this.statusIndicator = document.getElementById('camera-status-indicator');
        this.fpsIndicator = document.getElementById('fps-indicator');
        this.unknownCountEl = document.getElementById('unknown-count');
        this.presentCountEl = document.getElementById('present-count');
        this.remainingCountEl = document.getElementById('remaining-count');
        this.presentList = document.getElementById('present-students-list');
        this.timerEl = document.getElementById('session-timer');

        this.isProcessing = false;
        this.isRunning = false;
        this.frameCount = 0;
        this.lastFpsTime = performance.now();
        this.loopInterval = null;
        this.timerInterval = null;
        this.csrfToken = this.extractCsrfToken();

        console.log(`[RECOGNITION] Manager initialized for session #${this.sessionId} with ${this.markedIds.size} initial attendees.`);
    }

    static init(config) {
        const instance = new LiveAttendanceManager(config);
        instance.start();
        return instance;
    }

    extractSessionId() {
        const parts = window.location.pathname.split('/').filter(Boolean);
        const id = parts[parts.length - 1];
        return parseInt(id, 10) || null;
    }

    extractCsrfToken() {
        const input = document.querySelector('input[name="csrf_token"]');
        if (input) return input.value;
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        return '';
    }

    updateStatusUI(state, text) {
        if (!this.statusIndicator) return;
        const dot = this.statusIndicator.querySelector('span:first-child');
        const label = this.statusIndicator.querySelector('span:last-child');

        if (label) label.textContent = text;
        if (dot) {
            if (state === 'READY') {
                dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse mr-2';
            } else if (state === 'ERROR') {
                dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500 mr-2';
            } else {
                dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse mr-2';
            }
        }
    }

    startSessionTimer() {
        if (!this.timerEl) return;
        const startedAtStr = this.timerEl.dataset.startedAt;
        const durationMinutes = parseInt(this.timerEl.dataset.duration || '60', 10);
        if (!startedAtStr) return;

        const startedAt = new Date(startedAtStr).getTime();
        const endTime = startedAt + (durationMinutes * 60 * 1000);

        this.timerInterval = setInterval(() => {
            const now = Date.now();
            const diff = endTime - now;
            if (diff <= 0) {
                this.timerEl.textContent = '00:00 (Expired)';
                this.timerEl.classList.add('text-rose-600');
                clearInterval(this.timerInterval);
                return;
            }

            const mins = Math.floor(diff / 60000);
            const secs = Math.floor((diff % 60000) / 1000);
            this.timerEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }, 1000);
    }

    async start() {
        if (this.isRunning) return;

        if (!this.video) {
            console.error('[CAMERA] Video element #webcam-video not found in DOM.');
            this.updateStatusUI('ERROR', 'Webcam element missing');
            return;
        }

        this.startSessionTimer();

        await window.CameraService.startCamera(this.video, {
            onStateChange: (state, text) => this.updateStatusUI(state, text),
            onReady: (details) => {
                this.updateStatusUI('READY', 'Camera Active • Scanning Faces');
                this.startRecognitionLoop();
            },
            onError: (errDetails) => {
                this.updateStatusUI('ERROR', errDetails.title);
            }
        }, { width: 640, height: 480 });
    }

    startRecognitionLoop() {
        this.isRunning = true;
        this.frameCount = 0;
        this.lastFpsTime = performance.now();
        console.log('[RECOGNITION] Recognition loop started');

        if (this.loopInterval) clearInterval(this.loopInterval);

        this.loopInterval = setInterval(() => {
            this.processFrame();
        }, 650);
    }

    async processFrame() {
        if (!this.isRunning || this.isProcessing) return;
        if (!this.video || this.video.readyState < 2) return;

        this.isProcessing = true;

        try {
            const frame = window.CameraService.captureFrame(this.video, 0.85);
            if (!frame || !frame.dataUrl) {
                this.isProcessing = false;
                return;
            }

            this.frameCount++;
            const now = performance.now();
            const elapsed = (now - this.lastFpsTime) / 1000;
            if (elapsed >= 1.0) {
                const fps = Math.round((this.frameCount / elapsed) * 10) / 10;
                if (this.fpsIndicator) {
                    this.fpsIndicator.textContent = `${fps} FPS`;
                }
                this.frameCount = 0;
                this.lastFpsTime = now;
            }

            console.log(`[RECOGNITION] Processing frame (session #${this.sessionId})`);

            const response = await fetch(`/attendance/api/frame/${this.sessionId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ frame: frame.dataUrl })
            });

            if (response.ok) {
                const data = await response.json();
                this.handleRecognitionResults(data);
            } else if (response.status === 401 || response.status === 403) {
                console.warn('[RECOGNITION] Session unauthorized');
                this.updateStatusUI('ERROR', 'Session unauthorized');
            }
        } catch (err) {
            console.warn('[RECOGNITION] Frame processing error:', err);
        } finally {
            this.isProcessing = false;
        }
    }

    handleRecognitionResults(data) {
        if (!data || !data.success) {
            if (data && data.message) {
                console.warn(`[RECOGNITION] Backend message: ${data.message}`);
            }
            return;
        }

        const faces = data.faces || [];
        const newlyMarked = data.marked || [];
        const unknownCount = data.unknown_count !== undefined ? data.unknown_count : 0;

        console.log(`[RECOGNITION] Faces detected: ${faces.length}, Unknown: ${unknownCount}`);

        if (this.unknownCountEl) {
            this.unknownCountEl.textContent = unknownCount;
        }

        this.drawBoundingBoxes(faces);

        if (newlyMarked && newlyMarked.length > 0) {
            newlyMarked.forEach(student => {
                if (!this.markedIds.has(student.student_id)) {
                    console.log(`[ATTENDANCE] Marking student: ${student.name} (${student.roll_no}) [${student.status}]`);
                    this.markedIds.add(student.student_id);
                    this.markStudentInUI(student);
                    console.log('[ATTENDANCE] Success');
                }
            });
        }

        const matchedNames = faces.filter(f => f.matched && f.name).map(f => f.name);
        if (matchedNames.length > 0) {
            this.updateStatusUI('READY', `Scanning • Match: ${matchedNames.join(', ')}`);
        } else if (faces.length > 0) {
            this.updateStatusUI('READY', `Scanning • ${faces.length} Face(s) Detected`);
        } else {
            this.updateStatusUI('READY', 'Camera Active • Scanning Faces');
        }
    }

    drawBoundingBoxes(faces) {
        if (!this.canvas || !this.video) return;

        const vw = this.video.videoWidth;
        const vh = this.video.videoHeight;
        if (!vw || !vh) return;

        if (this.canvas.width !== vw || this.canvas.height !== vh) {
            this.canvas.width = vw;
            this.canvas.height = vh;
        }

        const ctx = this.canvas.getContext('2d');
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        faces.forEach(face => {
            const [x, y, w, h] = face.box || [0, 0, 0, 0];
            const isMatched = Boolean(face.matched);

            ctx.lineWidth = 3;
            ctx.strokeStyle = isMatched ? '#10b981' : '#f59e0b';
            ctx.strokeRect(x, y, w, h);

            const label = isMatched ? `${face.name} (${Math.round((face.confidence || 0) * 100)}%)` : 'Unknown';
            ctx.font = 'bold 13px sans-serif';
            const textWidth = ctx.measureText(label).width;

            ctx.fillStyle = isMatched ? 'rgba(16, 185, 129, 0.9)' : 'rgba(245, 158, 11, 0.9)';
            ctx.fillRect(x, y > 24 ? y - 24 : y, textWidth + 12, 22);

            ctx.fillStyle = '#ffffff';
            ctx.fillText(label, x + 6, y > 24 ? y - 8 : y + 16);
        });
    }

    markStudentInUI(student) {
        const studentId = student.student_id;

        const unmarkedRow = document.getElementById(`unmarked-row-${studentId}`)
            || document.getElementById(`student-unmarked-${studentId}`);
        if (unmarkedRow) {
            unmarkedRow.remove();
        }

        if (this.presentList) {
            const placeholder = this.presentList.querySelector('.empty-placeholder');
            if (placeholder) placeholder.remove();

            const existingRow = document.getElementById(`present-row-${studentId}`);
            if (!existingRow) {
                const item = document.createElement('div');
                item.id = `present-row-${studentId}`;
                item.className = 'p-3 bg-emerald-50/80 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 rounded-xl flex items-center justify-between animate-fade-in mb-2';
                item.innerHTML = `
                    <div class="flex items-center space-x-3">
                        <div class="w-8 h-8 rounded-full bg-emerald-600 text-white font-bold text-xs flex items-center justify-center">
                            ${(student.name || 'S').slice(0, 1)}
                        </div>
                        <div>
                            <div class="text-sm font-bold text-slate-800 dark:text-slate-100">${student.name}</div>
                            <div class="text-xs text-slate-500 font-mono">${student.roll_no || 'Enrolled'}</div>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="px-2 py-0.5 text-xs font-bold rounded-md bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300">
                            ${student.status || 'Present'}
                        </span>
                        <div class="text-[10px] text-slate-400 font-mono mt-0.5">
                            ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </div>
                    </div>
                `;
                this.presentList.prepend(item);
            }
        }

        if (this.presentCountEl) {
            this.presentCountEl.textContent = this.markedIds.size;
        }
        if (this.remainingCountEl) {
            const currentUnmarked = parseInt(this.remainingCountEl.textContent, 10) || 0;
            this.remainingCountEl.textContent = Math.max(0, currentUnmarked - 1);
        }

        if (window.App && window.App.toast) {
            window.App.toast('success', `Marked ${student.name} (${student.roll_no}) Present`);
        }
    }

    stop() {
        console.log('[RECOGNITION] Stopping recognition loop & releasing camera...');
        this.isRunning = false;

        if (this.loopInterval) {
            clearInterval(this.loopInterval);
            this.loopInterval = null;
        }
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        if (this.canvas) {
            const ctx = this.canvas.getContext('2d');
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        if (window.CameraService && this.video) {
            window.CameraService.stopCamera(this.video);
        }
        this.updateStatusUI('STOPPED', 'Session ended');
    }

    destroy() {
        this.stop();
    }
}

window.LiveAttendanceManager = LiveAttendanceManager;
