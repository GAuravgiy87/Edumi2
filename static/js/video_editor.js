// Video Editor Timeline SPA Logic
let videoProject = {
    duration: window.PROJECT_DURATION || 0,
    projectId: window.PROJECT_ID || 0,
    originalSrc: window.PROJECT_SRC || '',
    timeline: {
        tracks: [
            { id: 'track_1', name: 'Track 1', type: 'generic', clips: [] }
        ]
    }
};

let historyStack = [];
let historyIndex = -1;

const videoEl = document.getElementById('main-video');
const timelineUI = document.getElementById('timeline-tracks');
let timelineWidth = 0; 
let currentlyPlayingSrc = null;

function saveState() {
    historyStack = historyStack.slice(0, historyIndex + 1);
    historyStack.push(JSON.parse(JSON.stringify(videoProject.timeline)));
    historyIndex++;
    renderTimeline();
}

function undo() {
    if (historyIndex > 0) {
        historyIndex--;
        videoProject.timeline = JSON.parse(JSON.stringify(historyStack[historyIndex]));
        renderTimeline();
    }
}

function redo() {
    if (historyIndex < historyStack.length - 1) {
        historyIndex++;
        videoProject.timeline = JSON.parse(JSON.stringify(historyStack[historyIndex]));
        renderTimeline();
    }
}

function togglePlay() {
    const btn = document.getElementById('btn-play-pause');
    if (videoEl.paused) {
        videoEl.play();
        btn.innerHTML = '&#10074;&#10074;';
    } else {
        videoEl.pause();
        btn.innerHTML = '&#9654;';
    }
}

function initEditor() {
    initFabric();
    
    if (videoProject.timeline.tracks[0].clips.length === 0 && videoProject.duration > 0) {
        videoProject.timeline.tracks[0].clips.push({
            id: 'clip_' + Date.now(),
            type: 'video',
            start: 0,
            end: videoProject.duration,
            trimStart: 0,
            trimEnd: videoProject.duration,
            src: videoProject.originalSrc,
            text: 'Original Video'
        });
    }
    saveState();
    
    document.getElementById('tb-undo').addEventListener('click', undo);
    document.getElementById('tb-redo').addEventListener('click', redo);
    document.getElementById('btn-split').addEventListener('click', splitClip);
    document.getElementById('btn-add-text').addEventListener('click', addText);
    
    const playPauseBtn = document.getElementById('btn-play-pause');
    if (playPauseBtn) playPauseBtn.addEventListener('click', togglePlay);
    
    const exportBtn = document.getElementById('btn-master-export');
    if(exportBtn) exportBtn.addEventListener('click', exportTimeline);
    
    const uploadBtn = document.getElementById('btn-upload-asset');
    if (uploadBtn) uploadBtn.addEventListener('click', uploadAsset);
    
    // Scrubbing Logic
    if (timelineUI) {
        timelineUI.addEventListener('mousedown', (e) => {
            if (e.target.closest('.ve-clip-wrapper')) return; 
            const rect = timelineUI.getBoundingClientRect();
            const updateTime = (mx) => {
                const percent = Math.max(0, Math.min(1, (mx - rect.left) / rect.width));
                if (videoProject.duration > 0) {
                    const targetTime = percent * videoProject.duration;
                    scrubToTime(targetTime);
                }
            };
            updateTime(e.clientX);
            const scrubMove = (ev) => updateTime(ev.clientX);
            const scrubEnd = () => {
                window.removeEventListener('mousemove', scrubMove);
                window.removeEventListener('mouseup', scrubEnd);
            };
            window.addEventListener('mousemove', scrubMove);
            window.addEventListener('mouseup', scrubEnd);
        });
    }
    
    videoEl.addEventListener('play', () => {
        if (playPauseBtn) playPauseBtn.innerHTML = '&#10074;&#10074;';
        startSyncLoop();
    });
    videoEl.addEventListener('pause', () => {
        if (playPauseBtn) playPauseBtn.innerHTML = '&#9654;';
        stopSyncLoop();
    });
}

// Sequential Preview Engine
let globalTime = 0; 
let syncLoopId = null;

function startSyncLoop() {
    if (syncLoopId) cancelAnimationFrame(syncLoopId);
    let lastTime = performance.now();
    function loop(now) {
        const dt = (now - lastTime) / 1000;
        lastTime = now;
        globalTime += dt;
        if (globalTime > videoProject.duration) {
            globalTime = videoProject.duration;
            videoEl.pause();
        }
        updatePlayhead();
        syncLoopId = requestAnimationFrame(loop);
    }
    loop(performance.now());
}

function stopSyncLoop() {
    if (syncLoopId) cancelAnimationFrame(syncLoopId);
}

function scrubToTime(time) {
    globalTime = time;
    updatePlayhead();
}

function updatePlayhead() {
    const percent = videoProject.duration > 0 ? (globalTime / videoProject.duration) * 100 : 0;
    const playhead = document.getElementById('playhead');
    if (playhead) playhead.style.left = `${percent}%`;
    
    updateTextOverlays(globalTime);
    
    // Find which video clip should be playing right now based on globalTime
    let activeClip = null;
    for (let track of videoProject.timeline.tracks) {
        for (let clip of track.clips) {
            if (clip.type === 'video' && globalTime >= clip.start && globalTime <= clip.end) {
                activeClip = clip;
                break;
            }
        }
        if (activeClip) break;
    }
    
    if (activeClip) {
        // Calculate the relative time inside the clip
        const clipProgress = globalTime - activeClip.start;
        const internalTime = activeClip.trimStart + clipProgress;
        
        if (currentlyPlayingSrc !== activeClip.src) {
            videoEl.src = activeClip.src;
            currentlyPlayingSrc = activeClip.src;
            videoEl.currentTime = internalTime;
            if (!videoEl.paused) videoEl.play();
        } else {
            // Keep it synced if it drifted too much
            if (Math.abs(videoEl.currentTime - internalTime) > 0.5) {
                videoEl.currentTime = internalTime;
            }
        }
        videoEl.style.display = 'block';
    } else {
        videoEl.style.display = 'none';
    }
}

// DRAGGABLE CLIP & TRIM LOGIC
function attachClipDragEvents(clipEl, clip, trackIndex) {
    const center = clipEl.querySelector('.ve-clip-content');
    const handleL = clipEl.querySelector('.ve-clip-handle.left');
    const handleR = clipEl.querySelector('.ve-clip-handle.right');
    
    // Drag entire clip
    center.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        timelineWidth = timelineUI.getBoundingClientRect().width;
        if (timelineWidth === 0 || videoProject.duration === 0) return;

        const startX = e.clientX;
        const initialStart = clip.start;
        const initialEnd = clip.end;
        const clipDuration = initialEnd - initialStart;
        
        const onMouseMove = (ev) => {
            const dx = ev.clientX - startX;
            const dt = (dx / timelineWidth) * videoProject.duration;
            let newStart = initialStart + dt;
            let newEnd = newStart + clipDuration;
            
            if (newStart < 0) { newStart = 0; newEnd = clipDuration; }
            if (newEnd > videoProject.duration) { newEnd = videoProject.duration; newStart = newEnd - clipDuration; }
            
            const left = (newStart / videoProject.duration) * 100;
            clipEl.style.left = `${left}%`;
            
            clipEl.dataset.tempStart = newStart;
            clipEl.dataset.tempEnd = newEnd;
            clipEl.dataset.tempAction = 'move';
        };
        
        const onMouseUp = () => {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
            if (clipEl.dataset.tempAction === 'move') {
                clip.start = parseFloat(clipEl.dataset.tempStart);
                clip.end = parseFloat(clipEl.dataset.tempEnd);
                delete clipEl.dataset.tempAction;
                saveState();
            }
        };
        
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    });
    
    // Trim handles
    const setupTrim = (handle, side) => {
        if (!handle) return;
        handle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            timelineWidth = timelineUI.getBoundingClientRect().width;
            if (timelineWidth === 0 || videoProject.duration === 0) return;

            const startX = e.clientX;
            const initialStart = clip.start;
            const initialEnd = clip.end;
            const initialTrimStart = clip.trimStart || 0;
            const initialTrimEnd = clip.trimEnd || (initialEnd - initialStart);
            
            const onMouseMove = (ev) => {
                const dx = ev.clientX - startX;
                const dt = (dx / timelineWidth) * videoProject.duration;
                
                if (side === 'left') {
                    let newStart = initialStart + dt;
                    if (newStart >= initialEnd) newStart = initialEnd - 0.5;
                    if (newStart < 0) newStart = 0;
                    const diff = newStart - initialStart;
                    
                    const left = (newStart / videoProject.duration) * 100;
                    const width = ((initialEnd - newStart) / videoProject.duration) * 100;
                    
                    clipEl.style.left = `${left}%`;
                    clipEl.style.width = `${width}%`;
                    
                    clipEl.dataset.tempStart = newStart;
                    clipEl.dataset.tempTrimStart = initialTrimStart + diff;
                } else {
                    let newEnd = initialEnd + dt;
                    if (newEnd <= initialStart) newEnd = initialStart + 0.5;
                    if (newEnd > videoProject.duration) newEnd = videoProject.duration;
                    const diff = newEnd - initialEnd;
                    
                    const width = ((newEnd - initialStart) / videoProject.duration) * 100;
                    clipEl.style.width = `${width}%`;
                    
                    clipEl.dataset.tempEnd = newEnd;
                    clipEl.dataset.tempTrimEnd = initialTrimEnd + diff;
                }
                clipEl.dataset.tempAction = 'trim';
            };
            
            const onMouseUp = () => {
                window.removeEventListener('mousemove', onMouseMove);
                window.removeEventListener('mouseup', onMouseUp);
                if (clipEl.dataset.tempAction === 'trim') {
                    if (side === 'left') {
                        clip.start = parseFloat(clipEl.dataset.tempStart);
                        clip.trimStart = parseFloat(clipEl.dataset.tempTrimStart);
                    } else {
                        clip.end = parseFloat(clipEl.dataset.tempEnd);
                        clip.trimEnd = parseFloat(clipEl.dataset.tempTrimEnd);
                    }
                    delete clipEl.dataset.tempAction;
                    saveState();
                }
            };
            
            window.addEventListener('mousemove', onMouseMove);
            window.addEventListener('mouseup', onMouseUp);
        });
    };
    
    setupTrim(handleL, 'left');
    setupTrim(handleR, 'right');
}

function renderTimeline() {
    if (!timelineUI) return;
    timelineUI.innerHTML = '';
    
    // Add Ruler
    const ruler = document.createElement('div');
    ruler.className = 'trim-ruler';
    for (let i = 0; i <= videoProject.duration; i += Math.max(1, Math.floor(videoProject.duration/10))) {
        const tick = document.createElement('div');
        tick.className = 'trim-tick major';
        tick.style.left = `${(i / videoProject.duration) * 100}%`;
        
        const label = document.createElement('div');
        label.className = 'trim-tick-label';
        label.innerText = `0:${i.toString().padStart(2, '0')}`;
        tick.appendChild(label);
        ruler.appendChild(tick);
    }
    timelineUI.appendChild(ruler);
    
    videoProject.timeline.tracks.forEach((track, trackIndex) => {
        const trackEl = document.createElement('div');
        trackEl.className = `timeline-track-row`;
        
        const labelEl = document.createElement('div');
        labelEl.className = 'track-label-cell';
        labelEl.innerHTML = `<span>${track.name}</span>`;
        trackEl.appendChild(labelEl);
        
        const contentEl = document.createElement('div');
        contentEl.className = 'track-content-cell';
        
        track.clips.forEach(clip => {
            const clipEl = document.createElement('div');
            clipEl.className = 've-clip-wrapper';
            
            const width = videoProject.duration > 0 ? ((clip.end - clip.start) / videoProject.duration) * 100 : 0;
            const left = videoProject.duration > 0 ? (clip.start / videoProject.duration) * 100 : 0;
            clipEl.style.width = `${width}%`;
            clipEl.style.left = `${left}%`;
            
            clipEl.innerHTML = `
                <div class="ve-clip-handle left"></div>
                <div class="ve-clip-content">
                    <div class="ve-clip-thumbnails"></div>
                    <span style="position:relative; z-index:2;">${clip.text || 'Clip'}</span>
                </div>
                <div class="ve-clip-handle right"></div>
            `;
            
            // Generate Thumbnails for video tracks
            if (clip.type === 'video' && clip.src) {
                const thumbContainer = clipEl.querySelector('.ve-clip-thumbnails');
                const clipDuration = clip.end - clip.start;
                const numThumbs = Math.max(1, Math.min(10, Math.floor(clipDuration / 2)));
                
                for (let i = 0; i < numThumbs; i++) {
                    const thumb = document.createElement('div');
                    thumb.className = 've-clip-thumb';
                    const timePoint = clip.trimStart + (i * (clip.trimEnd - clip.trimStart) / numThumbs);
                    thumb.style.backgroundImage = `url('${clip.src}#t=${timePoint}')`;
                    thumbContainer.appendChild(thumb);
                }
            }
            
            // Text coloring
            if (clip.type === 'text') {
                clipEl.querySelector('.ve-clip-content').style.background = '#F59E0B';
            }
            
            attachClipDragEvents(clipEl, clip, trackIndex);
            contentEl.appendChild(clipEl);
        });
        
        trackEl.appendChild(contentEl);
        timelineUI.appendChild(trackEl);
    });
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function splitClip() {
    const time = globalTime;
    for (let track of videoProject.timeline.tracks) {
        const clipIndex = track.clips.findIndex(c => time > c.start && time < c.end);
        if (clipIndex !== -1) {
            const clip = track.clips[clipIndex];
            const newClip = JSON.parse(JSON.stringify(clip));
            
            clip.end = time;
            clip.trimEnd = clip.trimStart + (time - clip.start);
            
            newClip.id = 'clip_' + Date.now();
            newClip.start = time;
            newClip.trimStart = clip.trimEnd;
            
            track.clips.splice(clipIndex + 1, 0, newClip);
            saveState();
            return; // only split one clip at a time
        }
    }
}

function addText() {
    // Add text to the highest track, or create a new one
    let targetTrack = videoProject.timeline.tracks[videoProject.timeline.tracks.length - 1];
    if (targetTrack.clips.length > 0) {
        videoProject.timeline.tracks.push({
            id: 'track_' + Date.now(),
            name: `Track ${videoProject.timeline.tracks.length + 1}`,
            type: 'generic',
            clips: []
        });
        targetTrack = videoProject.timeline.tracks[videoProject.timeline.tracks.length - 1];
    }
    
    targetTrack.clips.push({
        id: 'text_' + Date.now(),
        type: 'text',
        text: 'New Text',
        start: globalTime,
        end: Math.min(globalTime + 5, videoProject.duration),
        x: 100,
        y: 100,
        fontsize: 48,
        color: 'white'
    });
    saveState();
}

function uploadAsset() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'audio/*,video/*';
    fileInput.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('asset_file', file);
        formData.append('asset_type', file.type.startsWith('video') ? 'video' : 'audio');
        
        fetch(`/video-editing/project/${videoProject.projectId}/upload-asset/`, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                const currentDuration = videoProject.duration;
                const newDuration = currentDuration + (data.duration || 10);
                videoProject.duration = newDuration;
                
                // Append video to Track 1
                videoProject.timeline.tracks[0].clips.push({
                    id: 'asset_' + Date.now(),
                    type: 'video',
                    asset_id: data.asset_id,
                    src: data.url,
                    start: currentDuration, 
                    end: newDuration,
                    trimStart: 0,
                    trimEnd: data.duration || 10,
                    text: file.name
                });
                
                saveState();
            } else {
                alert("Upload failed");
            }
        });
    };
    fileInput.click();
}

let fCanvas = null;

function initFabric() {
    fCanvas = new fabric.Canvas('fabric-canvas', {
        width: document.getElementById('video-stage').clientWidth,
        height: document.getElementById('video-stage').clientHeight
    });
    
    fCanvas.on('object:modified', function(e) {
        if (e.target && e.target.clipId) {
            for (let track of videoProject.timeline.tracks) {
                const clip = track.clips.find(c => c.id === e.target.clipId);
                if (clip) {
                    clip.x = e.target.left;
                    clip.y = e.target.top;
                    clip.fontsize = e.target.fontSize * e.target.scaleX;
                    saveState();
                    return;
                }
            }
        }
    });
}

function updateTextOverlays(time) {
    if (!fCanvas) return;
    fCanvas.clear();
    
    videoProject.timeline.tracks.forEach(track => {
        track.clips.forEach(clip => {
            if (clip.type === 'text' && time >= clip.start && time <= clip.end) {
                const textObj = new fabric.IText(clip.text, {
                    left: clip.x,
                    top: clip.y,
                    fontSize: clip.fontsize || 48,
                    fill: clip.color || 'white',
                    fontFamily: 'Arial',
                    stroke: 'black',
                    strokeWidth: 1,
                    editable: true
                });
                textObj.clipId = clip.id;
                fCanvas.add(textObj);
            }
        });
    });
    fCanvas.renderAll();
}

function exportTimeline() {
    const exportBtn = document.getElementById('btn-master-export');
    const qualitySelect = document.getElementById('export-quality');
    exportBtn.innerText = 'Processing...';
    exportBtn.disabled = true;
    
    if (qualitySelect) {
        videoProject.timeline.exportQuality = qualitySelect.value;
    }

    fetch(`/video-editing/project/${videoProject.projectId}/export-timeline/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(videoProject.timeline)
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'processing' || data.status === 'success') {
            const interval = setInterval(() => {
                fetch(`/video-editing/project/${videoProject.projectId}/status/`)
                .then(r => r.json())
                .then(statusData => {
                    if (statusData.status === 'ready') {
                        clearInterval(interval);
                        window.location.reload();
                    } else if (statusData.status === 'error') {
                        clearInterval(interval);
                        alert('Export failed: ' + statusData.error_message);
                        exportBtn.innerText = 'Export Timeline';
                        exportBtn.disabled = false;
                    }
                });
            }, 2000);
        } else {
            alert('Export failed: ' + data.error);
            exportBtn.innerText = 'Export Timeline';
            exportBtn.disabled = false;
        }
    });
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

window.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('timeline-tracks')) {
        initEditor();
    }
});
