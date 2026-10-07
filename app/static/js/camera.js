/**
 * CameraService - Unified WebRTC Camera Handler for Smart Attendance System
 */
class CameraService {
    static isReady = false;
    static currentVideo = null;
    static currentStream = null;

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
                actionable: 'Click the camera/lock icon in your browser address bar and set Camera permissions to "Allow".'
            };
        }

        if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            return {
                type: 'NO_HARDWARE',
                title: 'No Camera Detected',
                message: 'No video capture hardware was found on this system.',
                actionable: 'Ensure your webcam is connected and recognized in Windows Device Manager.'
            };
        }

        if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
            return {
                type: 'HARDWARE_LOCKED',
                title: 'Camera Busy / In Use',
                message: 'The camera is currently locked by another program (Zoom, Teams, Skype, or another tab).',
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

        CameraService.isReady = false;

        const targetVideo = videoElement || document.querySelector('video');
        if (!targetVideo) {
            const err = {
                type: 'NO_ELEMENT',
                title: 'Video Element Missing',
                message: 'Target video element was not found in the DOM.',
                actionable: 'Verify DOM element IDs.'
            };
            onError(err);
            return null;
        }

        CameraService.currentVideo = targetVideo;

        onStateChange('INITIALIZING', 'Requesting camera access...');

        const secInfo = CameraService.checkSecureContext();
        if (!secInfo.hasMediaDevices) {
            const errDetails = CameraService.mapCameraError(new Error('MediaDevices unavailable'));
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
            CameraService.stopCamera(targetVideo);

            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            CameraService.currentStream = stream;
            targetVideo.srcObject = stream;

            onStateChange('CONNECTING', 'Attaching video stream...');

            await new Promise((resolve) => {
                if (targetVideo.readyState >= 2) {
                    resolve();
                } else {
                    targetVideo.onloadedmetadata = () => resolve();
                }
            });

            await targetVideo.play();

            CameraService.isReady = true;
            onStateChange('READY', 'Camera streaming active');

            const details = {
                stream,
                videoWidth: targetVideo.videoWidth || 640,
                videoHeight: targetVideo.videoHeight || 480
            };
            onReady(details);
            return stream;
        } catch (err) {
            console.error('CameraService error:', err);
            CameraService.isReady = false;
            const errDetails = CameraService.mapCameraError(err);
            onStateChange('ERROR', errDetails.title);
            onError(errDetails);
            return null;
        }
    }

    static stopCamera(videoElement) {
        CameraService.isReady = false;
        const target = videoElement || CameraService.currentVideo || document.querySelector('video');
        if (target && target.srcObject) {
            const stream = target.srcObject;
            if (stream.getTracks) {
                stream.getTracks().forEach(track => track.stop());
            }
            target.srcObject = null;
        }
        if (CameraService.currentStream) {
            CameraService.currentStream.getTracks().forEach(t => t.stop());
            CameraService.currentStream = null;
        }
    }

    static captureFrame(arg1, arg2) {
        let video = CameraService.currentVideo || document.querySelector('video');
        let quality = 0.92;

        if (arg1 && typeof arg1 === 'object' && arg1.tagName === 'VIDEO') {
            video = arg1;
            quality = typeof arg2 === 'number' ? arg2 : 0.92;
        } else if (typeof arg1 === 'number') {
            quality = arg1;
        }

        if (!video || !video.videoWidth || video.videoWidth === 0) {
            return {
                success: false,
                error: 'Camera video is not active or ready.'
            };
        }

        try {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', quality);
            const base64 = dataUrl.split(',')[1] || '';

            return {
                success: true,
                dataUrl: dataUrl,
                base64: base64,
                width: canvas.width,
                height: canvas.height
            };
        } catch (e) {
            return {
                success: false,
                error: `Frame capture error: ${e.message}`
            };
        }
    }
}

window.CameraService = CameraService;
