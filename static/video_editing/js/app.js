// Reel — small client-side helpers for the editor workbench.
// No build step, no framework: this app is server-rendered and this file
// only adds the interactive touches (tabs, status polling, a couple of
// form conveniences) that don't need a round trip.

(function () {
    "use strict";

    // ---- Tool tab switching -------------------------------------------
    const tabs = document.querySelectorAll(".tool-tab");
    const panels = document.querySelectorAll(".tool-section");

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;

            tabs.forEach((t) => t.classList.remove("tool-tab--active"));
            tab.classList.add("tool-tab--active");

            panels.forEach((p) => {
                p.classList.toggle("tool-section--active", p.dataset.panel === target);
            });
        });
    });

    // Activate tab from URL query parameter if present
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get("tab");
    if (activeTab) {
        const targetTab = document.querySelector(`.tool-tab[data-tab="${activeTab}"]`);
        if (targetTab) {
            targetTab.click();
        }
    }

    // ---- Processing status polling -------------------------------------
    if (window.REEL_STATUS_URL && window.REEL_PROJECT_STATUS === "processing") {
        const poll = setInterval(async () => {
            try {
                const res = await fetch(window.REEL_STATUS_URL);
                const data = await res.json();
                if (data.status && data.status !== "processing") {
                    clearInterval(poll);
                    window.location.reload();
                }
            } catch (err) {
                clearInterval(poll);
            }
        }, 2500);
    }

    // ---- Disable submit buttons on form submit to prevent double-clicks
    document.querySelectorAll(".tool-panel form").forEach((form) => {
        // We will NOT disable form submit on trim-form
        if (form.id === "trim-form" || form.id === "bg-audio-form") return;
        form.addEventListener("submit", () => {
            const btn = form.querySelector("button[type=submit]");
            if (btn) {
                btn.dataset.originalText = btn.textContent;
                btn.textContent = "Processing…";
                setTimeout(() => {
                    btn.disabled = true;
                }, 0);
            }
        });
    });

    // ---- Show processing overlay on background audio submit
    const bgAudioForm = document.getElementById("bg-audio-form");
    if (bgAudioForm) {
        bgAudioForm.addEventListener("submit", () => {
            const overlay = document.getElementById("processing-overlay");
            if (overlay) {
                overlay.style.display = "flex";
                const txt = overlay.querySelector("p");
                if (txt) txt.textContent = "Adding background music...";
            }
        });
    }

    // ---- Visual Trim & Custom Player Controls Implementation -----------
    const video = document.getElementById("main-video");
    const startInput = document.getElementById("id_start_seconds");
    const endInput = document.getElementById("id_end_seconds");
    const trimContainer = document.getElementById("visual-trim-container");

    if (video && trimContainer) {
        const trimRuler = document.getElementById("trim-ruler");
        const trimTrack = document.getElementById("trim-track");
        const trimThumbnails = document.getElementById("trim-thumbnails");
        const trimDimLeft = document.getElementById("trim-dim-left");
        const trimDimRight = document.getElementById("trim-dim-right");
        const trimSelection = document.getElementById("trim-selection");
        const handleLeft = document.getElementById("trim-handle-left");
        const handleRight = document.getElementById("trim-handle-right");
        const trimPlayhead = document.getElementById("trim-playhead");
        const currentDisplay = document.getElementById("time-display-current");
        const totalDisplay = document.getElementById("time-display-total");

        // Player Controls elements
        const btnSkipStart = document.getElementById("btn-skip-start");
        const btnBack5 = document.getElementById("btn-back-5");
        const btnPlayPause = document.getElementById("btn-play-pause");
        const btnForward5 = document.getElementById("btn-forward-5");
        const btnSkipEnd = document.getElementById("btn-skip-end");
        const btnFullscreen = document.getElementById("btn-fullscreen");

        // Zoom elements
        const btnZoomIn = document.getElementById("tb-zoom-in");
        const btnZoomOut = document.getElementById("tb-zoom-out");
        const btnZoomFit = document.getElementById("tb-zoom-fit");

        let duration = 0;
        let startSeconds = 0;
        let endSeconds = 0;
        let zoomFactor = 1.0;
        const basePxPerSecond = 15;

        // --- Client-side Accumulative State ---
        const editorState = {
            trim: {
                start: 0,
                end: 0,
                mode: "extract",
                fade_in: false,
                fade_out: false
            },
            speed: 1.0,
            volume: 1.0,
            muted: false,
            text_overlays: [],
            rotate: 0,
            resize: null,
            grayscale: false,
            fade: null
        };

        // UI helper to update CSS filters on the video player
        const applyCSSEffects = () => {
            let filters = [];
            if (editorState.grayscale) {
                filters.push("grayscale(100%)");
            }
            video.style.filter = filters.join(" ");

            // Rotate transform
            if (editorState.rotate) {
                video.style.transform = `rotate(${editorState.rotate}deg)`;
            } else {
                video.style.transform = "";
            }
        };

        // Add item to custom edit history list
        const addHistoryItem = (type, description) => {
            const list = document.querySelector(".history-list");
            const emptyHint = document.querySelector(".history-panel p.muted-text");
            if (emptyHint) emptyHint.remove();

            let ul = list;
            if (!ul) {
                ul = document.createElement("ul");
                ul.className = "history-list";
                const panel = document.querySelector(".history-panel");
                if (panel) {
                    panel.appendChild(ul);
                }
            }

            const li = document.createElement("li");
            li.innerHTML = `
                <span class="history-tag">${type}</span>
                <span class="history-desc">${description}</span>
                <span class="history-time">Just now</span>
                <button type="button" class="history-revert-btn" style="background:none; border:none; color:#ff4a4a; cursor:pointer; font-size:11px; margin-left:10px;">Undo</button>
            `;

            // Setup revert action for client-side state
            li.querySelector(".history-revert-btn").addEventListener("click", () => {
                revertStateChange(type, description);
                li.remove();
            });

            ul.appendChild(li);
        };

        const revertStateChange = (type, description) => {
            if (type === "Grayscale") {
                editorState.grayscale = false;
                applyCSSEffects();
            } else if (type === "Rotate") {
                editorState.rotate = 0;
                applyCSSEffects();
            } else if (type === "Volume") {
                editorState.volume = 1.0;
                video.volume = 1.0;
            } else if (type === "Mute") {
                editorState.muted = false;
                video.muted = false;
            } else if (type === "Speed") {
                editorState.speed = 1.0;
                video.defaultPlaybackRate = 1.0;
                video.playbackRate = 1.0;
            } else if (type === "Text") {
                const cleanDesc = description.replace('Caption: "', '').slice(0, -1);
                const idx = editorState.text_overlays.findIndex(o => o.text === cleanDesc);
                if (idx !== -1) {
                    editorState.text_overlays.splice(idx, 1);
                    renderTextOverlays();
                }
            }
        };

        // --- Live Preview rendering for Text overlays ---
        const renderTextOverlays = () => {
            const container = document.getElementById("text-overlay-container");
            if (!container) return;
            container.innerHTML = "";

            // Helper function to get actual visible video rect inside container
            const getVideoRect = () => {
                const videoEl = document.getElementById("video-preview");
                if (!videoEl || !videoEl.videoWidth || !videoEl.videoHeight) {
                    return {
                        x: 0,
                        y: 0,
                        width: container.clientWidth,
                        height: container.clientHeight
                    };
                }
                const containerWidth = container.clientWidth;
                const containerHeight = container.clientHeight;
                const videoRatio = videoEl.videoWidth / videoEl.videoHeight;
                const containerRatio = containerWidth / containerHeight;

                let videoWidth, videoHeight;
                if (containerRatio > videoRatio) {
                    // Container is wider than video, scale to height
                    videoHeight = containerHeight;
                    videoWidth = videoHeight * videoRatio;
                } else {
                    // Container is taller than video, scale to width
                    videoWidth = containerWidth;
                    videoHeight = videoWidth / videoRatio;
                }

                const x = (containerWidth - videoWidth) / 2;
                const y = (containerHeight - videoHeight) / 2;

                return { x, y, width: videoWidth, height: videoHeight };
            };

            editorState.text_overlays.forEach((overlay) => {
                const el = document.createElement("div");

                // Proportional scaling so the browser preview matches the final export
                const actualHeight = parseFloat(window.REEL_PROJECT_HEIGHT) || 720;
                const playerHeight = video.clientHeight || 400;
                const scale = playerHeight / actualHeight;
                const displayFontSize = Math.max(10, Math.round(overlay.font_size * scale));

                el.style.fontSize = `${displayFontSize}px`;
                el.style.color = overlay.color;
                el.textContent = overlay.text;
                el.style.pointerEvents = "auto";
                el.style.cursor = "move";
                el.style.userSelect = "none";
                el.style.boxSizing = "border-box";
                el.style.whiteSpace = "pre-wrap";

                // Set up position styling
                if (overlay.position && overlay.position.startsWith("custom:")) {
                    const parts = overlay.position.substring(7).split(",");
                    const x_pct = parseFloat(parts[0]);
                    const y_pct = parseFloat(parts[1]);

                    const applyPosition = () => {
                        const videoRect = getVideoRect();
                        const t_w = el.offsetWidth;
                        const t_h = el.offsetHeight;

                        el.style.left = `${videoRect.x + (videoRect.width - t_w) * (x_pct / 100)}px`;
                        el.style.top = `${videoRect.y + (videoRect.height - t_h) * (y_pct / 100)}px`;
                        el.style.transform = "none";
                        el.style.margin = "0";
                    };

                    el.style.position = "absolute";
                    container.appendChild(el);
                    applyPosition();
                    setTimeout(applyPosition, 0); // fallback sync
                } else {
                    el.className = `preview-text-overlay pos-${overlay.position}`;
                    container.appendChild(el);
                }

                // Make it draggable
                let isDragging = false;
                let startX, startY;
                let startLeft, startTop;

                const onMouseDown = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    isDragging = true;

                    const rect = el.getBoundingClientRect();
                    const parentRect = container.getBoundingClientRect();

                    startLeft = rect.left - parentRect.left;
                    startTop = rect.top - parentRect.top;

                    startX = e.clientX || (e.touches && e.touches[0].clientX);
                    startY = e.clientY || (e.touches && e.touches[0].clientY);

                    document.addEventListener("mousemove", onMouseMove);
                    document.addEventListener("mouseup", onMouseUp);
                    document.addEventListener("touchmove", onMouseMove, { passive: false });
                    document.addEventListener("touchend", onMouseUp);
                };

                const onMouseMove = (e) => {
                    if (!isDragging) return;
                    e.preventDefault();

                    const clientX = e.clientX || (e.touches && e.touches[0].clientX);
                    const clientY = e.clientY || (e.touches && e.touches[0].clientY);

                    const dx = clientX - startX;
                    const dy = clientY - startY;

                    const videoRect = getVideoRect();
                    const t_w = el.offsetWidth;
                    const t_h = el.offsetHeight;

                    let newLeft = startLeft + dx;
                    let newTop = startTop + dy;

                    // Constrain to actual visible video rect
                    newLeft = Math.max(videoRect.x, Math.min(videoRect.x + videoRect.width - t_w, newLeft));
                    newTop = Math.max(videoRect.y, Math.min(videoRect.y + videoRect.height - t_h, newTop));

                    el.style.left = `${newLeft}px`;
                    el.style.top = `${newTop}px`;
                    el.style.transform = "none";
                    el.style.margin = "0";
                    el.style.position = "absolute";
                };

                const onMouseUp = () => {
                    if (!isDragging) return;
                    isDragging = false;

                    document.removeEventListener("mousemove", onMouseMove);
                    document.removeEventListener("mouseup", onMouseUp);
                    document.removeEventListener("touchmove", onMouseMove);
                    document.removeEventListener("touchend", onMouseUp);

                    const videoRect = getVideoRect();
                    const t_w = el.offsetWidth;
                    const t_h = el.offsetHeight;

                    const leftPx = parseFloat(el.style.left) || videoRect.x;
                    const topPx = parseFloat(el.style.top) || videoRect.y;

                    // Calculate position relative to visible video rect
                    const relativeLeft = leftPx - videoRect.x;
                    const relativeTop = topPx - videoRect.y;

                    const denomX = videoRect.width - t_w;
                    const denomY = videoRect.height - t_h;

                    const x_pct = denomX > 0 ? (relativeLeft / denomX) * 100 : 50;
                    const y_pct = denomY > 0 ? (relativeTop / denomY) * 100 : 50;

                    const newPosValue = `custom:${x_pct.toFixed(2)},${y_pct.toFixed(2)}`;
                    overlay.position = newPosValue;

                    const textFormEl = document.querySelector('form[action*="/text/"]');
                    if (textFormEl) {
                        const posInput = textFormEl.querySelector("#id_position");
                        if (posInput) {
                            let opt = posInput.querySelector('option[value^="custom:"]');
                            if (!opt) {
                                opt = document.createElement("option");
                                posInput.appendChild(opt);
                            }
                            opt.value = newPosValue;
                            opt.textContent = `Custom (${x_pct.toFixed(0)}%, ${y_pct.toFixed(0)}%)`;
                            posInput.value = newPosValue;
                        }
                    }
                };

                el.addEventListener("mousedown", onMouseDown);
                el.addEventListener("touchstart", onMouseDown, { passive: false });
            });
            renderTextTrackTimeline();
        };

        // --- Real-time sync of Text Overlay Form fields to editorState & preview ---
        const textFormEl = document.querySelector('form[action*="/text/"]');
        if (textFormEl) {
            const txtInput = textFormEl.querySelector("#id_text");
            const posInput = textFormEl.querySelector("#id_position");
            const colorInput = textFormEl.querySelector("#id_color");
            const sizeInput = textFormEl.querySelector("#id_font_size");
            const startInput = textFormEl.querySelector("#id_start_seconds");
            const endInput = textFormEl.querySelector("#id_end_seconds");

            const syncFormToOverlay = () => {
                if (!txtInput) return;
                const text = txtInput.value.trim();
                if (!text) {
                    editorState.text_overlays = [];
                    renderTextOverlays();
                    return;
                }

                if (editorState.text_overlays.length === 0) {
                    const startVal = startInput && startInput.value ? parseFloat(startInput.value) : 0;
                    const endVal = endInput && endInput.value ? parseFloat(endInput.value) : duration;
                    editorState.text_overlays = [{
                        text: text,
                        position: posInput ? posInput.value : "bottom",
                        color: colorInput ? colorInput.value : "white",
                        font_size: sizeInput ? (parseInt(sizeInput.value) || 80) : 80,
                        start: startVal,
                        end: endVal
                    }];
                    selectedOverlayIndex = 0;
                } else {
                    const overlay = editorState.text_overlays[0];
                    overlay.text = text;
                    if (posInput) overlay.position = posInput.value;
                    if (colorInput) overlay.color = colorInput.value;
                    if (sizeInput) overlay.font_size = parseInt(sizeInput.value) || 80;
                    if (startInput && startInput.value !== "") overlay.start = parseFloat(startInput.value);
                    if (endInput && endInput.value !== "") overlay.end = parseFloat(endInput.value);
                }
                renderTextOverlays();
            };

            [txtInput, sizeInput, startInput, endInput].forEach(input => {
                if (input) input.addEventListener("input", syncFormToOverlay);
            });
            [posInput, colorInput].forEach(input => {
                if (input) input.addEventListener("change", syncFormToOverlay);
            });
        }

        // --- Multi-track Timeline Text Row rendering ---
        const textTrackContent = document.getElementById("text-track-content");
        let selectedOverlayIndex = -1;
        // Synchronize Text Overlay Start/End Inputs with Playhead position
        const btnTextSetStart = document.getElementById("btn-text-set-start");
        const btnTextSetEnd = document.getElementById("btn-text-set-end");

        if (btnTextSetStart) {
            btnTextSetStart.addEventListener("click", () => {
                const playheadTime = parseFloat(video.currentTime.toFixed(2));
                const textFormEl = document.querySelector('form[action*="/text/"]');
                if (textFormEl) {
                    const input = textFormEl.querySelector('input[name="start_seconds"]');
                    if (input) input.value = playheadTime;
                }

                if (selectedOverlayIndex !== -1 && editorState.text_overlays[selectedOverlayIndex]) {
                    const overlay = editorState.text_overlays[selectedOverlayIndex];
                    if (playheadTime < overlay.end) {
                        overlay.start = playheadTime;
                        renderTextTrackTimeline();
                        renderTextOverlays();
                    }
                }
            });
        }

        if (btnTextSetEnd) {
            btnTextSetEnd.addEventListener("click", () => {
                const playheadTime = parseFloat(video.currentTime.toFixed(2));
                const textFormEl = document.querySelector('form[action*="/text/"]');
                if (textFormEl) {
                    const input = textFormEl.querySelector('input[name="end_seconds"]');
                    if (input) input.value = playheadTime;
                }

                if (selectedOverlayIndex !== -1 && editorState.text_overlays[selectedOverlayIndex]) {
                    const overlay = editorState.text_overlays[selectedOverlayIndex];
                    if (playheadTime > overlay.start) {
                        overlay.end = playheadTime;
                        renderTextTrackTimeline();
                        renderTextOverlays();
                    }
                }
            });
        }

        // Synchronize Background Audio Start/End Inputs with Playhead position
        const btnBgSetStart = document.getElementById("btn-bg-set-start");
        const btnBgSetEnd = document.getElementById("btn-bg-set-end");

        if (btnBgSetStart) {
            btnBgSetStart.addEventListener("click", () => {
                const playheadTime = parseFloat(video.currentTime.toFixed(2));
                const bgFormEl = document.getElementById("bg-audio-form");
                if (bgFormEl) {
                    const input = bgFormEl.querySelector('input[name="start_seconds"]');
                    if (input) input.value = playheadTime;
                }
            });
        }

        if (btnBgSetEnd) {
            btnBgSetEnd.addEventListener("click", () => {
                const playheadTime = parseFloat(video.currentTime.toFixed(2));
                const bgFormEl = document.getElementById("bg-audio-form");
                if (bgFormEl) {
                    const input = bgFormEl.querySelector('input[name="end_seconds"]');
                    if (input) input.value = playheadTime;
                }
            });
        }
        const savedTextOverlays = [];
        document.querySelectorAll(".history-desc[data-op-type='text_overlay']").forEach((el) => {
            const desc = el.dataset.desc || el.textContent || "";
            const regex = /Added text overlay:\s*"([^"]+)"\s*\[start=([\d.]+),end=([\d.]+)\]/;
            const match = desc.match(regex);
            if (match) {
                savedTextOverlays.push({
                    text: match[1],
                    start: parseFloat(match[2]),
                    end: parseFloat(match[3])
                });
            }
        });

        const savedAudioOverlays = [];
        document.querySelectorAll(".history-desc[data-op-type='volume']").forEach((el) => {
            const desc = el.dataset.desc || el.textContent || "";
            if (desc.includes("Added background audio")) {
                const regex = /Added background audio\s*'([^']+)'\s*\[start=([\d.]+),end=([\d.]+)\]/;
                const match = desc.match(regex);
                if (match) {
                    savedAudioOverlays.push({
                        text: match[1],
                        start: parseFloat(match[2]),
                        end: parseFloat(match[3])
                    });
                }
            }
        });

        function renderTextTrackTimeline() {
            if (!textTrackContent || !duration) return;
            textTrackContent.querySelectorAll(".timeline-text-block, .timeline-text-block--saved").forEach(el => el.remove());

            const pxPerSecond = basePxPerSecond * zoomFactor;

            // Sync Audio track wrapper width and draw saved audio blocks
            const audioTrack = document.getElementById("audio-track");
            if (audioTrack) {
                audioTrack.style.width = `${duration * pxPerSecond}px`;

                // Clear any previously rendered saved audio blocks
                audioTrack.querySelectorAll(".timeline-audio-block--saved").forEach(el => el.remove());

                // Render saved read-only audio blocks
                savedAudioOverlays.forEach((overlay, index) => {
                    const leftPx = overlay.start * pxPerSecond;
                    const widthPx = (overlay.end - overlay.start) * pxPerSecond;

                    const el = document.createElement("div");
                    el.className = "timeline-audio-block timeline-audio-block--saved audio-block";
                    el.style.zIndex = "2";
                    el.style.left = `${leftPx}px`;
                    el.style.width = `${widthPx}px`;
                    el.style.background = "linear-gradient(135deg, #10b981 0%, #059669 100%)";
                    el.style.border = "2px solid #34d399";
                    el.style.opacity = "0.75";
                    el.style.pointerEvents = "none";
                    el.style.position = "absolute";
                    el.style.height = "100%";
                    el.style.top = "0";
                    el.style.display = "flex";
                    el.style.alignItems = "center";
                    el.style.padding = "0 8px";
                    el.style.boxSizing = "border-box";
                    el.style.borderRadius = "10px";
                    el.style.overflow = "hidden";

                    // Waveform
                    const waveformContainer = document.createElement("div");
                    waveformContainer.innerHTML = generateWaveformSvg(widthPx, 44, index);
                    waveformContainer.style.position = "absolute";
                    waveformContainer.style.inset = "0";
                    waveformContainer.style.display = "flex";
                    waveformContainer.style.alignItems = "center";
                    waveformContainer.style.opacity = "0.7";
                    el.appendChild(waveformContainer);

                    // Text label
                    const span = document.createElement("span");
                    span.className = "audio-name";
                    span.style.color = "#ffffff";
                    span.style.fontSize = "11px";
                    span.style.overflow = "hidden";
                    span.style.textOverflow = "ellipsis";
                    span.style.whiteSpace = "nowrap";
                    span.style.position = "relative";
                    span.style.zIndex = "1";
                    span.style.fontWeight = "bold";
                    span.style.textShadow = "0 1px 2px rgba(0,0,0,0.5)";
                    span.textContent = `🎵 ${overlay.text}`;

                    el.appendChild(span);
                    audioTrack.appendChild(el);
                });
            }
            textTrackContent.style.width = `${duration * pxPerSecond}px`;

            // Render saved read-only text blocks
            savedTextOverlays.forEach((overlay) => {
                const leftPx = overlay.start * pxPerSecond;
                const widthPx = (overlay.end - overlay.start) * pxPerSecond;

                const el = document.createElement("div");
                el.className = "timeline-text-block timeline-block--saved";
                el.style.zIndex = "2";
                el.style.left = `${leftPx}px`;
                el.style.width = `${widthPx}px`;
                el.style.background = "rgba(82, 183, 136, 0.25)";
                el.style.border = "1px dashed #52b788";
                el.style.opacity = "0.75";
                el.style.pointerEvents = "none";

                const textSpan = document.createElement("span");
                textSpan.className = "text-content";
                textSpan.style.color = "#a7f3d0";
                textSpan.textContent = overlay.text;

                el.appendChild(textSpan);
                textTrackContent.appendChild(el);
            });

            editorState.text_overlays.forEach((overlay, index) => {
                const leftPx = overlay.start * pxPerSecond;
                const widthPx = (overlay.end - overlay.start) * pxPerSecond;

                const el = document.createElement("div");
                el.className = "timeline-text-block";
                el.style.zIndex = "3";
                if (index === selectedOverlayIndex) {
                    el.className += " selected";
                }
                el.style.left = `${leftPx}px`;
                el.style.width = `${widthPx}px`;

                // Resize handles
                const handleL = document.createElement("div");
                handleL.className = "text-resize-handle handle-left";
                const tooltipL = document.createElement("div");
                tooltipL.className = "handle-tooltip";
                tooltipL.style.background = "#52b788"; // Green color matching text overlays
                tooltipL.textContent = formatTime(overlay.start);
                handleL.appendChild(tooltipL);

                const handleR = document.createElement("div");
                handleR.className = "text-resize-handle handle-right";
                const tooltipR = document.createElement("div");
                tooltipR.className = "handle-tooltip";
                tooltipR.style.background = "#52b788"; // Green color matching text overlays
                tooltipR.textContent = formatTime(overlay.end);
                handleR.appendChild(tooltipR);

                const textSpan = document.createElement("span");
                textSpan.className = "text-content";
                textSpan.textContent = overlay.text;

                el.appendChild(handleL);
                el.appendChild(textSpan);
                el.appendChild(handleR);

                // Click to select/edit
                el.addEventListener("click", (e) => {
                    e.stopPropagation();
                    selectedOverlayIndex = index;
                    renderTextTrackTimeline();

                    const textFormEl = document.querySelector('form[action*="/text/"]');
                    if (textFormEl) {
                        textFormEl.querySelector("#id_text").value = overlay.text;
                        textFormEl.querySelector("#id_position").value = overlay.position;
                        textFormEl.querySelector("#id_color").value = overlay.color;
                        textFormEl.querySelector("#id_font_size").value = overlay.font_size;
                        textFormEl.querySelector("#id_start_seconds").value = overlay.start;
                        textFormEl.querySelector("#id_end_seconds").value = overlay.end;
                    }
                });

                // Dragging logic for Left Resize Handle
                setupDrag(handleL, (clientX) => {
                    let s = getSecondsFromX(clientX);
                    if (s < 0) s = 0;
                    // Enforce 1 second minimum duration constraint
                    if (s > overlay.end - 1.0) s = overlay.end - 1.0;
                    overlay.start = parseFloat(s.toFixed(2));
                    el.style.left = `${overlay.start * pxPerSecond}px`;
                    el.style.width = `${(overlay.end - overlay.start) * pxPerSecond}px`;
                    tooltipL.textContent = formatTime(overlay.start); // Update tooltip
                    renderTextOverlays();

                    const textFormEl = document.querySelector('form[action*="/text/"]');
                    if (textFormEl) {
                        textFormEl.querySelector('input[name="start_seconds"]').value = overlay.start;
                    }
                });

                // Dragging logic for Right Resize Handle
                setupDrag(handleR, (clientX) => {
                    let e = getSecondsFromX(clientX);
                    if (e > duration) e = duration;
                    // Enforce 1 second minimum duration constraint
                    if (e < overlay.start + 1.0) e = overlay.start + 1.0;
                    overlay.end = parseFloat(e.toFixed(2));
                    el.style.width = `${(overlay.end - overlay.start) * pxPerSecond}px`;
                    tooltipR.textContent = formatTime(overlay.end); // Update tooltip
                    renderTextOverlays();

                    const textFormEl = document.querySelector('form[action*="/text/"]');
                    if (textFormEl) {
                        textFormEl.querySelector('input[name="end_seconds"]').value = overlay.end;
                    }
                });

                textTrackContent.appendChild(el);
            });
        }

        // --- Intercept forms to handle preview changes and update state ---

        // Volume adjustments are handled by form submission to the backend.

        // All forms (Speed, Volume, Mute, Text, Rotate, Grayscale, Fade) now submit directly to the server for processing.

        // Master Export submit (AJAX JSON endpoint submission)
        const exportBtn = document.getElementById("btn-master-export");
        if (exportBtn) {
            exportBtn.addEventListener("click", async () => {
                const overlay = document.getElementById("processing-overlay");
                if (overlay) {
                    overlay.style.display = "flex";
                    const txt = overlay.querySelector("p");
                    if (txt) txt.textContent = "Processing edits with FFmpeg...";
                }

                // Append trim configurations directly from visual variables
                editorState.trim.start = startSeconds;
                editorState.trim.end = endSeconds;

                // Get mode and transitions from Trim options
                const modeRadio = document.querySelector('input[name="trim_mode"]:checked');
                if (modeRadio) editorState.trim.mode = modeRadio.value;
                editorState.trim.fade_in = document.querySelector('input[name="fade_in"]')?.checked || false;
                editorState.trim.fade_out = document.querySelector('input[name="fade_out"]')?.checked || false;

                try {
                    const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
                    const res = await fetch(window.location.pathname + "export/", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": csrf
                        },
                        body: JSON.stringify(editorState)
                    });
                    const data = await res.json();
                    if (data.status === "success") {
                        window.location.reload();
                    } else {
                        alert("Export failed: " + (data.error || "Unknown error"));
                        if (overlay) overlay.style.display = "none";
                    }
                } catch (err) {
                    alert("Error exporting: " + err);
                    if (overlay) overlay.style.display = "none";
                }
            });
        }

        // Add text caption directly from timeline
        const timelineAddTextBtn = document.getElementById("timeline-add-text-btn");
        if (timelineAddTextBtn) {
            timelineAddTextBtn.addEventListener("click", () => {
                const text = prompt("Enter text overlay:");
                if (!text || text.trim() === "") return;

                // Switch to the Text tool tab
                const textTab = document.querySelector('.tool-tab[data-tab="text"]');
                if (textTab) {
                    textTab.click();
                }

                // Pre-fill fields with current playhead time
                const start = parseFloat(video.currentTime.toFixed(2));
                const end = parseFloat(Math.min(duration, start + 3).toFixed(2));

                const overlay = {
                    text: text.trim(),
                    position: "bottom",
                    color: "white",
                    font_size: 80,
                    start: start,
                    end: end
                };

                editorState.text_overlays = [overlay]; // Stage this overlay client-side
                selectedOverlayIndex = 0;

                renderTextOverlays();
                renderTextTrackTimeline();

                const textFormEl = document.querySelector('form[action*="/text/"]');
                if (textFormEl) {
                    textFormEl.querySelector("#id_text").value = text.trim();
                    textFormEl.querySelector('input[name="start_seconds"]').value = start;
                    textFormEl.querySelector('input[name="end_seconds"]').value = end;

                    // Focus the text input field in case they want to refine it
                    const textInput = textFormEl.querySelector("#id_text");
                    if (textInput) {
                        textInput.focus();
                        textInput.select();
                    }
                }
            });
        }

        // ---- Timeline Utilities --------------------------------------------
        function formatTime(secs) {
            if (isNaN(secs) || secs < 0) return "00:00:00.000";
            const h = Math.floor(secs / 3600);
            const m = Math.floor((secs % 3600) / 60);
            const s = Math.floor(secs % 60);
            const ms = Math.floor((secs % 1) * 1000);
            return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
        }

        function generateWaveformSvg(width, height, seed = Math.random()) {
            // Generate professional-looking audio waveform with vertical bars
            let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`;
            // Gradient from bright top to dark bottom
            svg += `<defs><linearGradient id="waveGrad" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" style="stop-color:#d1d5db;stop-opacity:0.95"/><stop offset="50%" style="stop-color:#9ca3af;stop-opacity:0.85"/><stop offset="100%" style="stop-color:#4b5563;stop-opacity:0.7"/></linearGradient></defs>`;

            const centerY = height / 2;
            const barWidth = 3;
            const gap = 2;
            const numBars = Math.floor(width / (barWidth + gap));
            const baseline = centerY;

            for (let i = 0; i < numBars; i++) {
                const x = i * (barWidth + gap);
                // Create semi-random but realistic waveform pattern
                const wave1 = Math.sin(i * 0.15 + seed * 20) * 0.35;
                const wave2 = Math.sin(i * 0.06 + seed * 15) * 0.3;
                const wave3 = Math.sin(i * 0.25 + seed * 10) * 0.25;
                const randomFactor = Math.random() * 0.3;
                const amplitude = Math.max(0.1, Math.abs(wave1 + wave2 + wave3 + randomFactor));
                const barHeight = Math.max(3, amplitude * height * 0.9);

                // Draw bar above and below center for symmetric look
                const topY = centerY - barHeight / 2;
                
                svg += `<rect x="${x.toFixed(1)}" y="${topY.toFixed(1)}" width="${barWidth}" height="${barHeight.toFixed(1)}" rx="1.5" fill="url(#waveGrad)"/>`;
            }
            svg += `</svg>`;
            return svg;
        }
        window.generateWaveformSvg = generateWaveformSvg;


        function updateRuler() {
            if (!duration) return;
            trimRuler.innerHTML = "";

            const pxPerSecond = basePxPerSecond * zoomFactor;
            // Offset ruler ticks to align with track content area (same as playhead offset)
            const trackOffset = trimTrack.offsetLeft;
            const parentWidth = trimTrack.parentElement ? trimTrack.parentElement.clientWidth - 32 : 800;
            const totalWidth = Math.max(parentWidth, duration * pxPerSecond);

            const tracksWrapper = document.querySelector(".timeline-tracks-wrapper");
            if (tracksWrapper) {
                const style = window.getComputedStyle(tracksWrapper);
                trimRuler.style.marginLeft = style.marginLeft;
            } else {
                trimRuler.style.marginLeft = "16px";
            }

            trimRuler.style.width = `${trackOffset + totalWidth}px`; // extra room for label column
            trimTrack.style.width = `${totalWidth}px`;

            const textTrackContent = document.getElementById("text-track-content");
            const audioTrack = document.getElementById("audio-track");
            if (textTrackContent) textTrackContent.style.width = `${totalWidth}px`;
            if (audioTrack) audioTrack.style.width = `${totalWidth}px`;

            // Select smallest clean second interval that gives at least 60px of spacing
            const cleanIntervals = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600];
            let interval = 1;
            for (let i = 0; i < cleanIntervals.length; i++) {
                if (cleanIntervals[i] * pxPerSecond >= 35) {
                    interval = cleanIntervals[i];
                    break;
                }
                interval = cleanIntervals[i];
            }

            for (let i = 0; i <= duration; i += interval) {
                // Offset each tick/label by trackOffset so they align with the playhead
                const x = trackOffset + i * pxPerSecond;
                const tick = document.createElement("div");
                tick.className = "trim-tick major";
                tick.style.left = `${x}px`;
                trimRuler.appendChild(tick);

                const label = document.createElement("div");
                label.className = "trim-tick-label";
                label.style.left = `${x}px`;

                const h = Math.floor(i / 3600);
                const m = Math.floor((i % 3600) / 60);
                const s = Math.floor(i % 60);
                if (duration >= 3600) {
                    label.textContent = `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
                } else {
                    label.textContent = `${m}:${String(s).padStart(2, "0")}`;
                }
                trimRuler.appendChild(label);
            }

        }

        const clipBlocksContainer = document.getElementById("timeline-clip-blocks");

        async function renderClipBlocks() {
            if (!clipBlocksContainer || !duration) return;
            clipBlocksContainer.innerHTML = "";

            const clipsData = window.REEL_PROJECT_CLIPS || [];
            const pxPerSecond = basePxPerSecond * zoomFactor;
            const gapPx = 4; // Small gap between clips to show splits

            let accumTime = 0.0;
            clipsData.forEach((clip, index) => {
                const clipDur = parseFloat(clip.duration || 0.0);
                const clipTitle = clip.title || "Clip";

                const block = document.createElement("div");
                block.className = "timeline-clip-block";
                // Calculate position and width, accounting for gap (except after last clip)
                const blockLeft = accumTime * pxPerSecond + (index > 0 ? gapPx : 0);
                const blockWidth = (clipDur * pxPerSecond) - (index < clipsData.length - 1 ? gapPx : 0);
                
                block.style.left = `${blockLeft}px`;
                block.style.width = `${Math.max(blockWidth, 20)}px`; // Minimum 20px width

                // Thumbnail container for clip (empty flex container)
                const thumbContainer = document.createElement("div");
                thumbContainer.className = "timeline-clip-thumb";
                thumbContainer.style.display = "flex";
                thumbContainer.style.overflow = "hidden";
                block.appendChild(thumbContainer);

                // Label
                const label = document.createElement("span");
                label.className = "timeline-clip-label";
                label.textContent = clipTitle;
                label.title = clipTitle;
                block.appendChild(label);

                // Add clear divider
                if (index < clipsData.length - 1) {
                    const divider = document.createElement("div");
                    divider.className = "timeline-clip-divider";
                    block.appendChild(divider);
                }

                // Click handler
                block.addEventListener("click", (e) => {
                    e.stopPropagation();
                    startSeconds = parseFloat(accumTime.toFixed(2));
                    endSeconds = parseFloat((accumTime + clipDur).toFixed(2));
                    selectedClipIndex = index;
                    video.currentTime = startSeconds;
                    renderTrim();
                });

                clipBlocksContainer.appendChild(block);
                accumTime += clipDur;
            });

            // Now generate filmstrip thumbnails for all clips using tempVideo
            const tempVideo = document.createElement("video");
            tempVideo.crossOrigin = "anonymous";
            tempVideo.muted = true;
            tempVideo.preload = "auto";
            tempVideo.src = video.src;

            tempVideo.addEventListener("loadedmetadata", async () => {
                // Clear any existing abort controller
                if (window.tempVideoAbort) {
                    window.tempVideoAbort.abort();
                }
                const abortController = new AbortController();
                window.tempVideoAbort = abortController;
                const signal = abortController.signal;

                const clipBlocks = clipBlocksContainer.querySelectorAll(".timeline-clip-block");
                for (let i = 0; i < clipsData.length; i++) {
                    if (signal.aborted) return;
                    const clip = clipsData[i];
                    const clipStart = parseFloat(clip.start);
                    const clipEnd = parseFloat(clip.end);
                    const clipDuration = clipEnd - clipStart;
                    const clipBlock = clipBlocks[i];
                    const thumbContainer = clipBlock.querySelector(".timeline-clip-thumb");

                    thumbContainer.innerHTML = "";
                    if (!clipDuration || clipDuration <= 0) continue;
                    
                    // Calculate thumbnail count per clip
                    const containerWidth = thumbContainer.clientWidth;
                    const thumbWidth = 80;
                    let count = Math.max(2, Math.floor(containerWidth / thumbWidth));

                    for (let j = 0; j < count; j++) {
                        if (signal.aborted) return;
                        const time = clipStart + (clipDuration / (count - 1 || 1)) * j;
                        tempVideo.currentTime = time;

                        try {
                            await Promise.race([
                                new Promise(r => tempVideo.addEventListener("seeked", r, { once: true })),
                                new Promise(r => setTimeout(r, 500))
                            ]);
                            if (signal.aborted) return;
                            const canvas = document.createElement("canvas");
                            canvas.width = Math.floor(thumbWidth);
                            canvas.height = thumbContainer.clientHeight;
                            const ctx = canvas.getContext("2d");
                            ctx.drawImage(tempVideo, 0, 0, canvas.width, canvas.height);
                            thumbContainer.appendChild(canvas);
                        } catch (e) {
                            console.warn("Error drawing clip thumbnail:", e);
                        }
                    }
                }
            });
        }

        function renderTrim() {
            if (!duration) return;

            const pxPerSecond = basePxPerSecond * zoomFactor;
            const leftPx = startSeconds * pxPerSecond;
            const rightPx = endSeconds * pxPerSecond;
            const playheadPx = video.currentTime * pxPerSecond;

            // Highlight selection box
            trimSelection.style.left = `${leftPx}px`;
            trimSelection.style.width = `${rightPx - leftPx}px`;

            // Dim overlays
            trimDimLeft.style.width = `${leftPx}px`;
            trimDimRight.style.left = `${rightPx}px`;
            trimDimRight.style.width = `${(duration * pxPerSecond) - rightPx}px`;

            // Playhead — offset by track-label-cell width so the line aligns
            // with the content area and spans across ALL tracks (Text, Video, Audio)
            const trackLabelWidth = trimTrack.offsetLeft; // distance from wrapper edge to content area
            trimPlayhead.style.left = `${trackLabelWidth + playheadPx}px`;
            const playheadTooltip = document.getElementById("playhead-tooltip");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(video.currentTime);
            }

            // Time displays
            currentDisplay.textContent = formatTime(video.currentTime);
            totalDisplay.textContent = formatTime(duration);

            const tooltipL = document.getElementById("handle-tooltip-left");
            const tooltipR = document.getElementById("handle-tooltip-right");
            if (tooltipL) tooltipL.textContent = formatTime(startSeconds);
            if (tooltipR) tooltipR.textContent = formatTime(endSeconds);

            // Sync hidden inputs
            if (startInput) startInput.value = startSeconds.toFixed(2);
            if (endInput) endInput.value = endSeconds.toFixed(2);

            // Render multi-track timeline blocks
            renderTextTrackTimeline();
            renderSplitMarkers();
            renderClipBlocks();

            // Toggle selected-delete highlight class and enable/disable delete button
            const deleteBtnEl = document.getElementById("tb-delete");
            if (selectedClipIndex !== -1) {
                trimSelection.classList.add("selected-delete");
                if (deleteBtnEl) deleteBtnEl.removeAttribute("disabled");
            } else {
                trimSelection.classList.remove("selected-delete");
                if (deleteBtnEl) deleteBtnEl.setAttribute("disabled", "true");
            }
        }

        function getSecondsFromX(clientX) {
            const rect = trimTrack.getBoundingClientRect();
            const pxPerSecond = basePxPerSecond * zoomFactor;
            const relativeX = clientX - rect.left;
            const s = relativeX / pxPerSecond;
            return Math.max(0, Math.min(duration, s));
        }


        // Dragging helper
        function setupDrag(element, onDrag, onDragEnd) {
            function move(e) {
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                onDrag(clientX);
            }
            function stop() {
                element.classList.remove("dragging");
                window.removeEventListener("mousemove", move);
                window.removeEventListener("mouseup", stop);
                window.removeEventListener("touchmove", move);
                window.removeEventListener("touchend", stop);
                if (onDragEnd) onDragEnd();
            }
            element.addEventListener("mousedown", (e) => {
                e.preventDefault();
                e.stopPropagation();
                element.classList.add("dragging");
                window.addEventListener("mousemove", move);
                window.addEventListener("mouseup", stop);
            });
            element.addEventListener("touchstart", (e) => {
                e.preventDefault();
                e.stopPropagation();
                element.classList.add("dragging");
                window.addEventListener("touchmove", move);
                window.addEventListener("touchend", stop);
            });
        }

        const autoSubmitTrim = () => {
            if (startInput) startInput.value = startSeconds.toFixed(2);
            if (endInput) endInput.value = endSeconds.toFixed(2);

            const trimForm = document.getElementById("trim-form");
            if (trimForm) {
                const overlay = document.getElementById("processing-overlay");
                if (overlay) {
                    overlay.style.display = "flex";
                    const txt = overlay.querySelector("p");
                    if (txt) txt.textContent = "Trimming video...";
                }
                trimForm.submit();
            }
        };

        // Left handle drag
        setupDrag(handleLeft, (clientX) => {
            let s = getSecondsFromX(clientX);
            if (s < 0) s = 0;
            if (s > endSeconds - 0.5) s = endSeconds - 0.5;
            startSeconds = s;
            renderTrim();
        }, autoSubmitTrim);

        // Right handle drag
        setupDrag(handleRight, (clientX) => {
            let e = getSecondsFromX(clientX);
            if (e > duration) e = duration;
            if (e < startSeconds + 0.5) e = startSeconds + 0.5;
            endSeconds = e;
            renderTrim();
        }, autoSubmitTrim);

        // Video playback sync
        video.addEventListener("timeupdate", () => {
            if (trimPlayhead.classList.contains("dragging")) return;
            const pxPerSecond = basePxPerSecond * zoomFactor;
            const playheadPx = video.currentTime * pxPerSecond;
            const trackOffset = trimTrack.offsetLeft;
            trimPlayhead.style.left = `${trackOffset + playheadPx}px`;
            currentDisplay.textContent = formatTime(video.currentTime);
            const playheadTooltip = document.getElementById("playhead-tooltip");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(video.currentTime);
            }
            // Update video time display
            const timeCurrentEl = document.getElementById("video-time-current");
            if (timeCurrentEl) {
                timeCurrentEl.textContent = formatTime(video.currentTime);
            }

            // Re-render text overlays during playback
            renderTextOverlays();

            // Auto-scroll timeline to keep playhead in view
            const scrollArea = trimContainer.querySelector(".timeline-scroll-area");
            if (scrollArea && !video.paused) {
                const playheadLeft = playheadPx;
                const viewportWidth = scrollArea.clientWidth;
                const scrollLeft = scrollArea.scrollLeft;

                // If playhead is near or past the right edge, or behind the left edge, scroll it into view
                if (playheadLeft > (scrollLeft + viewportWidth - 150)) {
                    scrollArea.scrollLeft = playheadLeft - 150;
                } else if (playheadLeft < scrollLeft + 20) {
                    scrollArea.scrollLeft = Math.max(0, playheadLeft - 20);
                }
            }
        });
        
        // Update time display when metadata loads
        video.addEventListener("loadedmetadata", () => {
            const timeTotalEl = document.getElementById("video-time-total");
            if (timeTotalEl) {
                timeTotalEl.textContent = formatTime(video.duration);
            }
            const timeCurrentEl = document.getElementById("video-time-current");
            if (timeCurrentEl) {
                timeCurrentEl.textContent = formatTime(video.currentTime);
            }
            // Initialize progress bar
            updateVideoProgress();
        });

        // Get progress bar elements
        const videoProgressBar = document.getElementById("video-progress-bar");
        const videoProgressFilled = document.getElementById("video-progress-filled");
        const videoProgressHandle = document.getElementById("video-progress-handle");

        // Function to update progress bar based on video time
        function updateVideoProgress() {
            if (!video.duration || video.duration === 0) return;
            const progress = (video.currentTime / video.duration) * 100;
            if (videoProgressFilled) {
                videoProgressFilled.style.width = `${progress}%`;
            }
            if (videoProgressHandle) {
                videoProgressHandle.style.left = `${progress}%`;
            }
        }

        // Update progress bar on timeupdate
        video.addEventListener("timeupdate", updateVideoProgress);

        // Handle clicking on progress bar to seek
        let isDraggingProgress = false;

        function seekFromProgress(clientX) {
            if (!videoProgressBar || !video.duration) return;
            const rect = videoProgressBar.getBoundingClientRect();
            let clickX = clientX - rect.left;
            // Clamp to bar bounds
            clickX = Math.max(0, Math.min(clickX, rect.width));
            const progress = clickX / rect.width;
            video.currentTime = progress * video.duration;
        }

        if (videoProgressBar) {
            videoProgressBar.addEventListener("mousedown", (e) => {
                isDraggingProgress = true;
                seekFromProgress(e.clientX);
            });
        }

        // Handle mouse move and up on document
        document.addEventListener("mousemove", (e) => {
            if (!isDraggingProgress) return;
            seekFromProgress(e.clientX);
        });

        document.addEventListener("mouseup", () => {
            isDraggingProgress = false;
        });


        // --- Custom Player Control Listeners ---
        if (btnSkipStart) {
            btnSkipStart.addEventListener("click", () => {
                video.currentTime = 0;
            });
        }

        if (btnBack5) {
            btnBack5.addEventListener("click", () => {
                video.currentTime = Math.max(0, video.currentTime - 5);
            });
        }

        // Play/Pause button sync helper
        const syncPlayPauseIcons = () => {
            const isPaused = video.paused;
            const playIcon = document.getElementById("play-icon");
            const pauseIcon = document.getElementById("pause-icon");
            const tbPlayIcon = document.getElementById("tb-bottom-play-icon");
            const tbPauseIcon = document.getElementById("tb-bottom-pause-icon");

            if (playIcon) playIcon.style.display = isPaused ? "inline-block" : "none";
            if (pauseIcon) pauseIcon.style.display = isPaused ? "none" : "inline-block";
            if (tbPlayIcon) tbPlayIcon.style.display = isPaused ? "inline-block" : "none";
            if (tbPauseIcon) tbPauseIcon.style.display = isPaused ? "none" : "inline-block";
        };

        video.addEventListener("play", syncPlayPauseIcons);
        video.addEventListener("pause", syncPlayPauseIcons);

        if (btnPlayPause) {
            btnPlayPause.addEventListener("click", () => {
                if (video.paused) {
                    video.play();
                } else {
                    video.pause();
                }
            });
        }

        if (btnForward5) {
            btnForward5.addEventListener("click", () => {
                video.currentTime = Math.min(duration, video.currentTime + 5);
            });
        }

        if (btnSkipEnd) {
            btnSkipEnd.addEventListener("click", () => {
                video.currentTime = duration;
            });
        }

        if (btnFullscreen) {
            btnFullscreen.addEventListener("click", () => {
                if (video.requestFullscreen) {
                    video.requestFullscreen();
                } else if (video.webkitRequestFullscreen) {
                    video.webkitRequestFullscreen();
                } else if (video.msRequestFullscreen) {
                    video.msRequestFullscreen();
                }
            });
        }

        // --- Timeline Bottom Toolbar Listeners ---
        const tbBottomZoomFit = document.getElementById("tb-bottom-zoom-fit");
        if (tbBottomZoomFit) {
            tbBottomZoomFit.addEventListener("click", () => {
                if (btnZoomFit) btnZoomFit.click();
            });
        }

        // Fullscreen timeline toggle
        const tbBottomFullscreen = document.getElementById("tb-bottom-fullscreen");
        const fsTimelineBtn = document.getElementById("btn-fullscreen-timeline");
        const toggleTimelineFullscreen = () => {
            if (!trimContainer) return;
            trimContainer.classList.toggle("fullscreen-mode");
            const isFs = trimContainer.classList.contains("fullscreen-mode");
            if (isFs) {
                document.body.style.overflow = "hidden";
            } else {
                document.body.style.overflow = "";
            }
            updateRuler();
            renderTrim();
        };

        if (tbBottomFullscreen) tbBottomFullscreen.addEventListener("click", toggleTimelineFullscreen);
        if (fsTimelineBtn) fsTimelineBtn.addEventListener("click", toggleTimelineFullscreen);

        // --- Collapsible & Resizable Timeline Panel (Canva / CapCut Style) ---
        const timelineResizer = document.getElementById("timeline-resizer");
        const collapseBtn = document.getElementById("tb-collapse-timeline");
        const collapseIcon = document.getElementById("collapse-icon");
        const collapseText = document.getElementById("collapse-text");

        let lastExpandedHeight = parseFloat(localStorage.getItem("ve_timeline_height")) || 240;
        let isCollapsedState = localStorage.getItem("ve_timeline_collapsed") === "true";

        const setCollapseUIState = (collapsed) => {
            if (collapsed) {
                trimContainer.classList.add("timeline-collapsed");
                trimContainer.style.height = "128px";
                if (collapseText) collapseText.textContent = "Expand";
                if (collapseIcon) collapseIcon.setAttribute("data-lucide", "chevron-up");
            } else {
                trimContainer.classList.remove("timeline-collapsed");
                trimContainer.style.height = `${lastExpandedHeight}px`;
                if (collapseText) collapseText.textContent = "Minimize";
                if (collapseIcon) collapseIcon.setAttribute("data-lucide", "chevron-down");
            }
            if (typeof lucide !== 'undefined') lucide.createIcons();
            localStorage.setItem("ve_timeline_collapsed", collapsed ? "true" : "false");
            updateRuler();
            renderTrim();
            renderTextOverlays();
        };

        const toggleCollapse = () => {
            const nowCollapsed = !trimContainer.classList.contains("timeline-collapsed");
            setCollapseUIState(nowCollapsed);
        };

        if (collapseBtn) {
            collapseBtn.addEventListener("click", toggleCollapse);
        }

        if (timelineResizer) {
            timelineResizer.addEventListener("dblclick", toggleCollapse);

            let isResizing = false;
            let startY = 0;
            let startH = 0;

            const onStartResize = (e) => {
                e.preventDefault();
                e.stopPropagation();
                isResizing = true;
                timelineResizer.classList.add("is-dragging");
                startY = e.touches ? e.touches[0].clientY : e.clientY;
                startH = trimContainer.getBoundingClientRect().height;

                document.addEventListener("mousemove", onResizing);
                document.addEventListener("mouseup", onStopResize);
                document.addEventListener("touchmove", onResizing, { passive: false });
                document.addEventListener("touchend", onStopResize);
            };

            const onResizing = (e) => {
                if (!isResizing) return;
                if (e.cancelable) e.preventDefault();
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                const deltaY = startY - clientY; // Dragging UP increases height
                let newH = startH + deltaY;

                const maxH = Math.min(window.innerHeight * 0.7, 550);
                newH = Math.max(128, Math.min(maxH, newH));

                if (newH <= 140) {
                    trimContainer.classList.add("timeline-collapsed");
                    trimContainer.style.height = "128px";
                    if (collapseText) collapseText.textContent = "Expand";
                    if (collapseIcon) collapseIcon.setAttribute("data-lucide", "chevron-up");
                } else {
                    trimContainer.classList.remove("timeline-collapsed");
                    trimContainer.style.height = `${newH}px`;
                    lastExpandedHeight = newH;
                    if (collapseText) collapseText.textContent = "Minimize";
                    if (collapseIcon) collapseIcon.setAttribute("data-lucide", "chevron-down");
                }
                if (typeof lucide !== 'undefined') lucide.createIcons();
                updateRuler();
                renderTrim();
                renderTextOverlays();
            };

            const onStopResize = () => {
                if (!isResizing) return;
                isResizing = false;
                timelineResizer.classList.remove("is-dragging");
                document.removeEventListener("mousemove", onResizing);
                document.removeEventListener("mouseup", onStopResize);
                document.removeEventListener("touchmove", onResizing);
                document.removeEventListener("touchend", onStopResize);

                const finalH = trimContainer.getBoundingClientRect().height;
                const isNowCollapsed = finalH <= 135;
                localStorage.setItem("ve_timeline_collapsed", isNowCollapsed ? "true" : "false");
                if (!isNowCollapsed) {
                    localStorage.setItem("ve_timeline_height", finalH);
                    lastExpandedHeight = finalH;
                }
            };

            timelineResizer.addEventListener("mousedown", onStartResize);
            timelineResizer.addEventListener("touchstart", onStartResize, { passive: false });
        }

        // Restore initial state from localStorage
        if (isCollapsedState) {
            setCollapseUIState(true);
        } else if (lastExpandedHeight && lastExpandedHeight !== 240) {
            trimContainer.style.height = `${lastExpandedHeight}px`;
        }


        const playheadTooltip = document.getElementById("playhead-tooltip");

        // Throttle helper to prevent spamming video seek requests during fast drag
        function throttle(func, limit) {
            let inThrottle;
            return function (...args) {
                if (!inThrottle) {
                    func.apply(this, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            }
        }

        let dragLastTime = 0;
        const seekVideoThrottled = throttle((time) => {
            video.currentTime = time;
        }, 100);

        // Drag or click on timeline ruler to seek video
        setupDrag(trimRuler, (clientX) => {
            let time = getSecondsFromX(clientX);
            if (time < 0) time = 0;
            if (time > duration) time = duration;
            dragLastTime = time;

            if (!video.paused) {
                video.pause();
            }
            seekVideoThrottled(time);

            const pxPerSecond = basePxPerSecond * zoomFactor;
            trimPlayhead.style.left = `${trimTrack.offsetLeft + time * pxPerSecond}px`;
            currentDisplay.textContent = formatTime(time);
            const timeCurrentEl = document.getElementById("video-time-current");
            if (timeCurrentEl) {
                timeCurrentEl.textContent = formatTime(time);
            }
            updateVideoProgress();

            trimPlayhead.classList.add("dragging");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(time);
            }
        }, () => {
            trimPlayhead.classList.remove("dragging");
            video.currentTime = dragLastTime; // Ensure final seek is exact
        });

        // Grab and drag the playhead needle/cap directly
        setupDrag(trimPlayhead, (clientX) => {
            let time = getSecondsFromX(clientX);
            if (time < 0) time = 0;
            if (time > duration) time = duration;
            dragLastTime = time;

            if (!video.paused) {
                video.pause();
            }
            seekVideoThrottled(time);

            const pxPerSecond = basePxPerSecond * zoomFactor;
            trimPlayhead.style.left = `${trimTrack.offsetLeft + time * pxPerSecond}px`;
            currentDisplay.textContent = formatTime(time);
            const timeCurrentEl = document.getElementById("video-time-current");
            if (timeCurrentEl) {
                timeCurrentEl.textContent = formatTime(time);
            }
            updateVideoProgress();

            trimPlayhead.classList.add("dragging");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(time);
            }
        }, () => {
            trimPlayhead.classList.remove("dragging");
            video.currentTime = dragLastTime; // Ensure final seek is exact
        });



        const timelineAddAudioBtn = document.getElementById("timeline-add-audio-btn");
        const audioFileIn = document.getElementById("id_audio_file");
        let audioOverlay = null; // To store current audio overlay info

        if (audioFileIn) {
            audioFileIn.addEventListener("change", (e) => {
                const file = e.target.files[0];
                if (!file) return;

                // Default start/end
                let start = parseFloat(video.currentTime.toFixed(2));
                let end = parseFloat(Math.min(duration, start + 10).toFixed(2));

                audioOverlay = {
                    file: file,
                    filename: file.name,
                    start: start,
                    end: end
                };

                // Update form inputs
                const bgForm = document.getElementById("bg-audio-form");
                if (bgForm) {
                    const startIn = bgForm.querySelector('input[name="start_seconds"]');
                    const endIn = bgForm.querySelector('input[name="end_seconds"]');
                    if (startIn) startIn.value = start;
                    if (endIn) endIn.value = end;
                }

                renderAudioOverlay(); // Render on timeline
            });
        }


        function renderAudioOverlay() {
            const audioTrack = document.getElementById("audio-track");
            if (!audioTrack || !duration || !audioOverlay) return;

            // Remove existing block if any
            audioTrack.querySelectorAll(".temp-audio-block").forEach(el => el.remove());

            const pxPerSecond = basePxPerSecond * zoomFactor;
            const leftPx = audioOverlay.start * pxPerSecond;
            const widthPx = (audioOverlay.end - audioOverlay.start) * pxPerSecond;

            const el = document.createElement("div");
            el.className = "temp-audio-block audio-block";
            el.style.position = "absolute";
            el.style.left = `${leftPx}px`;
            el.style.width = `${widthPx}px`;
            el.style.height = "100%";
            el.style.top = "0";
            el.style.background = "linear-gradient(135deg, #10b981 0%, #059669 100%)";
            el.style.border = "2.5px solid #34d399";
            el.style.borderRadius = "10px";
            el.style.display = "flex";
            el.style.alignItems = "center";
            el.style.padding = "0 8px";
            el.style.boxSizing = "border-box";
            el.style.zIndex = "3";
            el.style.overflow = "hidden";

            // Waveform
            const waveformContainer = document.createElement("div");
            waveformContainer.innerHTML = generateWaveformSvg(widthPx, 44, audioOverlay.filename.length);
            waveformContainer.style.position = "absolute";
            waveformContainer.style.inset = "0";
            waveformContainer.style.display = "flex";
            waveformContainer.style.alignItems = "center";
            waveformContainer.style.opacity = "0.65";
            el.appendChild(waveformContainer);

            // Left resize handle
            const handleL = document.createElement("div");
            handleL.style.position = "absolute";
            handleL.style.left = "-4px";
            handleL.style.top = "0";
            handleL.style.width = "8px";
            handleL.style.height = "100%";
            handleL.style.cursor = "ew-resize";
            handleL.style.zIndex = "4";

            const tooltipL = document.createElement("div");
            tooltipL.style.position = "absolute";
            tooltipL.style.top = "-24px";
            tooltipL.style.left = "50%";
            tooltipL.style.transform = "translateX(-50%)";
            tooltipL.style.background = "#00bfff";
            tooltipL.style.color = "white";
            tooltipL.style.padding = "2px 6px";
            tooltipL.style.borderRadius = "4px";
            tooltipL.style.fontSize = "11px";
            tooltipL.style.whiteSpace = "nowrap";
            tooltipL.textContent = formatTime(audioOverlay.start);
            handleL.appendChild(tooltipL);

            // Right resize handle
            const handleR = document.createElement("div");
            handleR.style.position = "absolute";
            handleR.style.right = "-4px";
            handleR.style.top = "0";
            handleR.style.width = "8px";
            handleR.style.height = "100%";
            handleR.style.cursor = "ew-resize";
            handleR.style.zIndex = "4";

            const tooltipR = document.createElement("div");
            tooltipR.style.position = "absolute";
            tooltipR.style.top = "-24px";
            tooltipR.style.left = "50%";
            tooltipR.style.transform = "translateX(-50%)";
            tooltipR.style.background = "#00bfff";
            tooltipR.style.color = "white";
            tooltipR.style.padding = "2px 6px";
            tooltipR.style.borderRadius = "4px";
            tooltipR.style.fontSize = "11px";
            tooltipR.style.whiteSpace = "nowrap";
            tooltipR.textContent = formatTime(audioOverlay.end);
            handleR.appendChild(tooltipR);

            const span = document.createElement("span");
            span.style.color = "#fff";
            span.style.fontSize = "11px";
            span.style.overflow = "hidden";
            span.style.textOverflow = "ellipsis";
            span.style.whiteSpace = "nowrap";
            span.style.marginRight = "6px";
            span.style.flexGrow = "1";
            span.style.position = "relative";
            span.style.zIndex = "1";
            span.style.fontWeight = "bold";
            span.style.textShadow = "0 1px 2px rgba(0,0,0,0.5)";
            span.textContent = `🎵 ${audioOverlay.filename}`;

            // Cancel button (X)
            const cancelBtn = document.createElement("button");
            cancelBtn.innerHTML = "✖";
            cancelBtn.style.background = "none";
            cancelBtn.style.border = "none";
            cancelBtn.style.color = "#ff4d4d";
            cancelBtn.style.cursor = "pointer";
            cancelBtn.style.padding = "2px 4px";
            cancelBtn.style.marginRight = "6px";
            cancelBtn.style.fontSize = "11px";
            cancelBtn.style.flexShrink = "0";
            cancelBtn.title = "Cancel";
            cancelBtn.style.position = "relative";
            cancelBtn.style.zIndex = "1";
            cancelBtn.onclick = (e) => {
                e.stopPropagation();
                audioOverlay = null;
                audioTrack.querySelectorAll(".temp-audio-block").forEach(el => el.remove());
                if (audioFileIn) audioFileIn.value = "";
            };

            // Apply button
            const applyBtn = document.createElement("button");
            applyBtn.innerHTML = "Apply";
            applyBtn.style.background = "#52b788";
            applyBtn.style.color = "white";
            applyBtn.style.border = "none";
            applyBtn.style.borderRadius = "4px";
            applyBtn.style.padding = "2px 8px";
            applyBtn.style.cursor = "pointer";
            applyBtn.style.fontSize = "10px";
            applyBtn.style.fontWeight = "bold";
            applyBtn.style.flexShrink = "0";
            applyBtn.title = "Apply background audio";
            applyBtn.style.position = "relative";
            applyBtn.style.zIndex = "1";
            applyBtn.onclick = (e) => {
                e.stopPropagation();
                const bgForm = document.getElementById("bg-audio-form");
                if (bgForm) {
                    const overlay = document.getElementById("processing-overlay");
                    if (overlay) {
                        overlay.style.display = "flex";
                        const txt = overlay.querySelector("p");
                        if (txt) txt.textContent = "Adding background audio...";
                    }
                    bgForm.submit();
                }
            };

            el.appendChild(handleL);
            el.appendChild(span);
            el.appendChild(cancelBtn);
            el.appendChild(applyBtn);
            el.appendChild(handleR);

            // Drag the whole block
            setupDrag(el, (clientX) => {
                const pxPerSec = basePxPerSecond * zoomFactor;
                let newStart = getSecondsFromX(clientX);
                if (newStart < 0) newStart = 0;
                const blockDur = audioOverlay.end - audioOverlay.start;
                if (newStart + blockDur > duration) newStart = duration - blockDur;

                audioOverlay.start = parseFloat(newStart.toFixed(2));
                audioOverlay.end = parseFloat((newStart + blockDur).toFixed(2));

                // Update styles directly to prevent recursive render glitches
                el.style.left = `${audioOverlay.start * pxPerSec}px`;
                tooltipL.textContent = formatTime(audioOverlay.start);
                tooltipR.textContent = formatTime(audioOverlay.end);

                // Update form inputs
                const bgForm = document.getElementById("bg-audio-form");
                if (bgForm) {
                    const startIn = bgForm.querySelector('input[name="start_seconds"]');
                    const endIn = bgForm.querySelector('input[name="end_seconds"]');
                    if (startIn) startIn.value = audioOverlay.start;
                    if (endIn) endIn.value = audioOverlay.end;
                }
            });

            // Left handle drag
            setupDrag(handleL, (clientX) => {
                const pxPerSec = basePxPerSecond * zoomFactor;
                let newStart = getSecondsFromX(clientX);
                if (newStart < 0) newStart = 0;
                if (newStart > audioOverlay.end - 0.5) newStart = audioOverlay.end - 0.5;

                audioOverlay.start = parseFloat(newStart.toFixed(2));

                // Update styles directly to prevent recursive render glitches
                el.style.left = `${audioOverlay.start * pxPerSec}px`;
                el.style.width = `${(audioOverlay.end - audioOverlay.start) * pxPerSec}px`;
                tooltipL.textContent = formatTime(audioOverlay.start);

                const bgForm = document.getElementById("bg-audio-form");
                if (bgForm) {
                    const startIn = bgForm.querySelector('input[name="start_seconds"]');
                    if (startIn) startIn.value = audioOverlay.start;
                }
            });

            // Right handle drag
            setupDrag(handleR, (clientX) => {
                const pxPerSec = basePxPerSecond * zoomFactor;
                let newEnd = getSecondsFromX(clientX);
                if (newEnd > duration) newEnd = duration;
                if (newEnd < audioOverlay.start + 0.5) newEnd = audioOverlay.start + 0.5;

                audioOverlay.end = parseFloat(newEnd.toFixed(2));

                // Update styles directly to prevent recursive render glitches
                el.style.width = `${(audioOverlay.end - audioOverlay.start) * pxPerSec}px`;
                tooltipR.textContent = formatTime(audioOverlay.end);

                const bgForm = document.getElementById("bg-audio-form");
                if (bgForm) {
                    const endIn = bgForm.querySelector('input[name="end_seconds"]');
                    if (endIn) endIn.value = audioOverlay.end;
                }
            });

            audioTrack.appendChild(el);
        }

        if (timelineAddAudioBtn && audioFileIn) {
            timelineAddAudioBtn.addEventListener("click", () => {
                audioFileIn.click();
            });
        }
        // --- Zoom Control Listeners ---
        if (btnZoomIn) {
            btnZoomIn.addEventListener("click", () => {
                zoomFactor = Math.min(10.0, zoomFactor * 1.4);
                updateRuler();
                renderTrim();
                generateThumbnails();
                renderAudioOverlay();
            });
        }

        if (btnZoomOut) {
            btnZoomOut.addEventListener("click", () => {
                zoomFactor = Math.max(0.001, zoomFactor / 1.4);
                updateRuler();
                renderTrim();
                generateThumbnails();
                renderAudioOverlay();
            });
        }

        if (btnZoomFit) {
            btnZoomFit.addEventListener("click", () => {
                const parentWidth = trimTrack.parentElement.clientWidth;
                if (parentWidth && duration) {
                    zoomFactor = parentWidth / (duration * basePxPerSecond);
                    updateRuler();
                    renderTrim();
                    generateThumbnails();
                    renderAudioOverlay();
                }
            });
        }

        // --- Clips and Split points logic ---
        let splitPoints = [];
        let selectedClipIndex = -1;

        function getClips() {
            let clips = [];
            let lastT = 0;
            const sortedSplits = [...splitPoints].sort((a, b) => a - b);
            for (let i = 0; i < sortedSplits.length; i++) {
                let t = sortedSplits[i];
                if (t > lastT && t < duration) {
                    clips.push({ start: lastT, end: t });
                    lastT = t;
                }
            }
            if (lastT < duration) {
                clips.push({ start: lastT, end: duration });
            }
            return clips;
        }

        function renderSplitMarkers() {
            const tracksWrapper = document.querySelector(".timeline-tracks-wrapper");
            if (!tracksWrapper) return;

            // Remove existing split markers
            tracksWrapper.querySelectorAll(".trim-split-marker").forEach(el => el.remove());

            const pxPerSecond = basePxPerSecond * zoomFactor;
            splitPoints.forEach(t => {
                const el = document.createElement("div");
                el.className = "trim-split-marker";
                el.style.left = `${t * pxPerSecond}px`;
                tracksWrapper.appendChild(el);
            });
        }

        // Click on the video track to select a segment
        if (trimTrack) {
            trimTrack.addEventListener("click", (e) => {
                // If clicking handles, ignore to prevent selection reset during drag
                if (e.target.classList.contains("trim-handle") || e.target.closest(".trim-handle")) {
                    return;
                }
                const t = getSecondsFromX(e.clientX);
                const clips = getClips();
                const index = clips.findIndex(c => t >= c.start && t <= c.end);
                if (index !== -1) {
                    selectedClipIndex = index;
                    startSeconds = clips[index].start;
                    endSeconds = clips[index].end;
                    renderTrim();
                    video.currentTime = startSeconds;
                }
            });
        }

        // Split button click
        const splitBtn = document.getElementById("tb-split");
        if (splitBtn) {
            splitBtn.addEventListener("click", () => {
                const curT = parseFloat(video.currentTime.toFixed(2));
                if (curT > 0 && curT < duration && !splitPoints.includes(curT)) {
                    splitPoints.push(curT);
                    selectedClipIndex = -1; // reset selection
                    updateRuler();
                    renderTrim();
                }
            });
        }

        // Delete segment button click
        const deleteBtn = document.getElementById("tb-delete");
        if (deleteBtn) {
            deleteBtn.addEventListener("click", () => {
                if (selectedClipIndex === -1) return;
                const clips = getClips();
                const clip = clips[selectedClipIndex];
                if (confirm(`Are you sure you want to cut out the selected segment from ${formatTime(clip.start)} to ${formatTime(clip.end)}?`)) {
                    if (startInput) startInput.value = clip.start.toFixed(2);
                    if (endInput) endInput.value = clip.end.toFixed(2);

                    const trimForm = document.getElementById("trim-form");
                    if (trimForm) {
                        // Set trim_mode to delete
                        const deleteRadio = trimForm.querySelector('input[name="trim_mode"][value="delete"]');
                        if (deleteRadio) {
                            deleteRadio.checked = true;
                        }
                        const overlay = document.getElementById("processing-overlay");
                        if (overlay) {
                            overlay.style.display = "flex";
                            const txt = overlay.querySelector("p");
                            if (txt) txt.textContent = "Cutting out selected segment...";
                        }
                        trimForm.submit();
                    }
                }
            });
        }



        // Initialization
        video.addEventListener("loadedmetadata", initTrim);
        if (video.readyState >= 1) {
            initTrim();
        }

        let currentThumbnailAbortController = null;

        function initTrim() {
            duration = video.duration;
            window.duration = duration;
            if (!duration) return;

            // Update video time display
            const timeTotalEl = document.getElementById("video-time-total");
            if (timeTotalEl) {
                timeTotalEl.textContent = formatTime(video.duration);
            }
            const timeCurrentEl = document.getElementById("video-time-current");
            if (timeCurrentEl) {
                timeCurrentEl.textContent = formatTime(video.currentTime);
            }

            startSeconds = startInput && startInput.value ? parseFloat(startInput.value) : 0;
            endSeconds = endInput && endInput.value ? parseFloat(endInput.value) : duration;

            if (startSeconds < 0) startSeconds = 0;
            if (endSeconds > duration || endSeconds <= startSeconds) endSeconds = duration;

            // Automatically set default zoom factor to fit the container width, with a minimum value of 0.001
            const parentWidth = trimTrack.parentElement ? trimTrack.parentElement.clientWidth - 32 : 800;
            if (parentWidth && duration) {
                zoomFactor = Math.max(0.001, parentWidth / (duration * basePxPerSecond));
            }

            // Also allow clicking directly on timeline to move playhead
            const tracksWrapper = document.querySelector(".timeline-tracks-wrapper");
            if (tracksWrapper && !tracksWrapper.dataset.playheadClickBound) {
                tracksWrapper.dataset.playheadClickBound = "true";
                tracksWrapper.addEventListener("click", (e) => {
                    if (e.target.closest(".trim-handle") || e.target.closest(".text-resize-handle") || 
                        e.target.closest(".audio-resize-handle") || e.target.closest(".timeline-clip-block") ||
                        e.target.closest(".timeline-text-block") || e.target.closest(".timeline-audio-block")) {
                        return;
                    }
                    const newTime = getSecondsFromX(e.clientX);
                    video.currentTime = newTime;
                    renderTrim();
                    // Update time display and progress bar immediately
                    const timeCurrentEl = document.getElementById("video-time-current");
                    if (timeCurrentEl) {
                        timeCurrentEl.textContent = formatTime(newTime);
                    }
                    updateVideoProgress();
                });
            }

            updateRuler();
            renderTrim();
            generateThumbnails();
            renderAudioOverlay();
            updateVideoProgress();
        }

        // Dynamic filmstrip thumbnail generator using offscreen video seek
        async function generateThumbnails() {
            if (!duration) return;

            if (currentThumbnailAbortController) {
                currentThumbnailAbortController.abort();
            }
            const abortController = new AbortController();
            currentThumbnailAbortController = abortController;
            const signal = abortController.signal;

            trimThumbnails.innerHTML = "";

            // More thumbnails for fuller filmstrip
            const count = Math.min(50, Math.max(10, Math.floor(duration * 2)));

            const tempVideo = document.createElement("video");
            tempVideo.muted = true;
            tempVideo.playsInline = true;
            tempVideo.preload = "auto";

            tempVideo.addEventListener("loadedmetadata", async () => {
                try {
                    const w = 80;
                    const h = 64;
                    for (let i = 0; i < count; i++) {
                        if (signal.aborted) return;

                        const time = (duration / (count - 1 || 1)) * i;
                        tempVideo.currentTime = time;

                        // Wait for seek with a timeout of 1000ms so it never hangs
                        await Promise.race([
                            new Promise((r) => tempVideo.addEventListener("seeked", r, { once: true })),
                            new Promise((r) => setTimeout(r, 1000))
                        ]);

                        if (signal.aborted) return;

                        const canvas = document.createElement("canvas");
                        canvas.width = w;
                        canvas.height = h;
                        const ctx = canvas.getContext("2d");
                        ctx.drawImage(tempVideo, 0, 0, w, h);
                        trimThumbnails.appendChild(canvas);
                    }
                } catch (err) {
                    console.error("Error generating timeline thumbnails:", err);
                }
            });

            tempVideo.src = video.src;
            tempVideo.load();

            // Split button event listener
            const splitBtn = document.getElementById("tb-split");
            const splitForm = document.getElementById("split-form");
            const splitAtInput = document.getElementById("split-at-input");
            console.log("splitBtn found:", !!splitBtn);
            console.log("splitForm found:", !!splitForm);
            console.log("splitAtInput found:", !!splitAtInput);
            if (splitBtn && splitForm && splitAtInput) {
                splitBtn.addEventListener("click", () => {
                    const currentTime = video.currentTime;
                    console.log("Split button clicked at time:", currentTime);
                    splitAtInput.value = currentTime.toFixed(2);
                    splitForm.submit();
                });
            }
            // ---- Asset Bin Subtab Switching ----
            const subtabs = document.querySelectorAll(".subtab-btn");
            const subpanels = document.querySelectorAll(".subtab-panel");

            subtabs.forEach((tab) => {
                tab.addEventListener("click", () => {
                    const target = tab.dataset.subtab;

                    subtabs.forEach((t) => t.classList.remove("subtab-btn--active"));
                    tab.classList.add("subtab-btn--active");

                    subpanels.forEach((p) => {
                        p.style.display = p.dataset.subpanel === target ? "block" : "none";
                    });
                });
            });

            // ---- AJAX Asset Upload ----
            const triggerUploadBtn = document.getElementById("btn-trigger-upload-asset");
            const assetFileInput = document.getElementById("asset-file-input");

            if (triggerUploadBtn && assetFileInput) {
                triggerUploadBtn.addEventListener("click", () => {
                    assetFileInput.click();
                });

                assetFileInput.addEventListener("change", async (e) => {
                    const files = e.target.files;
                    if (!files || files.length === 0) return;

                    const file = files[0];
                    const formData = new FormData();
                    formData.append("video_file", file);

                    // Show processing overlay
                    const overlay = document.getElementById("processing-overlay");
                    if (overlay) {
                        overlay.style.display = "flex";
                        const txt = overlay.querySelector("p");
                        if (txt) txt.textContent = "Uploading asset clip...";
                    }

                    try {
                        const response = await fetch(window.REEL_UPLOAD_ASSET_URL, {
                            method: "POST",
                            headers: {
                                "X-CSRFToken": window.REEL_CSRF_TOKEN
                            },
                            body: formData
                        });

                        const data = await response.json();
                        if (data.success) {
                            window.location.reload();
                        } else {
                            alert("Upload failed: " + (data.error || "unknown error"));
                            if (overlay) overlay.style.display = "none";
                        }
                    } catch (err) {
                        console.error("Asset upload error:", err);
                        alert("Upload failed due to connection error.");
                        if (overlay) overlay.style.display = "none";
                    }
                });
            }

            // ---- Asset Drag-and-Drop & Click to Insert ----
            const assetCards = document.querySelectorAll(".asset-card");
            const timelineContainer = document.getElementById("visual-trim-container");
            const insertForm = document.getElementById("insert-asset-form");
            const insertAssetIdInput = document.getElementById("insert-asset-id");
            const insertAssetTimestampInput = document.getElementById("insert-asset-timestamp");

            // Click handler for "+" button on cards
            assetCards.forEach((card) => {
                const insertBtn = card.querySelector(".btn-insert-asset");
                if (insertBtn) {
                    insertBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        const assetId = card.dataset.assetId;
                        const currentTime = video ? video.currentTime : 0.0;

                        // Show processing overlay
                        const overlay = document.getElementById("processing-overlay");
                        if (overlay) {
                            overlay.style.display = "flex";
                            const txt = overlay.querySelector("p");
                            if (txt) txt.textContent = "Inserting clip into timeline...";
                        }

                        insertAssetIdInput.value = assetId;
                        insertAssetTimestampInput.value = currentTime;
                        insertForm.submit();
                    });
                }

                // Drag start
                card.addEventListener("dragstart", (e) => {
                    e.dataTransfer.setData("text/plain", card.dataset.assetId);
                    e.dataTransfer.effectAllowed = "copy";

                    // Add visual cue
                    if (timelineContainer) {
                        timelineContainer.classList.add("drag-hover-active");
                    }
                });

                card.addEventListener("dragend", () => {
                    if (timelineContainer) {
                        timelineContainer.classList.remove("drag-hover-active");
                    }
                });
            });

            // Drag-and-Drop on timeline
            if (timelineContainer && insertForm) {
                timelineContainer.addEventListener("dragover", (e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "copy";
                });

                timelineContainer.addEventListener("dragenter", (e) => {
                    e.preventDefault();
                    timelineContainer.style.borderColor = "var(--accent)";
                    timelineContainer.style.background = "rgba(82, 183, 136, 0.04)";
                });

                timelineContainer.addEventListener("dragleave", () => {
                    timelineContainer.style.borderColor = "";
                    timelineContainer.style.background = "";
                });

                timelineContainer.addEventListener("drop", (e) => {
                    e.preventDefault();
                    timelineContainer.style.borderColor = "";
                    timelineContainer.style.background = "";

                    const assetId = e.dataTransfer.getData("text/plain");
                    if (!assetId) return;

                    const currentTime = video ? video.currentTime : 0.0;

                    const overlay = document.getElementById("processing-overlay");
                    if (overlay) {
                        overlay.style.display = "flex";
                        const txt = overlay.querySelector("p");
                        if (txt) txt.textContent = "Inserting clip into timeline...";
                    }

                    insertAssetIdInput.value = assetId;
                    insertAssetTimestampInput.value = currentTime;
                    insertForm.submit();
                });
            }
        }
    }
})();
