"""
Great Expectations DataDocs Asset Localizer
============================================
Downloads all CDN assets from your actual GE index.html into a local 'local_assets' folder,
then patches all HTML files to use local paths instead of CDN URLs.

Usage:
    First time (download + patch):   python localize_ge_datadocs.py --all
    After each GE run (patch only):  python localize_ge_datadocs.py --patch
    Re-download everything:          python localize_ge_datadocs.py --all --force

Pipeline integration:
    Call localize_after_build() right after context.build_data_docs()
"""

import os
import re
import argparse
import urllib.request
from pathlib import Path
from typing import Dict


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

GE_ROOT = Path("C:/Users/rajsh/OneDrive/Documents/dataQualityImproved/outputs/great_expectations")
DATADOCS_ROOT = GE_ROOT / "uncommitted" / "data_docs" / "local_site"
ASSETS_DIR = DATADOCS_ROOT / "local_assets"


# ─────────────────────────────────────────────────────────────────────────────
# EXACT CDN ASSETS found in your index.html
# Format: "cdn_url": "local_filename"
# ─────────────────────────────────────────────────────────────────────────────

CDN_ASSETS: Dict[str, str] = {

    # ── CSS files ────────────────────────────────────────────────────────────

    "https://unpkg.com/bootstrap-table@1.19.1/dist/bootstrap-table.min.css":
        "bootstrap-table-1.19.1.min.css",

    "https://maxcdn.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css":
        "bootstrap-4.3.1.min.css",

    "https://unpkg.com/bootstrap-table@1.19.0/dist/extensions/filter-control/bootstrap-table-filter-control.min.css":
        "bootstrap-table-filter-control-1.19.0.min.css",

    "https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datepicker/1.9.0/css/bootstrap-datepicker.min.css":
        "bootstrap-datepicker-1.9.0.min.css",

    "https://cdn.jsdelivr.net/npm/@forevolve/bootstrap-dark@1.1.0/dist/css/bootstrap-prefers-dark.css":
        "bootstrap-prefers-dark-1.1.0.css",

    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css":
        "font-awesome-6.6.0.all.min.css",

    # ── JavaScript files ─────────────────────────────────────────────────────

    "https://cdn.jsdelivr.net/npm/vega@5":
        "vega-5.min.js",

    "https://cdn.jsdelivr.net/npm/vega-lite@4":
        "vega-lite-4.min.js",

    "https://cdn.jsdelivr.net/npm/vega-embed@6":
        "vega-embed-6.min.js",

    "https://code.jquery.com/jquery-3.4.1.min.js":
        "jquery-3.4.1.min.js",

    "https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.12.9/umd/popper.min.js":
        "popper-1.12.9.min.js",

    "https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js":
        "bootstrap-4.3.1.min.js",

    "https://unpkg.com/bootstrap-table@1.19.1/dist/bootstrap-table.min.js":
        "bootstrap-table-1.19.1.min.js",

    "https://unpkg.com/bootstrap-table@1.19.1/dist/extensions/filter-control/bootstrap-table-filter-control.min.js":
        "bootstrap-table-filter-control-1.19.1.min.js",

    "https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datepicker/1.9.0/js/bootstrap-datepicker.min.js":
        "bootstrap-datepicker-1.9.0.min.js",
}


# ── GE logo images (S3 hosted) ───────────────────────────────────────────────
# These have dynamic query strings (?d=...&dataContextId=...) so matched by base URL

IMAGE_ASSETS: Dict[str, str] = {
    "https://great-expectations-web-assets.s3.us-east-2.amazonaws.com/logo-long.png":
        "ge-logo-long.png",
    "https://great-expectations-web-assets.s3.us-east-2.amazonaws.com/full_logo_dark.png":
        "ge-logo-dark.png",
}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Download assets
# ─────────────────────────────────────────────────────────────────────────────

def download_assets(force: bool = False) -> None:
    """Downloads all CDN assets into ASSETS_DIR. Skips existing files unless force=True."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Saving assets to:\n   {ASSETS_DIR}\n")

    all_assets = {**CDN_ASSETS, **IMAGE_ASSETS}
    success, skipped, failed = 0, 0, 0

    for url, filename in all_assets.items():
        dest = ASSETS_DIR / filename

        if dest.exists() and not force:
            print(f"  ⏭  Skip (exists): {filename}")
            skipped += 1
            continue

        try:
            print(f"  ⬇  Downloading:   {filename}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read()
            dest.write_bytes(content)
            print(f"       ✓ {len(content):,} bytes")
            success += 1
        except Exception as e:
            print(f"       ✗ FAILED — {e}")
            failed += 1

    print(f"\n{'─'*55}")
    print(f"  Downloaded: {success}  |  Skipped: {skipped}  |  Failed: {failed}\n")
    if failed:
        print(f"  ⚠ Place any failed files manually in:\n    {ASSETS_DIR}\n")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Patch HTML files
# ─────────────────────────────────────────────────────────────────────────────

def patch_datadocs_html() -> None:
    """
    Scans every .html file under local_site/ and replaces CDN URLs with
    relative local paths pointing to local_assets/.

    Safe to run multiple times — idempotent.
    """
    if not DATADOCS_ROOT.exists():
        print(f"✗ DataDocs folder not found:\n  {DATADOCS_ROOT}")
        return

    html_files = list(DATADOCS_ROOT.rglob("*.html"))
    if not html_files:
        print("✗ No HTML files found in DataDocs folder.")
        return

    print(f"\n🔧 Patching {len(html_files)} HTML file(s)...\n")
    total_replacements = 0

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        original = content
        count = 0

        # Relative path from this HTML file to local_assets/
        rel = os.path.relpath(ASSETS_DIR, html_file.parent).replace("\\", "/")

        # 1. Replace exact JS/CSS CDN URLs
        for cdn_url, local_file in CDN_ASSETS.items():
            if cdn_url in content:
                content = content.replace(cdn_url, f"{rel}/{local_file}")
                count += 1

        # 2. Replace image URLs (base URL match, ignores dynamic query string)
        for base_url, local_file in IMAGE_ASSETS.items():
            pattern = re.escape(base_url) + r'(?:\?[^"\']*)?'
            new_content, n = re.subn(pattern, f"{rel}/{local_file}", content)
            if n:
                content = new_content
                count += n

        if content != original:
            html_file.write_text(content, encoding="utf-8")
            print(f"  ✓ Patched ({count:2d} replacements): {html_file.relative_to(DATADOCS_ROOT)}")
            total_replacements += count
        else:
            print(f"  ─ No changes needed:          {html_file.relative_to(DATADOCS_ROOT)}")

    print(f"\n{'─'*55}")
    print(f"  Total replacements: {total_replacements} across {len(html_files)} file(s)\n")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE INTEGRATION — drop-in function for datadocs_generator.py
# ─────────────────────────────────────────────────────────────────────────────

def localize_after_build() -> None:
    """
    Call this immediately after context.build_data_docs() in your pipeline.

    In datadocs_generator.py, replace:
        context.build_data_docs()

    With:
        context.build_data_docs()
        from localize_ge_datadocs import localize_after_build
        localize_after_build()
    """
    download_assets(force=False)   # skips already-downloaded files
    patch_datadocs_html()          # always re-patches (GE regenerates HTML each run)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Localize GE DataDocs CDN assets to a local folder"
    )
    parser.add_argument("--download", action="store_true", help="Only download assets")
    parser.add_argument("--patch",    action="store_true", help="Only patch HTML files")
    parser.add_argument("--all",      action="store_true", help="Download + patch (default)")
    parser.add_argument("--force",    action="store_true", help="Force re-download of all assets")
    args = parser.parse_args()

    if args.all or (not args.download and not args.patch):
        download_assets(force=args.force)
        patch_datadocs_html()
    else:
        if args.download:
            download_assets(force=args.force)
        if args.patch:
            patch_datadocs_html()

    print("✅ Done. Open index.html in your browser — no internet required.\n")


if __name__ == "__main__":
    main()
