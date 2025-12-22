from pathlib import Path
from curator.curate import run_curation
from curator.write import write_by_artist

BASE = Path("data")

inbox = BASE / "inbox.txt"
log = BASE / "curated.log"
artists_dir = BASE / "artists"

album_links = run_curation(inbox, log)

write_by_artist(album_links, artists_dir)

print(f"Written {len(album_links)} album links.")
