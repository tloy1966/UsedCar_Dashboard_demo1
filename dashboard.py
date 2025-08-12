#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8891 Car Data Dashboard
Interactive Streamlit dashboard for analyzing car listing data

Usage:
    streamlit run dashboard.py

Requirements:
    pip install streamlit pandas plotly seaborn matplotlib numpy
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import json
from pathlib import Path
import glob
from typing import Dict, List, Optional

# Page config
st.set_page_config(
    page_title="8891 汽車數據分析儀表板",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for drill-down functionality
if 'drill_down_filters' not in st.session_state:
    st.session_state.drill_down_filters = {}
if 'current_level' not in st.session_state:
    st.session_state.current_level = 'overview'
if 'breadcrumb' not in st.session_state:
    st.session_state.breadcrumb = ['總覽']

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

class DrillDownManager:
    """Manage drill-down navigation and filtering"""
    
    @staticmethod
    def reset_filters():
        """Reset all drill-down filters"""
        st.session_state.drill_down_filters = {}
        st.session_state.current_level = 'overview'
        st.session_state.breadcrumb = ['總覽']
    
    @staticmethod
    def add_filter(filter_type: str, filter_value: str, level_name: str):
        """Add a drill-down filter"""
        st.session_state.drill_down_filters[filter_type] = filter_value
        st.session_state.current_level = filter_type
        if level_name not in st.session_state.breadcrumb:
            st.session_state.breadcrumb.append(level_name)
    
    @staticmethod
    def remove_filter(filter_type: str):
        """Remove a drill-down filter"""
        if filter_type in st.session_state.drill_down_filters:
            del st.session_state.drill_down_filters[filter_type]
        
        # Update breadcrumb
        if len(st.session_state.breadcrumb) > 1:
            st.session_state.breadcrumb.pop()
        
        # Update current level
        if st.session_state.drill_down_filters:
            st.session_state.current_level = list(st.session_state.drill_down_filters.keys())[-1]
        else:
            st.session_state.current_level = 'overview'
    
    @staticmethod
    def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
        """Apply all active drill-down filters to dataframe"""
        filtered_df = df.copy()
        for filter_type, filter_value in st.session_state.drill_down_filters.items():
            if filter_type in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[filter_type] == filter_value]
        return filtered_df
    
    @staticmethod
    def render_breadcrumb():
        """Render navigation breadcrumb"""
        if len(st.session_state.breadcrumb) > 1:
            st.markdown("### 🧭 導航路徑")
            breadcrumb_text = " > ".join(st.session_state.breadcrumb)
            st.markdown(f"**{breadcrumb_text}**")
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔙 返回上一級", key="back_button"):
                    if len(st.session_state.breadcrumb) > 1:
                        # Remove last filter
                        last_filter = list(st.session_state.drill_down_filters.keys())[-1] if st.session_state.drill_down_filters else None
                        if last_filter:
                            DrillDownManager.remove_filter(last_filter)
                        st.rerun()
            
            with col2:
                if st.button("🏠 返回總覽", key="home_button"):
                    DrillDownManager.reset_filters()
                    st.rerun()
            
            st.divider()

class CarDataLoader:
    """Load and process car data from various sources"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
    
    def load_csv_data(self) -> pd.DataFrame:
        """Load data from CSV files"""
        csv_files = list(self.data_dir.glob("*.csv"))
        if not csv_files:
            return pd.DataFrame()
        
        all_data = []
        for file in csv_files:
            try:
                df = pd.read_csv(file, encoding='utf-8-sig')
                df['source_file'] = file.stem
                all_data.append(df)
            except Exception as e:
                st.warning(f"無法讀取檔案 {file.name}: {e}")
        
        if not all_data:
            return pd.DataFrame()
        
        combined_df = pd.concat(all_data, ignore_index=True)
        return self.clean_data(combined_df)
    
    def load_raw_json_data(self) -> pd.DataFrame:
        """Load data from raw JSONL files"""
        raw_dir = self.data_dir / "raw"
        if not raw_dir.exists():
            return pd.DataFrame()
        
        jsonl_files = list(raw_dir.rglob("*.jsonl"))
        if not jsonl_files:
            return pd.DataFrame()
        
        all_data = []
        for file in jsonl_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            all_data.append(data)
            except Exception as e:
                st.warning(f"無法讀取原始檔案 {file.name}: {e}")
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        return self.normalize_raw_data(df)
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize the data"""
        if df.empty:
            return df
        
        # Remove duplicates based on item_id
        if 'item_id' in df.columns:
            df = df.drop_duplicates(subset=['item_id'], keep='first')
        
        # Convert data types
        numeric_columns = ['year', 'mileage_km', 'price_ntd', 'views_today', 'views_total']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Filter reasonable values
        if 'year' in df.columns:
            df = df[(df['year'] >= 1990) & (df['year'] <= 2025)]
        if 'price_ntd' in df.columns:
            df = df[(df['price_ntd'] > 0) & (df['price_ntd'] < 10000000)]  # 0-1000萬
        if 'mileage_km' in df.columns:
            df = df[df['mileage_km'] >= 0]
        
        return df
    
    def normalize_raw_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize raw JSON data to match CSV format"""
        if df.empty:
            return df
        
        # Map raw fields to standard format
        field_mapping = {
            'itemId': 'item_id',
            'brandEnName': 'brand',
            'kindEnName': 'series',
            'modelEnName': 'model',
            'makeYear': 'year',
            'mileage': 'mileage_km',
            'price': 'price_ntd',
            'region': 'region',
            'color': 'color',
            'gas': 'fuel',
            'tab': 'transmission',
            'title': 'title',
            'dayViewNum': 'views_today',
            'totalViewNum': 'views_total'
        }
        
        # Rename columns
        for old_name, new_name in field_mapping.items():
            if old_name in df.columns:
                df[new_name] = df[old_name]
        
        # Keep only relevant columns
        relevant_columns = list(field_mapping.values())
        df = df[[col for col in relevant_columns if col in df.columns]]
        
        return self.clean_data(df)

class CarDataAnalyzer:
    """Analyze car data and create visualizations"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics"""
        if self.df.empty:
            return {}
        
        return {
            'total_cars': len(self.df),
            'avg_price': self.df['price_ntd'].mean() if 'price_ntd' in self.df.columns else 0,
            'avg_year': self.df['year'].mean() if 'year' in self.df.columns else 0,
            'avg_mileage': self.df['mileage_km'].mean() if 'mileage_km' in self.df.columns else 0,
            'brands_count': self.df['brand'].nunique() if 'brand' in self.df.columns else 0,
            'regions_count': self.df['region'].nunique() if 'region' in self.df.columns else 0
        }
    
    def create_interactive_treemap(self, group_by: str = 'brand', value_col: str = 'price_ntd') -> go.Figure:
        """Create interactive treemap with drill-down capability"""
        if self.df.empty or group_by not in self.df.columns:
            return go.Figure()
        
        # Aggregate data
        if value_col in self.df.columns:
            grouped = self.df.groupby(group_by).agg({
                value_col: ['count', 'mean', 'sum']
            }).round(0)
            grouped.columns = ['count', 'avg_value', 'total_value']
        else:
            grouped = self.df.groupby(group_by).size().to_frame('count')
            grouped['avg_value'] = 0
            grouped['total_value'] = grouped['count']
        
        grouped = grouped.reset_index()        # Create treemap
        fig = px.treemap(
            grouped, 
            path=[group_by], 
            values='count',
            color='avg_value',
            hover_data=['count', 'avg_value'],
            title=f'🔍 可點擊鑽取的車輛分布樹狀圖 ({group_by})',
            color_continuous_scale='viridis'
        )
        
        # Add custom data for proper price display (divide by 10,000 for 萬 units)
        avg_price_in_wan = grouped['avg_value'] / 10000
        fig.update_traces(
            customdata=avg_price_in_wan.values.reshape(-1, 1),
            hovertemplate='<b>%{label}</b><br>' +
                         '數量: %{value}<br>' +
                         '平均價格: %{customdata[0]:,.1f}萬<br>' +
                         '<i>點擊進行鑽取分析</i><extra></extra>'
        )
        
        # Add click event instructions
        fig.add_annotation(
            text="💡 點擊任一區塊進行鑽取分析",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=12, color="blue"),
            bgcolor="lightblue",
            bordercolor="blue",
            borderwidth=1
        )
        
        return fig
    
    def create_price_distribution(self) -> go.Figure:
        """Create price distribution histogram"""
        if self.df.empty or 'price_ntd' not in self.df.columns:
            return go.Figure()
        
        fig = px.histogram(
            self.df, 
            x='price_ntd', 
            nbins=50,
            title='價格分布圖',
            labels={'price_ntd': '價格 (新台幣)', 'count': '車輛數量'}
        )
        
        fig.update_layout(
            xaxis_title='價格 (新台幣)',
            yaxis_title='車輛數量'
        )
        
        return fig
    
    def create_year_price_scatter(self) -> go.Figure:
        """Create year vs price scatter plot"""
        if self.df.empty or 'year' not in self.df.columns or 'price_ntd' not in self.df.columns:
            return go.Figure()
        
        fig = px.scatter(
            self.df, 
            x='year', 
            y='price_ntd',
            color='brand' if 'brand' in self.df.columns else None,
            size='mileage_km' if 'mileage_km' in self.df.columns else None,
            hover_data=['model', 'region'] if all(col in self.df.columns for col in ['model', 'region']) else None,
            title='年份 vs 價格散點圖'
        )
        
        fig.update_layout(
            xaxis_title='年份',
            yaxis_title='價格 (新台幣)'
        )
        
        return fig
    
    def create_brand_comparison(self) -> go.Figure:
        """Create brand comparison chart"""
        if self.df.empty or 'brand' not in self.df.columns:
            return go.Figure()
        
        brand_stats = self.df.groupby('brand').agg({
            'price_ntd': ['count', 'mean', 'median'] if 'price_ntd' in self.df.columns else ['count'],
            'year': 'mean' if 'year' in self.df.columns else 'count',
            'mileage_km': 'mean' if 'mileage_km' in self.df.columns else 'count'
        }).round(0)
        
        brand_stats.columns = ['count', 'avg_price', 'median_price', 'avg_year', 'avg_mileage'] if 'price_ntd' in self.df.columns else ['count', 'avg_year', 'avg_mileage']
        brand_stats = brand_stats.reset_index()
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('車輛數量', '平均價格', '平均年份', '平均里程'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Add traces
        fig.add_trace(
            go.Bar(x=brand_stats['brand'], y=brand_stats['count'], name='數量'),
            row=1, col=1
        )
        
        if 'avg_price' in brand_stats.columns:
            fig.add_trace(
                go.Bar(x=brand_stats['brand'], y=brand_stats['avg_price'], name='平均價格'),
                row=1, col=2
            )
        
        if 'avg_year' in brand_stats.columns:
            fig.add_trace(
                go.Bar(x=brand_stats['brand'], y=brand_stats['avg_year'], name='平均年份'),
                row=2, col=1
            )
        
        if 'avg_mileage' in brand_stats.columns:
            fig.add_trace(
                go.Bar(x=brand_stats['brand'], y=brand_stats['avg_mileage'], name='平均里程'),
                row=2, col=2
            )
        
        fig.update_layout(height=600, title_text="品牌比較分析", showlegend=False)
        
        return fig
    
    def create_region_analysis(self) -> go.Figure:
        """Create region analysis chart"""
        if self.df.empty or 'region' not in self.df.columns:
            return go.Figure()
        
        region_stats = self.df['region'].value_counts().head(15)
        fig = px.bar(
            x=region_stats.index,
            y=region_stats.values,
            title='地區車輛分布 (前15名)',
            labels={'x': '地區', 'y': '車輛數量'}
        )
        
        fig.update_layout(
            xaxis_title='地區',
            yaxis_title='車輛數量',
            xaxis_tickangle=45
        )
        
        return fig
    
    def create_drill_down_bar_chart(self, x_col: str, y_col: str = 'count', title_prefix: str = "") -> go.Figure:
        """Create interactive bar chart for drill-down analysis"""
        if self.df.empty or x_col not in self.df.columns:
            return go.Figure()
        
        if y_col == 'count':
            grouped = self.df[x_col].value_counts().head(20)
            fig = px.bar(
                x=grouped.index,
                y=grouped.values,
                title=f'{title_prefix}按 {x_col} 分布 (可點擊鑽取)',
                labels={'x': x_col, 'y': '車輛數量'}
            )
        else:
            grouped = self.df.groupby(x_col)[y_col].mean().sort_values(ascending=False).head(20)
            fig = px.bar(
                x=grouped.index,
                y=grouped.values,
                title=f'{title_prefix}按 {x_col} 的平均 {y_col} (可點擊鑽取)',
                labels={'x': x_col, 'y': f'平均 {y_col}'}
            )
          # Enhanced styling for better interactivity
        fig.update_traces(
            marker_color='lightblue',
            marker_line_color='darkblue',
            marker_line_width=1,
            hovertemplate='<b>%{x}</b><br>值: %{y}<br><i>點擊進行鑽取</i><extra></extra>'
        )
        
        fig.update_layout(
            xaxis_tickangle=45,
            showlegend=False,
            hovermode='x unified',
            # Enable selection
            dragmode='select',
            selectdirection='h'  # 'h' for horizontal, 'v' for vertical, 'd' for diagonal, 'any' for any direction
        )
        
        # Add click instruction
        fig.add_annotation(
            text="💡 點擊柱狀圖進行鑽取分析",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=10, color="blue"),
            bgcolor="lightblue",
            bordercolor="blue",
            borderwidth=1
        )
        
        return fig
    
    def create_multi_level_treemap(self, levels: List[str], value_col: str = 'price_ntd') -> go.Figure:
        """Create multi-level treemap for hierarchical drill-down"""
        if self.df.empty or not all(col in self.df.columns for col in levels):
            return go.Figure()
        
        # Create a copy for processing
        clean_df = self.df.copy()
        
        # Convert year to string for better grouping (if it's in the levels)
        if 'year' in levels and 'year' in clean_df.columns:
            clean_df['year'] = clean_df['year'].astype(str)
        
        # Filter out rows with missing values in any level
        clean_df = clean_df.dropna(subset=levels)
        
        if clean_df.empty:
            return go.Figure()
        
        # Create hierarchical data
        if value_col in clean_df.columns:
            grouped = clean_df.groupby(levels).agg({
                value_col: ['count', 'mean']
            }).round(0)
            grouped.columns = ['count', 'avg_value']
        else:
            grouped = clean_df.groupby(levels).size().to_frame('count')
            grouped['avg_value'] = 0
        
        grouped = grouped.reset_index()
          # Handle special formatting for year if it's the first level
        if 'year' in levels:
            year_col_name = 'year'
            if year_col_name in grouped.columns:
                # Sort by year if it's one of the grouping levels
                grouped = grouped.sort_values(year_col_name)
        
        fig = px.treemap(
            grouped,
            path=levels,
            values='count',
            color='avg_value',
            hover_data=['count', 'avg_value'],
            title=f'🔍 多層級鑽取樹狀圖: {" > ".join(levels)}',
            color_continuous_scale='viridis'
        )
        
        # Add custom data for proper price display (divide by 10,000 for 萬 units)
        avg_price_in_wan = grouped['avg_value'] / 10000
        fig.update_traces(
            customdata=avg_price_in_wan.values.reshape(-1, 1),
            hovertemplate='<b>%{label}</b><br>' +
                         '數量: %{value}<br>' +
                         '平均價格: %{customdata[0]:,.1f}萬<br>' +
                         '<i>點擊進行鑽取分析</i><extra></extra>'
        )
        
        return fig
    
    def create_correlation_heatmap(self) -> go.Figure:
        """Create correlation heatmap for numerical columns"""
        numeric_cols = ['year', 'mileage_km', 'price_ntd', 'views_today', 'views_total']
        available_cols = [col for col in numeric_cols if col in self.df.columns]
        
        if len(available_cols) < 2:
            return go.Figure()
        
        corr_matrix = self.df[available_cols].corr()
        
        fig = px.imshow(
            corr_matrix,
            text_auto=True,
            aspect="auto",
            title="數值欄位相關性熱力圖",
            color_continuous_scale='RdBu'
        )
        
        return fig
    
    def get_drill_down_options(self) -> Dict[str, List[str]]:
        """Get available drill-down options based on current data"""
        options = {
            '品牌分析': ['brand', 'series', 'model'],
            '地區分析': ['region'],
            '年份分析': ['year'],
            '價格分析': ['price_ntd'],
            '燃料類型': ['fuel'],
            '變速箱': ['transmission'],
            '顏色': ['color']
        }
        
        # Filter options based on available columns
        available_options = {}
        for category, columns in options.items():
            available_columns = [col for col in columns if col in self.df.columns]
            if available_columns:
                available_options[category] = available_columns
        
        return available_options
def main():
    """Main dashboard function"""
    st.markdown('<h1 class="main-header">🚗 8891 汽車數據分析儀表板</h1>', unsafe_allow_html=True)
    
    # Render breadcrumb navigation
    DrillDownManager.render_breadcrumb()
    
    # Sidebar
    st.sidebar.title("📊 控制面板")
    
    # Data loading options
    st.sidebar.subheader("數據來源")
    data_source = st.sidebar.radio(
        "選擇數據來源:",
        ["CSV 檔案", "原始 JSON 檔案", "兩者合併"]
    )
    
    # Load data
    loader = CarDataLoader()
    
    if data_source == "CSV 檔案":
        df = loader.load_csv_data()
    elif data_source == "原始 JSON 檔案":
        df = loader.load_raw_json_data()
    else:  # 兩者合併
        csv_df = loader.load_csv_data()
        json_df = loader.load_raw_json_data()
        if not csv_df.empty and not json_df.empty:
            df = pd.concat([csv_df, json_df], ignore_index=True)
            # Remove duplicates
            if 'item_id' in df.columns:
                df = df.drop_duplicates(subset=['item_id'], keep='first')
        elif not csv_df.empty:
            df = csv_df
        elif not json_df.empty:
            df = json_df
        else:
            df = pd.DataFrame()
    
    if df.empty:
        st.error("❌ 找不到數據檔案！請確認 ./data 目錄中有 CSV 檔案或 raw/*/jsonl 檔案。")
        st.info("💡 請先運行 fetch_8891_csv.py 來獲取數據")
        return
    
    # Apply drill-down filters
    original_df = df.copy()
    df = DrillDownManager.apply_filters(df)
    
    # Show current filter info
    if st.session_state.drill_down_filters:
        st.sidebar.subheader("🎯 當前鑽取篩選")
        for filter_type, filter_value in st.session_state.drill_down_filters.items():
            st.sidebar.info(f"**{filter_type}:** {filter_value}")
        
        st.sidebar.markdown("---")
    
    # Initialize analyzer
    analyzer = CarDataAnalyzer(df)
    
    # Display summary stats
    st.subheader("📈 總覽統計")
    stats = analyzer.get_summary_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("總車輛數", f"{stats['total_cars']:,}")
    
    with col2:
        if stats['avg_price'] > 0:
            st.metric("平均價格", f"{stats['avg_price']/10000:,.1f} 萬")
    
    with col3:
        if stats['avg_year'] > 0:
            st.metric("平均年份", f"{stats['avg_year']:.0f}")
    
    with col4:
        st.metric("品牌數量", f"{stats['brands_count']}")
    
    # Interactive drill-down section
    st.subheader("🔍 互動式鑽取分析")
    
    # Get drill-down options
    drill_options = analyzer.get_drill_down_options()
    
    if drill_options:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Select drill-down category
            selected_category = st.selectbox(
                "選擇分析維度:",
                list(drill_options.keys()),
                key="drill_category"
            )
            if selected_category and drill_options[selected_category]:
                selected_column = drill_options[selected_category][0]  # Use first available column
                
                # Create and display interactive bar chart for drill-down
                fig_bar = analyzer.create_drill_down_bar_chart(
                    selected_column, 
                    title_prefix=f"當前篩選: "
                )
                st.plotly_chart(fig_bar, use_container_width=True, key=f"drill_bar_{selected_column}")
                
                # Enhanced manual drill-down interface
                if selected_column in df.columns:
                    available_values = sorted(df[selected_column].dropna().unique())
                    if available_values:
                        st.markdown("### 🎯 選擇進行鑽取分析")
                        
                        # Show top values with counts for easier selection
                        value_counts = df[selected_column].value_counts().head(15)
                        
                        col_a, col_b = st.columns([2, 1])
                        with col_a:
                            selected_value = st.selectbox(
                                f"選擇 {selected_column} (顯示前15個熱門選項):",
                                ["請選擇..."] + list(value_counts.index),
                                key=f"manual_drill_{selected_column}"
                            )
                        
                        with col_b:
                            if selected_value and selected_value != "請選擇...":
                                if st.button(f"🔍 鑽取", key=f"drill_btn_{selected_column}", type="primary"):
                                    DrillDownManager.add_filter(selected_column, selected_value, f"{selected_column}: {selected_value}")
                                    st.rerun()
                        
                        # Show value counts for reference
                        if len(value_counts) > 0:
                            with st.expander("📊 查看熱門選項統計", expanded=False):
                                display_df = pd.DataFrame({
                                    selected_column: value_counts.index,
                                    '數量': value_counts.values,
                                    '百分比': (value_counts.values / len(df) * 100).round(1)
                                })
                                st.dataframe(display_df, use_container_width=True)
        
        with col2:
            st.markdown("### 📋 鑽取使用說明")
            st.markdown("""
            **🎯 如何使用鑽取分析:**
            1. **選擇分析維度** - 從下拉選單選擇要分析的欄位
            2. **查看圖表** - 觀察分布情況
            3. **選擇鑽取目標** - 從熱門選項中選擇感興趣的值
            4. **點擊鑽取按鈕** - 系統會篩選數據並更新所有圖表
            5. **查看結果** - 所有分析都會根據新的篩選條件更新
            6. **返回上層** - 使用頂部的導航按鈕返回
            
            **💡 提示:**
            - 可以多次鑽取建立層級篩選
            - 使用頂部的麵包屑導航跟蹤位置
            - 下方會顯示熱門選項及其統計數據
            
            **可用維度:**
            """)
            for category, columns in drill_options.items():
                available_cols = [col for col in columns if col in df.columns]
                if available_cols:
                    st.markdown(f"- **{category}**: {', '.join(available_cols)}")
    
    # Enhanced filters section
    st.sidebar.subheader("🔍 進階篩選器")
    
    # Brand filter
    if 'brand' in df.columns:
        brands = ['全部'] + sorted(df['brand'].dropna().unique().tolist())
        selected_brand = st.sidebar.selectbox("品牌", brands, key="brand_filter")
        if selected_brand != '全部':
            df = df[df['brand'] == selected_brand]
    
    # Year filter
    if 'year' in df.columns and not df['year'].isna().all():
        year_range = st.sidebar.slider(
            "年份範圍",
            min_value=int(df['year'].min()),
            max_value=int(df['year'].max()),
            value=(int(df['year'].min()), int(df['year'].max())),
            key="year_filter"
        )
        df = df[(df['year'] >= year_range[0]) & (df['year'] <= year_range[1])]
    
    # Price filter
    if 'price_ntd' in df.columns and not df['price_ntd'].isna().all():
        price_range = st.sidebar.slider(
            "價格範圍 (萬)",
            min_value=0,
            max_value=int(df['price_ntd'].max()),
            value=(0, int(df['price_ntd'].max())),
            key="price_filter"
        )
        df = df[(df['price_ntd'] >= price_range[0]) & (df['price_ntd'] <= price_range[1])]
    
    # Update analyzer with filtered data
    analyzer = CarDataAnalyzer(df)
      # Main content
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🔍 互動鑽取", "🌳 樹狀圖", "📊 價格分析", "🔍 年份價格", "🏢 品牌比較", "📍 地區分析"])
    
    with tab1:
        st.subheader("🔍 互動式多層級鑽取分析")
        
        # Multi-level treemap
        st.markdown("### 📊 多層級樹狀圖")
        
        col1, col2 = st.columns([3, 1])
        
        with col2:            # Select hierarchy levels
            available_levels = ['brand', 'series', 'model', 'region', 'fuel', 'transmission', 'color', 'year']
            available_levels = [level for level in available_levels if level in df.columns]
            
            if len(available_levels) >= 2:
                selected_levels = st.multiselect(
                    "選擇層級 (按順序):",
                    available_levels,
                    default=available_levels[:2],
                    max_selections=3,
                    key="hierarchy_levels"
                )
                
                if selected_levels:
                    with col1:
                        fig_multi = analyzer.create_multi_level_treemap(selected_levels)
                        st.plotly_chart(fig_multi, use_container_width=True)
            else:
                st.warning("需要至少2個可用的分類欄位來建立多層級分析")
        
        # Correlation analysis
        st.markdown("### 🌡️ 數值欄位相關性分析")
        fig_corr = analyzer.create_correlation_heatmap()
        if fig_corr.data:
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.info("需要至少2個數值欄位來顯示相關性分析")
        
        # Dynamic insights
        st.markdown("### 💡 動態洞察")
        insights_col1, insights_col2 = st.columns(2)
        
        with insights_col1:
            if 'brand' in df.columns and 'price_ntd' in df.columns:
                top_brand = df.groupby('brand')['price_ntd'].mean().sort_values(ascending=False).iloc[0]
                top_brand_name = df.groupby('brand')['price_ntd'].mean().sort_values(ascending=False).index[0]
                st.metric("最高平均價格品牌", f"{top_brand_name}", f"{top_brand/10000:,.1f} 萬")
            
            if 'year' in df.columns:
                newest_year = df['year'].max()
                newest_count = len(df[df['year'] == newest_year])
                st.metric(f"{newest_year}年車款數量", f"{newest_count:,}")
        
        with insights_col2:
            if 'region' in df.columns:
                top_region = df['region'].value_counts().iloc[0]
                top_region_name = df['region'].value_counts().index[0]
                st.metric("車輛最多地區", f"{top_region_name}", f"{top_region:,} 輛")
            
            if 'views_total' in df.columns:
                avg_views = df['views_total'].mean()
                st.metric("平均總瀏覽數", f"{avg_views:,.0f}")
    
    with tab2:
        st.subheader("樹狀圖分析")
        treemap_option = st.selectbox(
            "選擇分組方式:",
            ["brand", "series", "region", "fuel", "transmission"],
            key="treemap_groupby"
        )
        
        if treemap_option in df.columns:
            fig = analyzer.create_interactive_treemap(treemap_option)
            st.plotly_chart(fig, use_container_width=True)
            
            # Show top categories
            st.markdown(f"### 📋 {treemap_option} 前10名")
            top_categories = df[treemap_option].value_counts().head(10)
            st.dataframe(top_categories.reset_index().rename(columns={'index': treemap_option, treemap_option: '數量'}))
        else:
            st.warning(f"數據中沒有 {treemap_option} 欄位")    
    with tab3:
        st.subheader("價格分布分析")
        fig = analyzer.create_price_distribution()
        st.plotly_chart(fig, use_container_width=True)
          # Price statistics
        if 'price_ntd' in df.columns:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("最低價格", f"{df['price_ntd'].min()/10000:,.1f} 萬")
            with col2:
                st.metric("最高價格", f"{df['price_ntd'].max()/10000:,.1f} 萬")
            with col3:
                st.metric("中位數價格", f"{df['price_ntd'].median()/10000:,.1f} 萬")
    
    with tab4:
        st.subheader("年份 vs 價格分析")
        fig = analyzer.create_year_price_scatter()
        st.plotly_chart(fig, use_container_width=True)
        
        # Add year-based insights
        if 'year' in df.columns and 'price_ntd' in df.columns:
            st.markdown("### 📊 按年份統計")
            yearly_stats = df.groupby('year').agg({
                'price_ntd': ['count', 'mean', 'median'],
                'mileage_km': 'mean' if 'mileage_km' in df.columns else 'count'
            }).round(0)
            yearly_stats.columns = ['車輛數', '平均價格', '中位數價格', '平均里程'] if 'mileage_km' in df.columns else ['車輛數', '平均價格', '中位數價格']
            st.dataframe(yearly_stats.tail(10))  # Show last 10 years
    
    with tab5:
        st.subheader("品牌比較分析")
        fig = analyzer.create_brand_comparison()
        st.plotly_chart(fig, use_container_width=True)
        
        # Brand detailed analysis
        if 'brand' in df.columns:
            st.markdown("### 📊 品牌詳細統計")
            brand_analysis = df.groupby('brand').agg({
                'price_ntd': ['count', 'mean', 'median', 'std'] if 'price_ntd' in df.columns else ['count'],
                'year': 'mean' if 'year' in df.columns else 'count',
                'mileage_km': 'mean' if 'mileage_km' in df.columns else 'count'
            }).round(2)
            
            # Flatten column names
            brand_analysis.columns = ['車輛數', '平均價格', '中位數價格', '價格標準差', '平均年份', '平均里程'] if 'price_ntd' in df.columns else ['車輛數', '平均年份', '平均里程']
            brand_analysis = brand_analysis.sort_values('車輛數', ascending=False)
            st.dataframe(brand_analysis)
    
    with tab6:
        st.subheader("地區分布分析")
        fig = analyzer.create_region_analysis()
        st.plotly_chart(fig, use_container_width=True)
        
        # Regional insights
        if 'region' in df.columns:
            st.markdown("### 🌍 地區詳細分析")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**車輛數量排名:**")
                region_counts = df['region'].value_counts().head(10)
                st.dataframe(region_counts.reset_index().rename(columns={'index': '地區', 'region': '車輛數'}))
            
            with col2:
                if 'price_ntd' in df.columns:
                    st.markdown("**平均價格排名:**")
                    region_prices = df.groupby('region')['price_ntd'].mean().sort_values(ascending=False).head(10)
                    # Convert to 萬 units for display
                    region_prices_wan = region_prices / 10000
                    st.dataframe(region_prices_wan.reset_index().rename(columns={'region': '地區', 'price_ntd': '平均價格 (萬)'}))
    
    # Enhanced data exploration section
    st.markdown("---")
    st.subheader("🔍 進階數據探索")
    
    exploration_col1, exploration_col2 = st.columns(2)
    
    with exploration_col1:
        # Custom analysis builder
        st.markdown("### 🛠️ 自定義分析")
        
        available_numeric = [col for col in ['year', 'mileage_km', 'price_ntd', 'views_today', 'views_total'] if col in df.columns]
        available_categorical = [col for col in ['brand', 'series', 'model', 'region', 'fuel', 'transmission', 'color'] if col in df.columns]
        
        if available_numeric and available_categorical:
            x_axis = st.selectbox("X軸 (分類):", available_categorical, key="custom_x")
            y_axis = st.selectbox("Y軸 (數值):", available_numeric, key="custom_y")
            
            if st.button("生成自定義圖表", key="custom_chart"):
                custom_fig = analyzer.create_drill_down_bar_chart(x_axis, y_axis, "自定義分析: ")
                st.plotly_chart(custom_fig, use_container_width=True)
    
    with exploration_col2:
        # Data quality insights
        st.markdown("### 📊 數據品質報告")
        
        total_rows = len(df)
        st.write(f"**總行數:** {total_rows:,}")
        
        # Missing values analysis
        missing_data = df.isnull().sum()
        missing_pct = (missing_data / total_rows * 100).round(2)
        
        quality_df = pd.DataFrame({
            '欄位': missing_data.index,
            '缺失數量': missing_data.values,
            '缺失比例(%)': missing_pct.values
        })
        quality_df = quality_df[quality_df['缺失數量'] > 0].sort_values('缺失比例(%)', ascending=False)
        
        if not quality_df.empty:
            st.dataframe(quality_df)
        else:
            st.success("✅ 沒有缺失值！")
    
    # Data table
    with st.expander("📋 詳細數據表格"):
        # Add search functionality
        search_term = st.text_input("🔍 搜尋 (在標題、品牌、型號中):", key="data_search")
        
        display_df = df.copy()
        if search_term:
            search_columns = [col for col in ['title', 'brand', 'model', 'series'] if col in display_df.columns]
            if search_columns:
                mask = False
                for col in search_columns:
                    mask |= display_df[col].astype(str).str.contains(search_term, case=False, na=False)
                display_df = display_df[mask]
        
        st.write(f"顯示 {len(display_df):,} 筆資料")
        st.dataframe(display_df.head(100))
    
    # Download filtered data
    st.sidebar.subheader("💾 下載數據")
    download_format = st.sidebar.radio("下載格式:", ["CSV", "JSON"], key="download_format")
    
    if st.sidebar.button("準備下載", key="prepare_download"):
        if download_format == "CSV":
            csv_data = df.to_csv(index=False, encoding='utf-8-sig')
            st.sidebar.download_button(
                label="📥 下載 CSV",
                data=csv_data,
                file_name=f"filtered_car_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_csv"
            )
        else:
            json_data = df.to_json(orient='records', force_ascii=False, indent=2)
            st.sidebar.download_button(
                label="📥 下載 JSON",
                data=json_data,
                file_name=f"filtered_car_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_json"
            )

if __name__ == "__main__":
    main()
