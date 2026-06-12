import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.http import Http404
from django.shortcuts import render


DATA_DIR = Path(settings.BASE_DIR) / "knowledge" / "data"


@lru_cache(maxsize=1)
def load_catalog():
    catalog_path = DATA_DIR / "catalog.json"
    if not catalog_path.exists():
        return {"categories": [], "pages": []}
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def home(request):
    catalog = load_catalog()
    stats = content_stats(catalog["pages"])
    return render(request, "knowledge/home.html", {"catalog": catalog, "stats": stats})


def category_index(request, category):
    catalog = load_catalog()
    category_record = next(
        (item for item in catalog["categories"] if item["slug"] == category),
        None,
    )
    if category_record is None:
        raise Http404("Category not found")
    pages = [
        enrich_summary(page)
        for page in catalog["pages"]
        if page["page_category"] == category
    ]
    return render(
        request,
        "knowledge/category.html",
        {"catalog": catalog, "category": category_record, "pages": pages},
    )


def knowledge_page(request, page_path):
    clean_path = "/" + page_path.strip("/") + "/"
    catalog = load_catalog()
    page_summary = next(
        (page for page in catalog["pages"] if page["path"] == clean_path),
        None,
    )
    if page_summary is None:
        raise Http404("Knowledge page not found")

    page_file = DATA_DIR / page_summary["data_file"]
    page = json.loads(page_file.read_text(encoding="utf-8"))
    return render(
        request,
        "knowledge/page.html",
        {"catalog": catalog, "page": page},
    )


def read_page(data_file):
    page_file = DATA_DIR / data_file
    return json.loads(page_file.read_text(encoding="utf-8"))


def enrich_summary(summary):
    page = read_page(summary["data_file"])
    enriched = dict(summary)
    enriched.update(
        {
            "content_block_count": len(page.get("content_blocks", [])),
            "table_count": len(page.get("tables", [])),
            "image_count": len(page.get("images", [])),
            "local_asset_count": len(
                [item for item in page.get("local_assets", []) if item.get("status") == "ok"]
            ),
            "has_local_content": bool(
                page.get("content_blocks") or page.get("tables") or page.get("images")
            ),
        }
    )
    return enriched


def content_stats(pages):
    stats = {
        "content_blocks": 0,
        "tables": 0,
        "images": 0,
        "local_assets": 0,
        "loaded_pages": 0,
    }
    for summary in pages:
        page = read_page(summary["data_file"])
        content_blocks = len(page.get("content_blocks", []))
        tables = len(page.get("tables", []))
        images = len(page.get("images", []))
        local_assets = len(
            [item for item in page.get("local_assets", []) if item.get("status") == "ok"]
        )
        stats["content_blocks"] += content_blocks
        stats["tables"] += tables
        stats["images"] += images
        stats["local_assets"] += local_assets
        if content_blocks or tables or images:
            stats["loaded_pages"] += 1
    return stats

# Create your views here.
