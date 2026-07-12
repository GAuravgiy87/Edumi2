
# VIDEO EDITING MODULE – COMPLETE FIX & REBUILD

> **Important:** Modify **only** the Video Editing module. Do **not** change authentication, dashboard, routing, database schema (unless absolutely required), application theme, layout, or any unrelated functionality.

## Objective

Rebuild the Video Editing module into a professional editor comparable to CapCut, Clipchamp, VN Editor, Adobe Premiere Rush, or the Windows Photos editor while preserving the existing application UI.

## Core Requirements

- Keep the current application theme and layout unchanged.
- No placeholder code.
- No broken buttons.
- No console/runtime errors.
- Production-ready implementation.
- Smooth playback and editing.

## Professional Timeline

Implement a multi-track timeline with:

- Zoom in/out
- Horizontal scrolling
- Vertical playhead extending through every track
- Time ruler
- Frame ruler
- Frame-accurate editing
- Drag-and-drop clips
- Snap to playhead
- Snap to clip edges
- Auto-scroll during playback
- Smooth scrubbing

### Playhead

- Visible red/current-time indicator spanning every track.
- Drag to seek.
- Click timeline ruler to jump.
- Smooth movement during playback.
- Stops exactly on pause.
- Continues from same frame.
- Auto-scrolls when reaching viewport edge.

### Time Display

Display:

- HH:MM:SS
- HH:MM:SS:FF (frame mode)

Support 24/30/60 FPS.

## Tracks

- Video
- Audio
- Text
- Images
- Stickers

Support unlimited tracks, locking, hiding, reordering, and synchronized playback.

## Video Editing

Support:
- Import multiple videos
- Split
- Trim
- Cut
- Merge
- Duplicate
- Copy/Paste
- Drag
- Replace
- Crop
- Rotate
- Flip
- Resize
- Scale
- Position
- Opacity
- Brightness
- Contrast
- Saturation
- Hue
- Blur
- Filters
- Speed
- Reverse
- Freeze frame
- Fade In/Out
- Volume
- Preview thumbnails

## Text

Unlimited text layers with:
- Fonts
- Size
- Color
- Outline
- Shadow
- Background
- Bold/Italic/Underline
- Alignment
- Letter spacing
- Line spacing
- Opacity
- Rotation
- Resize
- Drag
- Animations
- Timeline duration

## Audio

Support:
- Multiple tracks
- Waveform
- Trim
- Split
- Fade
- Volume
- Mute
- Voice-over
- Detach audio
- Extract audio
- Sync

## Images & Stickers

Support drag, resize, rotate, crop, opacity, animations, duplicate, delete, and timeline duration.

## Playback

- Play
- Pause
- Stop
- Previous/Next frame
- Loop
- Playback speed (0.25x–2x)
- Smooth preview
- No flicker

## Undo / Redo

Support every action.

Shortcuts:
- Ctrl+Z
- Ctrl+Shift+Z
- Ctrl+Y

## Keyboard Shortcuts

- Space: Play/Pause
- Delete: Delete selection
- Ctrl+C / Ctrl+V
- Ctrl+D
- Arrow keys: Frame navigation

## Export

Formats:
- MP4
- WEBM
- MOV (if supported)

Resolution:
- 720p
- 1080p
- 1440p
- 4K

FPS:
- 24
- 30
- 60

Quality:
- Low
- Medium
- High
- Ultra

Include export progress, ETA, and cancellation.

## Performance

Optimize for:
- Large projects
- Multiple tracks
- High-resolution videos
- Low memory usage
- No freezing
- Efficient rendering

## UI

Do not redesign the application.

Maintain the existing theme while making the video editor polished and professional.

## Final Validation Checklist

- Every button works.
- Timeline is frame accurate.
- Playhead is synchronized.
- Playback is smooth.
- Drag/drop works.
- Trim, split, merge work.
- Undo/Redo works.
- Export produces valid playable videos.
- No console errors.
- No runtime errors.
- No changes outside the Video Editing module.
