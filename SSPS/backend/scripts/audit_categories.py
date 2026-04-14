import json
import pandas as pd
from collections import Counter

def audit():
    repo_file = 'c:/Antigravity Work/backend/data/category_master_import.json'
    with open(repo_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    categories = data['categories']
    
    # 1. Depth distribution
    depths = Counter([c['depth'] for c in categories])
    
    # 2. Duplicate names analysis
    name_to_paths = {}
    for c in categories:
        name = c['name_ko']
        path = c['full_path']
        if name not in name_to_paths:
            name_to_paths[name] = []
        name_to_paths[name].append(path)
    
    ambiguous_names = {k: v for k, v in name_to_paths.items() if len(v) > 1}
    
    # 3. Parent-Child integrity
    orphans = []
    id_map = {c['naver_cat_id']: c for c in categories}
    for c in categories:
        if c['parent_id'] and c['parent_id'] not in id_map:
            orphans.append(c)
            
    # 4. Source analysis
    sources = Counter([c.get('source_type', 'unknown') for c in categories])
    
    audit_results = {
        "summary": {
            "total_nodes": len(categories),
            "depth_distribution": dict(depths),
            "source_distribution": dict(sources)
        },
        "ambiguity": {
            "ambiguous_names_count": len(ambiguous_names),
            "examples": {k: ambiguous_names[k] for k in list(ambiguous_names.keys())[:10]}
        },
        "integrity": {
            "orphan_count": len(orphans),
            "orphans": orphans[:5]
        }
    }
    
    with open('c:/Antigravity Work/backend/data/audit_report.json', 'w', encoding='utf-8') as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    audit()
