// Reel — small client-side helpers for the editor workbench.
// No build step, no framework: this app is server-rendered and this file
// only adds the interactive touches (tabs, status polling, a couple of
// form conveniences) that don't need a round trip.

(function () {
    "use strict";

    // ---- Tool tab switching (supports both ve- prefixed and legacy classes)
    const tabs = document.querySelectorAll(".tool-tab, .ve-tool-tab");
    const panels = document.querySelectorAll(".tool-section, .ve-tool-section");

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;

            tabs.forEach((t) => {
                t.classList.remove("tool-tab--active");
                t.classList.remove("ve-tool-tab--active");
            });
            tab.classList.add("tool-tab--active");
            tab.classList.add("ve-tool-tab--active");

            panels.forEach((p) => {
                const active = p.dataset.panel === target;
                p.classList.toggle("tool-section--active", active);
                p.classList.toggle("ve-tool-section--active", active);
            });
        });
    });

    // Activate tab from URL query parameter if present
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get("tab");
    if (activeTab) {
        const targetTab = document.querySelector(`.tool-tab[data-tab="${activeTab}"], .ve-tool-tab[data-tab="${activeTab}"]`);
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
                btn.textContent = "Processing\u2026";
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
                    panel.insertBefore(ul, panel.querySelector("form"));
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

            const t = video.currentTime;
            editorState.text_overlays.forEach((overlay) => {
                const start = overlay.start === null ? 0 : overlay.start;
                const end = overlay.end === null ? duration : overlay.end;

                if (t >= start && t <= end) {
                    const el = document.createElement("div");
                    el.className = `preview-text-overlay pos-${overlay.position}`;
                    el.style.color = overlay.color;
                    el.style.fontSize = `${overlay.font_size}px`;
                    el.textContent = overlay.text;
                    container.appendChild(el);
                }
            });
            renderTextTrackTimeline();
        };

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
            textTrackContent.innerHTML = "";

            const pxPerSecond = basePxPerSecond * zoomFactor;
            
            // Sync Audio track wrapper width and draw saved audio blocks
            const audioTrack = document.getElementById("audio-track");
            if (audioTrack) {
                audioTrack.style.width = `${duration * pxPerSecond}px`;
                
                // Clear any previously rendered saved audio blocks
                audioTrack.querySelectorAll(".timeline-audio-block--saved").forEach(el => el.remove());
                
                // Render saved read-only audio blocks
                savedAudioOverlays.forEach((overlay) => {
                    const leftPx = overlay.start * pxPerSecond;
                    const widthPx = (overlay.end - overlay.start) * pxPerSecond;
                    
                    const el = document.createElement("div");
                    el.className = "timeline-audio-block timeline-audio-block--saved";
                    el.style.zIndex = "2";
                    el.style.left = `${leftPx}px`;
                    el.style.width = `${widthPx}px`;
                    el.style.background = "rgba(30, 144, 255, 0.75)";
                    el.style.border = "1.5px dashed #00bfff";
                    el.style.opacity = "0.75";
                    el.style.pointerEvents = "none";
                    el.style.position = "absolute";
                    el.style.height = "100%";
                    el.style.top = "0";
                    el.style.display = "flex";
                    el.style.alignItems = "center";
                    el.style.padding = "0 8px";
                    el.style.boxSizing = "border-box";
                    el.style.borderRadius = "4px";
                    
                    const span = document.createElement("span");
                    span.className = "audio-name";
                    span.style.color = "#93c5fd";
                    span.style.fontSize = "11px";
                    span.style.overflow = "hidden";
                    span.style.textOverflow = "ellipsis";
                    span.style.whiteSpace = "nowrap";
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
                    font_size: 32,
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
            if (isNaN(secs) || secs < 0) return "0:00.00";
            const h = Math.floor(secs / 3600);
            const m = Math.floor((secs % 3600) / 60);
            const s = Math.floor(secs % 60);
            const ms = Math.floor((secs % 1) * 100);
            if (h > 0) {
                return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
            }
            return `${m}:${String(s).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
        }


        function updateRuler() {
            if (!duration) return;
            trimRuler.innerHTML = "";
            
            const pxPerSecond = basePxPerSecond * zoomFactor;
            const parentWidth = trimTrack.parentElement ? trimTrack.parentElement.clientWidth - 32 : 800;
            const totalWidth = Math.max(parentWidth, duration * pxPerSecond);
            trimRuler.style.width = `${totalWidth}px`;
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
                const x = i * pxPerSecond;
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

            // Playhead
            trimPlayhead.style.left = `${playheadPx}px`;
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
            const pxPerSecond = basePxPerSecond * zoomFactor;
            const playheadPx = video.currentTime * pxPerSecond;
            trimPlayhead.style.left = `${playheadPx}px`;
            currentDisplay.textContent = formatTime(video.currentTime);
            const playheadTooltip = document.getElementById("playhead-tooltip");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(video.currentTime);
            }
            
            // Re-render text overlays during playback
            renderTextOverlays();

            // Auto-scroll timeline to keep playhead in view
            const scrollArea = trimContainer.querySelector(".timeline-scroll-area");
            if (scrollArea && !video.paused) {
                const playheadLeft = playheadPx + 96; // 96px is margin-left of playhead
                const viewportWidth = scrollArea.clientWidth;
                const scrollLeft = scrollArea.scrollLeft;
                
                // If playhead is near or past the right edge, or behind the left edge, scroll it into view
                if (playheadLeft > (scrollLeft + viewportWidth - 150)) {
                    scrollArea.scrollLeft = playheadLeft - 150;
                } else if (playheadLeft < scrollLeft + 96) {
                    scrollArea.scrollLeft = playheadLeft - 96;
                }
            }
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

        if (btnPlayPause) {
            btnPlayPause.addEventListener("click", () => {
                if (video.paused) {
                    video.play();
                    btnPlayPause.textContent = "\u23F8"; // ⏸
                } else {
                    video.pause();
                    btnPlayPause.textContent = "\u25B6"; // ▶
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

        const playheadTooltip = document.getElementById("playhead-tooltip");

        // Drag or click on timeline ruler to seek video
        setupDrag(trimRuler, (clientX) => {
            let time = getSecondsFromX(clientX);
            if (time < 0) time = 0;
            if (time > duration) time = duration;
            video.currentTime = time;
            
            trimPlayhead.classList.add("dragging");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(time);
            }
        }, () => {
            trimPlayhead.classList.remove("dragging");
        });

        // Grab and drag the playhead needle/cap directly
        setupDrag(trimPlayhead, (clientX) => {
            let time = getSecondsFromX(clientX);
            if (time < 0) time = 0;
            if (time > duration) time = duration;
            video.currentTime = time;
            
            trimPlayhead.classList.add("dragging");
            if (playheadTooltip) {
                playheadTooltip.textContent = formatTime(time);
            }
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
            el.className = "temp-audio-block";
            el.style.position = "absolute";
            el.style.left = `${leftPx}px`;
            el.style.width = `${widthPx}px`;
            el.style.height = "100%";
            el.style.top = "0";
            el.style.background = "rgba(30, 144, 255, 0.85)";
            el.style.border = "2.5px solid #00bfff";
            el.style.borderRadius = "4px";
            el.style.display = "flex";
            el.style.alignItems = "center";
            el.style.padding = "0 8px";
            el.style.boxSizing = "border-box";
            el.style.zIndex = "3";
            
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
            span.textContent = `🎵 ${audioOverlay.filename}`;
            
            el.appendChild(handleL);
            el.appendChild(span);
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
                const audioTab = document.querySelector('.tool-tab[data-tab="audio"]');
                if (audioTab) {
                    audioTab.click();
                }
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

        // --- Revert/Delete timeline button ---
        const deleteBtn = document.getElementById("tb-delete");
        if (deleteBtn) {
            deleteBtn.addEventListener("click", () => {
                if (confirm("Discard all edits and revert to the original upload?")) {
                    const resetForm = document.getElementById("reset-form");
                    if (resetForm) resetForm.submit();
                }
            });
        }

        // --- Apply split/trim button (Option B: Sequentially set start & end) ---
        let isSettingStart = true;
        const trimBtn = document.getElementById("timeline-trim-btn");
        if (trimBtn) {
            trimBtn.addEventListener("click", () => {
                if (isSettingStart) {
                    startSeconds = parseFloat(video.currentTime.toFixed(2));
                    if (startSeconds >= endSeconds) {
                        endSeconds = duration;
                    }
                    trimBtn.style.color = ""; // reset to CSS default (accent)
                    const btnText = document.getElementById("trim-btn-text");
                    if (btnText) btnText.textContent = "Set End";
                    trimBtn.classList.add("trim-btn--setting-end");
                    isSettingStart = false;
                    renderTrim();
                } else {
                    let endSec = parseFloat(video.currentTime.toFixed(2));
                    if (endSec <= startSeconds) {
                        // If clicked before start, treat as new start point
                        startSeconds = endSec;
                        renderTrim();
                    } else {
                        endSeconds = endSec;
                        isSettingStart = true;
                        const btnText = document.getElementById("trim-btn-text");
                        if (btnText) btnText.textContent = "Split";
                        trimBtn.classList.remove("trim-btn--setting-end");
                        renderTrim();
                        autoSubmitTrim(); // Trigger backend trim instantly
                    }
                }
            });
        }



        // Initialization
        video.addEventListener("loadedmetadata", initTrim);
        if (video.readyState >= 1) {
            initTrim();
        }

        function initTrim() {
            duration = video.duration;
            if (!duration) return;

            startSeconds = startInput && startInput.value ? parseFloat(startInput.value) : 0;
            endSeconds = endInput && endInput.value ? parseFloat(endInput.value) : duration;

            if (startSeconds < 0) startSeconds = 0;
            if (endSeconds > duration || endSeconds <= startSeconds) endSeconds = duration;

            // Automatically set default zoom factor to fit the container width, with a minimum value of 0.001
            const parentWidth = trimTrack.parentElement ? trimTrack.parentElement.clientWidth - 32 : 800;
            if (parentWidth && duration) {
                zoomFactor = Math.max(0.001, parentWidth / (duration * basePxPerSecond));
            }



            updateRuler();
            renderTrim();
            generateThumbnails();
            renderAudioOverlay();
        }

        let currentThumbnailAbortController = null;

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
            
            // Limit count to max 8 thumbnails to prevent browser hang on long videos
            const count = 8;
            
            const tempVideo = document.createElement("video");
            tempVideo.muted = true;
            tempVideo.playsInline = true;
            tempVideo.preload = "auto";

            tempVideo.addEventListener("loadedmetadata", async () => {
                try {
                    const w = 120;
                    const h = 68;
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
        }
    }
})();
