# CWAC-328 Explore options for XSLX outputs in results

Make `cwac.py` create an XSLX version of `axe_core_audit.csv` at the end of a scan.
The XSLX document contains the following tabs:

Tab 1: The raw data from `axe_core_audit.csv`
Tab 2: Formulas that compute statistics about Tab 1

Include recommendations about python libraries to use and options for generating graphs and formulas within the xslx file

Include in the plan to comment on any security implications from importing data from the CSV file.
Could a malicious user embed a macro or formula in that data?