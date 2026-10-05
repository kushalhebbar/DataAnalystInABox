"""
Generate a complex test dataset with data quality issues for stress testing the pipeline.
Run: poetry run python code/tests/data/delivery_operations_complex.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_complex_dataset(n_rows=200, seed=42):
    """Generate a complex, stress-test dataset with realistic issues."""
    
    np.random.seed(seed)
    
    # Base parameters
    plants = ['Plant_A', 'Plant_B', 'Plant_C', 'Plant_D']
    regions = ['US_East', 'US_West', 'EU_Central', 'EU_West', 'APAC']
    carriers = ['Carrier_X', 'Carrier_Y', 'Carrier_Z', 'Carrier_W']
    categories = ['Engine', 'Chassis', 'Electrical', 'Interior', 'Suspension']
    priorities = ['Low', 'Medium', 'High', 'Critical']
    
    # Generate base dates
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=int(i)) for i in np.random.rand(n_rows) * 365]
    
    data = {
        'order_id': np.arange(10001, 10001 + n_rows),
        'customer_name': [f'Customer_{i % 50}' for i in range(n_rows)],
        'customer_email': [f'cust_{i % 50}@company.com' if np.random.rand() > 0.1 else np.nan 
                          for i in range(n_rows)],
        'order_date': [d.strftime('%Y-%m-%d') for d in dates],
        'plant': np.random.choice(plants, n_rows),
        'region': np.random.choice(regions, n_rows),
        'carrier': np.random.choice(carriers, n_rows),
        'product_category': np.random.choice(categories, n_rows),
        'planned_delivery_days': np.random.randint(2, 8, n_rows),
        'actual_delivery_days': np.random.randint(1, 12, n_rows),
        'units_shipped': np.random.randint(50, 500, n_rows),
        'shipping_cost_usd': np.random.uniform(500, 5000, n_rows).round(2),
        'priority_flag': np.random.choice(priorities, n_rows),
        'weather_delay': np.random.choice([0, 1, np.nan], n_rows, p=[0.7, 0.2, 0.1]),
        'vehicle_type': np.random.choice(['Truck', 'Van', 'Air', 'Rail', np.nan], n_rows, p=[0.4, 0.3, 0.15, 0.1, 0.05]),
        'avg_temp_celsius': np.random.uniform(-10, 40, n_rows).round(1),
        'humidity_pct': np.random.uniform(20, 95, n_rows).round(1),
    }
    
    df = pd.DataFrame(data)
    
    # Add calculated/derived column
    df['late_delivery'] = ((df['actual_delivery_days'] > df['planned_delivery_days']).astype(int))
    
    # Add outliers and data quality issues
    # 1. Outliers in shipping cost
    outlier_indices = np.random.choice(n_rows, size=int(0.05 * n_rows), replace=False)
    df.loc[outlier_indices, 'shipping_cost_usd'] = df.loc[outlier_indices, 'shipping_cost_usd'] * 10
    
    # 2. Duplicate rows
    dup_idx = np.random.choice(n_rows, size=5, replace=False)
    df = pd.concat([df, df.iloc[dup_idx].reset_index(drop=True)], ignore_index=True)
    
    # 3. More missing values
    missing_indices = np.random.choice(len(df), size=int(0.05 * len(df)), replace=False)
    df.loc[missing_indices, 'units_shipped'] = np.nan
    
    missing_indices = np.random.choice(len(df), size=int(0.03 * len(df)), replace=False)
    df.loc[missing_indices, 'shipping_cost_usd'] = np.nan
    
    # 4. Impossible values (data entry errors)
    df.loc[0, 'actual_delivery_days'] = -1
    df.loc[1, 'humidity_pct'] = 150
    
    # 5. Inconsistencies
    df.loc[2, 'planned_delivery_days'] = 0
    
    # Shuffle rows
    df = df.sample(frac=1).reset_index(drop=True)
    
    return df


if __name__ == '__main__':
    df = generate_complex_dataset(n_rows=200)
    
    output_path = os.path.dirname(__file__) + '/delivery_operations_complex.csv'
    df.to_csv(output_path, index=False)
    
    print(f"Generated complex dataset: {output_path}")
    print(f"  Rows: {len(df)}, Cols: {df.shape[1]}")
    print(f"  Missing values: {df.isna().sum().sum()}")
    print(f"  Duplicates: {df.duplicated().sum()}")
