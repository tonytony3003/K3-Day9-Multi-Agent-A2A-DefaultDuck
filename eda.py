import pandas as pd
import glob
import json

orders = pd.read_csv('data/olist_orders_dataset.csv')
items = pd.read_csv('data/olist_order_items_dataset.csv')
payments = pd.read_csv('data/olist_order_payments_dataset.csv')

def eda():
    files = glob.glob('input/EC_*.json')
    cases = []
    for f in files:
        with open(f, 'r', encoding='utf-8') as file:
            cases.append(json.load(file))
            
    print(f"Total cases: {len(cases)}")
    
    missing_customer_date = 0
    missing_carrier_date = 0
    statuses = set()
    
    for case in cases:
        order_id = case['customer_request']['claimed_order_id']
        o_row = orders[orders['order_id'] == order_id]
        if o_row.empty:
            print(f"Order {order_id} not found!")
            continue
            
        statuses.add(o_row['order_status'].iloc[0])
        
        if pd.isna(o_row['order_delivered_customer_date'].iloc[0]):
            missing_customer_date += 1
        if pd.isna(o_row['order_delivered_carrier_date'].iloc[0]):
            missing_carrier_date += 1
            
    print(f"Statuses in 50 cases: {statuses}")
    print(f"Missing customer delivery dates: {missing_customer_date}")
    print(f"Missing carrier delivery dates: {missing_carrier_date}")

if __name__ == '__main__':
    eda()
