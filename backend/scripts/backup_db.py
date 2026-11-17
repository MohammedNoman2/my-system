import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.backup_service import create_database_backup


if __name__ == "__main__":
    result = create_database_backup()
    print(json.dumps(result, ensure_ascii=False, indent=2))
