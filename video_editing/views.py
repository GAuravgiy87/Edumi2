# video_editing/views.py — THIN SHIM
# All logic lives in video_editing/views_logic/ sub-package.
# This file only re-exports so Django's URL resolver and any
# direct `from video_editing.views import X` imports keep working.
#
# Sub-files (video_editing/views_logic/):
#   utils.py            — process_video_edits, trim, mute, rotate, etc.
#   action_views.py     — add_edit_action, remove_edit_action
#   core_views.py       — edit_video, process_edits
#   download_view.py    — download_edited_video

from video_editing.views_logic import (
    edit_video,
    add_edit_action,
    remove_edit_action,
    process_edits,
    download_edited_video,
)
