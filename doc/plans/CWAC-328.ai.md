## Plan: Axe XLSX Export

Add a post-scan XLSX exporter for axe-core results that writes ./results/<audit_name>/axe_core_audit.xlsx after the scan completes. Recommend xlsxwriter as the primary engine because this feature needs more than plain DataFrame export: two worksheets, Excel formulas, formatting, tables, and optional embedded charts. Keep the first implementation scoped to axe_core_audit.csv only, with Sheet 1 as the raw CSV data and Sheet 2 as a statistics sheet whose values are computed from Sheet 1. Treat every CSV-derived cell value as untrusted input and design the export so raw data is stored as literal text or numbers, not attacker-controlled formulas, links, or macros.

**Steps**
1. Confirm the export contract and keep scope tight: generate one workbook named ./results/<audit_name>/axe_core_audit.xlsx; use exactly two worksheets named Raw Data and Statistics; skip generation with a logged warning when ./results/<audit_name>/axe_core_audit.csv is absent. This step blocks the rest because sheet names, filename, and missing-file behavior affect tests, docs, and formulas.
2. Add the XLSX dependency to /Users/eoinkelly/Developer/repos/cwac/pyproject.toml and /Users/eoinkelly/Developer/repos/cwac/requirements.txt. Recommended dependency: xlsxwriter pinned to a current compatible version. Recommendation rationale: CWAC writes a brand-new workbook at the end of a run, so xlsxwriter’s stronger write-only API for formulas, tables, and charts is a better fit than openpyxl’s read/modify strengths.
3. Add a new exporter function in /Users/eoinkelly/Developer/repos/cwac/src/output.py, for example generate_axe_core_xlsx_results(audit_name: str). This function should read ./results/<audit_name>/axe_core_audit.csv into pandas, open a pandas.ExcelWriter with engine="xlsxwriter", and configure the workbook so untrusted strings are not auto-promoted into formulas or hyperlinks. Recommended approach: pass XlsxWriter workbook options that disable automatic string-to-formula and string-to-URL conversion, and ensure any custom raw-cell writes use explicit string-writing APIs for untrusted text. Then write the raw data to the Raw Data sheet and apply workbook-level formatting such as freeze panes, autofilter/table formatting, sensible column widths, and text wrapping only where needed. This depends on step 2.
4. Add spreadsheet-injection hardening requirements to the exporter design. The source CSV contains page-derived values such as url, page_title, html, target, help, and helpUrl, which should be treated as attacker-controlled content. A malicious page could cause a CSV field to begin with =, +, -, @, tab, carriage return, or line feed, which some spreadsheet software may interpret as a formula if the exporter writes it using generic string handling. Recommendation: prevent formula and hyperlink auto-detection at the workbook writer level and never feed CSV-derived text into workbook features that create executable behavior, such as formulas, macros, buttons, or external links. Also note explicitly in the plan that cell text alone cannot embed a VBA macro into a newly generated .xlsx file; macro risk would only arise if the implementation intentionally adds a VBA project or macro-enabled workbook features, which this story should exclude. This depends on step 3 and blocks final raw-sheet writing decisions.
5. Write Sheet 1 as an Excel table rather than a plain grid. Name the table something stable such as AxeRawData and build all downstream formulas from structured references like AxeRawData[num_issues] instead of hard-coded A1 ranges. This avoids formula breakage when the number of rows changes across scans. This depends on step 4.
6. Build the Statistics sheet in /Users/eoinkelly/Developer/repos/cwac/src/output.py using conservative Excel formulas that are broadly compatible. Recommended MVP statistics:
   1. Total result rows from Raw Data.
   2. Total issue count from the num_issues column.
   3. Rows with issues versus rows with zero issues.
   4. Counts by impact using COUNTIF against the impact column.
   5. Counts by best-practice flag using COUNTIF against the best-practice column.
   6. Optional top-rule summary table using a Python-generated unique rule-id list in the Statistics sheet plus COUNTIF or SUMIF formulas against Raw Data.
   Use classic formulas such as COUNTA, SUM, COUNTIF, COUNTIFS, SUMIF, and SUMIFS for the first pass. Avoid Excel 365-only dynamic-array functions such as UNIQUE, FILTER, SORT, and XLOOKUP in the initial implementation because they complicate compatibility and can require future-function handling.
7. Generate chart-ready helper tables inside the Statistics sheet and optionally hide or place them below the visible summary area. Recommended chart options:
   1. Embedded clustered column chart for counts by impact.
   2. Embedded horizontal bar chart for top 10 axe rule IDs by issue count.
   3. Optional pie or doughnut chart for best-practice versus WCAG rows.
   Recommendation: embed charts in the Statistics sheet instead of creating a third Charts sheet, because the story currently specifies two tabs only. This step can run in parallel with some of the presentation formatting in step 6 once the summary-table layout is fixed.
8. Wire the exporter into the post-scan flow in /Users/eoinkelly/Developer/repos/cwac/cwac.py immediately after generate_axe_core_template_aware_results(self.config.audit_name). Use the same style of guarded post-processing already present there: catch FileNotFoundError and log a warning if axe_core_audit.csv was not produced. This depends on step 3.
9. Decide whether export should be always on or configurable. Recommendation: keep it always on for the first delivery because /Users/eoinkelly/Developer/repos/cwac/config.py contains a reporting field but no implemented reporting configuration. Introducing a new reporting schema is extra scope and is not required by CWAC-328. Explicitly exclude config-driven toggles from the first implementation unless the story is expanded.
10. Add focused tests. Recommended new file: /Users/eoinkelly/Developer/repos/cwac/tests/test_output.py. Split the implementation so the formula-layout logic is testable without opening Excel. Automated coverage should include:
   1. Exporter skips cleanly when the source CSV is missing.
   2. Exporter creates axe_core_audit.xlsx in the expected results folder when the CSV exists.
   3. Workbook metadata contains exactly two sheet names.
   4. Statistics sheet XML contains the expected key formulas or labels.
   5. A malicious fixture row with values beginning with =, +, -, @, tab, and a URL-like string is stored as literal cell data in Raw Data, not as Excel formulas or hyperlinks.
   6. The generated workbook contains no VBA project parts or macro-enabled content types.
   Because CWAC does not currently depend on openpyxl, avoid adding a second spreadsheet library just for tests unless the team wants easier workbook inspection. A lightweight alternative is to inspect the XLSX zip contents with zipfile and XML parsing.
11. Update user-facing documentation. At minimum, extend /Users/eoinkelly/Developer/repos/cwac/doc/audit-results.md to mention axe_core_audit.xlsx alongside axe_core_audit.csv and describe the two worksheets. Optionally update /Users/eoinkelly/Developer/repos/cwac/doc/audits/axe-core-audit.md with a short note that the raw CSV is also exported as an Excel workbook with a statistics tab and that CSV-derived values are treated as untrusted spreadsheet input.

**Relevant files**
- /Users/eoinkelly/Developer/repos/cwac/cwac.py — existing post-scan hook where generate_axe_core_template_aware_results(self.config.audit_name) is called after scan completion; best integration point for XLSX export.
- /Users/eoinkelly/Developer/repos/cwac/src/output.py — current CSV writing and axe_core post-processing logic; place new generate_axe_core_xlsx_results helper here and reuse the existing results-path conventions.
- /Users/eoinkelly/Developer/repos/cwac/pyproject.toml — add the chosen XLSX writer dependency.
- /Users/eoinkelly/Developer/repos/cwac/requirements.txt — keep the runtime dependency list aligned with pyproject.
- /Users/eoinkelly/Developer/repos/cwac/config.py — currently contains a reporting field but no active XLSX/reporting settings; reference this only if export configuration is later introduced.
- /Users/eoinkelly/Developer/repos/cwac/doc/audit-results.md — document the new workbook output in the results folder layout.
- /Users/eoinkelly/Developer/repos/cwac/doc/audits/axe-core-audit.md — optional note describing the spreadsheet output for this audit.
- /Users/eoinkelly/Developer/repos/cwac/tests/test_output.py — recommended new tests for exporter behavior and workbook structure.

**Verification**
1. Run the targeted unit test file for the exporter after implementation.
2. Run at least one existing test command that covers nearby code paths so the new dependency and import path do not break unrelated output logic.
3. Run CWAC with a config that produces axe_core_audit.csv and confirm that ./results/<audit_name>/axe_core_audit.xlsx is created next to the CSV outputs.
4. Open the workbook in Excel or LibreOffice and confirm there are exactly two sheets, Raw Data and Statistics.
5. Confirm Raw Data contains the full CSV contents, with headers preserved and no row loss.
6. Run a malicious-input fixture through the exporter and confirm cells that start with =, +, -, @, tab, carriage return, line feed, or URL-like schemes are stored as literal data in the Raw Data sheet rather than as formulas or clickable links.
7. Inspect the generated XLSX package and confirm there are worksheet string cells where expected, no unexpected formula nodes for raw-data columns, no hyperlink relationships derived from raw CSV values unless intentionally added by the exporter, and no VBA project payload such as vbaProject.bin.
8. Confirm Statistics formulas recalculate correctly when the workbook is opened and that embedded charts, if included, render without manual repair prompts.
9. Confirm the exporter does not fail the whole scan when axe_core_audit.csv is missing; it should log a warning and continue.

**Decisions**
- Recommended library: xlsxwriter.
- Alternative library: openpyxl if the team expects future work to reopen, edit, or append to existing workbooks after creation.
- Alternative minimal approach: pandas DataFrame.to_excel with no explicit engine handling is acceptable only for a bare two-sheet export without polished formulas/charts; it is not the best fit for CWAC-328 as written.
- Recommended graph strategy: native Excel charts embedded in the Statistics sheet, not external PNG graphs from matplotlib and not a separate charts tab.
- Recommended formula strategy: use structured table references and conservative cross-version formulas; avoid dynamic-array-heavy designs in the first pass.
- Security decision: treat all CSV-derived values as untrusted spreadsheet input and disable automatic string-to-formula and string-to-URL promotion in the raw-data export path.
- Security conclusion: a malicious user or page can cause formula injection if the exporter lets untrusted strings be interpreted by Excel, but they cannot embed a VBA macro merely by placing text in the CSV. Macro risk only appears if CWAC intentionally writes a macro-enabled workbook or embeds a VBA project, which this implementation should not do.
- Included scope: XLSX export for axe_core_audit.csv only.
- Excluded scope: export for other audit CSVs, config-driven toggles, pivot tables, macros, conditional formatting beyond basic readability, and a third charts worksheet.

**Further Considerations**
1. If stakeholders want template-level analytics rather than page-instance analytics, a later iteration could add a second workbook or a second formula block based on axe_core_audit_template_aware.csv. That is useful, but it should stay out of the first implementation because the current story explicitly anchors the workbook to axe_core_audit.csv.
2. If the team wants distinct-count statistics such as unique pages, unique base URLs, or unique issue IDs inside formulas, decide explicitly between broader compatibility and newer Excel features. Recommendation: for the first pass, either compute the unique label lists in Python and count them with formulas, or keep distinct-count metrics out of scope rather than depending on dynamic arrays.
3. If formulas must display calculated values correctly in non-Excel consumers that do not recalculate workbooks, consider supplying precomputed result values alongside formulas. Recommendation: defer unless a consumer requirement appears, since native Excel recalculation is likely sufficient for CWAC’s current workflow.
