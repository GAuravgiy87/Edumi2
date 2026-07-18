(function () {
    'use strict';

    /* =========================================================
       STATE
    ========================================================= */
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
        selectedClipIds: [],
        undoStack: [],
        redoStack: [],
        clipboard: null,
        snapEnabled: true,
        activeClipId: null
    };

    /* =========================================================
       DOM REFS
    ========================================================= */
    const el = {
        video:            document.getElementById('main-video'),
        playBtn:          document.getElementById('btn-play-pause'),
        playIcon:         document.getElementById('play-icon'),
        pauseIcon:        document.getElementById('pause-icon'),
        timeCurrent:      document.getElementById('time-current'),
        timeTotal:        document.getElementById('time-total'),
        volumeSlider:     document.getElementById('volume-slider'),
        muteBtn:          document.getElementById('btn-mute'),
        volumeIcon:       document.getElementById('volume-icon'),
        muteIcon:         document.getElementById('mute-icon'),
        skipStart:        document.getElementById('btn-skip-start'),
        back5:            document.getElementById('btn-back-5'),
        forward5:         document.getElementById('btn-forward-5'),
        skipEnd:          document.getElementById('btn-skip-end'),
        fullscreenBtn:    document.getElementById('btn-fullscreen'),
        toolTabs:         document.querySelectorAll('.ve-tool-tab'),
        toolSections:     document.querySelectorAll('.ve-tool-section'),
        mediaFileInput:   document.getElementById('media-file-input'),
        dropZone:         document.getElementById('drop-zone'),
        browseBtn:        document.getElementById('btn-browse-media'),
        mediaList:        document.getElementById('media-list'),
        splitBtn:         document.getElementById('btn-split'),
        deleteBtn:        document.getElementById('btn-delete'),
        copyBtn:          document.getElementById('btn-copy'),
        pasteBtn:         document.getElementById('btn-paste'),
        undoBtn:          document.getElementById('tb-undo'),
        redoBtn:          document.getElementById('tb-redo'),
        zoomIn:           document.getElementById('btn-zoom-in'),
        zoomOut:          document.getElementById('btn-zoom-out'),
        zoomFit:          document.getElementById('btn-zoom-fit'),
        zoomSlider:       document.getElementById('zoom-slider'),
        snapBtn:          document.getElementById('btn-snap'),
        exportBtn:        document.getElementById('btn-export'),
        masterExport:     document.getElementById('btn-master-export'),
        tlScroll:         document.getElementById('timeline-scroll'),
        ruler:            document.getElementById('time-ruler'),
        tlTracks:         document.getElementById('timeline-tracks'),
        videoTrack:       document.getElementById('video-track'),
        audioTrack:       document.getElementById('audio-track'),
        textTrack:        document.getElementById('text-track'),
        effectTrack:      document.getElementById('effect-track'),
        playhead:         document.getElementById('playhead'),
        playheadTime:     document.getElementById('playhead-time'),
        snapGuide:        document.getElementById('snap-guide'),
        overlayContainer: document.getElementById('text-overlay-container'),
        // Text modal
        addTextBtn:       document.getElementById('btn-add-text'),
        addTextQuick:     document.getElementById('btn-add-text-quick'),
        textModal:        document.getElementById('text-modal-backdrop'),
        textModalClose:   document.getElementById('text-modal-close'),
        textModalCancel:  document.getElementById('text-modal-cancel'),
        applyTextBtn:     document.getElementById('btn-apply-text'),
        textInput:        document.getElementById('text-input'),
        fontSizeInput:    document.getElementById('font-size-input'),
        textColorInput:   document.getElementById('text-color-input'),
        textPositionSel:  document.getElementById('text-position-select'),
        textBgSel:        document.getElementById('text-bg-select'),
        textStartInput:   document.getElementById('text-start-input'),
        textEndInput:     document.getElementById('text-end-input'),
        textClipList:     document.getElementById('text-clip-list'),
    };

    /* =========================================================
       HELPERS
    ========================================================= */
    function fmt(s) {
        if (isNaN(s) || s < 0) s = 0;
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const sec = Math.floor(s % 60);
        return h > 0
            ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
            : `${m}:${String(sec).padStart(2,'0')}`;
    }

    function pxPerSec() { return state.pxPerSecond * state.zoomFactor; }
    function tlWidth()   { return state.projectDuration * pxPerSec(); }

    function timeToPx(t)  { return t * pxPerSec(); }
    function pxToTime(px) { return px / pxPerSec(); }

    function persistState() {
        try {
            localStorage.setItem(`edumi_ve_${state.projectId}`, JSON.stringify({
                clips: state.clips,
                duration: state.projectDuration
            }));
        } catch(e) {}
    }

    function saveUndo() {
        state.undoStack.push(JSON.parse(JSON.stringify(state.clips)));
        if (state.undoStack.length > 50) state.undoStack.shift();
        state.redoStack = [];
        persistState();
    }

    function undo() {
        if (!state.undoStack.length) return;
        state.redoStack.push(JSON.parse(JSON.stringify(state.clips)));
        state.clips = state.undoStack.pop();
        persistState(); renderClips(); renderTextOverlays(); renderTextClipList();
    }

    function redo() {
        if (!state.redoStack.length) return;
        state.undoStack.push(JSON.parse(JSON.stringify(state.clips)));
        state.clips = state.redoStack.pop();
        persistState(); renderClips(); renderTextOverlays(); renderTextClipList();
    }

    /* =========================================================
       SNAP
    ========================================================= */
    const SNAP_PX = 8; // pixels threshold

    function snapTime(t, excludeId) {
        if (!state.snapEnabled) return t;
        const candidates = [0, state.projectDuration];
        state.clips.forEach(c => {
            if (c.id === excludeId) return;
            candidates.push(c.start, c.end);
        });
        candidates.push(el.video.currentTime);
        let best = t, bestDist = SNAP_PX / pxPerSec();
        candidates.forEach(ct => {
            const d = Math.abs(t - ct);
            if (d < bestDist) { bestDist = d; best = ct; }
        });
        return best;
    }

    function showSnapGuide(px) {
        if (!el.snapGuide) return;
        el.snapGuide.style.left = px + 'px';
        el.snapGuide.classList.add('visible');
    }

    function hideSnapGuide() {
        if (el.snapGuide) el.snapGuide.classList.remove('visible');
    }

    /* =========================================================
       TIMELINE WIDTH / DURATION
    ========================================================= */
    function recalcDuration() {
        let maxEnd = el.video.duration || (window.PROJECT_DURATION || 60);
        state.clips.forEach(c => { if (c.end > maxEnd) maxEnd = c.end; });
        // Add a small buffer
        let nd = Math.max(Math.ceil(maxEnd), maxEnd + 5);
        if (nd !== state.projectDuration) {
            state.projectDuration = nd;
            renderRuler();
        }
        updateTlWidth();
    }

    function updateTlWidth() {
        const w = tlWidth();
        if (el.ruler)    el.ruler.style.width    = w + 'px';
        if (el.tlTracks) el.tlTracks.style.width = w + 'px';
        document.querySelectorAll('.ve-track-content').forEach(t => t.style.width = w + 'px');
    }

    /* =========================================================
       RULER
    ========================================================= */
    function renderRuler() {
        if (!el.ruler) return;
        el.ruler.innerHTML = '';
        const w = tlWidth();
        const dur = state.projectDuration;

        // Pick tick interval based on zoom
        const pps = pxPerSec();
        let majorSec = 30, minorSec = 5;
        if (pps > 80)      { majorSec = 5;  minorSec = 1;  }
        else if (pps > 30) { majorSec = 10; minorSec = 2;  }
        else if (pps > 12) { majorSec = 20; minorSec = 5;  }

        for (let t = 0; t <= dur; t += minorSec) {
            const x = timeToPx(t);
            const isMajor = (t % majorSec === 0);

            const tick = document.createElement('div');
            Object.assign(tick.style, {
                position: 'absolute',
                left: x + 'px',
                bottom: '0',
                width: '1px',
                height: isMajor ? '14px' : '6px',
                background: isMajor ? 'var(--ve-border-strong)' : 'var(--ve-border)'
            });
            el.ruler.appendChild(tick);

            if (isMajor) {
                const lbl = document.createElement('span');
                Object.assign(lbl.style, {
                    position: 'absolute',
                    left: x + 'px',
                    top: '4px',
                    transform: 'translateX(-50%)',
                    fontSize: '10px',
                    fontWeight: '600',
                    color: 'var(--ve-text-muted)',
                    fontFamily: 'ui-monospace,monospace',
                    pointerEvents: 'none',
                    whiteSpace: 'nowrap'
                });
                lbl.textContent = fmt(t);
                el.ruler.appendChild(lbl);
            }
        }
    }

    /* =========================================================
       TIME DISPLAY
    ========================================================= */
    function updateTimeDisplay() {
        const t = state.timelineTime;
        const f = fmt(t);
        if (el.timeCurrent)  el.timeCurrent.textContent  = f;
        if (el.playheadTime) el.playheadTime.textContent = f;
        if (el.timeTotal)    el.timeTotal.textContent    = fmt(state.projectDuration);
        updatePlayhead();
    }

    function updatePlayhead() {
        if (!el.playhead) return;
        const x = timeToPx(state.timelineTime);
        el.playhead.style.left = x + 'px';

        if (state.isPlaying && el.tlScroll) {
            const sl = el.tlScroll.scrollLeft;
            const cw = el.tlScroll.clientWidth;
            if (x > sl + cw * 0.78 || x < sl) {
                el.tlScroll.scrollLeft = Math.max(0, x - cw * 0.2);
            }
        }
    }

    /* =========================================================
       PLAY / PAUSE
    ========================================================= */
    function togglePlay() {
        if (state.isPlaying) {
            state.isPlaying = false;
            setPlayIcons(false);
            el.video.pause();
        } else {
            if (state.timelineTime >= state.projectDuration) {
                state.timelineTime = 0;
            }
            state.isPlaying = true;
            setPlayIcons(true);
            // Kickstart play unconditionally to unlock browser autoplay restrictions
            el.video.play().catch(()=>{});
        }
    }

    function setPlayIcons(playing) {
        state.isPlaying = playing;
        const pIcon = document.getElementById('play-icon');
        const ppIcon = document.getElementById('pause-icon');
        if (pIcon)  pIcon.style.display  = playing ? 'none'  : 'block';
        if (ppIcon) ppIcon.style.display = playing ? 'block' : 'none';
    }

    function updateVolumeIcons() {
        const muted = state.isMuted || state.volume === 0;
        const vIcon = document.getElementById('volume-icon');
        const mIcon = document.getElementById('mute-icon');
        if (vIcon) vIcon.style.display = muted ? 'none'  : 'block';
        if (mIcon) mIcon.style.display = muted ? 'block' : 'none';
    }

    /* =========================================================
       CLIP RENDERING
    ========================================================= */
    function renderClips() {
        recalcDuration();
        [el.videoTrack, el.audioTrack, el.textTrack, el.effectTrack].forEach(t => { if(t) t.innerHTML = ''; });

        state.clips.forEach(clip => {
            const div = document.createElement('div');
            div.className = `ve-clip ve-clip-${clip.type}`;
            div.dataset.id = clip.id;
            div.style.left  = timeToPx(clip.start) + 'px';
            div.style.width = timeToPx(clip.end - clip.start) + 'px';
            if (clip.id === state.selectedClipId) div.classList.add('ve-clip-selected');

            // Handles
            const lh = document.createElement('div');
            lh.className = 've-clip-handle ve-clip-handle-left';
            const rh = document.createElement('div');
            rh.className = 've-clip-handle ve-clip-handle-right';

            // Label
            const lbl = document.createElement('div');
            lbl.className = 've-clip-label';
            lbl.textContent = clip.type === 'effect' ? `Effect: ${clip.effect}` : (clip.name || clip.text || clip.type);

            // For text clips: show the text content as label with "T" badge
            if (clip.type === 'text') {
                const badge = document.createElement('span');
                badge.style.cssText = 'background:rgba(0,0,0,.3);border-radius:3px;padding:0 4px;margin-right:5px;font-size:9px;letter-spacing:.05em;';
                badge.textContent = 'T';
                lbl.prepend(badge);
            }
            // For effect clips: show "FX" badge
            if (clip.type === 'effect') {
                const badge = document.createElement('span');
                badge.style.cssText = 'background:rgba(0,0,0,.3);border-radius:3px;padding:0 4px;margin-right:5px;font-size:9px;letter-spacing:.05em;';
                badge.textContent = 'FX';
                lbl.prepend(badge);
            }

            // Waveform for audio
            if (clip.type === 'audio' && clip.waveform) {
                const cvs = document.createElement('canvas');
                cvs.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;opacity:.6;pointer-events:none;';
                div.appendChild(cvs);
                requestAnimationFrame(() => {
                    const ctx = cvs.getContext('2d');
                    cvs.width  = cvs.offsetWidth;
                    cvs.height = cvs.offsetHeight;
                    ctx.fillStyle = 'rgba(255,255,255,.85)';
                    const bw = cvs.width / clip.waveform.length;
                    const cy = cvs.height / 2;
                    clip.waveform.forEach((v, i) => {
                        const bh = v * cvs.height * .75;
                        ctx.fillRect(i * bw, cy - bh/2, Math.max(1, bw - .5), bh);
                    });
                });
            }

            div.appendChild(lh);
            div.appendChild(rh);
            div.appendChild(lbl);

            div.addEventListener('click', e => { e.stopPropagation(); selectClip(clip.id); });

            const trackEl = clip.type === 'video' ? el.videoTrack
                          : clip.type === 'audio' ? el.audioTrack
                          : clip.type === 'effect' ? el.effectTrack
                          : el.textTrack;
            if (trackEl) trackEl.appendChild(div);

            makeDraggable(div, clip);
            makeResizable(div, clip, lh, rh);
        });
    }

    function selectClip(id) {
        state.selectedClipId = id;
        renderClips();
        const clip = state.clips.find(c => c.id === id);
        if (clip) {
            // Set playhead to clip start
            state.timelineTime = clip.start;
            // If it's a video clip, update the video element
            if (clip.type === 'video' && el.video) {
                if (el.video.src !== clip.src && clip.src) {
                    el.video.src = clip.src;
                }
                el.video.currentTime = clip.sourceStart;
                // Update active clip ID
                state.activeClipId = clip.id;
            }
            updateTimeDisplay();
            updatePlayhead();
        }
        // If text clip, populate modal fields for quick edit
        if (clip && clip.type === 'text') {
            renderTextClipList();
        }
    }

    /* =========================================================
       DRAG & RESIZE
    ========================================================= */
    function makeDraggable(div, clip) {
        let dragging = false, startX, startLeft;

        div.addEventListener('mousedown', e => {
            if (e.target.classList.contains('ve-clip-handle')) return;
            e.stopPropagation();
            dragging = true;
            startX = e.clientX;
            startLeft = parseFloat(div.style.left) || 0;
            div.style.zIndex = '20';
            div.style.cursor = 'grabbing';

            const onMove = e => {
                if (!dragging) return;
                let newLeft = startLeft + (e.clientX - startX);
                if (newLeft < 0) newLeft = 0;
                let ns = snapTime(pxToTime(newLeft), clip.id);
                const snapped = ns !== pxToTime(newLeft);
                if (snapped) showSnapGuide(timeToPx(ns));
                else hideSnapGuide();
                const dur = clip.end - clip.start;
                clip.start = ns;
                clip.end   = ns + dur;
                div.style.left = timeToPx(ns) + 'px';
                recalcDuration();
            };

            const onUp = () => {
                dragging = false;
                div.style.zIndex = '';
                div.style.cursor = 'grab';
                hideSnapGuide();
                saveUndo();
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup',   onUp);
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup',   onUp);
        });
    }

    function makeResizable(div, clip, lh, rh) {
        function startResize(e, side) {
            e.stopPropagation(); e.preventDefault();
            let startX = e.clientX;
            let origLeft  = parseFloat(div.style.left)  || 0;
            let origWidth = parseFloat(div.style.width) || 0;
            let origStart = clip.start, origEnd = clip.end;
            let origSourceStart = clip.sourceStart || 0;
            let origSourceEnd = clip.sourceEnd || (clip.end - clip.start);

            const onMove = e => {
                const dx = e.clientX - startX;
                if (side === 'left') {
                    let nl = origLeft + dx;
                    if (nl < 0) nl = 0;
                    let ns = snapTime(pxToTime(nl), clip.id);
                    
                    // Constrain so we don't extend past the beginning of the video file
                    if (origSourceStart + (ns - origStart) < 0) {
                        ns = origStart - origSourceStart;
                    }
                    if (ns >= clip.end - 0.1) ns = clip.end - 0.1;
                    
                    showSnapGuide(timeToPx(ns));
                    clip.start = ns;
                    clip.sourceStart = origSourceStart + (ns - origStart);
                    
                    div.style.left  = timeToPx(ns) + 'px';
                    div.style.width = timeToPx(clip.end - ns) + 'px';
                } else {
                    let nw = origWidth + dx;
                    let ne = snapTime(pxToTime(origLeft + nw), clip.id);
                    if (ne <= clip.start + 0.1) ne = clip.start + 0.1;
                    
                    showSnapGuide(timeToPx(ne));
                    clip.end = ne;
                    clip.sourceEnd = origSourceEnd + (ne - origEnd);
                    
                    div.style.width = timeToPx(ne - clip.start) + 'px';
                }
                recalcDuration();
            };
            const onUp = () => {
                hideSnapGuide();
                saveUndo();
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup',   onUp);
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup',   onUp);
        }
        lh.addEventListener('mousedown', e => startResize(e, 'left'));
        rh.addEventListener('mousedown', e => startResize(e, 'right'));
    }

    /* =========================================================
       TEXT OVERLAYS (on video canvas)
    ========================================================= */
    function renderTextOverlays() {
        if (!el.overlayContainer) return;
        el.overlayContainer.innerHTML = '';
        const t = state.timelineTime;

        state.clips.filter(c => c.type === 'text' && t >= c.start && t <= c.end).forEach(clip => {
            const ov = document.createElement('div');
            ov.style.cssText = `
                position:absolute;
                color:${clip.color||'#fff'};
                font-size:${clip.fontSize||36}px;
                font-weight:700;
                text-shadow:2px 2px 6px rgba(0,0,0,.8);
                padding:8px 14px;
                cursor:move;
                user-select:none;
                max-width:90%;
                text-align:center;
                z-index:5;
                border-radius:4px;
            `;

            if (clip.bg === 'dark')
                ov.style.background = 'rgba(0,0,0,.55)';
            else if (clip.bg === 'blur')
                ov.style.backdropFilter = 'blur(6px)';

            if (clip.x !== undefined) {
                ov.style.left = clip.x + 'px'; ov.style.top = clip.y + 'px';
            } else {
                switch(clip.position) {
                    case 'top':    ov.style.top='5%';  ov.style.left='50%'; ov.style.transform='translateX(-50%)'; break;
                    case 'center': ov.style.top='50%'; ov.style.left='50%'; ov.style.transform='translate(-50%,-50%)'; break;
                    default:       ov.style.bottom='5%';ov.style.left='50%'; ov.style.transform='translateX(-50%)';
                }
            }

            ov.textContent = clip.text || '';

            // Drag overlay
            let od = false, ox, oy;
            ov.addEventListener('mousedown', e => {
                od = true;
                const r = ov.getBoundingClientRect();
                ox = e.clientX - r.left; oy = e.clientY - r.top;
                ov.style.zIndex = '100';
            });
            document.addEventListener('mousemove', e => {
                if (!od) return;
                const cr = el.overlayContainer.getBoundingClientRect();
                let nx = e.clientX - cr.left - ox;
                let ny = e.clientY - cr.top  - oy;
                nx = Math.max(0, Math.min(nx, cr.width  - ov.offsetWidth));
                ny = Math.max(0, Math.min(ny, cr.height - ov.offsetHeight));
                ov.style.left = nx + 'px'; ov.style.top = ny + 'px';
                ov.style.bottom = 'auto'; ov.style.transform = 'none';
                clip.x = nx; clip.y = ny;
            });
            document.addEventListener('mouseup', () => { od = false; ov.style.zIndex = '5'; });

            el.overlayContainer.appendChild(ov);
        });
    }

    /* =========================================================
       TEXT CLIP LIST (right panel)
    ========================================================= */
    function renderTextClipList() {
        if (!el.textClipList) return;
        el.textClipList.innerHTML = '';
        const textClips = state.clips.filter(c => c.type === 'text');
        if (!textClips.length) {
            el.textClipList.innerHTML = '<p style="font-size:11px;color:var(--ve-text-muted);text-align:center;padding:10px 0;">No text clips yet.</p>';
            return;
        }
        textClips.forEach(clip => {
            const item = document.createElement('div');
            item.className = 've-text-clip-item' + (clip.id === state.selectedClipId ? ' selected' : '');
            item.innerHTML = `
                <div class="ve-text-clip-dot"></div>
                <div class="ve-text-clip-info">
                    <div class="ve-text-clip-name">${clip.text || 'Text'}</div>
                    <div class="ve-text-clip-time">${fmt(clip.start)} – ${fmt(clip.end)}</div>
                </div>
                <button class="ve-text-clip-del" title="Delete" data-id="${clip.id}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                </button>`;
            item.addEventListener('click', e => {
                if (e.target.closest('.ve-text-clip-del')) {
                    const id = e.target.closest('.ve-text-clip-del').dataset.id;
                    saveUndo();
                    state.clips = state.clips.filter(c => c.id !== id);
                    if (state.selectedClipId === id) state.selectedClipId = null;
                    renderClips(); renderTextOverlays(); renderTextClipList();
                } else {
                    selectClip(clip.id);
                    // Jump playhead to clip start
                    state.timelineTime = clip.start;
                    el.video.currentTime = clip.start;
                    updateTimeDisplay();
                }
            });
            el.textClipList.appendChild(item);
        });
    }

    /* =========================================================
       TEXT MODAL
    ========================================================= */
    function openTextModal() {
        if (!el.textModal) return;
        // Pre-fill start/end from current playhead
        const cur = el.video.currentTime || state.timelineTime;
        if (el.textStartInput) el.textStartInput.value = cur.toFixed(1);
        if (el.textEndInput)   el.textEndInput.value   = (cur + 5).toFixed(1);
        if (el.textInput)      el.textInput.value = '';
        el.textModal.classList.add('open');
        if (el.textInput) el.textInput.focus();
    }

    function closeTextModal() {
        if (el.textModal) el.textModal.classList.remove('open');
    }

    function applyText() {
        const text = el.textInput?.value?.trim();
        if (!text) { if (el.textInput) el.textInput.focus(); return; }
        saveUndo();
        const clip = {
            id:       `text-${Date.now()}`,
            type:     'text',
            name:     text,
            text:     text,
            fontSize: parseInt(el.fontSizeInput?.value || 36),
            color:    el.textColorInput?.value || '#ffffff',
            position: el.textPositionSel?.value || 'bottom',
            bg:       el.textBgSel?.value || 'none',
            start:    parseFloat(el.textStartInput?.value || state.timelineTime),
            end:      parseFloat(el.textEndInput?.value   || state.timelineTime + 5)
        };
        state.clips.push(clip);
        selectClip(clip.id);
        renderClips(); renderTextOverlays(); renderTextClipList();
        closeTextModal();
        // Switch right panel to text tab
        document.querySelector('.ve-tool-tab[data-tab="text"]')?.click();
    }

    /* =========================================================
       PLAYHEAD DRAG on ruler / track area
    ========================================================= */
    function initPlayheadDrag() {
        let seeking = false;

        function seek(e) {
            if (!el.tlScroll) return;
            const rect = el.tlScroll.getBoundingClientRect();
            let x = e.clientX - rect.left + el.tlScroll.scrollLeft;
            if (x < 0) x = 0;
            let t = pxToTime(x);
            t = Math.max(0, Math.min(t, state.projectDuration));
            state.timelineTime = t;
            // Sync video
            const vc = state.clips.find(c => c.type === 'video' && t >= c.start && t < c.end);
            if (vc) {
                if (el.video.src !== vc.src && vc.src) {
                    const onMeta = () => {
                        el.video.currentTime = vc.sourceStart + (t - vc.start);
                        el.video.removeEventListener('loadedmetadata', onMeta);
                    };
                    el.video.addEventListener('loadedmetadata', onMeta);
                    el.video.src = vc.src;
                    el.video.load();
                } else {
                    el.video.currentTime = vc.sourceStart + (t - vc.start);
                }
                state.activeClipId = vc.id;
            } else {
                el.video.currentTime = t;
                state.activeClipId = null;
            }
            updateTimeDisplay();
        }

        function applyEffectToVideo(effectName) {
            if (!effectName) {
                el.video.style.filter = 'none';
                return;
            }
            switch (effectName) {
                case 'grayscale':  el.video.style.filter = 'grayscale(100%)'; break;
                case 'sepia':      el.video.style.filter = 'sepia(100%)'; break;
                case 'blur':       el.video.style.filter = 'blur(4px)'; break;
                case 'brightness': el.video.style.filter = 'brightness(130%)'; break;
                case 'contrast':   el.video.style.filter = 'contrast(150%)'; break;
                case 'saturate':   el.video.style.filter = 'saturate(200%)'; break;
                default:           el.video.style.filter = 'none'; break;
            }
        }

        if (el.tlScroll) {
            el.tlScroll.addEventListener('mousedown', e => {
                if (e.target.closest('.ve-clip') && !e.target.closest('.ve-tl-ruler')) return;
                
                // Pause playback if the user starts dragging the playhead
                if (state.isPlaying) {
                    togglePlay();
                }

                seeking = true;
                document.body.style.cursor = 'ew-resize';
                // deselect clip on empty area click
                if (!e.target.closest('.ve-clip')) { state.selectedClipId = null; renderClips(); }
                seek(e);
            });
        }

        document.addEventListener('mousemove', e => { if (seeking) seek(e); });
        document.addEventListener('mouseup',   ()  => {
            seeking = false;
            document.body.style.cursor = '';
        });
    }

    /* =========================================================
       MASTER CLOCK (rAF-based)
    ========================================================= */
    function startMasterClock() {
        let last = performance.now();

        function tick(now) {
            const delta = (now - last) / 1000;
            last = now;

            if (state.isPlaying) {
                const vc = state.clips.find(c => c.type === 'video' && state.timelineTime >= c.start && state.timelineTime < c.end);
                
                let advanceTimeline = true;

                if (vc) {
                    if (state.activeClipId !== vc.id) {
                        advanceTimeline = false;
                        state.activeClipId = vc.id;
                        if (el.video.src !== vc.src && vc.src) {
                            const onMeta = () => {
                                el.video.currentTime = vc.sourceStart + (state.timelineTime - vc.start);
                                el.video.play().catch(()=>{});
                                el.video.removeEventListener('loadedmetadata', onMeta);
                            };
                            el.video.addEventListener('loadedmetadata', onMeta);
                            el.video.src = vc.src;
                            el.video.load();
                        } else {
                            el.video.currentTime = vc.sourceStart + (state.timelineTime - vc.start);
                            el.video.play().catch(()=>{});
                        }
                    } else {
                        const expectedTime = vc.sourceStart + (state.timelineTime - vc.start);
                        
                        if (el.video.readyState >= 3 && !el.video.ended && expectedTime < vc.sourceEnd) {
                            if (!el.video.paused) {
                                let syncedTime = vc.start + (el.video.currentTime - vc.sourceStart);
                                // Prevent browser keyframe snapping from pulling timeline out of clip bounds
                                if (syncedTime < vc.start) syncedTime = vc.start;
                                state.timelineTime = syncedTime;
                                advanceTimeline = false; 
                            } else {
                                el.video.play().catch(()=>{});
                                advanceTimeline = false;
                            }
                        } else if (el.video.ended || expectedTime >= vc.sourceEnd) {
                            if (!el.video.paused) el.video.pause();
                            advanceTimeline = true;
                        } else {
                            advanceTimeline = false;
                            if (el.video.paused) el.video.play().catch(()=>{});
                        }
                    }
                } else {
                    if (state.activeClipId !== null) {
                        el.video.pause();
                        state.activeClipId = null;
                    } else if (!el.video.paused) {
                        el.video.pause();
                    }
                }

                if (advanceTimeline) {
                    state.timelineTime += delta;
                }

                let maxClipEnd = 0;
                state.clips.forEach(c => { if (c.end > maxClipEnd) maxClipEnd = c.end; });

                if (state.timelineTime >= maxClipEnd) {
                    state.timelineTime = maxClipEnd;
                    state.isPlaying = false;
                    setPlayIcons(false);
                    el.video.pause();
                }
            }

            updateTimeDisplay();
            renderTextOverlays();
            syncVideoEffect(state.timelineTime);
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    function syncVideoEffect(t) {
        const ec = state.clips.find(c => c.type === 'effect' && t >= c.start && t < c.end);
        applyEffectToVideo(ec ? ec.effect : null);
    }

    /* =========================================================
       SPLIT / DELETE / COPY / PASTE
    ========================================================= */
    function splitAtPlayhead() {
        const t = state.timelineTime;
        const targets = state.selectedClipId
            ? state.clips.filter(c => c.id === state.selectedClipId && t > c.start && t < c.end)
            : state.clips.filter(c => t > c.start && t < c.end);
        if (!targets.length) return;
        saveUndo();
        targets.forEach((clip, idx) => {
            const ci = state.clips.findIndex(c => c.id === clip.id);
            const right = {
                ...clip,
                id: `${clip.type}-${Date.now()}-${idx}`,
                start: t,
                end: clip.end,
                sourceStart: clip.sourceStart + (t - clip.start),
                sourceEnd: clip.sourceEnd
            };
            clip.end = t;
            state.clips.splice(ci + 1, 0, right);
        });
        state.selectedClipId = null;
        renderClips();
    }

    function deleteSelected() {
        if (!state.selectedClipId) return;
        saveUndo();
        state.clips = state.clips.filter(c => c.id !== state.selectedClipId);
        state.selectedClipId = null;
        renderClips(); renderTextOverlays(); renderTextClipList();
    }

    function copySelected() {
        if (!state.selectedClipId) return;
        const c = state.clips.find(c => c.id === state.selectedClipId);
        if (c) state.clipboard = JSON.parse(JSON.stringify(c));
    }

    function pasteClip() {
        if (!state.clipboard) return;
        saveUndo();
        const nc = JSON.parse(JSON.stringify(state.clipboard));
        nc.id = `${nc.type}-${Date.now()}`;
        const dur = nc.end - nc.start;
        nc.start = state.timelineTime;
        nc.end   = nc.start + dur;
        state.clips.push(nc);
        selectClip(nc.id);
        renderClips(); renderTextOverlays(); renderTextClipList();
    }

    /* =========================================================
       ZOOM
    ========================================================= */
    function setZoom(factor) {
        state.zoomFactor = Math.max(0.1, Math.min(8, factor));
        state.pxPerSecond = state.zoomFactor * 50;
        if (el.zoomSlider) el.zoomSlider.value = Math.round(state.pxPerSecond);
        renderRuler(); renderClips(); updatePlayhead(); updateTlWidth();
    }

    function zoomFit() {
        if (!el.tlScroll) return;
        const vw = el.tlScroll.clientWidth;
        const newPps = vw / state.projectDuration;
        state.pxPerSecond = newPps;
        state.zoomFactor  = newPps / 50;
        if (el.zoomSlider) el.zoomSlider.value = Math.round(newPps);
        renderRuler(); renderClips(); updatePlayhead(); updateTlWidth();
    }

    /* =========================================================
       FILE UPLOAD / MEDIA
    ========================================================= */
    async function generateWaveform(file) {
        return new Promise(resolve => {
            const ac = new (window.AudioContext || window.webkitAudioContext)();
            const fr = new FileReader();
            fr.onload = async e => {
                try {
                    const buf = await ac.decodeAudioData(e.target.result);
                    const raw = buf.getChannelData(0);
                    const n = 200, bs = Math.floor(raw.length / n);
                    const data = Array.from({length:n}, (_,i) => {
                        let s=0; for(let j=0;j<bs;j++) s += Math.abs(raw[i*bs+j]); return s/bs;
                    });
                    const mx = Math.max(...data);
                    resolve(data.map(v => v/mx));
                } catch(e) { resolve(null); }
            };
            fr.readAsArrayBuffer(file);
        });
    }

    function handleFile(file) {
        const item = document.createElement('div');
        item.className = 've-media-item';
        const thumb = document.createElement('div');
        thumb.className = 've-media-thumb';
        const emoji = file.type.startsWith('video/') ? '🎬' : file.type.startsWith('audio/') ? '🎵' : '🖼️';
        thumb.textContent = emoji;
        thumb.style.cssText = 'display:flex;align-items:center;justify-content:center;font-size:18px;';
        const info = document.createElement('div');
        info.className = 've-media-info';
        info.innerHTML = `<p class="ve-media-name">${file.name}</p><p class="ve-media-meta">${(file.size/1024/1024).toFixed(2)} MB</p>`;
        item.appendChild(thumb); item.appendChild(info);
        item.addEventListener('dblclick', () => addToTimeline(file));
        if (el.mediaList) el.mediaList.appendChild(item);
    }

    async function addToTimeline(file) {
        saveUndo();
        const type = file.type.startsWith('audio/') ? 'audio' : 'video';
        const url  = URL.createObjectURL(file);
        const med = document.createElement(type === 'audio' ? 'audio' : 'video');
        med.src = url;
        
        // First get metadata
        const metadata = await new Promise(resolve => {
            med.onloadedmetadata = () => resolve({ duration: med.duration });
            med.onerror = () => resolve({ duration: 10 }); // fallback
        });
        
        const actualDuration = metadata.duration || 10;
        
        let insertTime = state.timelineTime;
        if (type === 'video') {
            const videoClips = state.clips.filter(c => c.type === 'video');
            let maxVidEnd = 0;
            videoClips.forEach(c => { if (c.end > maxVidEnd) maxVidEnd = c.end; });
            insertTime = maxVidEnd;
        }

        const clip = {
            id: `${type}-${Date.now()}`,
            type,
            name: file.name,
            src: url,
            sourceStart: 0,
            sourceEnd: actualDuration,
            start: insertTime,
            end: insertTime + actualDuration
        };
        
        if (type === 'audio') clip.waveform = await generateWaveform(file);
        
        state.clips.push(clip);
        
        // Update project duration if this clip goes longer than current
        if (clip.end > state.projectDuration) {
            state.projectDuration = clip.end;
        }
        
        selectClip(clip.id);
        renderClips();
        renderRuler();
        updateTlWidth();
    }

    /* =========================================================
       EXPORT
    ========================================================= */
    function exportProject() {
        const res  = document.getElementById('export-resolution')?.value || '1080p';
        const qual = document.getElementById('export-quality')?.value    || 'high';
        const fmt2 = document.getElementById('export-format')?.value     || 'mp4';
        const body = {
            tracks: [
                { type:'video',  clips: state.clips.filter(c=>c.type==='video').map(c=>({id:c.id,trimStart:c.sourceStart,trimEnd:c.sourceEnd,start:c.start,end:c.end})) },
                { type:'text',   clips: state.clips.filter(c=>c.type==='text').map(c=>({id:c.id,text:c.text,position:c.position,fontsize:c.fontSize,color:c.color,start:c.start,end:c.end})) },
                { type:'effect', clips: state.clips.filter(c=>c.type==='effect').map(c=>({id:c.id,effect:c.effect,start:c.start,end:c.end})) }
            ],
            exportQuality: qual, exportResolution: res, exportFormat: fmt2
        };
        fetch(`/video-editing/project/${state.projectId}/export-timeline/`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},
            body: JSON.stringify(body)
        }).then(r=>r.json()).then(d=>{
            if (d.status==='processing') { alert('Export started!'); pollExport(); }
            else alert('Export failed: ' + d.error);
        }).catch(()=>alert('Export failed!'));
    }

    function pollExport() {
        const iv = setInterval(()=>{
            fetch(`/video-editing/project/${state.projectId}/status/`).then(r=>r.json()).then(d=>{
                if (d.status==='ready') { clearInterval(iv); alert('Export complete!'); window.location.reload(); }
                else if (d.status==='error') { clearInterval(iv); alert('Export failed: '+d.error_message); }
            });
        }, 2000);
    }

    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(?:^|;)\\s*'+name+'=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : null;
    }

    /* =========================================================
       INIT
    ========================================================= */
    function init() {
        // Load saved state
        try {
            const saved = localStorage.getItem(`edumi_ve_${state.projectId}`);
            if (saved) {
                const p = JSON.parse(saved);
                state.clips = (p.clips||[]).map(c=>({...c, sourceStart:c.sourceStart??c.start, sourceEnd:c.sourceEnd??c.end, src:c.src||(el.video?.src||'')}));
                if (p.duration) state.projectDuration = p.duration;
            }
        } catch(e){}

        if (!state.clips.length) {
            state.clips.push({ id:'video-1', type:'video', name:'Project Video', src:el.video?.src||'', sourceStart:0, sourceEnd:state.projectDuration, start:0, end:state.projectDuration });
            persistState();
        }

        // Video events
        if (el.video) {
            el.video.addEventListener('loadedmetadata', () => {
                const actualDuration = el.video.duration;
                // Only update project/video-1 duration if it's the very first load and we haven't made any edits
                if (!state.isPlaying && !state.activeClipId && actualDuration && !isNaN(actualDuration)) {
                    const initialClip = state.clips.find(c => c.id === 'video-1');
                    // Check if it's still the initial state
                    if (initialClip && state.clips.length === 1 && state.undoStack.length === 0) {
                        state.projectDuration = Math.max(actualDuration, window.PROJECT_DURATION || 0, state.projectDuration || 0);
                        initialClip.sourceEnd = actualDuration;
                        initialClip.end = state.projectDuration;
                        updateTimeDisplay();
                        renderRuler();
                        renderClips();
                        updateTlWidth();
                    }
                }
            });
            el.video.addEventListener('timeupdate', () => {
                if (!state.isPlaying) {
                    state.timelineTime = el.video.currentTime;
                    updateTimeDisplay();
                    renderTextOverlays();
                }
            });
        }

        startMasterClock();
        initPlayheadDrag();

        // Tool tabs
        el.toolTabs.forEach(tab => tab.addEventListener('click', () => {
            el.toolTabs.forEach(t => t.classList.remove('ve-tool-tab--active'));
            tab.classList.add('ve-tool-tab--active');
            const target = tab.dataset.tab;
            el.toolSections.forEach(s => s.classList.toggle('ve-tool-section--active', s.dataset.panel === target));
        }));

        // Player controls
        el.playBtn?.addEventListener('click', togglePlay);
        el.skipStart?.addEventListener('click', () => { 
            el.video.currentTime = 0; 
            state.timelineTime = 0;
            updateTimeDisplay();
        });
        el.back5?.addEventListener('click',    () => { 
            const newTime = Math.max(0, el.video.currentTime - 5); 
            el.video.currentTime = newTime;
            state.timelineTime = newTime;
            updateTimeDisplay();
        });
        el.forward5?.addEventListener('click', () => { 
            const newTime = Math.min(el.video.duration||99999, el.video.currentTime + 5); 
            el.video.currentTime = newTime;
            state.timelineTime = newTime;
            updateTimeDisplay();
        });
        el.skipEnd?.addEventListener('click',  () => { 
            const newTime = el.video.duration||0; 
            el.video.currentTime = newTime;
            state.timelineTime = newTime;
            updateTimeDisplay();
        });

        // Volume
        el.volumeSlider?.addEventListener('input', e => {
            state.volume = parseFloat(e.target.value);
            el.video.volume = state.volume;
            state.isMuted = state.volume === 0;
            updateVolumeIcons();
        });
        el.muteBtn?.addEventListener('click', () => {
            state.isMuted = !state.isMuted;
            el.video.muted = state.isMuted;
            updateVolumeIcons();
        });

        // Fullscreen
        el.fullscreenBtn?.addEventListener('click', () => {
            const st = document.querySelector('.ve-video-stage');
            if (!document.fullscreenElement) st.requestFullscreen?.();
            else document.exitFullscreen?.();
        });

        // Timeline actions
        el.splitBtn?.addEventListener('click',  splitAtPlayhead);
        el.deleteBtn?.addEventListener('click', deleteSelected);
        el.copyBtn?.addEventListener('click',   copySelected);
        el.pasteBtn?.addEventListener('click',  pasteClip);
        el.undoBtn?.addEventListener('click',   undo);
        el.redoBtn?.addEventListener('click',   redo);

        // Text modal
        [el.addTextBtn, el.addTextQuick].forEach(b => b?.addEventListener('click', openTextModal));
        el.textModalClose?.addEventListener('click',  closeTextModal);
        el.textModalCancel?.addEventListener('click', closeTextModal);
        el.textModal?.addEventListener('click', e => { if (e.target === el.textModal) closeTextModal(); });
        el.applyTextBtn?.addEventListener('click', applyText);
        el.textInput?.addEventListener('keydown', e => { if (e.key === 'Enter') applyText(); if (e.key === 'Escape') closeTextModal(); });

        // Snap toggle
        el.snapBtn?.addEventListener('click', () => {
            state.snapEnabled = !state.snapEnabled;
            el.snapBtn.dataset.active = state.snapEnabled ? 'true' : 'false';
        });

        // Zoom
        el.zoomIn?.addEventListener('click',  () => setZoom(state.zoomFactor * 1.25));
        el.zoomOut?.addEventListener('click', () => setZoom(state.zoomFactor / 1.25));
        el.zoomFit?.addEventListener('click', zoomFit);
        el.zoomSlider?.addEventListener('input', e => {
            state.pxPerSecond = parseInt(e.target.value);
            state.zoomFactor  = state.pxPerSecond / 50;
            renderRuler(); renderClips(); updatePlayhead(); updateTlWidth();
        });

        // Export
        el.exportBtn?.addEventListener('click',    exportProject);
        el.masterExport?.addEventListener('click', exportProject);

        // Media upload
        el.browseBtn?.addEventListener('click', () => el.mediaFileInput?.click());
        el.mediaFileInput?.addEventListener('change', e => Array.from(e.target.files).forEach(handleFile));
        if (el.dropZone) {
            el.dropZone.addEventListener('click',     () => el.mediaFileInput?.click());
            el.dropZone.addEventListener('dragover',  e => { e.preventDefault(); el.dropZone.style.borderColor='var(--ve-primary)'; });
            el.dropZone.addEventListener('dragleave', () => el.dropZone.style.borderColor='');
            el.dropZone.addEventListener('drop', e => {
                e.preventDefault(); el.dropZone.style.borderColor='';
                Array.from(e.dataTransfer.files).forEach(handleFile);
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', e => {
            const tag = e.target.tagName;
            if (tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT') return;
            if (e.code==='Space')                                  { e.preventDefault(); togglePlay(); }
            if (e.code==='KeyS' && !e.ctrlKey && !e.metaKey)      splitAtPlayhead();
            if (e.code==='Delete'||e.code==='Backspace')           deleteSelected();
            if (e.code==='KeyT' && !e.ctrlKey && !e.metaKey)      openTextModal();
            if (e.code==='KeyF' && !e.ctrlKey && !e.metaKey)      zoomFit();
            if (e.code==='Equal'||e.code==='NumpadAdd')            setZoom(state.zoomFactor * 1.25);
            if (e.code==='Minus'||e.code==='NumpadSubtract')       setZoom(state.zoomFactor / 1.25);
            if ((e.ctrlKey||e.metaKey)&&e.code==='KeyZ'&&!e.shiftKey) { e.preventDefault(); undo(); }
            if ((e.ctrlKey||e.metaKey)&&(e.code==='KeyY'||(e.shiftKey&&e.code==='KeyZ'))) { e.preventDefault(); redo(); }
            if ((e.ctrlKey||e.metaKey)&&e.code==='KeyC') copySelected();
            if ((e.ctrlKey||e.metaKey)&&e.code==='KeyV') pasteClip();
            if ((e.ctrlKey||e.metaKey)&&e.code==='KeyX') { copySelected(); deleteSelected(); }
            if (e.code==='ArrowLeft')  { e.preventDefault(); el.video.currentTime = Math.max(0, el.video.currentTime - (e.shiftKey ? 1/30 : 1)); }
            if (e.code==='ArrowRight') { e.preventDefault(); el.video.currentTime = Math.min(el.video.duration||99999, el.video.currentTime + (e.shiftKey ? 1/30 : 1)); }
        });

        // Effects
        // Effects
        document.querySelectorAll('.ve-effect-btn').forEach(btn => {
            btn.addEventListener('click', e => {
                const effect = e.target.dataset.effect;
                const t = state.timelineTime;
                const newClip = {
                    id: `effect-${Date.now()}`,
                    type: 'effect',
                    effect: effect,
                    start: t,
                    end: t + 5
                };
                state.clips.push(newClip);
                saveUndo();
                selectClip(newClip.id);
                renderClips();
                
                // Force video filter update if we dropped it at playhead
                const ec = state.clips.find(c => c.type === 'effect' && t >= c.start && t < c.end);
                applyEffectToVideo(ec ? ec.effect : null);
            });
        });

        // Initial render
        renderRuler(); renderClips(); renderTextOverlays(); renderTextClipList();
        updateTimeDisplay();
    }

    // Boot
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

})();
