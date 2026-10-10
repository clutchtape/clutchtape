"""One-time ownership migration for only Clutchtape data directories."""
import os
from pathlib import Path
for root in map(Path,('/db','/data','/backups')):
    root.mkdir(parents=True,exist_ok=True)
    for base,dirs,files in os.walk(root,followlinks=False):
        for path in [Path(base)]+[Path(base)/n for n in dirs+files]:
            if not path.is_symlink():os.chown(path,10001,10001)
    os.chmod(root,0o700)
print('Clutchtape storage ownership ready.')
