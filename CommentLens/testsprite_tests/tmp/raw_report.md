
# TestSprite AI Testing Report(MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** youtube-comment-analyzer
- **Date:** 2026-04-25
- **Prepared by:** TestSprite AI Team

---

## 2️⃣ Requirement Validation Summary

#### Test TC001 get_root_dashboard
- **Test Code:** [TC001_get_root_dashboard.py](./TC001_get_root_dashboard.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/affc9af3-ac23-44a1-9e3b-497f8ff8294e
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC002 post_start_comment_collection
- **Test Code:** [TC002_post_start_comment_collection.py](./TC002_post_start_comment_collection.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 39, in <module>
  File "<string>", line 36, in test_post_start_comment_collection
AssertionError: Expected status 'started' but got 'accepted'

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/21129af6-4360-4bef-8575-ec0c81a27216
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC003 get_collection_status
- **Test Code:** [TC003_get_collection_status.py](./TC003_get_collection_status.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/695cc1be-aba2-4fc3-87ae-9d071ede6f30
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC004 post_stop_collection_task
- **Test Code:** [TC004_post_stop_collection_task.py](./TC004_post_stop_collection_task.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 41, in <module>
  File "<string>", line 16, in test_post_stop_collection_task
AssertionError: Missing task_id or incorrect status in start response

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/56e3a879-6144-472d-8da4-9e0f3516dfc0
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC005 get_collection_history
- **Test Code:** [TC005_get_collection_history.py](./TC005_get_collection_history.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/46466cbe-9b82-4c2b-a811-9d790fee1074
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC006 post_analysis_preprocess
- **Test Code:** [TC006_post_analysis_preprocess.py](./TC006_post_analysis_preprocess.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 53, in <module>
  File "<string>", line 31, in test_post_analysis_preprocess
  File "<string>", line 17, in create_collection
AssertionError: Expected status 'started', got accepted

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/adc57277-baad-47e9-8563-d330f14c7d59
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC007 post_analysis_preprocess_bad_input
- **Test Code:** [TC007_post_analysis_preprocess_bad_input.py](./TC007_post_analysis_preprocess_bad_input.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 61, in <module>
  File "<string>", line 45, in test_post_analysis_preprocess_bad_input
AssertionError: Response JSON has neither 'error' nor 'detail' key

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/2ff08f5b-bb83-42d5-98c8-b1f3643a5cef
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC008 post_analysis_hybrid_pipeline
- **Test Code:** [TC008_post_analysis_hybrid_pipeline.py](./TC008_post_analysis_hybrid_pipeline.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/6625487c-76fb-4cd6-95e5-dddbe4ec5954
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC009 post_analysis_hybrid_llm_skipped
- **Test Code:** [TC009_post_analysis_hybrid_llm_skipped.py](./TC009_post_analysis_hybrid_llm_skipped.py)
- **Test Error:** Traceback (most recent call last):
  File "/var/task/handler.py", line 258, in run_with_retry
    exec(code, exec_env)
  File "<string>", line 59, in <module>
  File "<string>", line 56, in test_post_analysis_hybrid_llm_skipped
AssertionError: Results do not indicate that LLM was skipped and fallback used

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/1ce72e0b-77ce-4078-b4dc-6fbb2cdd2733
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC010 post_analysis_sna_mode
- **Test Code:** [TC010_post_analysis_sna_mode.py](./TC010_post_analysis_sna_mode.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/acdc9c70-2d97-4fca-aaae-5cf9b8249258/f95f110d-7a67-4dcb-a3c3-850879789d74
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---


## 3️⃣ Coverage & Matching Metrics

- **50.00** of tests passed

| Requirement        | Total Tests | ✅ Passed | ❌ Failed  |
|--------------------|-------------|-----------|------------|
| ...                | ...         | ...       | ...        |
---


## 4️⃣ Key Gaps / Risks
{AI_GNERATED_KET_GAPS_AND_RISKS}
---