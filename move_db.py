import shutil
from pathlib import Path

base = Path('.')
db_dir = base / 'database'

# Move db.sqlite3
src_db = base / 'db.sqlite3'
dst_db = db_dir / 'db.sqlite3'

if src_db.exists() and not dst_db.exists():
    print(f"Moving {src_db} to {dst_db}...")
    shutil.move(str(src_db), str(dst_db))
else:
    print(f"db.sqlite3 already moved or not found")

# Move media directory contents
src_media = base / 'media'
dst_media = db_dir / 'media'

if src_media.exists() and src_media.is_dir():
    print(f"Moving media contents from {src_media} to {dst_media}...")
    for item in src_media.iterdir():
        dest_item = dst_media / item.name
        if dest_item.exists():
            print(f"Skipping {item.name} (already exists)")
        else:
            shutil.move(str(item), str(dest_item))
            print(f"Moved {item.name}")
    try:
        src_media.rmdir()
        print("Removed old media directory")
    except OSError:
        print(f"Could not remove old media directory (not empty)")
