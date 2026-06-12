# PythonAnywhere Data Fix

Live issue:

- `https://npgchub.pythonanywhere.com/` opens.
- Home page shows `0` local content pages, `0` blocks, `0` tables.
- Category URLs like `/admissions/` return 404.

Meaning:

The Django app is deployed, but PythonAnywhere cannot read the generated JSON data folder:

```text
knowledge/data/
```

This folder must contain:

```text
knowledge/data/catalog.json
knowledge/data/about/*.json
knowledge/data/admissions/*.json
knowledge/data/academics/*.json
...
```

Expected local count:

```text
229 JSON files
```

That means:

- `1` catalog file
- `228` page JSON files

## Check On PythonAnywhere Bash

Open PythonAnywhere Bash console and go to your project folder:

```bash
cd ~/npgcDataHub
```

If your project is inside another folder, use that real path.

Run:

```bash
find knowledge/data -name "*.json" | wc -l
```

Expected:

```text
229
```

Then run:

```bash
python - <<'PY'
import json
from pathlib import Path

p = Path("knowledge/data/catalog.json")
print("catalog exists:", p.exists())
print("catalog size:", p.stat().st_size if p.exists() else 0)

if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    print("page_count:", d.get("page_count"))
    print("categories:", len(d.get("categories", [])))
    print("pages:", len(d.get("pages", [])))
PY
```

Expected:

```text
catalog exists: True
page_count: 228
categories: 10
pages: 228
```

## Upload Missing Data

Upload the full local folder:

```text
D:\system coding\npgcDataHub\knowledge\data
```

to PythonAnywhere:

```text
~/npgcDataHub/knowledge/data
```

Do not upload only code files. The website content is stored in JSON files inside `knowledge/data`.

## Reload Web App

After upload, go to:

```text
PythonAnywhere Dashboard > Web > Reload
```

Then test:

```text
https://npgchub.pythonanywhere.com/
https://npgchub.pythonanywhere.com/admissions/
https://npgchub.pythonanywhere.com/admissions/admission-eligibility/
```

## Important Code Change

`knowledge/views.py` has been updated to remove catalog caching. This avoids the site staying stuck at `0` after data files are uploaded.

Upload this updated file too:

```text
knowledge/views.py
```

