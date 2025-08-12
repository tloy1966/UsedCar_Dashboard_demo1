# 8891 API Enhancement Summary

## Changes Made

### 1. Added Filter Parameters to API Specification

**Added Filters:**
- `makeYear[]=2015_2025` - Filters vehicles by year range (2015-2025)
- `price=500000_2000000` - Filters vehicles by price range (50萬-200萬 NT$)

**URL Format:**
```
https://www.8891.com.tw/api/v5/items/search?page=1&api=6.19&device_id=...&sort=year-desc&makeYear[]=2015_2025&price=500000_2000000
```

### 2. Made Brand and Kind Optional

**Before:** Brand and kind were required parameters
**After:** Brand and kind are now optional, allowing general searches

**Benefits:**
- Can search all vehicles using only filters
- Can search by brand only (all Toyota vehicles)
- Can search by model only (all RAV4 from any brand)
- More flexible search configurations

### 3. Enhanced Configuration Structure

**New `filters` section in config.json:**
```json
{
  "filters": {
    "make_year_range": "2015_2025",
    "price_range": "500000_2000000"
  }
}
```

**Enhanced `tasks` section:**
```json
{
  "tasks": [
    {
      "brand": "toyota",
      "kind": "rav4",
      "enabled": true,
      "pages": 2
    },
    {
      "comment": "General search without specific brand/kind",
      "enabled": true,
      "pages": 3
    },
    {
      "brand": "toyota",
      "comment": "All Toyota vehicles",
      "enabled": false,
      "pages": 3
    }
  ]
}
```

### 4. Updated Code Structure

**New Classes:**
- `FilterConfig` - Manages filter parameters
- Enhanced `Task` with optional brand/kind

**Modified Functions:**
- `build_url()` - Now accepts optional brand/kind parameters
- `load_config()` - Returns both tasks and filter config
- `run()` - Uses filter config for API queries

**Enhanced Features:**
- Smart CSV filename generation (brand_kind.csv, toyota.csv, general.csv)
- Better error handling for optional parameters
- Configurable filter parameters

### 5. API Parameter Encoding

**Filter Formats:**
- `makeYear[]` - Year range format: `YYYY_YYYY` (e.g., "2015_2025")
- `price` - Price range format: `min_max` in NT$ (e.g., "500000_2000000" = 50萬-200萬)

**URL Encoding:**
- Automatic URL encoding of parameters
- Proper handling of array parameters (`makeYear[]`)

### 6. Test Results

**✅ Specific Brand/Kind Search:**
```bash
python fetch_8891_csv.py --test toyota rav4
# Returns: Toyota RAV4 vehicles, 2015-2025, 50-200萬
```

**✅ General Search (No Brand/Kind):**
```bash
python fetch_8891_csv.py --config config_8891.json --pages 1
# Returns: Mixed brands, all within filter criteria
```

**✅ Data Quality:**
- 40 items per page
- All vehicles within specified year range (2015-2025)
- All vehicles within price range (50-200萬)
- Proper Chinese text encoding
- Diverse brand mix in general searches

### 7. Usage Examples

**1. Search specific brand and model:**
```json
{
  "brand": "toyota",
  "kind": "rav4",
  "enabled": true,
  "pages": 2
}
```

**2. Search all vehicles from a brand:**
```json
{
  "brand": "toyota",
  "enabled": true,
  "pages": 3
}
```

**3. General search with filters only:**
```json
{
  "enabled": true,
  "pages": 5
}
```

**4. Custom filter ranges:**
```json
{
  "filters": {
    "make_year_range": "2020_2025",
    "price_range": "1000000_3000000"
  }
}
```

### 8. File Naming Convention

**New Dynamic Naming:**
- `toyota_rav4.csv` - Specific brand and kind
- `toyota.csv` - Brand only
- `general.csv` - No specific brand/kind
- Similar naming for JSONL files

### 9. Backward Compatibility

**✅ Maintained:**
- All existing functionality preserved
- Existing config files still work
- Same command-line interface
- Same CSV output format

**🆕 Enhanced:**
- Optional brand/kind parameters
- Configurable filters
- More flexible search options
- Better file naming

## Summary

The API now supports:
1. **Filtered searches** with year and price ranges
2. **Optional brand/kind** parameters for flexible querying
3. **Configurable filters** via config file
4. **General searches** across all vehicles
5. **Smart file naming** based on search parameters

This makes the API much more versatile while maintaining full backward compatibility.
