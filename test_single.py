import json
from main import process_case

with open('input/EC_001.json', 'r', encoding='utf-8') as f:
    case_data = json.load(f)

result = process_case(case_data)
print(json.dumps(result, indent=2, ensure_ascii=False))
