import hashlib
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "knowledge" / "data"
STATIC_ASSET_DIR = ROOT / "static" / "knowledge" / "source_files"
STATIC_URL_PREFIX = "/static/knowledge/source_files"


def extension_for(url, content_type):
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext:
        return path_ext[:12]
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    return guessed or ".bin"


def safe_name(url, content_type=""):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    stem = Path(urlparse(url).path).stem
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()[:50] or "asset"
    return f"{stem}-{digest}{extension_for(url, content_type)}"


def download(url):
    head_name = safe_name(url)
    existing = list(STATIC_ASSET_DIR.glob(f"*-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]}.*"))
    if existing:
        target = existing[0]
        return {
            "original_url": url,
            "local_path": str(target.relative_to(ROOT)).replace("\\", "/"),
            "local_url": f"{STATIC_URL_PREFIX}/{target.name}",
            "status": "ok",
        }

    response = requests.get(
        url,
        timeout=35,
        headers={"User-Agent": "npgcDataHubAssetDownloader/1.0"},
    )
    response.raise_for_status()
    name = safe_name(response.url, response.headers.get("content-type", ""))
    target = STATIC_ASSET_DIR / name
    target.write_bytes(response.content)
    return {
        "original_url": url,
        "local_path": str(target.relative_to(ROOT)).replace("\\", "/"),
        "local_url": f"{STATIC_URL_PREFIX}/{target.name}",
        "status": "ok",
    }


def is_document_asset(url):
    path = urlparse(url).path.lower()
    return path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"))


def candidate_urls_for_page(page):
    urls = []
    urls.extend(image.get("src") for image in page.get("images", []) if image.get("src"))
    for asset in page.get("source_assets", []):
        if is_document_asset(asset):
            urls.append(asset)
    return sorted(set(url for url in urls if url and url.startswith("http")))


def main():
    STATIC_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    files = list(DATA_DIR.glob("*/*.json"))
    cache = {}
    failures = []
    total = 0

    for data_file in files:
        page = json.loads(data_file.read_text(encoding="utf-8"))
        urls = candidate_urls_for_page(page)
        if not urls:
            continue

        local_assets = []
        for url in urls:
            total += 1
            try:
                if url not in cache:
                    cache[url] = download(url)
                local_assets.append(cache[url])
            except Exception as exc:
                failure = {"url": url, "page": page.get("path"), "error": str(exc)}
                failures.append(failure)
                local_assets.append(
                    {
                        "original_url": url,
                        "local_path": "",
                        "local_url": "",
                        "status": "error",
                        "error": str(exc),
                    }
                )

        page["local_assets"] = local_assets
        local_by_original = {
            item["original_url"]: item
            for item in local_assets
            if item.get("status") == "ok"
        }
        for image in page.get("images", []):
            local = local_by_original.get(image.get("src"))
            if local:
                image["local_url"] = local["local_url"]
                image["local_path"] = local["local_path"]
        data_file.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{page.get('path')} assets={len(local_assets)}")

    report = {
        "asset_references": total,
        "unique_downloaded_or_cached": len(cache),
        "failure_count": len(failures),
        "failures": failures,
    }
    (ROOT / "asset_download_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"Asset download complete: {len(cache)} unique assets, "
        f"{len(failures)} failures."
    )


if __name__ == "__main__":
    main()
