# TestSprite AI Testing Report (MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** SSPS
- **Date:** 2026-05-02
- **Prepared by:** TestSprite AI Team
- **Test Scope:** Frontend & Integration (Development Environment)

---

## 2️⃣ Requirement Validation Summary

### Requirement 1: Dashboard Visualization & 3D Trend Chart
#### Test TC001 View real-time stats and data freshness on dashboard load
- **Status:** ✅ Passed
- **Analysis / Findings:** The dashboard correctly retrieves and displays the real-time statistics and data freshness indicator upon load.

#### Test TC002 View the 3D trend chart on dashboard load
- **Status:** ❌ Failed
- **Analysis / Findings:** ECharts 3D visualization is failing to render. The DOM lacks the WebGL `<canvas>` elements, indicating a possible missing dependency (`echarts-gl`) or a script execution error in rendering the 3D map.

#### Test TC007 Rotate or pan the 3D trend view to inspect different slices
- **Status:** ❌ Failed
- **Analysis / Findings:** Since the 3D chart (TC002) fails to render, panning and rotation interactions are naturally unavailable. An opaque overlay was also observed intercepting events.

#### Test TC003 Open a domain time-series detail by selecting a chart point
- **Status:** ❌ Failed
- **Analysis / Findings:** Clicking the placeholder SVG does not trigger the expected time-series detail pane, likely due to the failure of the 3D chart initialization.

---

### Requirement 2: Keyword Analysis & Category Routing (N-Depth / Phase 1 & 2)
#### Test TC004 Run N-depth analysis from a category keyword and review results
- **Status:** ❌ Failed
- **Analysis / Findings:** The test expected an N-depth category tree (Phase 1) and a trend chart for the keyword 'wireless earbuds'. However, the system correctly identified it as a leaf node and routed it to the product list (Phase 2), causing a test expectation mismatch.

#### Test TC005 Start analysis from a popular keyword chip
- **Status:** ❌ Failed
- **Analysis / Findings:** The mock data injection logic succeeded, and the product list for '경량패딩' successfully updated. However, the test failed because it also expected a focused trend chart, which is not part of the Phase 2 (Leaf Node) UI design.

#### Test TC008 Iterate on N-depth analysis by refining the keyword fragment
- **Status:** 🚫 BLOCKED
- **Analysis / Findings:** The interactive text input field for refining searches was not found by the testing agent within the expected N-depth analysis view.

#### Test TC013 Chip selection is reflected consistently in analysis area
- **Status:** ✅ Passed
- **Analysis / Findings:** The system correctly responds to keyword chip selections.

#### Test TC014 Explore returned category path and drill into listed products or keywords
- **Status:** ✅ Passed
- **Analysis / Findings:** The system properly drills down into category paths and displays associated elements.

---

### Requirement 3: Data Collection & System Status
#### Test TC006 See collection progress indicators during rolling updates
- **Status:** ✅ Passed
- **Analysis / Findings:** Progress indicators are clearly visible and function as intended during updates.

#### Test TC009 Browse popular keywords and switch between chips
- **Status:** ✅ Passed
- **Analysis / Findings:** Popular keyword chips load and allow switching seamlessly.

#### Test TC010 Identify which keywords are currently most collected
- **Status:** ✅ Passed
- **Analysis / Findings:** The UI clearly identifies the most collected keywords from the data pipeline.

---

### Requirement 4: RAPTOR AI Planning Engine Integration
#### Test TC011 Generate a short-form plan from a keyword input
- **Status:** 🚫 BLOCKED
- **Analysis / Findings:** The test expects a standalone keyword text input on the RAPTOR panel. However, the application design requires users to click the "RAPTOR 기획" button from a product card (Phase 2) to pass the data, rather than typing a keyword manually.

#### Test TC012 Regenerate a plan after refining the input
- **Status:** ❌ Failed
- **Analysis / Findings:** Fails for the same reason as TC011; no manual keyword refinement input exists on the RAPTOR page itself.

#### Test TC015 Navigate between dashboard and RAPTOR without losing input expectations
- **Status:** ❌ Failed
- **Analysis / Findings:** Navigation works, but the test fails because it cannot find the text input field to verify the preservation of input state.

---

## 3️⃣ Coverage & Matching Metrics

- **Total Tests:** 15
- **Passed:** 6 (40.00%)
- **Failed:** 7
- **Blocked:** 2

| Requirement                                 | Total Tests | ✅ Passed | ❌ Failed | 🚫 Blocked |
|---------------------------------------------|-------------|-----------|-----------|------------|
| 1. Dashboard & 3D Trend Chart               | 4           | 1         | 3         | 0          |
| 2. Keyword Analysis & Category Routing      | 5           | 2         | 2         | 1          |
| 3. Data Collection & System Status          | 3           | 3         | 0         | 0          |
| 4. RAPTOR AI Engine Integration             | 3           | 0         | 2         | 1          |

---

## 4️⃣ Key Gaps / Risks

1. **Test Expectation vs. UI Design Mismatch:**
   - Tests expecting trend charts in the Leaf Node view (Phase 2) are failing (e.g., TC005). The current UI correctly replaces the trend chart with the Top 10 Product Grid when a specific product is searched.
   - Tests expecting manual text inputs on the RAPTOR page are failing (TC011, TC012, TC015). The current architecture relies on passing product payload data via button clicks instead of manual text entry.
2. **ECharts 3D Rendering Issue:**
   - The 3D trend chart fails to load `WebGL/canvas` (TC002, TC003, TC007). This indicates either missing libraries (like `echarts-gl.min.js`) in `index.html` or a script execution failure during the initialization of the 3D scatter/bar plot.
3. **Data Availability in Tests:**
   - The mock data injection successfully unblocked product rendering, proving the frontend logic works. However, alignment is needed between the automated test steps and the actual intended user workflows.
