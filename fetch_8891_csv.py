#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local-only 8891 fetcher (auto-pagination):
- Reads brand/kind pairs from a local config JSON
- Auto-fetches pages until no more items (or safety --max-pages reached)
- Saves normalized rows to CSV (per brand-kind)
- (Optional) archives raw JSON lines locally

Requires: Python 3.10+, requests
  pip install requests

Examples:
  python fetch_8891_csv.py --config config_8891.json --out-dir ./data --auto --max-pages 300 --sleep 1.2 --raw-jsonl
  python fetch_8891_csv.py --config config_8891.json --out-dir ./data --pages 5   # fixed pages mode
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import re
import sys
import time
import urllib3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Disable SSL warnings when verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.8891.com.tw/api/v5/items/search"

# ------------------ Chinese text support ------------------

def setup_chinese_support():
    """Setup proper Chinese text support for Windows terminal"""
    import sys
    import os
    
    # Set UTF-8 encoding for stdout/stderr
    if sys.platform.startswith('win'):
        try:
            # Try to set console to UTF-8 mode
            os.system('chcp 65001 > nul')
        except:
            pass
    
    # Ensure proper encoding for print statements
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass

# ------------------ helpers: parse CJK fields to numbers ------------------

def clean_text(text: Optional[str]) -> str:
    """Clean and normalize text to handle encoding issues, especially for Chinese characters"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    
    # Handle common encoding issues for Chinese text
    try:
        # Check if text contains garbled characters that might be double-encoded
        if any(char in text for char in ['�', '?', '\ufffd']):
            # Try to fix common Chinese encoding issues
            try:
                # Method 1: Try fixing double-encoded UTF-8
                if isinstance(text.encode('latin1'), bytes):
                    fixed_text = text.encode('latin1').decode('utf-8', errors='ignore')
                    if fixed_text and not any(char in fixed_text for char in ['�', '?', '\ufffd']):
                        text = fixed_text
            except (UnicodeDecodeError, UnicodeEncodeError):
                try:
                    # Method 2: Try fixing Big5 to UTF-8 issues
                    fixed_text = text.encode('cp1252', errors='ignore').decode('utf-8', errors='ignore')
                    if fixed_text and not any(char in fixed_text for char in ['�', '?', '\ufffd']):
                        text = fixed_text
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass
        
        # Additional cleanup for Chinese text
        # Remove replacement characters and null bytes
        text = text.replace('�', '').replace('\ufffd', '').replace('\x00', '')
        
        # Normalize Chinese punctuation and whitespace
        text = text.replace('　', ' ')  # Replace full-width space with normal space
        text = ' '.join(text.split())  # Normalize whitespace
        
    except Exception:
        # If all else fails, keep the original text but clean obvious issues
        text = text.replace('�', '').replace('\ufffd', '').replace('\x00', '')
    
    return text.strip()

def parse_price_to_ntd(price_str: Optional[str]) -> Optional[int]:
    if price_str is None:
        return None
    s = str(price_str).strip().replace(',', '')
    if s == '':
        return None
    if '萬' in s:
        try:
            return int(round(float(s.replace('萬', '')) * 10000))
        except ValueError:
            return None
    m = re.findall(r'[\d.]+', s)
    try:
        return int(float(m[0])) if m else None
    except ValueError:
        return None

def parse_mileage_to_km(mileage_str: Optional[str]) -> Optional[int]:
    if mileage_str is None:
        return None
    s = str(mileage_str).strip().replace(',', '')
    s = s.replace('公里', '').replace('KM', '').replace('km', '')
    if s == '':
        return None
    if '萬' in s:
        try:
            return int(round(float(s.replace('萬', '')) * 10000))
        except ValueError:
            return None
    m = re.findall(r'[\d.]+', s)
    try:
        return int(float(m[0])) if m else None
    except ValueError:
        return None

def parse_year(*values: Optional[str]) -> Optional[int]:
    for v in values:
        if not v:
            continue
        m = re.search(r'(19|20)\d{2}', str(v))
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                pass
    return None

# ------------------ normalization ------------------

def normalize_item(r: Dict[str, Any]) -> Dict[str, Any]:
    year = parse_year(r.get("makeYear"), r.get("yearType"))
    price_ntd = parse_price_to_ntd(r.get("price"))
    mileage_km = parse_mileage_to_km(r.get("mileage"))
    return {
        "item_id": r.get("itemId"),
        "brand": clean_text(r.get("brandEnName")),
        "series": clean_text(r.get("kindEnName")),
        "model": clean_text(r.get("modelEnName")),
        "year": year,
        "mileage_km": mileage_km,
        "price_ntd": price_ntd,
        "region": clean_text(r.get("region")),
        "color": clean_text(r.get("color")),
        "fuel": clean_text(r.get("gas")),
        "transmission": clean_text(r.get("tab")),
        "post_at": clean_text(r.get("itemPostDate")),
        "renew_at": clean_text(r.get("itemRenewDate")),
        "views_today": r.get("dayViewNum"),
        "views_total": r.get("totalViewNum"),
        "title": clean_text(r.get("title")),
        "sub_title": clean_text(r.get("subTitle")),
        "image": clean_text(r.get("image")),
        "big_image": clean_text(r.get("bigImage")),
    }

CSV_COLUMNS = [
    "item_id","brand","series","model","year","mileage_km","price_ntd","region",
    "color","fuel","transmission","post_at","renew_at","views_today","views_total",
    "title","sub_title","image","big_image"
]

# ------------------ config structures ------------------

from dataclasses import dataclass

@dataclass
class Task:
    brand: Optional[str] = None
    kind: Optional[str] = None
    enabled: bool = True
    pages: int = 3

@dataclass 
class FilterConfig:
    make_year_range: Optional[str] = "2015_2025"  # Default year range
    price_range: Optional[str] = "500000_2000000"  # Default price range 50-200萬
    
def load_config(path: Path) -> tuple[list[Task], FilterConfig]:
    data = json.loads(path.read_text("utf-8"))
    
    # Load filter configuration
    filters_data = data.get("filters", {})
    filter_config = FilterConfig(
        make_year_range=filters_data.get("make_year_range", "2015_2025"),
        price_range=filters_data.get("price_range", "500000_2000000")
    )
    
    # Load tasks
    tasks: list[Task] = []
    for entry in data.get("tasks", []):
        tasks.append(Task(
            brand=entry.get("brand"),  # Allow None
            kind=entry.get("kind"),    # Allow None
            enabled=entry.get("enabled", True),
            pages=int(entry.get("pages", data.get("defaults", {}).get("pages", 3)))
        ))
    return tasks, filter_config

# ------------------ network fetch ------------------

def build_url(page: int, base_query: Dict[str, str], brand: Optional[str] = None, kind: Optional[str] = None) -> str:
    q = {"page": str(page)}
    
    # Add brand and kind only if provided
    if brand:
        q["brand"] = brand
    if kind:
        q["kind"] = kind
    
    q.update(base_query)
    params = "&".join(f"{k}={requests.utils.quote(str(v))}" for k,v in q.items())
    return f"{BASE_URL}?{params}"

def fetch_page(session: requests.Session, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    logging.debug(f"Fetching URL: {url}")
    logging.debug(f"Headers: {headers}")
    
    # Ensure we get UTF-8 response for Chinese content
    r = session.get(url, headers=headers, timeout=30, verify=False)
    logging.debug(f"Response status: {r.status_code}")
    logging.debug(f"Response headers: {dict(r.headers)}")
    
    r.raise_for_status()
    
    # Handle encoding properly for Chinese content
    if r.encoding is None or r.encoding == 'ISO-8859-1':
        r.encoding = 'utf-8'
    
    response_text = r.text
    logging.debug(f"Response length: {len(response_text)} chars")
    logging.debug(f"Response encoding: {r.encoding}")
    logging.debug(f"Response preview: {response_text[:500]}...")
    
    try:
        json_data = r.json()
        logging.debug(f"JSON parsed successfully. Keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict'}")
        return json_data
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        logging.error(f"Response content: {response_text}")
        raise

# ------------------ CSV IO ------------------

def ensure_csv(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        import csv
        with path.open("w", newline="", encoding="utf-8-sig") as f:  # Add BOM for better Excel compatibility
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()

def load_existing_ids(path: Path) -> set[int]:
    ids: set[int] = set()
    if not path.exists():
        return ids
    import csv
    with path.open("r", newline="", encoding="utf-8-sig") as f:  # Handle BOM if present
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ids.add(int(row["item_id"]))
            except Exception:
                continue
    return ids

def append_rows(path: Path, rows: list[dict]):
    import csv
    with path.open("a", newline="", encoding="utf-8-sig") as f:  # Consistent encoding
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        for r in rows:
            # Clean up any encoding issues in the data
            cleaned_row = {}
            for key, value in r.items():
                if isinstance(value, str):
                    # Fix common encoding issues and normalize the text
                    cleaned_value = value.encode('utf-8', errors='ignore').decode('utf-8')
                    cleaned_row[key] = cleaned_value
                else:
                    cleaned_row[key] = value
            writer.writerow(cleaned_row)

# ------------------ debugging helper ------------------

def test_single_request(brand: str, kind: str, page: int = 1):
    """Test a single request for debugging purposes"""
    base_query = {
        "api": "6.19",
        "device_id": "77591190-5a8a-8d40-fe2d-47ccd84c5a85-a",
        "sort": "year-desc",
        "makeYear[]": "2015_2025",  # Filter for years 2015-2025
        "price": "500000_2000000"   # Filter for price range 50-200萬 (in NT$)
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://auto.8891.com.tw/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    }
    
    url = build_url(page, base_query, brand, kind)
    print(f"Testing URL: {url}")
    
    session = requests.Session()
    try:
        data = fetch_page(session, url, headers)
        print(f"Success! Response type: {type(data)}")
        if isinstance(data, dict):
            print(f"Response keys: {list(data.keys())}")
            
            # Show detailed structure
            for key, value in data.items():
                print(f"  {key}: {type(value)}")
                if isinstance(value, dict):
                    print(f"    Dict keys: {list(value.keys())}")
                elif isinstance(value, list):
                    print(f"    List length: {len(value)}")
                    if value:
                        print(f"    First item type: {type(value[0])}")
                else:
                    print(f"    Value: {str(value)[:100]}")
            
            # Try to find items using the improved logic
            items = None
            if 'data' in data and isinstance(data['data'], dict):
                data_obj = data['data']
                for key in ("items", "list", "results", "listings"):
                    if key in data_obj and isinstance(data_obj[key], list):
                        items = data_obj[key]
                        print(f"Found {len(items)} items in data.{key}")
                        break
            
            if items is None:
                for key in ["items", "list", "data", "results", "listings"]:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        print(f"Found {len(items)} items in '{key}'")
                        break
            
            if items and len(items) > 0:
                print(f"First item keys: {list(items[0].keys())}")
                
                # Show some sample fields with encoding
                sample_item = items[0]
                print("中文欄位處理示例 (Chinese field processing examples):")
                for field in ["region", "color", "title", "brandName", "kindName"]:
                    # Try both English and Chinese field names
                    for field_name in [field, field.replace("Name", "")]:
                        if field_name in sample_item:
                            raw_value = sample_item[field_name]
                            cleaned_value = clean_text(raw_value)
                            if raw_value and isinstance(raw_value, str):
                                print(f"  {field_name}:")
                                print(f"    原始值 (Raw): {repr(raw_value)}")
                                print(f"    清理後 (Cleaned): {repr(cleaned_value)}")
                                if raw_value != cleaned_value:
                                    print(f"    顯示效果 (Display): {cleaned_value}")
                            break
                
                print(f"Sample item: {json.dumps(items[0], indent=2, ensure_ascii=False)}")
            else:
                print("No items found in response!")
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

# ------------------ main run ------------------

def run(config_path: Path, out_dir: Path, pages: Optional[int], sleep_sec: float, raw_jsonl: bool,
        auto: bool, max_pages: int, stop_on_unchanged: bool, debug: bool = False):
    
    # Set up logging
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('debug.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    logging.info(f"Starting fetch with config: {config_path}")
    
    tasks, filter_config = load_config(config_path)
    tasks = [t for t in tasks if t.enabled]
    logging.info(f"Loaded {len(tasks)} enabled tasks")
    
    if pages is not None:
        for t in tasks:
            t.pages = pages

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    if raw_jsonl:
        raw_dir.mkdir(parents=True, exist_ok=True)

    base_query = {
        "api": "6.19",
        "device_id": "77591190-5a8a-8d40-fe2d-47ccd84c5a85-a",
        "sort": "year-desc"
    }
    
    # Add filters if specified
    if filter_config.make_year_range:
        base_query["makeYear[]"] = filter_config.make_year_range
    if filter_config.price_range:
        base_query["price"] = filter_config.price_range
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://auto.8891.com.tw/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    }

    session = requests.Session()
    total_new = 0

    for t in tasks:
        # Handle optional brand and kind
        brand = t.brand.lower() if t.brand else None
        kind = t.kind.lower() if t.kind else None
        
        # Create filename based on available fields
        filename_parts = []
        if brand:
            filename_parts.append(brand)
        if kind:
            filename_parts.append(kind)
        if not filename_parts:
            filename_parts.append("general")
        
        csv_filename = "_".join(filename_parts) + ".csv"
        csv_path = out_dir / csv_filename
        ensure_csv(csv_path)
        existing_ids = load_existing_ids(csv_path)

        search_desc = f"{brand or 'all'}/{kind or 'all'}"
        print(f"==> {search_desc}: mode={'auto' if auto else 'fixed'}, pages={t.pages}, existing={len(existing_ids)}")
        rows_to_append: list[dict] = []

        if raw_jsonl:
            date_key = dt.datetime.now().strftime("%Y-%m-%d")
            raw_path = raw_dir / f"dt={date_key}"
            raw_path.mkdir(parents=True, exist_ok=True)
            jsonl_filename = "_".join(filename_parts) + ".jsonl"
            jsonl_file = raw_path / jsonl_filename
            raw_fp = open(jsonl_file, "a", encoding="utf-8")
        else:
            raw_fp = None

        page = 1
        fetched_pages = 0

        while True:
            if not auto and page > t.pages:
                break
            if auto and fetched_pages >= max_pages:
                print(f"[INFO] reached safety max-pages={max_pages}, stopping.")
                break

            url = build_url(page=page, base_query=base_query, brand=brand, kind=kind)
            try:
                data = fetch_page(session, url, headers=headers)
            except Exception as ex:
                print(f"[WARN] fetch failed p={page}: {ex}")
                time.sleep(sleep_sec)
                break

            # Extract items
            items = None
            
            # Debug: Log response structure
            logging.debug(f"Response data type: {type(data)}")
            if isinstance(data, dict):
                logging.debug(f"Response keys: {list(data.keys())}")
                for key, value in data.items():
                    logging.debug(f"  {key}: {type(value)} - {len(value) if isinstance(value, (list, dict)) else str(value)[:100]}")
            
            # Try different ways to extract items
            if isinstance(data, dict):
                # First check if 'data' contains an object with items
                if 'data' in data and isinstance(data['data'], dict):
                    data_obj = data['data']
                    logging.debug(f"Found data object with keys: {list(data_obj.keys())}")
                    for key in ("items", "list", "results", "listings"):
                        if key in data_obj and isinstance(data_obj[key], list):
                            items = data_obj[key]
                            logging.debug(f"Found items in data.{key}: {len(items)} items")
                            break
                
                # If not found, try direct keys on main object
                if items is None:
                    for key in ("items", "list", "data", "results", "listings"):
                        if key in data and isinstance(data[key], list):
                            items = data[key]
                            logging.debug(f"Found items in key '{key}': {len(items)} items")
                            break
            
            # Fallback: if data itself is a list
            if items is None and isinstance(data, list):
                items = data
                logging.debug(f"Data is a list: {len(items)} items")

            if not items:
                logging.info(f"No items found at page {page}. Response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                # Debug: Show more details about the response
                if isinstance(data, dict) and 'data' in data:
                    logging.info(f"Data object structure: {type(data['data'])} - {list(data['data'].keys()) if isinstance(data['data'], dict) else 'not a dict'}")
                print(f"[INFO] no more items at page {page}, stopping.")
                break

            logging.debug(f"Processing {len(items)} items from page {page}")
            before_count = len(rows_to_append)
            for it in items:
                try:
                    item_id = int(it.get("itemId"))
                except Exception:
                    item_id = None

                if raw_fp is not None:
                    raw_fp.write(json.dumps(it, ensure_ascii=False) + "\n")

                if item_id is None or item_id in existing_ids:
                    continue

                norm = normalize_item(it)
                rows_to_append.append(norm)
                existing_ids.add(item_id)

            new_rows_this_page = len(rows_to_append) - before_count
            print(f"[PAGE {page}] items={len(items)}, new_rows={new_rows_this_page}")
            fetched_pages += 1
            page += 1
            time.sleep(sleep_sec)

            if auto and stop_on_unchanged and new_rows_this_page == 0:
                print("[INFO] page produced zero new rows; likely reached tail or duplicates. Stopping.")
                break

        if raw_fp is not None:
            raw_fp.close()

        if rows_to_append:
            append_rows(csv_path, rows_to_append)
            print(f"[OK] appended {len(rows_to_append)} new rows -> {csv_path}")
            total_new += len(rows_to_append)
        else:
            print("[OK] no new rows to append")

    print(f"Done. New rows total: {total_new}")

def main(argv=None):
    # Setup Chinese text support first
    setup_chinese_support()
    
    ap = argparse.ArgumentParser(description="Fetch 8891 search results into local CSV files (per brand-kind).")
    ap.add_argument("--config", help="Path to config JSON (brand/kind list). Required unless using --test mode.")
    ap.add_argument("--out-dir", default="./data", help="Output directory for CSVs (default: ./data)")
    ap.add_argument("--pages", type=int, default=None, help="Fixed pages per brand-kind (disables --auto)")
    ap.add_argument("--sleep", type=float, default=1.0, help="Sleep seconds between requests/pages (default: 1.0)")
    ap.add_argument("--raw-jsonl", action="store_true", help="Also archive raw JSON lines under out-dir/raw/dt=YYYY-MM-DD")
    ap.add_argument("--auto", action="store_true", help="Auto-fetch until no more items or safety cap")
    ap.add_argument("--max-pages", type=int, default=200, help="Safety cap for auto mode (default: 200)")
    ap.add_argument("--no-stop-on-unchanged", action="store_true", help="Do not stop when a page yields zero new rows")
    ap.add_argument("--debug", action="store_true", help="Enable debug logging (saves to debug.log)")
    ap.add_argument("--test", nargs=2, metavar=('BRAND', 'KIND'), help="Test mode: fetch single page for brand/kind")
    args = ap.parse_args(argv)

    # Test mode
    if args.test:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        brand, kind = args.test
        print(f"Testing single request for {brand}/{kind}")
        test_single_request(brand, kind)
        return 0
    
    # Config is required for normal operation
    if not args.config:
        ap.error("--config is required unless using --test mode")
    auto = bool(args.auto and args.pages is None)
    stop_on_unchanged = not args.no_stop_on_unchanged

    run(Path(args.config), Path(args.out_dir), args.pages, args.sleep, args.raw_jsonl,
        auto, args.max_pages, stop_on_unchanged, args.debug)

if __name__ == "__main__":
    # Setup Chinese text support (Windows)
    setup_chinese_support()
    
    sys.exit(main())
