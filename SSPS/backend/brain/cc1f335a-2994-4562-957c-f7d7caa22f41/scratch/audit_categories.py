import sys
import os

# 백엔드 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.engine.category_manager import NAVER_CATEGORY_TREE

def audit_tree():
    stats = {}
    
    def count_nodes(node, depth, domain):
        if domain not in stats:
            stats[domain] = {1: 0, 2: 0, 3: 0, 4: 0}
        
        stats[domain][depth] += 1
        
        if isinstance(node, dict) and "subcategories" in node:
            for sub_name, sub_info in node["subcategories"].items():
                count_nodes(sub_info, depth + 1, domain)

    for domain_name, domain_info in NAVER_CATEGORY_TREE.items():
        count_nodes(domain_info, 1, domain_name)

    print("| 분야 | Depth 1 | Depth 2 | Depth 3 | Depth 4 | 총합 |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for d, s in stats.items():
        total = sum(s.values())
        print(f"| {d} | {s[1]} | {s[2]} | {s[3]} | {s[4]} | {total} |")

if __name__ == "__main__":
    audit_tree()
