#!/usr/bin/env python3
import shutil
from pathlib import Path

# Get base directory
base = Path('.').resolve()
db_dir = base / 'database'

# ============================================
# Step 1: Create organized subdirectories
# ============================================
subdirs = [
    'db/sqlite',     # Main SQLite database
    'media/face_photos',    # Face recognition photos
    'media/videos',         # Uploaded videos
    'media/recordings',     # Camera recordings
    'media/temp',           # Temporary files
    'media/audio',          # Audio files
    'media/documents',      # Documents
    'backups',              # Database backups
    'logs',                 # Application logs
    'cache',                # Cache files
]

for subdir in subdirs:
    full_path = db_dir / subdir
    full_path.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Created directory: {subdir}")

# ============================================
# Step 2: Move db.sqlite3 files into db/sqlite/
# ============================================
print("\nMoving database files...")

# Move the database file from database/ into database/db/sqlite/
current_db = db_dir / 'db.sqlite3'
target_db = db_dir / 'db/sqlite/db.sqlite3'
if current_db.exists() and current_db.is_file():
    if target_db.exists():
        print(f"  Target {target_db} already exists - skipping")
    else:
        shutil.move(str(current_db), str(target_db))
        print(f"[OK] Moved db.sqlite3 to db/sqlite/")
else:
    print(f"  No db.sqlite3 found at {current_db}")

# Also check root directory for db.sqlite3
root_db = base / 'db.sqlite3'
if root_db.exists() and root_db.is_file():
    try:
        shutil.move(str(root_db), str(target_db))
        print(f"[OK] Moved root db.sqlite3 to db/sqlite/")
    except Exception as e:
        print(f"  Note: Could not move root db.sqlite3 (may be in use) - {e}")

# ============================================
# Step 3: Reorganize media files properly
# ============================================
print("\nOrganizing media files...")

# Fix the media/media nesting issue
old_media_root = db_dir / 'media/media'
if old_media_root.exists() and old_media_root.is_dir():
    print(f"  Found nested media at {old_media_root} - fixing...")
    for item in old_media_root.iterdir():
        dest = db_dir / 'media' / item.name
        if dest.exists():
            if dest.is_dir():
                # Merge directories
                for subitem in item.iterdir():
                    subdest = dest / subitem.name
                    if not subdest.exists():
                        shutil.move(str(subitem), str(subdest))
            else:
                print(f"  Skipping {item.name} (already exists)")
        else:
            shutil.move(str(item), str(dest))
    
    # Try to remove empty old_media_root
    try:
        old_media_root.rmdir()
        print("[OK] Fixed media nesting issue")
    except:
        pass

print("\n[DONE] Database organization complete!")
print("\nFinal Structure:")
print(str(db_dir))
for subdir in sorted(subdirs):
    print(f"  |- {subdir}")
