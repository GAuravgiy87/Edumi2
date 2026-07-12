(function () {
    'use strict';

    // --- State ---
    let state = {
        projectId: window.PROJECT_ID || 1,
        projectDuration: window.PROJECT_DURATION || 60,
        timelineTime: 0,
        isPlaying: false,
        volume: 1,
        isMuted: false,
        zoomFactor: 1,
        pxPerSecond: 50,
        clips: [],
        selectedClipId: null,
        undoStack: [],
        redoStack: [],
        clipboard: null,
        isTrimming: false
    };

    // --- DOM Elements ---
    const elements = {
        mainVideo: document.getElementById('main-video'),
        playPauseBtn: document.getElementById('btn-play-pause'),
        playPauseBtn: document.getElementById('btn-play-pause'),
        timeCurrent: document.getElementById('time-current'),
        timeTotal: document.getElementById('time-total'),
        timelineTime: document.getElementById('timeline-time'),
        volumeSlider: document.getElementById('volume-slider'),
        muteBtn: document.getElementById('btn-mute'),
        skipStartBtn: document.getElementById('btn-skip-start'),
        back5Btn: document.getElementById('btn-back-5'),
        forward5Btn: document.getElementById('btn-forward-5'),
        skipEndBtn: document.getElementById('btn-skip-end'),
        fullscreenBtn: document.getElementById('btn-fullscreen'),
        toolTabs: document.querySelectorAll('.ve-tool-tab'),
        toolSections: document.querySelectorAll('.ve-tool-section'),
        mediaFileInput: document.getElementById('media-file-input'),
        dropZone: document.getElementById('drop-zone'),
        browseMediaBtn: document.getElementById('btn-browse-media'),
        mediaList: document.getElementById('media-list'),
        splitBtn: document.getElementById('btn-split'),
        deleteBtn: document.getElementById('btn-delete'),
        copyBtn: document.getElementById('btn-copy'),
        pasteBtn: document.getElementById('btn-paste'),
        undoBtn: document.getElementById('tb-undo'),
        redoBtn: document.getElementById('tb-redo'),
        zoomInBtn: document.getElementById('btn-zoom-in'),
        zoomOutBtn: document.getElementById('btn-zoom-out'),
        zoomFitBtn: document.getElementById('btn-zoom-fit'),
        exportBtn: document.getElementById('btn-export'),
        masterExportBtn: document.getElementById('btn-master-export'),
        timelineScroll: document.getElementById('timeline-scroll'),
        timeRuler: document.getElementById('time-ruler'),
        timelineTracks: document.getElementById('timeline-tracks'),
        videoTrack: document.getElementById('video-track'),
        audioTrack: document.getElementById('audio-track'),
        textTrack: document.getElementById('text-track'),
        playhead: document.getElementById('playhead'),
        playheadTooltip: document.getElementById('playhead-tooltip'),
        addTextBtn: document.getElementById('btn-add-text'),
        textProperties: document.getElementById('text-properties'),
        textInput: document.getElementById('text-input'),
        fontSizeInput: document.getElementById('font-size-input'),
        textColorInput: document.getElementById('text-color-input'),
        textPositionSelect: document.getElementById('text-position-select'),
        textStartInput: document.getElementById('text-start-input'),
        textEndInput: document.getElementById('text-end-input'),
        applyTextBtn: document.getElementById('btn-apply-text'),
        textOverlayContainer: document.getElementById('text-overlay-container')
    };

    // --- Helper Functions ---
    function formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) seconds = 0;
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        // Always return H:MM:SS to match the 0:00:00 placeholder in HTML
        return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    function persistState() {
        localStorage.setItem(`edumi_project_${state.projectId}`, JSON.stringify({
            clips: state.clips,
            duration: state.projectDuration
        }));
    }

    // Save state to undo stack
    function saveState() {
        // Deep copy clips to avoid reference issues
        const stateCopy = JSON.parse(JSON.stringify(state.clips));
        state.undoStack.push(stateCopy);
        state.redoStack = []; // Clear redo stack when new action is performed
        persistState();
    }

    // Undo last action
    function undo() {
        if (state.undoStack.length === 0) return;
        
        // Save current state to redo stack
        const currentState = JSON.parse(JSON.stringify(state.clips));
        state.redoStack.push(currentState);
        
        // Restore previous state
        const previousState = state.undoStack.pop();
        state.clips = previousState;
        
        persistState();
        renderClips();
        renderTextOverlays();
    }

    // Redo last undone action
    function redo() {
        if (state.redoStack.length === 0) return;
        
        // Save current state to undo stack
        const currentState = JSON.parse(JSON.stringify(state.clips));
        state.undoStack.push(currentState);
        
        // Restore next state
        const nextState = state.redoStack.pop();
        state.clips = nextState;
        
        persistState();
        renderClips();
        renderTextOverlays();
    }

    function getTimelineWidth() {
        return state.projectDuration * state.pxPerSecond * state.zoomFactor;
    }

    function updateTimeDisplay() {
        elements.timeCurrent.textContent = formatTime(state.timelineTime);
        if (elements.timelineTime) {
            elements.timelineTime.textContent = formatTime(state.timelineTime);
        }
        if (state.projectDuration) {
            elements.timeTotal.textContent = formatTime(state.projectDuration);
        }
        updatePlayheadPosition();
    }

    function updatePlayheadPosition() {
        const timelineWidth = getTimelineWidth();
        const playheadX = (state.timelineTime / state.projectDuration) * timelineWidth;
        elements.playhead.style.left = playheadX + 'px';
        
        // Auto-scroll timeline if playing
        if (state.isPlaying && elements.timelineScroll) {
            const scrollLeft = elements.timelineScroll.scrollLeft;
            const clientWidth = elements.timelineScroll.clientWidth;
            if (playheadX > scrollLeft + clientWidth * 0.8 || playheadX < scrollLeft) {
                elements.timelineScroll.scrollLeft = Math.max(0, playheadX - clientWidth * 0.2);
            }
        }
    }

    function togglePlayPause() {
        const pIcon = document.getElementById('play-icon');
        const mIcon = document.getElementById('pause-icon');
        if (elements.mainVideo.paused) {
            elements.mainVideo.play();
            if (pIcon) pIcon.style.display = 'none';
            if (mIcon) mIcon.style.display = 'block';
            state.isPlaying = true;
        } else {
            elements.mainVideo.pause();
            if (pIcon) pIcon.style.display = 'block';
            if (mIcon) mIcon.style.display = 'none';
            state.isPlaying = false;
        }
    }

    function updateVolumeIcons() {
        const vIcon = document.getElementById('volume-icon');
        const mIcon = document.getElementById('mute-icon');
        if (state.isMuted || state.volume === 0) {
            if (vIcon) vIcon.style.display = 'none';
            if (mIcon) mIcon.style.display = 'block';
        } else {
            if (vIcon) vIcon.style.display = 'block';
            if (mIcon) mIcon.style.display = 'none';
        }
    }

    // --- Timeline Width Update ---
    function recalculateProjectDuration() {
        let maxEnd = 0;
        state.clips.forEach(clip => {
            if (clip.end > maxEnd) maxEnd = clip.end;
        });
        
        let minDuration = 60;
        if (elements.mainVideo && elements.mainVideo.duration) {
            minDuration = elements.mainVideo.duration;
        }
        
        // Expand the timeline in 10-second chunks to avoid continuous DOM recreation during drag
        let targetDuration = Math.max(maxEnd + 15, minDuration);
        let newDuration = Math.ceil(targetDuration / 10) * 10;
        
        if (state.projectDuration !== newDuration) {
            state.projectDuration = newDuration;
            updateTimelineWidth();
            renderTimeRuler();
        }
    }

    function updateTimelineWidth() {
        const timelineWidth = getTimelineWidth();
        elements.timeRuler.style.width = timelineWidth + 'px';
        elements.timelineTracks.style.width = timelineWidth + 'px';
        const trackContents = document.querySelectorAll('.ve-track-content');
        trackContents.forEach(track => {
            track.style.width = timelineWidth + 'px';
        });
    }

    // --- Timeline Rendering ---
    function renderTimeRuler() {
        elements.timeRuler.innerHTML = '';
        const timelineWidth = getTimelineWidth();
        const interval = state.zoomFactor > 2 ? 1 : state.zoomFactor > 0.5 ? 5 : 10;
        
        for (let t = 0; t <= state.projectDuration; t += interval) {
            const x = (t / state.projectDuration) * timelineWidth;
            const tick = document.createElement('div');
            tick.style.position = 'absolute';
            tick.style.left = `${x}px`;
            tick.style.bottom = '0';
            tick.style.width = '1px';
            tick.style.height = '12px';
            tick.style.backgroundColor = 'var(--ve-border)';
            elements.timeRuler.appendChild(tick);

            if (t % 30 === 0 || t === 0) {
                const label = document.createElement('div');
                label.style.position = 'absolute';
                label.style.left = `${x}px`;
                label.style.bottom = '16px';
                label.style.transform = 'translateX(-50%)';
                label.style.fontSize = '11px';
                label.style.color = 'var(--ve-text-muted)';
                label.style.fontFamily = 'JetBrains Mono, monospace';
                label.textContent = formatTime(t);
                elements.timeRuler.appendChild(label);
            }
        }
    }

    function renderClips() {
        recalculateProjectDuration();
        
        elements.videoTrack.innerHTML = '';
        elements.audioTrack.innerHTML = '';
        elements.textTrack.innerHTML = '';

        state.clips.forEach(clip => {
            const clipEl = document.createElement('div');
            clipEl.className = `ve-clip ve-clip-${clip.type}`;
            clipEl.dataset.id = clip.id;
            const timelineWidth = getTimelineWidth();
            clipEl.style.left = `${(clip.start / state.projectDuration) * timelineWidth}px`;
            clipEl.style.width = `${((clip.end - clip.start) / state.projectDuration) * timelineWidth}px`;
            
            if (clip.id === state.selectedClipId) {
                clipEl.classList.add('ve-clip-selected');
            }

            const handleLeft = document.createElement('div');
            handleLeft.className = 've-clip-handle ve-clip-handle-left';
            
            const handleRight = document.createElement('div');
            handleRight.className = 've-clip-handle ve-clip-handle-right';
            
            const label = document.createElement('div');
            label.className = 've-clip-label';
            label.textContent = clip.name;
            
            clipEl.appendChild(handleLeft);
            clipEl.appendChild(handleRight);
            clipEl.appendChild(label);

            // Render waveform for audio clips
            if (clip.type === 'audio' && clip.waveform) {
                const waveformContainer = document.createElement('div');
                waveformContainer.style.position = 'absolute';
                waveformContainer.style.top = '0';
                waveformContainer.style.left = '0';
                waveformContainer.style.right = '0';
                waveformContainer.style.bottom = '0';
                waveformContainer.style.display = 'flex';
                waveformContainer.style.alignItems = 'center';
                waveformContainer.style.justifyContent = 'space-around';
                waveformContainer.style.padding = '4px';
                waveformContainer.style.pointerEvents = 'none';

                const canvas = document.createElement('canvas');
                canvas.style.width = '100%';
                canvas.style.height = '100%';
                const ctx = canvas.getContext('2d');
                
                // Set canvas size to match element size
                const rect = clipEl.getBoundingClientRect();
                canvas.width = rect.width || clipEl.offsetWidth || 100;
                canvas.height = rect.height || clipEl.offsetHeight || 44;

                // Draw waveform
                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                const barWidth = canvas.width / clip.waveform.length;
                const centerY = canvas.height / 2;

                clip.waveform.forEach((value, index) => {
                    const barHeight = value * canvas.height * 0.8;
                    const x = index * barWidth;
                    ctx.fillRect(x, centerY - barHeight/2, Math.max(1, barWidth - 1), barHeight);
                });

                waveformContainer.appendChild(canvas);
                clipEl.appendChild(waveformContainer);
            }
            
            clipEl.addEventListener('click', (e) => {
                e.stopPropagation();
                selectClip(clip.id);
            });
            
            if (clip.type === 'video') {
                elements.videoTrack.appendChild(clipEl);
            } else if (clip.type === 'audio') {
                elements.audioTrack.appendChild(clipEl);
            } else if (clip.type === 'text') {
                elements.textTrack.appendChild(clipEl);
            }
            
            // Make clip draggable
            makeDraggable(clipEl, clip);
            // Make handles resizable
            makeResizable(clipEl, clip, handleLeft, handleRight);
        });
    }

    function selectClip(id) {
        state.selectedClipId = id;
        renderClips();
    }

    // Snap threshold in seconds
    const SNAP_THRESHOLD = 0.1;

    function snapTo(time, currentClip) {
        let snappedTime = time;
        
        // Snap to playhead
        if (Math.abs(time - elements.mainVideo.currentTime) < SNAP_THRESHOLD) {
            snappedTime = elements.mainVideo.currentTime;
        }
        
        // Snap to other clip edges
        state.clips.forEach(otherClip => {
            if (currentClip && otherClip.id === currentClip.id) return;
            
            if (Math.abs(time - otherClip.start) < SNAP_THRESHOLD) {
                snappedTime = otherClip.start;
            }
            if (Math.abs(time - otherClip.end) < SNAP_THRESHOLD) {
                snappedTime = otherClip.end;
            }
        });
        
        return snappedTime;
    }

    function makeDraggable(element, clip) {
        let isDragging = false;
        let startX, startLeft;
        
        element.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('ve-clip-handle')) return;
            
            isDragging = true;
            startX = e.clientX;
            startLeft = parseFloat(element.style.left) || 0;
            
            element.style.cursor = 'grabbing';
            element.style.zIndex = '10';
            
            const onMouseMove = (e) => {
                if (!isDragging) return;
                const deltaX = e.clientX - startX;
                let newLeft = startLeft + deltaX;
                
                const pxPerSec = state.pxPerSecond * state.zoomFactor;
                const clipWidth = parseFloat(element.style.width) || 0;
                
                if (newLeft < 0) newLeft = 0;
                
                // Calculate new start and end times
                let newStart = newLeft / pxPerSec;
                const duration = clip.end - clip.start;
                let newEnd = newStart + duration;
                
                // Snap start time
                newStart = snapTo(newStart, clip);
                newEnd = newStart + duration;
                
                // Snap end time
                newEnd = snapTo(newEnd, clip);
                newStart = newEnd - duration;
                
                // Update left position
                newLeft = newStart * pxPerSec;
                
                element.style.left = `${newLeft}px`;
                
                clip.start = newStart;
                clip.end = newEnd;
                
                recalculateProjectDuration();
            };
            
            const onMouseUp = () => {
                isDragging = false;
                element.style.cursor = 'grab';
                element.style.zIndex = '';
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                
                saveState(); // Save state after drag
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    }

    function makeResizable(element, clip, leftHandle, rightHandle) {
        const timelineWidth = getTimelineWidth();
        
        const resizeLeft = (e) => {
            e.stopPropagation();
            
            let isResizing = true;
            let startX = e.clientX;
            let startLeft = parseFloat(element.style.left) || 0;
            let startWidth = parseFloat(element.style.width) || 0;
            
            const onMouseMove = (e) => {
                if (!isResizing) return;
                const deltaX = e.clientX - startX;
                let newLeft = startLeft + deltaX;
                let newWidth = startWidth - deltaX;
                
                if (newLeft < 0) {
                    newLeft = 0;
                    newWidth = startLeft + startWidth;
                }
                if (newWidth < 20) {
                    newWidth = 20;
                    newLeft = startLeft + startWidth - 20;
                }
                
                const pxPerSec = state.pxPerSecond * state.zoomFactor;
                
                // Snap new start time
                let newStart = newLeft / pxPerSec;
                newStart = snapTo(newStart, clip);
                
                // Ensure we don't trim past the source start
                let timeDiff = newStart - clip.start;
                if (clip.sourceStart + timeDiff < 0) {
                    timeDiff = -clip.sourceStart;
                    newStart = clip.start + timeDiff;
                }
                
                newLeft = newStart * pxPerSec;
                newWidth = (clip.end - newStart) * pxPerSec;
                
                element.style.left = `${newLeft}px`;
                element.style.width = `${newWidth}px`;
                
                clip.sourceStart += timeDiff;
                clip.start = newStart;
                
                state.timelineTime = newStart;
                updateTimeDisplay();
                recalculateProjectDuration();
            };
            
            const onMouseUp = () => {
                isResizing = false;
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                
                saveState(); // Save state after resize
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        };
        
        const resizeRight = (e) => {
            e.stopPropagation();
            
            let isResizing = true;
            let startX = e.clientX;
            let startWidth = parseFloat(element.style.width) || 0;
            
            const onMouseMove = (e) => {
                if (!isResizing) return;
                const deltaX = e.clientX - startX;
                let newWidth = startWidth + deltaX;
                
                const pxPerSec = state.pxPerSecond * state.zoomFactor;
                if (newWidth < 20) newWidth = 20;
                
                // Snap new end time
                let newEnd = clip.start + (newWidth / pxPerSec);
                newEnd = snapTo(newEnd, clip);
                
                let timeDiff = newEnd - clip.end;
                
                newWidth = (newEnd - clip.start) * pxPerSec;
                
                element.style.width = `${newWidth}px`;
                
                clip.sourceEnd += timeDiff;
                clip.end = newEnd;
                
                state.timelineTime = newEnd;
                updateTimeDisplay();
                recalculateProjectDuration();
            };
            
            const onMouseUp = () => {
                isResizing = false;
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                
                saveState(); // Save state after resize
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        };
        
        leftHandle.addEventListener('mousedown', resizeLeft);
        rightHandle.addEventListener('mousedown', resizeRight);
    }

    // --- Text Overlays ---
    function renderTextOverlays() {
        if (!elements.textOverlayContainer) return;
        elements.textOverlayContainer.innerHTML = '';
        
        state.clips.filter(c => c.type === 'text').forEach(clip => {
            if (elements.mainVideo.currentTime >= clip.start && elements.mainVideo.currentTime <= clip.end) {
                const overlay = document.createElement('div');
                overlay.style.position = 'absolute';
                overlay.style.color = clip.color || '#ffffff';
                overlay.style.fontSize = `${clip.fontSize || 32}px`;
                overlay.style.fontWeight = 'bold';
                overlay.style.textShadow = '2px 2px 4px rgba(0, 0, 0, 0.8)';
                overlay.style.padding = '10px';
                overlay.style.cursor = 'move';
                overlay.style.userSelect = 'none';
                overlay.dataset.clipId = clip.id;
                
                // Use custom x/y if available, otherwise use position preset
                if (clip.x !== undefined && clip.y !== undefined) {
                    overlay.style.left = `${clip.x}px`;
                    overlay.style.top = `${clip.y}px`;
                    overlay.style.transform = 'none';
                } else {
                    switch (clip.position) {
                        case 'top':
                            overlay.style.top = '20px';
                            overlay.style.left = '50%';
                            overlay.style.transform = 'translateX(-50%)';
                            break;
                        case 'center':
                            overlay.style.top = '50%';
                            overlay.style.left = '50%';
                            overlay.style.transform = 'translate(-50%, -50%)';
                            break;
                        case 'bottom':
                        default:
                            overlay.style.bottom = '20px';
                            overlay.style.left = '50%';
                            overlay.style.transform = 'translateX(-50%)';
                            break;
                    }
                }
                
                overlay.textContent = clip.text || 'Text';
                
                // Make text draggable
                let isDragging = false;
                let offsetX, offsetY;
                
                overlay.addEventListener('mousedown', (e) => {
                    isDragging = true;
                    const rect = overlay.getBoundingClientRect();
                    offsetX = e.clientX - rect.left;
                    offsetY = e.clientY - rect.top;
                    overlay.style.zIndex = '1000';
                });
                
                document.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    
                    const containerRect = elements.textOverlayContainer.getBoundingClientRect();
                    let newX = e.clientX - containerRect.left - offsetX;
                    let newY = e.clientY - containerRect.top - offsetY;
                    
                    // Constrain to container
                    newX = Math.max(0, Math.min(newX, containerRect.width - overlay.offsetWidth));
                    newY = Math.max(0, Math.min(newY, containerRect.height - overlay.offsetHeight));
                    
                    overlay.style.left = `${newX}px`;
                    overlay.style.top = `${newY}px`;
                    overlay.style.bottom = 'auto';
                    overlay.style.transform = 'none';
                    
                    // Update clip position
                    clip.x = newX;
                    clip.y = newY;
                });
                
                document.addEventListener('mouseup', () => {
                    isDragging = false;
                    overlay.style.zIndex = '';
                });
                
                elements.textOverlayContainer.appendChild(overlay);
            }
        });
    }

    // --- Playhead Drag ---
    function initPlayheadDrag() {
        let isDragging = false;

        const startDrag = (e) => {
            isDragging = true;
            document.body.style.cursor = 'ew-resize';
            handleDrag(e);
        };

        const handleDrag = (e) => {
            if (!isDragging) return;
            const rect = elements.timelineScroll.getBoundingClientRect();
            let clickX = e.clientX - rect.left + elements.timelineScroll.scrollLeft;
            if (clickX < 0) clickX = 0;
            
            const timelineWidth = getTimelineWidth();
            
            let time = clickX / (state.pxPerSecond * state.zoomFactor);
            time = snapTo(time, null); // Snap playhead to clips
            
            state.timelineTime = Math.max(0, time);
            
            // Sync mainVideo
            const activeVideoClip = state.clips.find(c => c.type === 'video' && state.timelineTime >= c.start && state.timelineTime < c.end);
            if (activeVideoClip) {
                state.activeClipId = activeVideoClip.id;
                if (elements.mainVideo.src !== activeVideoClip.src && activeVideoClip.src) {
                    elements.mainVideo.src = activeVideoClip.src;
                }
                elements.mainVideo.currentTime = activeVideoClip.sourceStart + (state.timelineTime - activeVideoClip.start);
            } else {
                state.activeClipId = null;
            }
            
            updatePlayheadPosition();
            updateTimeDisplay();
        };

        const endDrag = () => {
            isDragging = false;
            document.body.style.cursor = '';
        };

        if (elements.timelineScroll) {
            elements.timelineScroll.addEventListener('mousedown', (e) => {
                // Only drag playhead when clicking on ruler/background, not on clips or handles
                const isClip = e.target.closest('.ve-clip');
                const isHandle = e.target.classList.contains('ve-clip-handle');
                if (!isClip && !isHandle) {
                    if (state.selectedClipId) {
                        state.selectedClipId = null;
                        renderClips(); // Deselect on empty click
                    }
                    startDrag(e);
                }
            });
        }

        document.addEventListener('mousemove', handleDrag);
        document.addEventListener('mouseup', endDrag);
    }

    // --- Initialization ---
    function init() {
        // Load from local storage
        const savedData = localStorage.getItem(`edumi_project_${state.projectId}`);
        if (savedData) {
            try {
                const parsed = JSON.parse(savedData);
                state.clips = (parsed.clips || []).map(c => ({
                    ...c,
                    sourceStart: c.sourceStart !== undefined ? c.sourceStart : c.start,
                    sourceEnd: c.sourceEnd !== undefined ? c.sourceEnd : c.end,
                    src: c.src || (elements.mainVideo ? elements.mainVideo.src : '')
                }));
                if (parsed.duration) {
                    state.projectDuration = parsed.duration;
                }
            } catch(e) {
                console.error("Failed to load saved project state", e);
            }
        }
        
        if (state.clips.length === 0) {
            // Add initial video clip
            state.clips.push({
                id: 'video-1',
                type: 'video',
                name: 'Project Video',
                src: elements.mainVideo ? elements.mainVideo.src : '',
                sourceStart: 0,
                sourceEnd: state.projectDuration,
                start: 0,
                end: state.projectDuration
            });
            persistState();
        }
        
        // Initialize UI
        if (elements.mainVideo) {
            elements.mainVideo.addEventListener('loadedmetadata', () => {
                if (!window.PROJECT_DURATION) {
                    state.projectDuration = elements.mainVideo.duration;
                }
                updateTimeDisplay();
                renderTimeRuler();
                renderClips();
                updateTimelineWidth();
            });
            // Replaced timeupdate with requestAnimationFrame Master Clock
            let lastUpdate = performance.now();
            function masterClock(now) {
                if (state.isPlaying && !state.isTrimming) {
                    const delta = (now - lastUpdate) / 1000.0;
                    
                    // Sync timelineTime to mainVideo if playing normally, otherwise increment
                    if (state.activeClipId && elements.mainVideo.readyState >= 2 && !elements.mainVideo.paused) {
                        const clip = state.clips.find(c => c.id === state.activeClipId);
                        if (clip) {
                            state.timelineTime = clip.start + (elements.mainVideo.currentTime - clip.sourceStart);
                        }
                    } else {
                        state.timelineTime += delta; // Move forward in gaps
                    }
                    
                    if (state.timelineTime >= state.projectDuration) {
                        state.timelineTime = 0;
                    }
                    
                    // Gap-Skipping and Clip Transition Logic
                    const activeVideoClip = state.clips.find(c => c.type === 'video' && state.timelineTime >= c.start && state.timelineTime < c.end);
                    if (!activeVideoClip) {
                        // We are in a gap. Find the next video clip.
                        const nextClip = state.clips
                            .filter(c => c.type === 'video' && c.start > state.timelineTime)
                            .sort((a, b) => a.start - b.start)[0];
                        
                        if (nextClip) {
                            state.activeClipId = nextClip.id;
                            state.timelineTime = nextClip.start;
                            if (elements.mainVideo.src !== nextClip.src && nextClip.src) {
                                elements.mainVideo.src = nextClip.src;
                            }
                            elements.mainVideo.currentTime = nextClip.sourceStart;
                            elements.mainVideo.play().catch(e => console.log("Play interrupted", e));
                        } else {
                            // No more video clips after this point. Keep timeline running for other tracks until it loops.
                            elements.mainVideo.pause();
                        }
                    } else if (state.activeClipId !== activeVideoClip.id) {
                        // Transitioned into a different clip
                        state.activeClipId = activeVideoClip.id;
                        if (elements.mainVideo.src !== activeVideoClip.src && activeVideoClip.src) {
                            elements.mainVideo.src = activeVideoClip.src;
                        }
                        elements.mainVideo.currentTime = activeVideoClip.sourceStart + (state.timelineTime - activeVideoClip.start);
                        elements.mainVideo.play().catch(e => console.log("Play interrupted", e));
                    }
                }
                
                updateTimeDisplay();
                renderTextOverlays();
                
                lastUpdate = now;
                requestAnimationFrame(masterClock);
            }
            requestAnimationFrame(masterClock);
            
            elements.mainVideo.addEventListener('play', () => {
                const pIcon = document.getElementById('play-icon');
                const mIcon = document.getElementById('pause-icon');
                if (pIcon) pIcon.style.display = 'none';
                if (mIcon) mIcon.style.display = 'block';
                state.isPlaying = true;
            });
            
            elements.mainVideo.addEventListener('pause', () => {
                const pIcon = document.getElementById('play-icon');
                const mIcon = document.getElementById('pause-icon');
                if (pIcon) pIcon.style.display = 'block';
                if (mIcon) mIcon.style.display = 'none';
                state.isPlaying = false;
            });
        }
        
        // Ensure initial correct duration if video is already loaded
        if (elements.mainVideo && elements.mainVideo.readyState >= 1) {
            if (!window.PROJECT_DURATION) {
                state.projectDuration = elements.mainVideo.duration;
            }
        }
        
        initPlayheadDrag();
        
        // Tool tabs
        elements.toolTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                elements.toolTabs.forEach(t => t.classList.remove('ve-tool-tab--active'));
                tab.classList.add('ve-tool-tab--active');
                
                const target = tab.dataset.tab;
                elements.toolSections.forEach(section => {
                    section.classList.toggle('ve-tool-section--active', section.dataset.panel === target);
                });
            });
        });
        
        // Play/pause button
        if (elements.playPauseBtn) {
            elements.playPauseBtn.addEventListener('click', togglePlayPause);
        }
        
        // Skip buttons
        if (elements.skipStartBtn) {
            elements.skipStartBtn.addEventListener('click', () => {
                elements.mainVideo.currentTime = 0;
            });
        }
        
        if (elements.back5Btn) {
            elements.back5Btn.addEventListener('click', () => {
                const newTime = elements.mainVideo.currentTime - 5;
                elements.mainVideo.currentTime = Math.max(0, newTime);
            });
        }
        
        if (elements.forward5Btn) {
            elements.forward5Btn.addEventListener('click', () => {
                const duration = elements.mainVideo.duration || state.projectDuration || 60;
                const newTime = elements.mainVideo.currentTime + 5;
                elements.mainVideo.currentTime = Math.min(duration, newTime);
            });
        }
        
        if (elements.skipEndBtn) {
            elements.skipEndBtn.addEventListener('click', () => {
                const duration = elements.mainVideo.duration || state.projectDuration || 60;
                elements.mainVideo.currentTime = duration;
            });
        }
        
        // Volume controls
        if (elements.volumeSlider) {
            elements.volumeSlider.addEventListener('input', (e) => {
                state.volume = parseFloat(e.target.value);
                elements.mainVideo.volume = state.volume;
                if (state.volume === 0) {
                    state.isMuted = true;
                } else {
                    state.isMuted = false;
                }
                updateVolumeIcons();
            });
        }
        
        if (elements.muteBtn) {
            elements.muteBtn.addEventListener('click', () => {
                state.isMuted = !state.isMuted;
                elements.mainVideo.muted = state.isMuted;
                updateVolumeIcons();
            });
        }
        
        // Add text button
        if (elements.addTextBtn) {
            elements.addTextBtn.addEventListener('click', () => {
                elements.textProperties.style.display = 'block';
                
                if (elements.textStartInput) {
                    elements.textStartInput.value = elements.mainVideo.currentTime.toFixed(2);
                }
                if (elements.textEndInput) {
                    elements.textEndInput.value = (elements.mainVideo.currentTime + 5).toFixed(2);
                }
            });
        }
        
        // Apply text button
        if (elements.applyTextBtn) {
            elements.applyTextBtn.addEventListener('click', () => {
                saveState(); // Save state before adding text
                
                const newClip = {
                    id: `text-${Date.now()}`,
                    type: 'text',
                    name: elements.textInput?.value || 'Text',
                    text: elements.textInput?.value || 'Text',
                    fontSize: parseInt(elements.fontSizeInput?.value || 32),
                    color: elements.textColorInput?.value || '#ffffff',
                    position: elements.textPositionSelect?.value || 'bottom',
                    start: parseFloat(elements.textStartInput?.value || elements.mainVideo.currentTime),
                    end: parseFloat(elements.textEndInput?.value || elements.mainVideo.currentTime + 5)
                };
                state.clips.push(newClip);
                selectClip(newClip.id);
                renderClips();
                renderTextOverlays();
                elements.textProperties.style.display = 'none';
            });
        }
        
        // Zoom buttons
        if (elements.zoomInBtn) {
            elements.zoomInBtn.addEventListener('click', () => {
                state.zoomFactor = Math.min(5, state.zoomFactor * 1.2);
                renderTimeRuler();
                renderClips();
                updatePlayheadPosition();
                updateTimelineWidth();
            });
        }
        
        if (elements.zoomOutBtn) {
            elements.zoomOutBtn.addEventListener('click', () => {
                state.zoomFactor = Math.max(0.2, state.zoomFactor / 1.2);
                renderTimeRuler();
                renderClips();
                updatePlayheadPosition();
                updateTimelineWidth();
            });
        }
        
        if (elements.zoomFitBtn) {
            elements.zoomFitBtn.addEventListener('click', () => {
                state.zoomFactor = 1;
                renderTimeRuler();
                renderClips();
                updatePlayheadPosition();
                updateTimelineWidth();
            });
        }
        
        // Undo button
        if (elements.undoBtn) {
            elements.undoBtn.addEventListener('click', undo);
        }
        
        // Redo button
        if (elements.redoBtn) {
            elements.redoBtn.addEventListener('click', redo);
        }
        
        // Split button
        if (elements.splitBtn) {
            elements.splitBtn.addEventListener('click', () => {
                const currentTime = elements.mainVideo.currentTime;
                
                let clipsToSplit = [];
                if (state.selectedClipId) {
                    const selectedClip = state.clips.find(c => c.id === state.selectedClipId);
                    if (selectedClip && currentTime > selectedClip.start && currentTime < selectedClip.end) {
                        clipsToSplit.push(selectedClip);
                    }
                }
                
                // If no valid selected clip, split all clips under the playhead
                if (clipsToSplit.length === 0) {
                    clipsToSplit = state.clips.filter(c => currentTime > c.start && currentTime < c.end);
                }
                
                if (clipsToSplit.length === 0) return;
                
                saveState(); // Save state before split
                
                clipsToSplit.forEach((clip, idx) => {
                    const clipIndex = state.clips.findIndex(c => c.id === clip.id);
                    if (clipIndex === -1) return;
                    
                    const newClip = {
                        ...clip,
                        id: `${clip.type}-${Date.now()}-${idx}`,
                        start: currentTime,
                        sourceStart: clip.sourceStart + (currentTime - clip.start)
                    };
                    
                    clip.end = currentTime;
                    clip.sourceEnd = clip.sourceStart + (currentTime - clip.start);
                    
                    state.clips.splice(clipIndex + 1, 0, newClip);
                    if (clipsToSplit.length === 1) {
                        state.selectedClipId = newClip.id;
                    }
                });
                
                if (clipsToSplit.length > 1) {
                    state.selectedClipId = null;
                }
                renderClips();
            });
        }
        
        // Delete button
        if (elements.deleteBtn) {
            elements.deleteBtn.addEventListener('click', () => {
                if (!state.selectedClipId) return;
                
                saveState(); // Save state before delete
                
                state.clips = state.clips.filter(c => c.id !== state.selectedClipId);
                state.selectedClipId = null;
                renderClips();
                renderTextOverlays();
            });
        }

        // Cut, Copy, Paste
        if (elements.copyBtn) {
            elements.copyBtn.addEventListener('click', () => {
                if (!state.selectedClipId) return;
                const clip = state.clips.find(c => c.id === state.selectedClipId);
                if (clip) state.clipboard = JSON.parse(JSON.stringify(clip));
            });
        }
        

        
        if (elements.pasteBtn) {
            elements.pasteBtn.addEventListener('click', () => {
                if (!state.clipboard) return;
                saveState();
                const newClip = JSON.parse(JSON.stringify(state.clipboard));
                newClip.id = `${newClip.type}-${Date.now()}`;
                
                // Place at playhead
                const duration = newClip.end - newClip.start;
                newClip.start = elements.mainVideo.currentTime;
                newClip.end = newClip.start + duration;
                
                state.clips.push(newClip);
                selectClip(newClip.id);
                renderClips();
                renderTextOverlays();
            });
        }
        
        // Fullscreen button
        if (elements.fullscreenBtn) {
            elements.fullscreenBtn.addEventListener('click', () => {
                const stage = document.querySelector('.ve-video-stage');
                if (!document.fullscreenElement) {
                    if (stage.requestFullscreen) {
                        stage.requestFullscreen();
                    } else if (stage.webkitRequestFullscreen) {
                        stage.webkitRequestFullscreen();
                    } else if (stage.msRequestFullscreen) {
                        stage.msRequestFullscreen();
                    }
                } else {
                    if (document.exitFullscreen) {
                        document.exitFullscreen();
                    } else if (document.webkitExitFullscreen) {
                        document.webkitExitFullscreen();
                    } else if (document.msExitFullscreen) {
                        document.msExitFullscreen();
                    }
                }
            });
        }
        
        // Global Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in an input or textarea
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            if (e.code === 'Space') {
                e.preventDefault();
                togglePlayPause();
            } else if (e.code === 'Delete' || e.code === 'Backspace') {
                if (elements.deleteBtn) elements.deleteBtn.click();
            } else if (e.code === 'KeyS' && !e.ctrlKey && !e.metaKey) {
                if (elements.splitBtn) elements.splitBtn.click();
            } else if (e.code === 'KeyZ' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                undo();
            } else if (e.code === 'KeyY' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                redo();
            } else if (e.code === 'KeyC' && (e.ctrlKey || e.metaKey)) {
                if (elements.copyBtn) elements.copyBtn.click();
            } else if (e.code === 'KeyX' && (e.ctrlKey || e.metaKey)) {
                if (state.selectedClipId) {
                    const clip = state.clips.find(c => c.id === state.selectedClipId);
                    if (clip) {
                        state.clipboard = JSON.parse(JSON.stringify(clip));
                        saveState();
                        state.clips = state.clips.filter(c => c.id !== state.selectedClipId);
                        state.selectedClipId = null;
                        renderClips();
                        renderTextOverlays();
                    }
                }
            } else if (e.code === 'KeyV' && (e.ctrlKey || e.metaKey)) {
                if (elements.pasteBtn) elements.pasteBtn.click();
            } else if (e.code === 'ArrowLeft') {
                e.preventDefault();
                const newTime = elements.mainVideo.currentTime - 1;
                elements.mainVideo.currentTime = Math.max(0, newTime);
            } else if (e.code === 'ArrowRight') {
                e.preventDefault();
                const duration = elements.mainVideo.duration || state.projectDuration || 60;
                const newTime = elements.mainVideo.currentTime + 1;
                elements.mainVideo.currentTime = Math.min(duration, newTime);
            }
        });

        // Add dummy media elements to list
        if (elements.mediaList) {
            elements.exportBtn.addEventListener('click', exportProject);
        }
        if (elements.masterExportBtn) {
            elements.masterExportBtn.addEventListener('click', exportProject);
        }
        
        // File input
        if (elements.browseMediaBtn && elements.mediaFileInput) {
            elements.browseMediaBtn.addEventListener('click', () => {
                elements.mediaFileInput.click();
            });
            
            elements.mediaFileInput.addEventListener('change', (e) => {
                Array.from(e.target.files).forEach(file => handleFileUpload(file));
            });
        }
        
        // Drag and drop
        if (elements.dropZone) {
            elements.dropZone.addEventListener('click', () => {
                if (elements.mediaFileInput) elements.mediaFileInput.click();
            });
            
            elements.dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                elements.dropZone.style.borderColor = 'var(--ve-primary)';
                elements.dropZone.style.backgroundColor = 'rgba(99, 102, 241, 0.1)';
            });
            
            elements.dropZone.addEventListener('dragleave', () => {
                elements.dropZone.style.borderColor = 'var(--ve-border)';
                elements.dropZone.style.backgroundColor = 'transparent';
            });
            
            elements.dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                elements.dropZone.style.borderColor = 'var(--ve-border)';
                elements.dropZone.style.backgroundColor = 'transparent';
                
                Array.from(e.dataTransfer.files).forEach(file => handleFileUpload(file));
            });
        }
        
        // Keydown events
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

            if (e.code === 'Space') {
                e.preventDefault();
                togglePlayPause();
            }
            
            if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                undo();
            }
            
            if ((e.ctrlKey && e.shiftKey && e.key === 'z') || (e.ctrlKey && e.key === 'y')) {
                e.preventDefault();
                redo();
            }
            
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (state.selectedClipId) {
                    e.preventDefault();
                    if (elements.deleteBtn) elements.deleteBtn.click();
                }
            }
            
            if (e.key === 's') {
                if (elements.splitBtn) elements.splitBtn.click();
            }
            
            // Frame / 5s navigation
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                if (e.shiftKey) {
                    // Frame by frame
                    elements.mainVideo.currentTime = Math.max(0, elements.mainVideo.currentTime - 1/30);
                } else {
                    // Back 5s
                    elements.mainVideo.currentTime = Math.max(0, elements.mainVideo.currentTime - 5);
                }
            }
            
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                const duration = elements.mainVideo.duration || state.projectDuration || 60;
                if (e.shiftKey) {
                    elements.mainVideo.currentTime = Math.min(duration, elements.mainVideo.currentTime + 1/30);
                } else {
                    elements.mainVideo.currentTime = Math.min(duration, elements.mainVideo.currentTime + 5);
                }
            }
        });
        
        // Timeline click to seek
        if (elements.timelineScroll) {
            elements.timelineScroll.addEventListener('click', (e) => {
                const rect = elements.timelineScroll.getBoundingClientRect();
                const clickX = e.clientX - rect.left - 150;
                if (clickX < 0) return;
                
                const time = (clickX / getTimelineWidth()) * state.projectDuration;
                elements.mainVideo.currentTime = Math.max(0, Math.min(state.projectDuration, time));
            });
        }
        
        // Initial render
        renderTimeRuler();
        renderClips();
        renderTextOverlays();
    }
    
    function updateVolumeIcons() {
        const vIcon = document.getElementById('volume-icon');
        const mIcon = document.getElementById('mute-icon');
        if (vIcon && mIcon) {
            if (state.isMuted || state.volume === 0) {
                vIcon.style.display = 'none';
                mIcon.style.display = 'block';
            } else {
                vIcon.style.display = 'block';
                mIcon.style.display = 'none';
            }
        }
    }
    
    // Generate waveform data from audio file
    async function generateWaveform(file) {
        return new Promise((resolve) => {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const reader = new FileReader();
            
            reader.onload = async (e) => {
                const arrayBuffer = e.target.result;
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                
                // Get audio data
                const rawData = audioBuffer.getChannelData(0); // Use first channel
                const samples = 200; // Number of waveform points
                const blockSize = Math.floor(rawData.length / samples);
                const waveformData = [];
                
                for (let i = 0; i < samples; i++) {
                    let sum = 0;
                    for (let j = 0; j < blockSize; j++) {
                        sum += Math.abs(rawData[i * blockSize + j]);
                    }
                    waveformData.push(sum / blockSize);
                }
                
                // Normalize
                const max = Math.max(...waveformData);
                const normalized = waveformData.map(v => v / max);
                
                resolve(normalized);
            };
            
            reader.readAsArrayBuffer(file);
        });
    }

    function handleFileUpload(file) {
        const mediaItem = document.createElement('div');
        mediaItem.className = 've-media-item';
        
        const thumb = document.createElement('div');
        thumb.className = 've-media-thumb';
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                thumb.style.backgroundImage = `url(${e.target.result})`;
                thumb.style.backgroundSize = 'cover';
                thumb.style.backgroundPosition = 'center';
            };
            reader.readAsDataURL(file);
        } else if (file.type.startsWith('video/')) {
            thumb.style.backgroundColor = 'var(--ve-primary)';
            const icon = document.createElement('div');
            icon.innerHTML = '🎬';
            icon.style.fontSize = '20px';
            icon.style.display = 'flex';
            icon.style.alignItems = 'center';
            icon.style.justifyContent = 'center';
            icon.style.height = '100%';
            thumb.appendChild(icon);
        } else if (file.type.startsWith('audio/')) {
            thumb.style.backgroundColor = 'var(--ve-success)';
            const icon = document.createElement('div');
            icon.innerHTML = '🎵';
            icon.style.fontSize = '20px';
            icon.style.display = 'flex';
            icon.style.alignItems = 'center';
            icon.style.justifyContent = 'center';
            icon.style.height = '100%';
            thumb.appendChild(icon);
        }
        
        const info = document.createElement('div');
        info.className = 've-media-info';
        
        const name = document.createElement('p');
        name.className = 've-media-name';
        name.textContent = file.name;
        
        const meta = document.createElement('p');
        meta.className = 've-media-meta';
        meta.textContent = (file.size / 1024 / 1024).toFixed(2) + ' MB';
        
        info.appendChild(name);
        info.appendChild(meta);
        
        mediaItem.appendChild(thumb);
        mediaItem.appendChild(info);
        
        mediaItem.addEventListener('dblclick', () => {
            addMediaToTimeline(file);
        });
        
        if (elements.mediaList) {
            elements.mediaList.appendChild(mediaItem);
        }
    }
    
    async function addMediaToTimeline(file) {
        saveState(); // Save state before adding media
        
        let type = 'video';
        if (file.type.startsWith('audio/')) type = 'audio';
        if (file.type.startsWith('image/')) type = 'text';
        
        const url = URL.createObjectURL(file);
        
        const newClip = {
            id: `${type}-${Date.now()}`,
            type: type,
            name: file.name,
            file: file, // Store the file for waveform generation
            src: url,
            sourceStart: 0,
            sourceEnd: 10,
            start: state.timelineTime,
            end: state.timelineTime + 10
        };
        
        if (type === 'video' || type === 'audio') {
            const media = document.createElement(type);
            media.src = url;
            await new Promise(resolve => {
                media.onloadedmetadata = () => {
                    newClip.sourceEnd = media.duration;
                    newClip.end = state.timelineTime + media.duration;
                    resolve();
                };
                media.onerror = resolve;
            });
        }
        
        // Generate waveform for audio files
        if (type === 'audio') {
            newClip.waveform = await generateWaveform(file);
        }
        
        state.clips.push(newClip);
        selectClip(newClip.id);
        renderClips();
    }

    // Export functionality
    function exportProject() {
        const exportResolution = document.getElementById('export-resolution')?.value || '1080p';
        const exportQuality = document.getElementById('export-quality')?.value || 'high';
        const exportFormat = document.getElementById('export-format')?.value || 'mp4';

        // Prepare timeline data for backend
        const timelineData = {
            tracks: [
                {
                    type: 'video',
                    clips: state.clips.filter(c => c.type === 'video').map(c => ({
                        id: c.id,
                        trimStart: c.sourceStart !== undefined ? c.sourceStart : c.start,
                        trimEnd: c.sourceEnd !== undefined ? c.sourceEnd : c.end,
                        start: c.start,
                        end: c.end
                    }))
                },
                {
                    type: 'text',
                    clips: state.clips.filter(c => c.type === 'text').map(c => ({
                        id: c.id,
                        text: c.text,
                        position: c.position,
                        fontsize: c.fontSize,
                        color: c.color,
                        start: c.start,
                        end: c.end
                    }))
                }
            ],
            exportQuality: exportQuality,
            exportResolution: exportResolution,
            exportFormat: exportFormat
        };

        // Send to backend
        fetch(`/video-editing/project/${state.projectId}/export-timeline/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(timelineData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'processing') {
                alert('Export started! Please wait...');
                // Poll for status
                pollExportStatus();
            } else {
                alert('Export failed: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error exporting:', error);
            alert('Export failed!');
        });
    }

    function pollExportStatus() {
        const interval = setInterval(() => {
            fetch(`/video-editing/project/${state.projectId}/status/`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'ready') {
                        clearInterval(interval);
                        alert('Export complete!');
                        window.location.reload();
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        alert('Export failed: ' + data.error_message);
                    }
                });
        }, 2000);
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Start the app
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
