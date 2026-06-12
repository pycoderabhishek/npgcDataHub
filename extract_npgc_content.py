import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "knowledge" / "data"
CATALOG = DATA_DIR / "catalog.json"
RAW_DIR = ROOT / "source" / "raw_html"

BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li"}
SKIP_TAGS = {"script", "style", "noscript"}
SKIP_CLASSES = {"page-sidebar", "navbar", "footer", "header", "widget"}
ASSET_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
)


def clean_text(value):
    value = re.sub(r"\s+", " ", value or "")
    return value.strip()


def has_class(attrs, needle):
    class_value = attrs.get("class", "")
    return needle in class_value.split() or needle in class_value


def should_skip(attrs):
    class_value = attrs.get("class", "")
    id_value = attrs.get("id", "")
    text = f"{class_value} {id_value}".lower()
    return any(skip in text for skip in SKIP_CLASSES)


class MainContentParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.capture_depth = 0
        self.skip_depth = 0
        self.blocks = []
        self.tables = []
        self.assets = []
        self.images = []
        self.links = []
        self.current_block = None
        self.current_block_tag = None
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.heading_stack = []

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        tag = tag.lower()

        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.capture_depth == 0 and tag in {"div", "article", "main", "section"}:
            if has_class(attrs, "content-wrapper"):
                self.capture_depth = 1
                return
            if has_class(attrs, "page-content"):
                self.capture_depth = 1
                return
            if has_class(attrs, "table-responsive"):
                self.capture_depth = 1
                return

        if self.capture_depth == 0:
            return

        self.capture_depth += 1
        if should_skip(attrs):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return

        if tag == "a":
            href = attrs.get("href")
            if href:
                absolute = urljoin(self.base_url, href)
                self.links.append(absolute)
                if absolute.lower().split("?")[0].endswith(ASSET_EXTENSIONS):
                    self.assets.append(absolute)
        elif tag == "img":
            src = attrs.get("src")
            if src:
                self.images.append(
                    {
                        "src": urljoin(self.base_url, src),
                        "alt": clean_text(attrs.get("alt", "")),
                    }
                )
        elif tag == "table":
            self.current_table = []
        elif tag == "tr" and self.current_table is not None:
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None:
            self.current_cell = []
        elif tag in BLOCK_TAGS and self.current_table is None:
            self.current_block = []
            self.current_block_tag = tag

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return

        if self.capture_depth == 0:
            return

        if self.skip_depth:
            self.skip_depth -= 1
            self.capture_depth = max(0, self.capture_depth - 1)
            return

        if tag in {"td", "th"} and self.current_cell is not None:
            cell = clean_text(" ".join(self.current_cell))
            self.current_row.append(cell)
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if any(self.current_row):
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.current_table is not None:
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag in BLOCK_TAGS and self.current_block is not None:
            text = clean_text(" ".join(self.current_block))
            if text:
                self.blocks.append({"type": self.current_block_tag, "text": text})
            self.current_block = None
            self.current_block_tag = None

        self.capture_depth = max(0, self.capture_depth - 1)

    def handle_data(self, data):
        if self.capture_depth == 0 or self.skip_depth:
            return
        if self.current_cell is not None:
            self.current_cell.append(data)
        elif self.current_block is not None:
            self.current_block.append(data)


class BodyFallbackParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.body_depth = 0
        self.skip_depth = 0
        self.blocks = []
        self.tables = []
        self.assets = []
        self.images = []
        self.links = []
        self.current_block = None
        self.current_block_tag = None
        self.current_table = None
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        tag = tag.lower()
        if tag == "body":
            self.body_depth = 1
            return
        if self.body_depth == 0:
            return
        self.body_depth += 1
        if tag in SKIP_TAGS or should_skip(attrs):
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "a":
            href = attrs.get("href")
            if href:
                absolute = urljoin(self.base_url, href)
                self.links.append(absolute)
                if absolute.lower().split("?")[0].endswith(ASSET_EXTENSIONS):
                    self.assets.append(absolute)
        elif tag == "img":
            src = attrs.get("src")
            if src:
                self.images.append(
                    {
                        "src": urljoin(self.base_url, src),
                        "alt": clean_text(attrs.get("alt", "")),
                    }
                )
        elif tag == "table":
            self.current_table = []
        elif tag == "tr" and self.current_table is not None:
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None:
            self.current_cell = []
        elif tag in BLOCK_TAGS and self.current_table is None:
            self.current_block = []
            self.current_block_tag = tag

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.body_depth == 0:
            return
        if self.skip_depth:
            self.skip_depth -= 1
            self.body_depth = max(0, self.body_depth - 1)
            return
        if tag in {"td", "th"} and self.current_cell is not None:
            self.current_row.append(clean_text(" ".join(self.current_cell)))
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if any(self.current_row):
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.current_table is not None:
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag in BLOCK_TAGS and self.current_block is not None:
            text = clean_text(" ".join(self.current_block))
            if text and not is_layout_text(text):
                self.blocks.append({"type": self.current_block_tag, "text": text})
            self.current_block = None
            self.current_block_tag = None
        self.body_depth = max(0, self.body_depth - 1)

    def handle_data(self, data):
        if self.body_depth == 0 or self.skip_depth:
            return
        if self.current_cell is not None:
            self.current_cell.append(data)
        elif self.current_block is not None:
            self.current_block.append(data)


def is_layout_text(text):
    normalized = clean_text(text).lower()
    blocked = {
        "home",
        "about us",
        "academics",
        "admission",
        "facilities",
        "library",
        "student support",
        "media",
        "contact us",
        "quick links",
        "useful links",
        "social media",
    }
    return normalized in blocked or len(normalized) <= 1


def normalize_table(table):
    if not table:
        return {"headers": [], "rows": []}
    headers = table[0]
    rows = table[1:]
    if len(table) == 1:
        return {"headers": [], "rows": table}
    return {"headers": headers, "rows": rows}


def extract_page(url):
    response = requests.get(
        url,
        timeout=35,
        headers={"User-Agent": "npgcDataHubContentExtractor/1.0"},
    )
    response.raise_for_status()
    html = response.text
    parser = MainContentParser(response.url)
    parser.feed(html)
    if not parser.blocks and not parser.tables and not parser.images:
        fallback = BodyFallbackParser(response.url)
        fallback.feed(html)
        parser.blocks = fallback.blocks
        parser.tables = fallback.tables
        parser.assets = fallback.assets
        parser.images = fallback.images
        parser.links = fallback.links
    return {
        "final_url": response.url,
        "raw_html": html,
        "content_blocks": parser.blocks,
        "tables": [normalize_table(table) for table in parser.tables],
        "extracted_assets": sorted(set(parser.assets)),
        "images": parser.images,
        "extracted_links": sorted(set(parser.links)),
    }


def blocks_to_text(blocks, tables):
    parts = [block["text"] for block in blocks]
    for table in tables:
        if table["headers"]:
            parts.append(" | ".join(table["headers"]))
        for row in table["rows"]:
            parts.append(" | ".join(row))
    return "\n".join(part for part in parts if part)


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for index, summary in enumerate(catalog["pages"], start=1):
        data_file = DATA_DIR / summary["data_file"]
        page = json.loads(data_file.read_text(encoding="utf-8"))
        url = page.get("source_url")
        if not url:
            continue
        if page.get("extraction_status") == "ok" and page.get("content"):
            print(f"[{index}/{catalog['page_count']}] SKIP {summary['path']}")
            continue
        try:
            extracted = extract_page(url)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
            page["extraction_status"] = "error"
            page["extraction_error"] = str(exc)
            data_file.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[{index}/{catalog['page_count']}] ERROR {url}: {exc}")
            continue

        raw_name = re.sub(r"[^a-zA-Z0-9]+", "-", summary["path"].strip("/")).strip("-")
        (RAW_DIR / f"{raw_name}.html").write_text(extracted["raw_html"], encoding="utf-8")

        page["source_url"] = extracted["final_url"]
        page["content_blocks"] = extracted["content_blocks"]
        page["tables"] = extracted["tables"]
        page["content"] = blocks_to_text(extracted["content_blocks"], extracted["tables"])
        page["images"] = extracted["images"]
        page["source_assets"] = sorted(
            set(page.get("source_assets", [])) | set(extracted["extracted_assets"])
        )
        page["related_links"] = sorted(
            set(page.get("related_links", [])) | set(extracted["extracted_links"])
        )[:80]
        page["extraction_status"] = "ok"
        page["extraction_error"] = ""
        data_file.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f"[{index}/{catalog['page_count']}] OK {summary['path']} "
            f"blocks={len(page['content_blocks'])} tables={len(page['tables'])}"
        )
        time.sleep(0.08)

    report = {
        "page_count": catalog["page_count"],
        "failure_count": len(failures),
        "failures": failures,
    }
    (ROOT / "content_extraction_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Extraction complete with {len(failures)} failures.")


if __name__ == "__main__":
    main()
