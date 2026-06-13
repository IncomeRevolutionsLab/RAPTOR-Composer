
# TestSprite AI Testing Report(MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** SSPS
- **Date:** 2026-05-02
- **Prepared by:** TestSprite AI Team

---

## 2️⃣ Requirement Validation Summary

#### Test TC001 View real-time stats and data freshness on dashboard load
- **Test Code:** [TC001_View_real_time_stats_and_data_freshness_on_dashboard_load.py](./TC001_View_real_time_stats_and_data_freshness_on_dashboard_load.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/35bae5ab-d5cf-4510-b248-6b6f32a7b0af
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC002 View the 3D trend chart on dashboard load
- **Test Code:** [TC002_View_the_3D_trend_chart_on_dashboard_load.py](./TC002_View_the_3D_trend_chart_on_dashboard_load.py)
- **Test Error:** TEST FAILURE

The 3D trend visualization did not render on initial dashboard load.

Observations:
- No <canvas> elements or WebGL/three.js renderer markers were found in the page DOM.
- The main visualization panels are empty placeholders; only small SVG elements (color legend) are present.

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/5ba38c70-d1cc-47f6-84c6-f795051927b6
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC003 Open a domain time-series detail by selecting a chart point
- **Test Code:** [TC003_Open_a_domain_time_series_detail_by_selecting_a_chart_point.py](./TC003_Open_a_domain_time_series_detail_by_selecting_a_chart_point.py)
- **Test Error:** TEST FAILURE

Selecting a point in the 3D trend visualization did not reveal time-series details for the chosen domain.

Observations:
- Clicked the chart SVG (index 1448) and no detail pane or time-series chart appeared.
- The large trend panel area remained empty after the click.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/19e8db04-4216-4ca3-8657-cadca02449bd
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC004 Run N-depth analysis from a category keyword and review results
- **Test Code:** [TC004_Run_N_depth_analysis_from_a_category_keyword_and_review_results.py](./TC004_Run_N_depth_analysis_from_a_category_keyword_and_review_results.py)
- **Test Error:** TEST FAILURE

The category analysis UI did not display the N-depth category path/tree or the focused trend chart after submitting 'wireless earbuds'.

Observations:
- The results page shows a product list for 'wireless earbuds'.
- No N-depth category path/tree control or category path was found on the page after multiple scroll/search attempts.
- No focused trend chart or '관련 키워드' section was found on the page.

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/fe8dd8c9-a7ea-42db-9093-bbf4098bf5bf
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC005 Start analysis from a popular keyword chip
- **Test Code:** [TC005_Start_analysis_from_a_popular_keyword_chip.py](./TC005_Start_analysis_from_a_popular_keyword_chip.py)
- **Test Error:** TEST FAILURE

Selecting a popular keyword chip did not fully update the analysis view — the product list updated but the focused trend chart for the selected keyword did not appear.

Observations:
- The product list updated and shows items for '경량패딩' (e.g., '경량패딩 분석' and product items).
- No chart title, legend entry, or series label mentions '경량패딩' — focused trend chart not found.
- Clicking the '분석' button started analysis UI but did not produce a labeled focused trend chart for the keyword.

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/a2081680-463c-4921-adb0-6be068bc1e38
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC006 See collection progress indicators during rolling updates
- **Test Code:** [TC006_See_collection_progress_indicators_during_rolling_updates.py](./TC006_See_collection_progress_indicators_during_rolling_updates.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/f3ec4824-6fea-4731-9244-08789eeb7a84
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC007 Rotate or pan the 3D trend view to inspect different slices
- **Test Code:** [TC007_Rotate_or_pan_the_3D_trend_view_to_inspect_different_slices.py](./TC007_Rotate_or_pan_the_3D_trend_view_to_inspect_different_slices.py)
- **Test Error:** TEST FAILURE

Users cannot rotate or pan the 3D trend visualization — interactions do not update the view.

Observations:
- Clicking the visualization's SVG (index 218) and sending ArrowLeft produced no visible view change.
- An opaque triangular/play overlay is present and appears to intercept interactions.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/64a099fc-bede-43ff-9d0d-65ed03d36aaa
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC008 Iterate on N-depth analysis by refining the keyword fragment
- **Test Code:** [TC008_Iterate_on_N_depth_analysis_by_refining_the_keyword_fragment.py](./TC008_Iterate_on_N_depth_analysis_by_refining_the_keyword_fragment.py)
- **Test Error:** TEST BLOCKED

The feature could not be reached — the category/keyword input field and submit control needed to refine the search were not identifiable in the visible interactive elements, so I cannot enter "protein bar" and re-run the analysis.

Observations:
- The page shows the results for the previous 'protein' analysis, but the category/keyword input and the submit button indexes are not present in the interactive element list.
- Without the input or submit element index I cannot perform the keyword refinement and re-run the analysis.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/c15d278e-e541-4e5d-84c3-cbcbed9d3a52
- **Status:** BLOCKED
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC009 Browse popular keywords and switch between chips
- **Test Code:** [TC009_Browse_popular_keywords_and_switch_between_chips.py](./TC009_Browse_popular_keywords_and_switch_between_chips.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/95a28037-210e-4c83-bfe5-265fb967d9c4
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC010 Identify which keywords are currently most collected
- **Test Code:** [TC010_Identify_which_keywords_are_currently_most_collected.py](./TC010_Identify_which_keywords_are_currently_most_collected.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/7fc307b1-b0c3-4d20-9b1b-6c8d5120d0e0
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC011 Generate a short-form plan from a keyword input
- **Test Code:** [TC011_Generate_a_short_form_plan_from_a_keyword_input.py](./TC011_Generate_a_short_form_plan_from_a_keyword_input.py)
- **Test Error:** TEST BLOCKED

The feature required to run this test is not present on the RAPTOR page, so the requested workflow cannot be executed.

Observations:
- The page displays a target duration slider, AI engine and video engine selects, and a '명품 기획안 생성 시작' button.
- No text input or keyword field is present to submit a keyword.
- The '데이터 가져오기 (SSPS)' control shows connection/pending state which may indicate external data is not available.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/dad887ff-d005-4dac-9272-00b37a9c54a9
- **Status:** BLOCKED
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC012 Regenerate a plan after refining the input
- **Test Code:** [TC012_Regenerate_a_plan_after_refining_the_input.py](./TC012_Regenerate_a_plan_after_refining_the_input.py)
- **Test Error:** TEST FAILURE

Refining the RAPTOR input and requesting regeneration could not be tested because the necessary keyword/refinement input fields are not available on the RAPTOR page.

Observations:
- The RAPTOR panel shows '연결 대기 중...' and a '데이터 가져오기 (SSPS)' button, but no keyword or refinement text fields are present.
- Clicking '데이터 가져오기 (SSPS)' multiple times (3 attempts) did not change the UI or reveal those input fields.

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/29ba3ff4-b531-47bc-a43c-66959adebf74
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC013 Chip selection is reflected consistently in analysis area
- **Test Code:** [TC013_Chip_selection_is_reflected_consistently_in_analysis_area.py](./TC013_Chip_selection_is_reflected_consistently_in_analysis_area.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/48b7127f-dfe7-43cd-8076-3bb01b2aecf9
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC014 Explore returned category path and drill into listed products or keywords
- **Test Code:** [TC014_Explore_returned_category_path_and_drill_into_listed_products_or_keywords.py](./TC014_Explore_returned_category_path_and_drill_into_listed_products_or_keywords.py)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/03b3d771-70ea-45d0-a2ca-350ecdecfee6
- **Status:** ✅ Passed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC015 Navigate between dashboard and RAPTOR without losing input expectations
- **Test Code:** [TC015_Navigate_between_dashboard_and_RAPTOR_without_losing_input_expectations.py](./TC015_Navigate_between_dashboard_and_RAPTOR_without_losing_input_expectations.py)
- **Test Error:** TEST FAILURE

The RAPTOR keyword/text input field required to enter a generation keyword is missing, so the test cannot complete the intended verification of entering a keyword and confirming round-trip navigation behavior.

Observations:
- The left-side panel shows the target duration slider, AI Planning Engine select, Video Synthesis select, and a '명품 기획안 생성 시작' (generate) button, but there is no visible text/keyword input field.
- There is a button labeled 'SSPS 시장 분석으로 이동' (to go to SSPS/dashboard), but without the keyword input the test objective to enter new input cannot be executed.

- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/caf643bd-2f58-4731-b7ad-aedebe0dd4cd/13760eb6-d8e6-4d0f-bf72-ed0225d3b437
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---


## 3️⃣ Coverage & Matching Metrics

- **40.00** of tests passed

| Requirement        | Total Tests | ✅ Passed | ❌ Failed  |
|--------------------|-------------|-----------|------------|
| ...                | ...         | ...       | ...        |
---


## 4️⃣ Key Gaps / Risks
{AI_GNERATED_KET_GAPS_AND_RISKS}
---