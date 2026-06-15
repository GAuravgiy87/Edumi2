# ✂️ Video Editing Module

<details open>
<summary><b>1. Core Purpose</b></summary>
The `video_editing` app provides an in-platform, non-destructive timeline editor for recorded and uploaded videos. It acts as an interface layer over system-level FFmpeg commands.
</details>

<details>
<summary><b>2. Rationale & Architecture</b></summary>
Built to allow educators to trim "dead air" from class recordings or overlay text/audio without needing external tools like Premiere Pro. It uses an "Action Log" architecture (non-destructive) where edits are saved as a series of instructions and only compiled when explicitly requested.
</details>

<details>
<summary><b>3. Usage Instructions</b></summary>

- **Editing**: From a video's detail page, a user selects "Edit". They can add multiple actions (Trim, Mute, Rotate, Text Overlay, Add Audio).
- **Previewing**: The UI provides a client-side representation of the actions.
- **Processing**: When the user hits "Save & Process", the backend executes the accumulated actions against the source video.
</details>

<details>
<summary><b>4. System Integrations</b></summary>
- **External Dependencies**: Relies heavily on the system's `ffmpeg` binary.
- **Videos App**: Pulls source files from the `videos` app and saves newly rendered copies back into it.
</details>

<details>
<summary><b>5. Key Files Breakdown</b></summary>

- `models.py`: Defines `VideoEditSession` (the current workspace) and `VideoEditAction` (individual steps like 'trim' or 'add_text').
- `views_logic/utils.py`: The core engine. It parses `VideoEditAction` records and constructs the exact `subprocess.run(['ffmpeg', ...])` arrays required to execute the edits.
- `views_logic/action_views.py`: API endpoints for the frontend to add, reorder, or delete actions in the current session.
</details>