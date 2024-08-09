let a11ytable_{{ include.uniqueID }} = new A11ytable({
    tableID: '{{ include.uniqueID }}' + '-table',
    columnSelectorFieldsetId: '{{ include.uniqueID }}' + '-column-selector-fieldset',
    filterInputId: '{{ include.uniqueID }}' + '-filter-input',
    downloadButtonId: '{{ include.uniqueID }}' + '-download-button',
    tableData:{{ include.tableData | jsonify }},
});

// Generate table
a11ytable_{{ include.uniqueID }}.generateTable();

// When any button is clicked where its id ends with "-raw-download-button"
// download the raw CSV data
raw_data_{{ include.uniqueID }}_download.addEventListener("click", function() {
    download_base64_csv("{{ include.rawData }}", "{{ include.organisation | slugify }}_{{ include.auditType | slugify }}.csv");
});