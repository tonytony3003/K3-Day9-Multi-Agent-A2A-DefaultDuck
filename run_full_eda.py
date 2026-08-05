import pandas as pd
import json
import glob
import os

def analyze():
    # Load data
    orders = pd.read_csv('data/olist_orders_dataset.csv')
    items = pd.read_csv('data/olist_order_items_dataset.csv')
    payments = pd.read_csv('data/olist_order_payments_dataset.csv')
    
    input_files = glob.glob('input/EC_*.json')
    output_files = glob.glob('output/EC_*.json')
    
    analysis = {
        "total_cases": len(input_files),
        "issues": {},
        "statuses": {},
        "total_refund_brl": 0.0,
        "actions": {},
        "causes": {}
    }
    
    for f in output_files:
        with open(f, 'r', encoding='utf-8') as file:
            res = json.load(file)
            
        issue = res['assessment']['primary_issue']
        analysis['issues'][issue] = analysis['issues'].get(issue, 0) + 1
        
        status = res['assessment']['case_status']
        analysis['statuses'][status] = analysis['statuses'].get(status, 0) + 1
        
        analysis['total_refund_brl'] += res['financial_resolution']['recommended_refund_brl']
        
        for action in res['resolution_actions']:
            analysis['actions'][action] = analysis['actions'].get(action, 0) + 1
            
        for cause in res['root_cause_analysis']['ranked_causes']:
            c_code = cause['cause_code']
            analysis['causes'][c_code] = analysis['causes'].get(c_code, 0) + 1
            
    with open('eda_results.json', 'w') as f:
        json.dump(analysis, f, indent=2)
        
    print("EDA completed. Results saved to eda_results.json.")

if __name__ == "__main__":
    analyze()
