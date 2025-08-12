#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo Data Generator for 8891 Car Dashboard
Generate sample car data for testing the dashboard

Usage:
    python generate_demo_data.py
"""

import pandas as pd
import numpy as np
import random
from pathlib import Path

def generate_demo_data(num_records=1000):
    """Generate demo car data"""
    
    # Sample data lists
    brands = ['Toyota', 'Honda', 'Nissan', 'Mercedes-Benz', 'BMW', 'Audi', 'Volkswagen', 'Ford', 'Chevrolet', 'Hyundai']
    series_map = {
        'Toyota': ['Camry', 'Corolla', 'RAV4', 'Prius', 'Highlander'],
        'Honda': ['Civic', 'Accord', 'CR-V', 'Pilot', 'Fit'],
        'Nissan': ['Altima', 'Sentra', 'Rogue', 'Pathfinder', 'Maxima'],
        'Mercedes-Benz': ['C-Class', 'E-Class', 'S-Class', 'GLC', 'GLE'],
        'BMW': ['3 Series', '5 Series', '7 Series', 'X3', 'X5'],
        'Audi': ['A3', 'A4', 'A6', 'Q3', 'Q5'],
        'Volkswagen': ['Jetta', 'Passat', 'Tiguan', 'Atlas', 'Golf'],
        'Ford': ['Mustang', 'F-150', 'Explorer', 'Escape', 'Focus'],
        'Chevrolet': ['Camaro', 'Silverado', 'Equinox', 'Malibu', 'Cruze'],
        'Hyundai': ['Elantra', 'Sonata', 'Tucson', 'Santa Fe', 'Accent']
    }
    
    regions = ['台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市', '新竹市', '苗栗縣', '彰化縣', '南投縣', '雲林縣', '嘉義市', '屏東縣', '宜蘭縣', '花蓮縣']
    colors = ['白色', '黑色', '銀色', '紅色', '藍色', '灰色', '棕色', '綠色', '黃色', '橘色']
    fuels = ['汽油', '柴油', '油電混合', '電動', 'LPG']
    transmissions = ['手排', '自排', 'CVT', '手自排']
    
    # Generate random data
    data = []
    
    for i in range(num_records):
        brand = random.choice(brands)
        series = random.choice(series_map[brand])
        model = f"{series} {random.choice(['Deluxe', 'Sport', 'Premium', 'Standard', 'Limited'])}"
        
        # Price varies by brand and year
        base_price = {
            'Toyota': 80, 'Honda': 75, 'Nissan': 70,
            'Mercedes-Benz': 200, 'BMW': 180, 'Audi': 170,
            'Volkswagen': 90, 'Ford': 85, 'Chevrolet': 80, 'Hyundai': 65
        }[brand]
        
        year = random.randint(2010, 2024)
        year_factor = (year - 2010) / 14  # Newer cars cost more
        price = int(base_price * (0.5 + year_factor * 1.5) * random.uniform(0.8, 1.3))
        
        # Mileage varies by year
        max_mileage = (2024 - year) * random.randint(8000, 15000)
        mileage = random.randint(1000, max_mileage) if max_mileage > 1000 else random.randint(100, 5000)
        
        record = {
            'item_id': f"demo_{i+1:06d}",
            'brand': brand,
            'series': series,
            'model': model,
            'year': year,
            'mileage_km': mileage,
            'price_ntd': price,
            'region': random.choice(regions),
            'color': random.choice(colors),
            'fuel': random.choice(fuels),
            'transmission': random.choice(transmissions),
            'title': f"{year} {brand} {model}",
            'views_today': random.randint(0, 100),
            'views_total': random.randint(100, 5000)
        }
        
        data.append(record)
    
    return pd.DataFrame(data)

def main():
    """Generate and save demo data"""
    print("🚗 生成示範車輛數據...")
    
    # Create data directory
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    # Generate demo data
    df = generate_demo_data(1000)
    
    # Save as CSV
    output_file = data_dir / "demo_car_data.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"✅ 已生成 {len(df)} 筆示範數據")
    print(f"📁 保存位置: {output_file}")
    print(f"📊 數據概況:")
    print(f"   - 品牌數量: {df['brand'].nunique()}")
    print(f"   - 年份範圍: {df['year'].min()} - {df['year'].max()}")
    print(f"   - 價格範圍: {df['price_ntd'].min()} - {df['price_ntd'].max()} 萬")
    print(f"   - 地區數量: {df['region'].nunique()}")
    
    print("\n🎯 現在可以運行 dashboard:")
    print("   python -m streamlit run dashboard.py")

if __name__ == "__main__":
    main()
