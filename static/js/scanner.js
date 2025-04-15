// file: app/static/js/scanner.js

document.addEventListener('DOMContentLoaded', () => {
    const videoElement = document.getElementById('camera-feed');
    const startBtn = document.getElementById('start-scan-btn');
    const stopBtn = document.getElementById('stop-scan-btn');
    const buyerDisplay = document.getElementById('current-buyer');
    const itemDisplay = document.getElementById('current-item');
    const priceDisplay = document.getElementById('accumulated-price');
    const statusMessage = document.getElementById('status-message');
    const cameraError = document.getElementById('camera-error');

    let stream = null;
    let barcodeDetector = null;
    let detectionInterval = null;
    let isDetecting = false;
    let lastDetectedBarcode = null;
    let lastDetectedTime = 0;
    const debounceMs = 1500; // Adjust debounce time

    // --- Check for BarcodeDetector API support ---
    if (!('BarcodeDetector' in window)) {
        console.error('Barcode Detector API not supported in this browser.');
        cameraError.textContent = 'Barcode scanning not supported by this browser. Try Chrome, Edge, or Opera on Desktop/Android.';
        startBtn.disabled = true;
        // Consider loading a fallback library like ZXing-JS here if desired
        return;
    } else {
        // Define supported formats (adjust as needed for CODE_128 etc.)
        BarcodeDetector.getSupportedFormats()
            .then(supportedFormats => {
                console.log("Supported barcode formats:", supportedFormats);
                // Initialize detector (adjust formats if needed)
                barcodeDetector = new BarcodeDetector({ formats: ['code_128', 'qr_code', 'ean_13'] }); // Add relevant formats
            })
            .catch(err => {
                 console.error("Error checking supported formats:", err);
                 cameraError.textContent = 'Error initializing barcode scanner.';
                 startBtn.disabled = true;
            });
    }

    // --- Camera Handling ---
    async function startCamera() {
        cameraError.textContent = '';
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' } // Prefer back camera
            });
            videoElement.srcObject = stream;
            videoElement.play(); // Important for starting the feed
            startBtn.style.display = 'none';
            stopBtn.style.display = 'inline-block';
            console.log("Camera started");
            startDetection(); // Start detection loop once camera is ready
        } catch (err) {
            console.error("Error accessing camera:", err);
            cameraError.textContent = `Error accessing camera: ${err.name}. Ensure permission is granted.`;
            stopCamera(); // Clean up if start failed
        }
    }

    function stopCamera() {
        stopDetection();
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
            videoElement.srcObject = null;
            console.log("Camera stopped");
        }
        startBtn.style.display = 'inline-block';
        stopBtn.style.display = 'none';
        isDetecting = false;
    }

    // --- Barcode Detection ---
    async function detectBarcode() {
        if (!barcodeDetector || !videoElement.srcObject || videoElement.readyState !== videoElement.HAVE_ENOUGH_DATA || isDetecting) {
            // console.log("Detection skipped (not ready or already detecting)");
            return; // Don't detect if not ready or already processing
        }

        isDetecting = true; // Prevent concurrent detections

        try {
            const barcodes = await barcodeDetector.detect(videoElement);
            if (barcodes.length > 0) {
                const detectedValue = barcodes[0].rawValue; // Use the first detected barcode
                const currentTime = Date.now();

                // Debounce: Ignore if same barcode detected too quickly
                if (detectedValue === lastDetectedBarcode && (currentTime - lastDetectedTime < debounceMs)) {
                    // console.log("Debounced:", detectedValue);
                } else {
                    console.log('Barcode detected:', detectedValue);
                    lastDetectedBarcode = detectedValue;
                    lastDetectedTime = currentTime;
                    await sendBarcodeToServer(detectedValue); // Send to backend
                }
            }
        } catch (err) {
            console.error('Error detecting barcode:', err);
            // Potentially display a temporary error to the user
        } finally {
             isDetecting = false; // Allow next detection cycle
        }
    }

    function startDetection() {
        if (!detectionInterval) {
            // Check frequently, but `detectBarcode` itself has a guard (`isDetecting`)
            detectionInterval = setInterval(detectBarcode, 250); // Adjust interval as needed
            console.log("Barcode detection started");
        }
    }

    function stopDetection() {
        if (detectionInterval) {
            clearInterval(detectionInterval);
            detectionInterval = null;
            console.log("Barcode detection stopped");
        }
        lastDetectedBarcode = null; // Reset debounce on stop
    }

    // --- Communication with Server ---
    async function sendBarcodeToServer(barcodeValue) {
        try {
            // Show loading/processing indicator?
            statusMessage.textContent = `Processing: ${barcodeValue}...`;
            statusMessage.className = 'alert alert-warning';

            const response = await fetch('/scan/process_scan', { // Use url_for in template if needed, or hardcode
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // Add CSRF token header if enabled/needed
                    // 'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ barcode: barcodeValue })
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }

            const result = await response.json();
            console.log("Server response:", result);
            updateUI(result); // Update UI based on server response

        } catch (error) {
            console.error('Error sending barcode to server:', error);
            statusMessage.textContent = `Error: ${error.message}. Check connection or try again.`;
            statusMessage.className = 'alert alert-danger';
            // Optionally update state display to show error state?
        }
    }

    // --- UI Update ---
    function updateUI(result) {
        // Update status message
        statusMessage.textContent = result.message || 'Status updated.';
        statusMessage.className = result.status === 'success' ? 'alert alert-success' : 'alert alert-danger';

        // Update state display
        const state = result.state || {};
        buyerDisplay.textContent = state.buyer_name || 'None';
        itemDisplay.textContent = state.item_name || 'None';
        priceDisplay.textContent = state.accumulated_price ? state.accumulated_price.toFixed(2) : '0.00';
    }

    // --- Event Listeners ---
    startBtn.addEventListener('click', startCamera);
    stopBtn.addEventListener('click', stopCamera);

    // Optional: Stop camera when navigating away
    window.addEventListener('beforeunload', stopCamera);

});

// Helper function to get CSRF token from cookie (if needed)
// function getCsrfToken() {
//     return document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];
// }