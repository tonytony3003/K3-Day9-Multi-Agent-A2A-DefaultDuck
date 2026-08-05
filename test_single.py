import json
from main import process_case

if __name__ == '__main__':
    with open('input/EC_001.json', 'r', encoding='utf-8') as f:
        case_data = json.load(f)
        
    print("Testing case EC_001.json...")
    result = process_case(case_data)
    
    print("\nFINAL RESULT JSON:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
