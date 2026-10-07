/**
 * Smart Attendance System - Live Webcam Recognition Client
 */

class LiveAttendanceManager {
    constructor(config) {
        this.sessionId = config.sessionId;
        this.apiEndpoint = config.apiEndpoint || `/attendance/api/frame/${this.sessionId}`;
        this.video = document.getElementById(config.videoId || 'webcam-video');
        this.canvas = document.getElementById(config.canvasId || 'webcam-canvas');
        this.statusIndicator = document.getElementById('camera-status-indicator');
        this.fpsIndicator = document.getElementById('fps-indicator');
        this.presentList = document.getElementById('present-students-list');
        this.remainingList = document.getElementById('remaining-students-list');
        this.presentCountEl = document.getElementById('present-count');
        this.remainingCountEl = document.getElementById('remaining-count');
        this.unknownCountEl = document.getElementById('unknown-count');
        this.timerEl = document.getElementById('session-timer');

        this.stream = null;
        this.isRunning = false;
        this.isProcessing = false;
        this.throttleInterval = 700; // ms
        this.lastFrameTime = 0;
        this.frameCount = 0;
        this.lastFpsCalc = Date.now();
        this.markedStudentIds = new Set(config.initialMarkedIds || []);

        // Hidden canvas for extracting JPEG frames
        this.captureCanvas = document.createElement('canvas');
        this.captureCtx = this.captureCanvas.getContext('2d');
    }

    async start() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showCameraError("Your browser does not support webcam access. Please use Chrome, Edge, or Firefox, or switch to Manual Attendance.");
            return;
        }

        try {
            this.updateStatus("Connecting to camera...", "amber");
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: false
            });

            this.video.srcObject = this.stream;
            await this.video.play();

            this.captureCanvas.width = this.video.videoWidth || 640;
            this.captureCanvas.height = this.video.videoHeight || 480;
            this.canvas.width = this.video.clientWidth || 640;
            this.canvas.height = this.video.clientHeight || 480;

            this.isRunning = true;
            this.updateStatus("Live - Detecting Faces", "emerald");
            this.startLoop();
            this.startTimer();

            showToast("Webcam connected. Position faces in the frame.", "success");
        } catch (err) {
            console.error("Camera access error:", err);
            let msg = "Could not access camera.";
            if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                msg = "Camera permission was denied. Please allow camera access in your browser settings, or continue with Manual Attendance.";
            } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                msg = "No webcam device detected on your system. Please connect a camera or use Manual Attendance.";
            } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
                msg = "Webcam is already in use by another application. Please close other camera tabs/apps and reload.";
            }
            this.showCameraError(msg);
        }
    }

    startLoop() {
        const loop = async (timestamp) => {
            if (!this.isRunning) return;

            // Draw current face bounding boxes
            // Check throttle interval for backend recognition
            const now = Date.now();
            if (now - this.lastFrameTime >= this.throttleInterval && !this.isProcessing) {
                this.lastFrameTime = now;
                await this.captureAndSendFrame();
            }

            // Calculate FPS
            this.frameCount++;
            if (now - this.lastFpsCalc >= 1000) {
                const fps = Math.round((this.frameCount * 1000) / (now - this.lastFpsCalc));
                if (this.fpsIndicator) this.fpsIndicator.textContent = `${fps} FPS`;
                this.frameCount = 0;
                this.lastFpsCalc = now;
            }

            requestAnimationFrame(loop);
        };

        requestAnimationFrame(loop);
    }

    async captureAndSendFrame() {
        if (!this.video || this.video.readyState !== 4) return;

        this.isProcessing = true;
        try {
            const vw = this.video.videoWidth;
            const vh = this.video.videoHeight;
            if (this.captureCanvas.width !== vw || this.captureCanvas.height !== vh) {
                this.captureCanvas.width = vw;
                this.captureCanvas.height = vh;
            }

            this.captureCtx.drawImage(this.video, 0, 0, vw, vh);
            const base64Data = this.captureCanvas.toDataURL('image/jpeg', 0.85);

            const res = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ frame: base64Data })
            });

            if (!res.ok) {
                console.warn(`Server frame response: ${res.status}`);
                this.isProcessing = false;
                return;
            }

            const data = await res.json();
            this.handleFrameResponse(data);
        } catch (err) {
            console.error("Frame processing network error:", err);
        } finally {
            this.isProcessing = false;
        }
    }

    handleFrameResponse(data) {
        if (!data.success) {
            if (data.session_status === 'ended') {
                this.stop();
                showToast(data.message || "Session has ended.", "info");
                setTimeout(() => window.location.reload(), 1500);
            }
            return;
        }

        // Draw bounding boxes on the overlay canvas
        this.renderCanvasOverlay(data.faces || []);

        // Process newly marked students
        if (data.marked && data.marked.length > 0) {
            for (const item of data.marked) {
                if (!this.markedStudentIds.has(item.student_id)) {
                    this.markedStudentIds.add(item.student_id);
                    this.addPresentStudent(item);
                    this.removeRemainingStudent(item.student_id);
                    showToast(`Marked ${item.status}: ${item.name} (${item.roll_no})`, "success", 3000);
                }
            }
        }

        // Update unknown count
        if (this.unknownCountEl) {
            this.unknownCountEl.textContent = data.unknown_count || 0;
        }
    }

    renderCanvasOverlay(faces) {
        if (!this.canvas) return;
        const ctx = this.canvas.getContext('2d');
        const cw = this.canvas.width;
        const ch = this.canvas.height;
        ctx.clearRect(0, 0, cw, ch);

        const vw = this.video.videoWidth || 640;
        const vh = this.video.videoHeight || 480;
        const scaleX = cw / vw;
        const scaleY = ch / vh;

        for (const face of faces) {
            const [x, y, w, h] = face.box;
            const sx = x * scaleX;
            const sy = y * scaleY;
            const sw = w * scaleX;
            const sh = h * scaleY;

            ctx.lineWidth = 3;
            if (face.matched) {
                ctx.strokeStyle = '#10B981'; // Emerald
                ctx.fillStyle = '#10B981';
            } else {
                ctx.strokeStyle = '#F59E0B'; // Amber
                ctx.fillStyle = '#F59E0B';
            }

            // Draw bounding box rounded corner rectangle
            this.drawRoundedRect(ctx, sx, sy, sw, sh, 8);
            ctx.stroke();

            // Label background
            const label = face.matched ? `${face.name} (${Math.round(face.confidence * 100)}%)` : 'Unknown Face';
            ctx.font = 'bold 13px system-ui, -apple-system, sans-serif';
            const textMetrics = ctx.measureText(label);
            const labelWidth = textMetrics.width + 16;
            const labelHeight = 24;

            ctx.beginPath();
            ctx.roundRect(sx, sy - labelHeight - 4, labelWidth, labelHeight, 6);
            ctx.fill();

            // Label text
            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(label, sx + 8, sy - 8);
        }
    }

    drawRoundedRect(ctx, x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }

    addPresentStudent(item) {
        if (!this.presentList) return;

        // Remove empty placeholder if any
        const emptyState = document.getElementById('present-empty-state');
        if (emptyState) emptyState.remove();

        const row = document.createElement('div');
        row.id = `present-row-${item.student_id}`;
        row.className = 'p-3 bg-emerald-50/80 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 rounded-xl flex items-center justify-between animate-fadeIn';
        row.innerHTML = `
            <div class="flex items-center space-x-3">
                <div class="w-8 h-8 rounded-full bg-emerald-600 text-white font-bold text-xs flex items-center justify-center">
                    ${item.name.charAt(0)}
                </div>
                <div>
                    <div class="text-sm font-bold text-slate-800 dark:text-slate-100">${escapeHtml(item.name)}</div>
                    <div class="text-xs text-slate-500 font-mono">${escapeHtml(item.roll_no)}</div>
                </div>
            </div>
            <div class="text-right">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${item.status === 'Late' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}">
                    ${item.status}
                </span>
                <div class="text-[10px] text-slate-400 mt-0.5">${item.time || 'Just now'}</div>
            </div>
        `;

        this.presentList.prepend(row);
        this.updateCounts();
    }

    removeRemainingStudent(studentId) {
        const row = document.getElementById(`remaining-row-${studentId}`);
        if (row) row.remove();
        this.updateCounts();
    }

    updateCounts() {
        if (this.presentCountEl) {
            this.presentCountEl.textContent = this.markedStudentIds.size;
        }
        if (this.remainingCountEl && this.remainingList) {
            const count = this.remainingList.children.length;
            this.remainingCountEl.textContent = count;
        }
    }

    startTimer() {
        if (!this.timerEl) return;
        const startTimeStr = this.timerEl.dataset.startedAt;
        const durationMinutes = parseInt(this.timerEl.dataset.duration || '60', 10);
        const startTime = startTimeStr ? new Date(startTimeStr).getTime() : Date.now();
        const endTime = startTime + durationMinutes * 60 * 1000;

        const timerInterval = setInterval(() => {
            if (!this.isRunning) {
                clearInterval(timerInterval);
                return;
            }

            const now = Date.now();
            const distance = endTime - now;

            if (distance <= 0) {
                clearInterval(timerInterval);
                this.timerEl.textContent = "00:00 (Expired)";
                this.stop();
                showToast("Session time has elapsed. Closing session...", "warning");
                setTimeout(() => window.location.reload(), 2000);
                return;
            }

            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            this.timerEl.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }, 1000);
    }

    updateStatus(text, color) {
        if (!this.statusIndicator) return;
        this.statusIndicator.innerHTML = `
            <span class="w-2.5 h-2.5 rounded-full bg-${color}-500 mr-2 ${color === 'emerald' ? 'live-indicator' : ''}"></span>
            <span class="text-xs font-semibold text-slate-700 dark:text-slate-300">${escapeHtml(text)}</span>
        `;
    }

    showCameraError(msg) {
        this.updateStatus("Camera Inactive", "rose");
        const container = document.getElementById('webcam-container-box');
        if (container) {
            container.innerHTML = `
                <div class="p-8 text-center bg-rose-50 dark:bg-rose-950/40 border-2 border-dashed border-rose-300 dark:border-rose-800 rounded-2xl">
                    <div class="w-14 h-14 mx-auto mb-4 text-rose-500 bg-rose-100 dark:bg-rose-900/50 rounded-2xl flex items-center justify-center">
                        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                    </div>
                    <h3 class="text-base font-bold text-slate-900 dark:text-slate-100 mb-2">Camera Unavailable</h3>
                    <p class="text-sm text-slate-600 dark:text-slate-300 max-w-md mx-auto mb-6 leading-relaxed">${escapeHtml(msg)}</p>
                    <div class="flex items-center justify-center space-x-3">
                        <button type="button" onclick="location.reload()" class="px-4 py-2 text-sm font-semibold bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-xl hover:bg-slate-50 transition">
                            Retry Camera
                        </button>
                        <a href="/attendance/manual/${this.sessionId}" class="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-md transition">
                            Switch to Manual Attendance
                        </a>
                    </div>
                </div>
            `;
        }
    }

    stop() {
        this.isRunning = false;
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
}
