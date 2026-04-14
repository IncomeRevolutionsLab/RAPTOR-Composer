import os

def audit_manually():
    with open("backend/engine/category_manager.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple count of subcategory entries
    subcat_count = content.count('"subcategories":')
    print(f"Current Hardcoded Nodes with subcategories: {subcat_count}")
    
    # Count specific nodes in Beauty
    beauty_start = content.find('"화장품/미용":')
    beauty_end = content.find('"디지털/가전":')
    beauty_content = content[beauty_start:beauty_end]
    print(f"Beauty Nodes (Manual count check): {beauty_content.count('{')}")

if __name__ == "__main__":
    audit_manually()
