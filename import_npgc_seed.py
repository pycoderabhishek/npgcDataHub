import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "npgc_page_records_seed.json"
DATA_DIR = ROOT / "knowledge" / "data"

CATEGORY_LABELS = {
    "about": "About College",
    "academics": "Academics",
    "admissions": "Admissions",
    "contact": "Contact",
    "departments-faculty": "Departments and Faculty",
    "facilities": "Facilities",
    "general": "General Information",
    "media": "Media and Events",
    "notices": "Notices",
    "student-services": "Student Services",
}

CATEGORY_ORDER = [
    "about",
    "admissions",
    "academics",
    "departments-faculty",
    "student-services",
    "facilities",
    "notices",
    "media",
    "contact",
    "general",
]


def slugify(value):
    value = value.lower()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "page"


def humanize_source_url(url):
    parsed = urlparse(url)
    stem = Path(parsed.path).stem
    if not stem:
        return "Home"
    stem = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    stem = stem.replace("-", " ").replace("_", " ")
    if parsed.query:
        query = parse_qs(parsed.query)
        if "Id" in query:
            stem = f"{stem} {query['Id'][0]}"
    return re.sub(r"\s+", " ", stem).strip().title()


def best_title(record):
    source_title = humanize_source_url(record.get("url", ""))
    for heading in record.get("headings", []):
        text = heading.get("text", "").strip()
        generic = {
            "admission",
            "academics",
            "about us",
            "facilities",
            "gallery",
            "news",
            "notices",
            "quick links",
            "latest events",
        }
        if text and text.lower() not in generic:
            return text
        if text and source_title.lower() not in generic:
            return source_title
    title = record.get("title", "").strip()
    if title and title.lower() != "national post graduate college":
        return title
    return source_title


def category_for(record):
    text = f"{record.get('url', '')} {best_title(record)}".lower()
    if "department" in text or "faculty" in text:
        return "departments-faculty"
    category = record.get("page_category") or "general"
    return category if category in CATEGORY_LABELS else "general"


def source_slug(record):
    parsed = urlparse(record.get("url", ""))
    title_slug = slugify(best_title(record))
    if parsed.query:
        query = parse_qs(parsed.query)
        if "Id" in query:
            return f"{title_slug}-{query['Id'][0]}"
    return title_slug


def make_overview(record, title, category_label):
    source = record.get("url", "")
    headings = [
        item.get("text", "")
        for item in record.get("headings", [])
        if item.get("text")
    ]
    heading_text = ", ".join(headings[:4])
    if heading_text:
        return (
            f"This page stores NPGC {category_label.lower()} information for {title}. "
            f"Captured source headings include: {heading_text}. Source page: {source}"
        )
    return (
        f"This page stores NPGC {category_label.lower()} information for {title}. "
        f"Source page: {source}"
    )


def build_records(seed):
    used_paths = Counter()
    pages = []
    by_category = defaultdict(list)

    for record in seed:
        if not record.get("url"):
            continue
        category = category_for(record)
        category_label = CATEGORY_LABELS[category]
        title = best_title(record)
        slug = source_slug(record)
        base_path = f"/{category}/{slug}/"
        used_paths[base_path] += 1
        path = base_path
        if used_paths[base_path] > 1:
            path = f"/{category}/{slug}-{used_paths[base_path]}/"

        data_file = f"{category}/{Path(path.strip('/')).name}.json"
        page = {
            "path": path,
            "source_url": record.get("url", ""),
            "title": title,
            "category": category_label,
            "page_category": category,
            "keywords": sorted(
                set([category_label, title, "NPGC", "National Post Graduate College"])
            ),
            "last_updated": "",
            "breadcrumb": [
                {"title": "Home", "url": "/"},
                {"title": category_label, "url": f"/{category}/"},
                {"title": title, "url": path},
            ],
            "headings": record.get("headings", []),
            "overview": make_overview(record, title, category_label),
            "content": record.get("content", ""),
            "tables": [],
            "faq": record.get("faq", []),
            "related_links": record.get("related_links", [])[:20],
            "source_assets": record.get("source_assets", [])[:50],
            "external_links": record.get("external_links", [])[:20],
        }
        pages.append((page, data_file))
        by_category[category].append(page)

    return pages, by_category


def main():
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed = json.loads(SOURCE.read_text(encoding="utf-8"))
    pages, by_category = build_records(seed)

    summaries = []
    for page, data_file in pages:
        target = DATA_DIR / data_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        summaries.append(
            {
                "title": page["title"],
                "path": page["path"],
                "source_url": page["source_url"],
                "page_category": page["page_category"],
                "category": page["category"],
                "data_file": data_file,
            }
        )

    categories = []
    for slug in CATEGORY_ORDER:
        if slug not in by_category:
            continue
        categories.append(
            {
                "slug": slug,
                "title": CATEGORY_LABELS[slug],
                "url": f"/{slug}/",
                "page_count": len(by_category[slug]),
            }
        )

    catalog = {
        "site_title": "npgcDataHub",
        "source": "https://www.npgc.in/",
        "page_count": len(summaries),
        "categories": categories,
        "pages": sorted(
            summaries,
            key=lambda item: (item["page_category"], item["title"], item["path"]),
        ),
    }
    (DATA_DIR / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Generated {len(summaries)} knowledge pages in {DATA_DIR}")


if __name__ == "__main__":
    main()
