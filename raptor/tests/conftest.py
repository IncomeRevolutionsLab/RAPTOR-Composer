import pytest
import os
import json
import re
from datetime import datetime, timedelta

class MockResponse:
    def __init__(self, data):
        self.data = data

class MockQuery:
    def __init__(self, table_name):
        self.table_name = table_name
        self.filters = []
        self._order = None
        self._limit = None
        self._select_cols = "*"

    def select(self, cols="*"):
        self._select_cols = cols
        return self

    def insert(self, data):
        self._insert_data = data
        return self

    def update(self, data):
        self._update_data = data
        return self

    def delete(self):
        self._delete_op = True
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def neq(self, field, value):
        self.filters.append(("neq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, values))
        return self

    def like(self, field, pattern):
        self.filters.append(("like", field, pattern))
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def limit(self, count):
        self._limit = count
        return self

    def execute(self):
        db_path = os.environ.get("DATABASE_PATH", "test_user_videos.json")
        records = []
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except:
                records = []

        # 1. Insert 처리
        if hasattr(self, "_insert_data"):
            data = self._insert_data
            if self.table_name == "projects":
                proj_id = data.get("project_id")
                existing = next((r for r in records if r.get("project_id") == proj_id), None)
                if existing:
                    existing.update(data)
                else:
                    if "task_id" not in data:
                        data["task_id"] = f"task_{proj_id}"
                    if "status" not in data:
                        data["status"] = "pending"
                    records.append(data)
            elif self.table_name == "tasks":
                task_id = data.get("task_id")
                proj_id = data.get("project_id")
                proj_rec = next((r for r in records if r.get("project_id") == proj_id or r.get("task_id") == task_id), None)
                if proj_rec:
                    proj_rec.update(data)
                    if "expires_at" not in proj_rec and (proj_rec.get("status") == "completed" or proj_rec.get("status") == "success"):
                        proj_rec["expires_at"] = (datetime.utcnow() + timedelta(days=14)).isoformat()
                else:
                    if "expires_at" not in data and (data.get("status") == "completed" or data.get("status") == "success"):
                        data["expires_at"] = (datetime.utcnow() + timedelta(days=14)).isoformat()
                    records.append(data)
            else:
                records.append(data)

            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(records, f)
            return MockResponse([data])

        filtered = list(records)
        
        # 2. Update 처리
        if hasattr(self, "_update_data"):
            updated_any = []
            for r in filtered:
                match = True
                for op, field, val in self.filters:
                    r_val = r.get(field)
                    if field == "task_id" and not r_val and r.get("project_id"):
                        r_val = f"task_{r.get('project_id')}"
                    if op == "eq" and r_val != val:
                        match = False
                    elif op == "in" and r_val not in val:
                        match = False
                if match:
                    r.update(self._update_data)
                    if "expires_at" not in r and (r.get("status") == "completed" or r.get("status") == "success" or self._update_data.get("status") == "completed"):
                        r["expires_at"] = (datetime.utcnow() + timedelta(days=14)).isoformat()
                    updated_any.append(r)
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(records, f)
            return MockResponse(updated_any)

        # 3. Delete 처리
        if hasattr(self, "_delete_op"):
            remaining = []
            deleted = []
            for r in records:
                match = True
                for op, field, val in self.filters:
                    r_val = r.get(field)
                    if field == "project_id" and not r_val and r.get("task_id"):
                        r_val = f"proj_{r.get('task_id')}"
                    
                    if op == "eq" and r_val != val:
                        match = False
                    elif op == "in" and r_val not in val:
                        match = False
                if match:
                    deleted.append(r)
                else:
                    remaining.append(r)
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(remaining, f)
            return MockResponse(deleted)

        res_data = []
        for r in filtered:
            match = True
            for op, field, val in self.filters:
                if op == "eq":
                    r_val = r.get(field)
                    if field == "user_id" and r_val != val:
                        match = False
                    elif field == "task_id":
                        if not r_val and r.get("project_id"):
                            r_val = f"task_{r.get('project_id')}"
                        if r_val != val:
                            match = False
                    elif field == "project_id" and r.get("project_id") != val:
                        match = False
                elif op == "in":
                    r_val = r.get(field)
                    if field == "project_id" and not r_val and r.get("task_id"):
                        r_val = f"proj_{r.get('task_id')}"
                    if r_val not in val:
                        match = False
            if match:
                res_data.append(r)

        if self._select_cols == "*, tasks(*)":
            proj_dict = {}
            for r in res_data:
                p_id = r.get("project_id") or f"proj_{r.get('task_id')}"
                if p_id not in proj_dict:
                    proj_dict[p_id] = {
                        "project_id": p_id,
                        "product_name": r.get("product_name") or "Test Product",
                        "created_at": r.get("created_at"),
                        "user_id": r.get("user_id"),
                        "plan_snapshot": r.get("plan_snapshot") or {},
                        "tasks": []
                    }
                if r.get("task_id"):
                    proj_dict[p_id]["tasks"].append({
                        "task_id": r.get("task_id"),
                        "project_id": p_id,
                        "task_type": r.get("task_type") or "final_render",
                        "description": r.get("description") or r.get("product_name"),
                        "status": r.get("status"),
                        "result_url": r.get("result_url"),
                        "error": r.get("error"),
                        "created_at": r.get("created_at")
                    })
            return MockResponse(list(proj_dict.values()))

        final_list = []
        for r in res_data:
            if self.table_name == "projects":
                p_id = r.get("project_id") or f"proj_{r.get('task_id')}"
                final_list.append({
                    "project_id": p_id,
                    "product_name": r.get("product_name"),
                    "created_at": r.get("created_at"),
                    "user_id": r.get("user_id"),
                    "plan_snapshot": r.get("plan_snapshot")
                })
            elif self.table_name == "tasks":
                p_id = r.get("project_id") or f"proj_{r.get('task_id')}"
                final_list.append({
                    "task_id": r.get("task_id"),
                    "project_id": p_id,
                    "task_type": r.get("task_type") or "final_render",
                    "description": r.get("description") or r.get("product_name"),
                    "status": r.get("status"),
                    "result_url": r.get("result_url"),
                    "error": r.get("error"),
                    "created_at": r.get("created_at")
                })
            else:
                final_list.append(r)

        return MockResponse(final_list)

class MockStorageBucket:
    def upload(self, *args, **kwargs):
        return True
    def remove(self, *args, **kwargs):
        return True

class MockStorage:
    def from_(self, bucket_name):
        return MockStorageBucket()

class MockSupabaseClient:
    def __init__(self):
        self.storage = MockStorage()
    def table(self, table_name):
        return MockQuery(table_name)

@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    mock_client = MockSupabaseClient()
    import main
    monkeypatch.setattr(main, "supabase", mock_client)
    
    # Mock sanitize_uuid for tests
    def mock_sanitize_uuid(user_id_str):
        uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        if uuid_pattern.match(user_id_str) or user_id_str == "beta_tester":
            return user_id_str
        return "4dc22913-6cd4-41c3-b3c7-14256a05183f"
        
    monkeypatch.setattr(main, "sanitize_uuid", mock_sanitize_uuid)
    
    # Inject dependency override for JWT user verification to support legacy tests
    main.app.dependency_overrides[main.get_jwt_user_id] = lambda: "beta_tester"
