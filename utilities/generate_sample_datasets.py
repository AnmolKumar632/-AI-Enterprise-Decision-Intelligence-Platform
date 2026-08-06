import os
import datetime
import random
import pandas as pd
import numpy as np

def generate_datasets():
    # Define directories
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', 'samples')
    os.makedirs(sample_dir, exist_ok=True)
    
    sales_path = os.path.join(sample_dir, 'sales_data.csv')
    fraud_path = os.path.join(sample_dir, 'transactional_fraud_data.csv')
    
    random.seed(42)
    np.random.seed(42)
    
    # ----------------------------------------------------
    # DATASET 1: Sales Data (Regression/Classification/Forecasting)
    # ----------------------------------------------------
    sales_rows = 150
    start_date = datetime.date(2025, 1, 1)
    
    dates = [start_date + datetime.timedelta(days=i) for i in range(sales_rows)]
    regions = ['East', 'West', 'North', 'South']
    categories = ['Electronics', 'Office Supplies', 'Furniture']
    products = {
        'Electronics': ['Laptop', 'Smartphone', 'Wireless Mouse', 'Keyboard'],
        'Office Supplies': ['Paper Pack', 'Gel Pens', 'Binder', 'Notebook'],
        'Furniture': ['Office Chair', 'Desk', 'Table Lamp', 'Bookcase']
    }
    
    data_sales = []
    for i in range(sales_rows):
        date_val = dates[i].strftime('%Y-%m-%d')
        region = random.choice(regions)
        category = random.choice(categories)
        product = random.choice(products[category])
        
        # Quantity & Price
        qty = random.randint(1, 10)
        unit_price = round(random.uniform(10.0, 150.0), 2)
        if product == 'Laptop':
            unit_price = round(random.uniform(600.0, 1200.0), 2)
            
        sales = round(qty * unit_price, 2)
        cost = round(sales * random.uniform(0.5, 0.8), 2)
        profit = round(sales - cost, 2)
        
        # Add some random missingness (for cleaning display)
        if i % 15 == 0:
            qty = None
        if i % 20 == 0:
            profit = None
            
        data_sales.append({
            "Date": date_val,
            "Region": region,
            "Category": category,
            "Product": product,
            "Quantity": qty,
            "Unit_Price": unit_price,
            "Sales": sales,
            "Profit": profit
        })
        
    df_sales = pd.DataFrame(data_sales)
    df_sales.to_csv(sales_path, index=False)
    print(f"Generated sample sales dataset at: {sales_path}")
    
    # ----------------------------------------------------
    # DATASET 2: Transactional Fraud Data (Anomaly Detection)
    # ----------------------------------------------------
    fraud_rows = 120
    data_fraud = []
    
    for i in range(fraud_rows):
        txn_id = f"TXN_{10000 + i}"
        amount = round(float(np.random.exponential(scale=150.0)), 2) # Exponential distribution
        age = random.randint(18, 70)
        failed_attempts = random.choices([0, 1, 2, 3], weights=[0.85, 0.10, 0.04, 0.01])[0]
        
        # Inject explicit anomalies/outliers (extreme parameters)
        if i in [15, 42, 78, 105]:
            amount = round(random.uniform(5000.0, 10000.0), 2) # Huge amount outlier
            failed_attempts = 5 # high login attempts
            age = 99
            
        data_fraud.append({
            "Transaction_ID": txn_id,
            "Amount": amount,
            "Age": age,
            "Failed_Login_Attempts": failed_attempts
        })
        
    df_fraud = pd.DataFrame(data_fraud)
    df_fraud.to_csv(fraud_path, index=False)
    print(f"Generated sample anomaly dataset at: {fraud_path}")

if __name__ == '__main__':
    generate_datasets()
