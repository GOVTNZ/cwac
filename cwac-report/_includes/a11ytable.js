/**
 * @file A11ytable is an accessible, sortable, filterable table
 * @author Callum McMenamin
 * @version 1.0.0
 * @example
 * html:
 * <fieldset id="my-table-column-selector"></fieldset>
 * <input id="my-table-filter" type="text">
 * <table id="my-table"></table>
 * <button id="my-table-download-button">Download</button>
 * js:
 * let table = new A11ytable({
 *     tableID: "my-table",
 *     filterInputId: "my-table-filter",
 *     columnSelectorFieldsetId: "my-table-column-selector",
 *     downloadButtonId: "my-table-download-button",
 *     tableData: [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
 *     hiddenColumns: ["a"],
 *     sortStatus: {
 *         column: "a",
 *         order: "descending"
 *     }
 * });
 * table.generateTable();
 * @example
 * html:
 * <table id="my-table"></table>
 * js:
 * let table = new A11ytable({
 *     tableID: "my-table"
 * });
 * table.fetchData("data.json").then(() => {
 *     table.generateTable();
 * });
 */

export class A11ytable {

    /**
     * @description Creates a new A11ytable
     * @param {object} [{}] the options for the table
     * @param {string} {}.tableID the id of the table (required)
     * @param {string} [{}.filterInputId=null] the id of the filter input
     * @param {string} [{}.columnSelectorFieldsetId=null] the id of the column selector
     * @param {string} [{}.downloadButtonId=null] the id of the download button
     * @param {object[]} [{}.tableData=[]] the data to load into the table
     * @param {string[]} [{}.hiddenColumns=[]] the columns to hide
     * @param {object} [{}.sortStatus=null] the column to sort by and the order
     * @returns {void}
     * @example
     * html:
     * <fieldset id="my-table-column-selector"></fieldset>
     * <input id="my-table-filter" type="text">
     * <table id="my-table"></table>
     * js:
     * let table = new A11ytable({
     *     tableID: "my-table",
     *     filterInputId: "my-table-filter",
     *     columnSelectorFieldsetId: "my-table-column-selector",
     *     downloadButtonId: "my-table-download-button",
     *     tableData: [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
     *     hiddenColumns: ["a"],
     *     sortStatus: {
     *         column: "a",
     *         order: "descending"
     *     }
     * });
     * table.generateTable();
     * @example
     * html:
     * <table id="my-table"></table>
     * js:
     * let table = new A11ytable({
     *   tableID: "my-table"
     * });
     * table.fetchData("data.json").then(() => {
     *  table.generateTable();
     * });
     */
    constructor({
        tableID,
        filterInputId = null,
        columnSelectorFieldsetId = null,
        downloadButtonId = null,
        tableData = [],
        hiddenColumns = [],
        sortStatus = null
    } = {}) {

        // Validate all IDs provided
        this.validateIDs({
            tableID,
            filterInputId,
            columnSelectorFieldsetId,
            downloadButtonId
        });

        // The table element
        this.table = document.getElementById(tableID);

        // Add the 'a11ytable' class to the table
        this.table.classList.add("a11ytable");

        // The filter input element
        this.filterInput = document.getElementById(filterInputId);
        // Add the 'a11ytable' class to the filter input
        this.filterInput.classList.add("a11ytable");

        // The column selector element
        this.columnSelectorFieldset = document.getElementById(columnSelectorFieldsetId);
        // Add the 'a11ytable' class to the column selector
        this.columnSelectorFieldset.classList.add("a11ytable");

        // The download button element
        this.downloadButton = document.getElementById(downloadButtonId);

        // The table data
        this.tableData = tableData;

        // List of columns to hide (by column name)
        this.hiddenColumns = hiddenColumns;

        // Tracks what column is used to sort the table and the order
        // (either "ascending" or "descending")
        this.sortStatus = sortStatus;
        
        // An element used to send aria-live alerts to the user
        // about relevant changes to the table
        this.ariaAlertElement = null;

        // Used to keep a reference to an alert timeout
        // so alerts can be cancelled if new information is available
        this.ariaAlertTimeout = null;
    }

    /**
     * @description Fetches data from a url
     * @param {string} url the url to fetch data from
     * @returns {void}
     * @async
     * @example
     * html: <table id="my-table"></table>
     * js:
     * let table = new A11ytable("my-table");
     * table.fetchData("data.json").then(() => {
     *     table.generateTable();
     * });
     */
    async fetchData(url) {
        let response = await fetch(url);
        let data = await response.json();
        this.tableData = data;
    }

    /**
     * @description Loads data from an object for the table
     * @param {object} data the data to load
     * @returns {void}
     * @example
     * html: <table id="my-table"></table>
     * js:
     * let table = new A11ytable("my-table");
     * table.loadData([
     *     {
     *         "name": "Callum",
     *         "age": 26
     *     },
     *     {
     *         "name": "John",
     *         "age": 28
     *     }
     * ]);
     * table.generateTable();
     */
    loadData(data) {
        this.tableData = data;
    }

    /**
     * @description Run filter on the table data and return the number of results
     * @returns {number} the number of results
     * @example
     * html: <table id="my-table"></table>
     * js:
     * let table = new A11ytable("my-table");
     * table.fetchData("https://example.com/data.json").then(() => {
     *   table.generateTable();
     *   table.filterTableData("Callum");
     * });
     */
    filterTableData(sendAriaLiveALert = false) {

        // Get the filter term
        let filterTerm = this.filterInput.value;

        // If the filter term is blank, show all rows
        if (filterTerm === "") {
            let tableRows = this.table.querySelectorAll("tbody tr");
            tableRows.forEach(row => {
                // Remove display none property if it is set to none
                if (row.style.display === "none") {
                    row.style.display = "";
                }
            });

            // Get number of rows in tableRows            
            return tableRows.length - 1;
        }

        // Split the filter term by spaces
        let filterTerms = filterTerm.split(" ");

        // Remove all empty strings from filterTerms
        filterTerms = filterTerms.filter(term => term !== "");

        // Select every row in the table except for the header
        let tableRows = this.table.querySelectorAll("tbody tr");

        // Track how many rows are visible
        let visibleRows = 0;

        // Iterate through tableRows
        tableRows.forEach(row => {
            // A dict that counts whether each filter term has been found
            // ONLY rows that have all terms discovered are visible
            let filterTermDiscovered = {};

            // Iterate through filterTerms
            filterTerms.forEach(term => {
                // If the filter term is not blank
                if (term !== "") {
                    // Set filterTermDiscovered[term] to false
                    filterTermDiscovered[term.toLowerCase()] = false;
                }
            });


            // Select every td inside of row
            let tableCells = row.querySelectorAll("td");

            // Iterate through filterTerms
            filterTerms.forEach(term => {
                // If the filter term is not blank
                if (term === "") return;

                // Iterate through tableCells
                tableCells.forEach(cell => {
                    // Iterate through filter terms
                    if (cell.textContent.toLowerCase().includes(term.toLowerCase())) {
                        filterTermDiscovered[term.toLowerCase()] = true;
                    }

                    // If the search term is double-quoted, only match exact matches
                    if (term.startsWith('"') && term.endsWith('"')) {
                        // Remove the double quotes from the term
                        let exactTerm = term.replace(/"/g, "");
                        // If the cell text matches the exact term
                        if (cell.textContent.toLowerCase() === exactTerm.toLowerCase()) {
                            filterTermDiscovered[term.toLowerCase()] = true;
                        }
                    }

                    // Filter by expression e.g. "age>18"
                    if (this.filterCellByExpression(term, cell.textContent, tableCells)) {
                        filterTermDiscovered[term.toLowerCase()] = true;
                    }
                });
            });

            // Iterate through filterTermDiscovered
            let allTermsDiscovered = true;
            for (let term in filterTermDiscovered) {
                if (allTermsDiscovered && !filterTermDiscovered[term]) {
                    allTermsDiscovered = false;
                }
            }

            // If the term has not been discovered, hide the row
            if (!allTermsDiscovered) {
                row.style.display = "none";
            } else {
                // Display table row
                row.style.display = "";
                // Count the visible rows
                visibleRows++;
            }

        });

        // Send an aria-live alert to the user
        if (sendAriaLiveALert) {
            // Make a string that says "x results found" with an s if there is more than one result
            let resultsString = visibleRows + " result";
            if (visibleRows !== 1) {
                resultsString += "s";
            }
            resultsString += " found";
            this.sendAriaLiveAlert(resultsString, 1500);
        }

        return visibleRows;
    }

    /*
     * @description Filter table data by expression
     * @param {string} expression - The expression to filter by
     * @param {string} cell - The cell text content to filter
     * @param {array} row - The table rows to filter
     * @returns {bool} - True if the cell matches the expression
     */
    filterCellByExpression(expression, cell, row) {

        // Ensure expression contains <, > or =
        if (!expression.includes("<") && !expression.includes(">") && !expression.includes("=")) {
            return false;
        }

        // Split the string by the first instance of <, > or =
        let splitTerm = expression.split(/<|>|=/, 2);

        // Check that there are two operands in the split term
        if (splitTerm.length !== 2) {
            return false;
        }

        // Get the column name from the first operand
        let columnName = splitTerm[0];
        // Get the value from the second operand
        let value = splitTerm[1];

        // Iterate through the table headers to find the column index
        let columnIndex = 0;
        for (let key in this.tableData[0]) {
            if (key === columnName) {
                break;
            }
            columnIndex++;
        }

        // Check if columnName exists in the row
        if (!this.tableData[0].hasOwnProperty(columnName)) {
            return false;
        }

        // Iterate through the table cells to find the column index
        let currentCellIndex = 0;
        for (let cell of row) {
            if (currentCellIndex === columnIndex) {
                // Check if the cell text is less than the value
                if (expression.includes("<")) {
                    if (Number(cell.textContent) < Number(value)) {
                        return true;
                    }
                }
                // Check if the cell text is greater than the value
                if (expression.includes(">")) {
                    if (Number(cell.textContent) > Number(value)) {
                        return true;
                    }
                }
                // Check if the cell text is equal to the value
                if (expression.includes("=")) {
                    if (cell.textContent === value) {
                        return true;
                    }

                }
            }
            currentCellIndex++;
        }

        return false;
    }



    /**
     * @description Register a filter input
     * @example
     * html:
     * <table id="my-table-filter"></table>
     * <input id="my-input" type="text">
     * js:
     * let table = new A11ytable("my-table");
     * table.fetchData("https://example.com/data.json").then(() => {
     *     table.generateTable();
     *     table.registerFilterInput("my-table-filter");
     * });
     */
    registerFilterInput() {
        // Add an event listener to the input for any key presses
        this.filterInput.addEventListener("keyup", () => {
            // Filter the table data with 'true' to send an aria-live alert
            this.filterTableData(true);
        });
    }

    /**
     * @description Sorts the table data by a column
     * @param {string} column the column to sort by
     * @param {string} order the order to sort by, either "ascending" or "descending"
     * @returns {void}
     * @example
     * html:
     * <table id="my-table"></table>
     * js:
     * let table = new A11ytable("my-table");
     * table.fetchData("https://example.com/data.json").then(() => {
     *     table.generateTable();
     *     table.sortBy("name", "ascending");
     * });
     */
    sortBy(column, order) {

        // Throw an error if order is not "ascending" or "descending"
        if (!(order === "ascending" || order === "descending")) {
            throw new Error("Order must be either 'ascending' or 'descending'");
        }

        // If the order is ascending, sort the data by the column
        if (order === "ascending") {
            this.tableData.sort((a, b) => {
                if (a[column] < b[column]) {
                    return -1;
                } else if (a[column] > b[column]) {
                    return 1;
                } else {
                    return 0;
                }
            });
        }

        // If the order is descending, sort the data by the column
        if (order === "descending") {
            this.tableData.sort((a, b) => {
                if (a[column] > b[column]) {
                    return -1;
                } else if (a[column] < b[column]) {
                    return 1;
                } else {
                    return 0;
                }
            });
        }
    }

    /**
     * @description Update the table so its aria-sort attributes match this.sortStatus
     * @returns {void}
     */
    updateHeaderAriaSortAttributes() {
        let tableHead = this.table.querySelector("thead");
        let tableHeadCells = tableHead.querySelectorAll("th");
        // Iterate through tableHeadCells and update the aria-sort attribute
        tableHeadCells.forEach(cell => {
            // Get the column name from the button's data-column attribute
            let columnMame = cell.querySelector("button").getAttribute("data-key");
            if (this.sortStatus !== null && columnMame === this.sortStatus.column) {
                cell.setAttribute("aria-sort", this.sortStatus.order);
            } else {
                // Remove the aria-sort attribute
                cell.removeAttribute("aria-sort");
            }
        });
    }

    /**
     * @description Toggle the sort order
     * @param {boolean} columnName the name of the column that was selected
     * @returns {void}
     */
    toggleSortOrder(columnName) {
        // If sortStatus is not set, set it to ascending
        if (this.sortStatus === null || columnName !== this.sortStatus.column) {
            this.sortStatus = { "column": columnName, "order": "ascending" };
        } else {
            // if sortStatus is set, toggle it
            if (this.sortStatus.order === "ascending") {
                this.sortStatus = { "column": columnName, "order": "descending" };
            } else {
                this.sortStatus = { "column": columnName, "order": "ascending" };
            }
        }
    }

    /**
     * @description Generates an aria-live region and adds it to the DOM
     * @returns {void}
     */
    generateAriaLiveRegion() {
        this.ariaAlertElement = document.createElement("div");
        this.ariaAlertElement.setAttribute("aria-live", "polite");
        this.ariaAlertElement.setAttribute("aria-atomic", "true");
        this.ariaAlertElement.classList.add("visuallyhidden");
        this.table.insertAdjacentElement("afterend", this.ariaAlertElement);
    }

    /**
     * @description Sends an aria-live alert to the user
     * @param {string} message the message to send
     * @param {number} [delay=null] the delay in milliseconds before sending the message
     * @returns {void}
     */
    sendAriaLiveAlert(message, delay = null) {
        if (delay !== null) {
            // Cancel any previous alerts
            clearTimeout(this.ariaAlertTimeout);
            this.ariaAlertTimeout = setTimeout(() => {
                // Empty this.ariaAlertElement
                this.ariaAlertElement.textContent = "";
                // Wait 127ms and add new text
                setTimeout(() => {
                    this.ariaAlertElement.textContent = message;
                }, 175);
            }, delay);
            return;
        } else {
            // Empty this.ariaAlertElement
            this.ariaAlertElement.textContent = "";
            // Wait 250ms and add new text
            setTimeout(() => {
                this.ariaAlertElement.textContent = message;
            }, 250);
        }
    }

    /**
     * @description Generates a table header from data
     * @returns {void}
     */
    generateTableHead() {
        let thead = document.createElement("thead");
        let tr = document.createElement("tr");
        for (let key in this.tableData[0]) {
            // If the key is in hiddenColumns, skip it
            if (this.hiddenColumns.includes(key)) {
                continue;
            }

            let th = document.createElement("th");

            // Add a 'sort by' button to each cell, with descending as the default
            let sortButton = document.createElement("button");

            // Add the key as the text content of the button
            sortButton.textContent = key;

            // Set a data attribute on the button to store its key
            sortButton.setAttribute("data-key", key);

            // Make a sort arrow
            let sortArrow = this.generateArrowSVG(key);

            // Append the sort arrow text to the button
            sortButton.innerHTML += sortArrow;

            // Create a visually hidden span to contain the accessible description of the button
            let descriptionSpan = document.createElement("span");
            // Make it display:none
            descriptionSpan.style.display = "none";
            // Give it a unique id
            descriptionSpan.setAttribute("id", `${this.table.id}-sort-by-${key}-description`);
            // Set the text content
            descriptionSpan.textContent = this.generateSortButtonDescription(key);
            // Append the description span to the button
            sortButton.appendChild(descriptionSpan);
            // Set the button's aria-describedby to the ID of descriptionSpan
            sortButton.setAttribute("aria-describedby", descriptionSpan.getAttribute("id"));

            // Attach a click event listener to the button
            // that calls the sortBy method with the column name
            // and the order
            sortButton.addEventListener("click", () => {

                this.toggleSortOrder(key);

                this.sortBy(key, this.sortStatus.order);

                // Update all all sort buttons
                let buttons = this.table.querySelectorAll("thead button");
                buttons.forEach(button => {
                    let key = button.getAttribute("data-key");
                    // Update the arrow SVG to point in the right direction
                    // Delete the SVG from the button
                    button.innerHTML = button.innerHTML.replace(/<svg.*svg>/, "");
                    // Generate a new SVG and append it to the button
                    let svg = this.generateArrowSVG(key);
                    button.innerHTML += svg;
                    // Update the description span
                    // Get the button's describedby ID
                    let describedby = button.getAttribute("aria-describedby");
                    // Get the description span
                    let descriptionSpan = document.getElementById(describedby);
                    // Update the description span's text content
                    descriptionSpan.textContent = this.generateSortButtonDescription(key);
                });

                // Refresh the table
                this.refreshTable();
                this.filterTableData();
                this.updateHeaderAriaSortAttributes();

            });

            // Set scope="col" on th
            th.setAttribute("scope", "col");

            // Append button to cell
            th.appendChild(sortButton);
            tr.appendChild(th);
        }

        thead.appendChild(tr);

        // Replace the <thead> element if it exists, otherwise append it
        if (this.table.querySelector("thead")) {
            this.table.replaceChild(thead, this.table.querySelector("thead"));
        } else {
            this.table.appendChild(thead);
        }

        // Update the table header cell aria-sort attributes
        this.updateHeaderAriaSortAttributes();
    }

    /**
     * @description Generates a table body from data
     * @returns {void}
     */
    generateTableBody() {
        // Create a tbody element
        let tbody = document.createElement("tbody");
        // Iterate over the data and add a row for each item
        this.tableData.forEach(row => {
            let tr = document.createElement("tr");

            // Iterate over row object and create a cell for each value, and append it to tr
            for (let key in row) {
                // If the key is in the hiddenColumns array, skip it
                if (this.hiddenColumns.includes(key)) {
                    continue;
                }
                let td = document.createElement("td");
                td.textContent = row[key];
                tr.appendChild(td);
            }

            // Append the row to the tbody
            tbody.appendChild(tr);
        });

        // Replace the <tbody> element if it exists, otherwise append it
        if (this.table.querySelector("tbody")) {
            this.table.replaceChild(tbody, this.table.querySelector("tbody"));
        } else {
            this.table.appendChild(tbody);
        }
    }

    /**
     * @description Clear the table
     * @returns {void}
     */
    clearTable() {
        // Remove the <thead> and <tbody> elements
        if (this.table.querySelector("thead")) {
            this.table.removeChild(this.table.querySelector("thead"));
        }
        if (this.table.querySelector("tbody")) {
            this.table.removeChild(this.table.querySelector("tbody"));
        }
    }

    /**
     * @description Detects table control elements and registers them
     * @returns {void}
     */
    registerTableControls() {
        // If there is a filter input, register it
        if (this.filter !== null) {
            this.registerFilterInput();
        }

        // If there is a column selector, register it
        if (this.columnSelector !== null) {
            this.registerColumnSelector();
        }

        // If there is a download button, register it
        if (this.downloadButton !== null) {
            this.registerDownloadButton();
        }
    }

    /**
     * @description Validates all IDs provided to the constructor
     * @param {object} ids an object containing all IDs
     * @returns {void}
     */
    validateIDs(ids) {
        // If the table ID is not provided, throw an error
        if (ids.tableID === undefined) {
            throw new Error("You must provide a tableID to the constructor");
        }

        // Iterate through the IDs and validate them
        for (let id in ids) {
            // If the ID is null, skip it
            if (ids[id] === null) {
                continue;
            }
            // If the ID is not a string, throw an error
            if (typeof ids[id] !== "string") {
                throw new Error(`All IDs must be strings (or null) ${{id}} is not a string`);
            }

            // If the ID does not exist in the DOM, throw an error
            if (document.getElementById(ids[id]) === null) {
                throw new Error(`#${id} does not exist in the DOM`);
            }
        }
    }

    /**
     * @description Generates the table from the data
     * @returns {void}
     */
    generateTable() {
        /* Clear the table */
        this.clearTable();

        /* Add a table head */
        this.generateTableHead();

        /* Add a table body */
        this.generateTableBody();

        /* Register table controls */
        this.registerTableControls();

        /* Generate the aria-live region */
        this.generateAriaLiveRegion();
    }

    /**
     * @description Returns an arrow for the a table header cell
     * @param {object} forHeaderCell the header cell to generate the arrow for
     * @returns {string} an svg arrow
     */
    generateArrowSVG(forHeaderCell) {
        let svg_tag_start = "<svg aria-hidden=\"true\" viewBox=\"0 0 100 200\" width=\"100\" height=\"200\">";
        let top_arrow = "<polyline points=\"20 50, 50 20, 80 50\"></polyline>";
        let mid_line = "<line x1=\"50\" y1=\"25\" x2=\"50\" y2=\"170\" style=\"stroke-width:20\"></line>";
        let bottom_arrow = "<polyline points=\"20 150, 50 180, 80 150\"></polyline>";
        let svg_tag_end = "</svg>";

        let sortStatusIsSet = this.sortStatus !== null;
        let ascending = !sortStatusIsSet || this.sortStatus.order === "ascending" ? true : false;
        let outputSVG = svg_tag_start;

        if (!sortStatusIsSet || !(forHeaderCell === this.sortStatus.column && !ascending)) {
            outputSVG += top_arrow;
        }

        outputSVG += mid_line;

        if (!sortStatusIsSet || !(forHeaderCell === this.sortStatus.column && ascending)) {
            outputSVG += bottom_arrow;
        }

        outputSVG += svg_tag_end;

        return outputSVG;
    }

    /**
     * @description Registers a download button for a table
     * @returns {void}
     */
    registerDownloadButton() {
        this.downloadButton.addEventListener("click", () => {
            this.downloadTableAsCSV();
        });
    }

    generateSortButtonDescription(key) {
        if (this.sortStatus !== null) {
            // If the key differs from the current sort key, return a description for ascending sort
            if (key !== this.sortStatus.column) {
                return `Sort by ${key}, ascending`;
            }
            // Invert ascending and descending
            let order = this.sortStatus.order === "ascending" ? "descending" : "ascending";
            return `Sort by ${key}, ${order}`;
        } else {
            return `Sort by ${key}, ascending`;
        }
    }

    /**
     * @description Refreshes the table
     * @param {bool} refreshHeader refresh the header
     * @returns {void}
     */
    refreshTable(refreshHeader = false) {
        this.generateTableBody();

        if (refreshHeader) {
            this.generateTableHead();
        }

        // Re-run the sort
        if (this.sortStatus !== null) {
            this.sortBy(this.sortStatus.column, this.sortStatus.order);
        }

        // Update aria-sort attributes
        this.updateHeaderAriaSortAttributes();

        // Re-run the filter
        this.filterTableData();
    }

    /**
     * @description Downloads the table as a CSV
     * @returns {void}
     */
    downloadTableAsCSV() {
        let csv_string = "";
        let columns = this.tableData[0];
        let rows = this.tableData;

        function csvEncode(str) {
            if (/[",\n]/.test(str)) {
                str = `"${str.replace(/"/g, '""')}"`;
            }
            return str;
        }

        // Add columns to CSV string
        for (let key in columns) {
            if (this.hiddenColumns.includes(key)) {
                continue;
            }
            csv_string += csvEncode(key) + ",";
        }

        // End the line
        csv_string = csv_string.slice(0, -1) + "\n";

        // Iterate rest of rows, add to CSV string
        for (let row of rows) {
            for (let key in row) {
                if (this.hiddenColumns.includes(key)) {
                    continue;
                }
                csv_string += csvEncode(row[key]) + ",";
            }
            // End the line
            csv_string = csv_string.slice(0, -1) + "\n";
        }

        // Start a download
        let blob = new Blob([csv_string], { type: "text/csv" });
        let url = URL.createObjectURL(blob);
        let link = document.createElement("a");
        link.href = url;
        link.download = "table.csv";
        document.body.appendChild(link);
        link.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(link);
    }

    /**
     * @description Populates an <fieldset> element with checkboxes for each column name
     * @returns {void}
     * @example
     * html:
     * <fieldset id="column-selector">
     *    <legend>Column Selector</legend>
     *   <input type="checkbox" name="column1" checked aria-controls="table1">
     *  <input type="checkbox" name="column2" checked aria-controls="table1">
     * </fieldset>
     * <table id="my-table"></table>
     * js:
     * let table = new A11ytable("my-table");
     * table.registerColumnSelector("column-selector");
     * table.fetchData("my-data.json").then(() => {
     *    table.registerColumnSelector("column-selector");
     * });
     */
    registerColumnSelector() {
        let columns = this.tableData[0];

        // Add the 'Select All' checkbox
        let selectAllCheckbox = document.createElement("input");
        selectAllCheckbox.type = "checkbox";
        selectAllCheckbox.id = this.table.id + "-column-selector-select-all-checkbox";
        selectAllCheckbox.checked = true;
        selectAllCheckbox.setAttribute("aria-controls", "");
        selectAllCheckbox.addEventListener("change", (e) => {
            let checked = e.target.checked;
            let checkboxes = this.columnSelectorFieldset.querySelectorAll("input[type=checkbox]");
            for (let i = 0; i < checkboxes.length; i++) {
                checkboxes[i].checked = checked;
            }
            // If the selectAllCheckbox is checked, clear this.hiddenColumns
            if (checked) {
                this.hiddenColumns = [];
            } else {
                // Else, set this.hiddenColumns to all columns
                this.hiddenColumns = Object.keys(columns);
            }

            // Rebuild the table with true to refresh the header as well
            this.refreshTable(true);
        });

        // Create a label
        let selectAllLabel = document.createElement("label");
        selectAllLabel.appendChild(selectAllCheckbox);
        selectAllLabel.appendChild(document.createTextNode("All"));
        this.columnSelectorFieldset.appendChild(selectAllLabel);

        // Create a ul to hold the checkboxes
        let ul = document.createElement("ul");

        for (let key in columns) {
            // Create a checkbox
            let checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.id = this.table.id + "-column-selector-checkbox-" + key;
            // Add a data-column attribute to store the column name in the checkbox
            checkbox.setAttribute("data-column", key);
            checkbox.checked = true;

            // Append the checkbox name to the selectAllCheckbox's aria-controls attribute
            selectAllCheckbox.setAttribute("aria-controls", selectAllCheckbox.getAttribute("aria-controls") + " " + checkbox.id);

            // Set aria-controls to the table's id
            checkbox.setAttribute("aria-controls", this.table.id);

            // Add an event listener to the checkbox
            checkbox.addEventListener("change", (e) => {
                let column = e.target.getAttribute("data-column");
                let checked = e.target.checked;

                // If checked is false, add column to hiddenColumns
                if (!checked) {
                    this.hiddenColumns.push(column);
                } else {
                    // If checked is true, remove column from hiddenColumns
                    this.hiddenColumns.splice(this.hiddenColumns.indexOf(column), 1);
                }

                // If all checkboxes are unchecked (excluding the 'select all' checkbox), uncheck the 'Select All' checkbox
                let checkboxes = this.columnSelectorFieldset.querySelectorAll("input[type=checkbox][id]:not([id='" + selectAllCheckbox.id + "'])");
                let numberOfCheckedCheckboxes = 0;
                for (let i = 0; i < checkboxes.length; i++) {
                    if (checkboxes[i].checked) {
                        numberOfCheckedCheckboxes++;
                    }
                }
               
                // If all checkboxes are checked, check the 'Select All' checkbox
                if (numberOfCheckedCheckboxes === checkboxes.length) {
                    selectAllCheckbox.indeterminate = false;
                    selectAllCheckbox.checked = true;
                }

                // If no checkboxes are checked, uncheck the 'Select All' checkbox
                if (numberOfCheckedCheckboxes === 0) {
                    selectAllCheckbox.indeterminate = false;
                    selectAllCheckbox.checked = false;
                }

                // If some (but not all) checkboxes are checked, set 'Select All' to indeterminate
                if (numberOfCheckedCheckboxes > 0 && numberOfCheckedCheckboxes < checkboxes.length) {
                    selectAllCheckbox.indeterminate = true;
                    selectAllCheckbox.checked = false;
                }

                // Rebuild the table with true to force a rebuild of the header
                this.refreshTable(true);

            });

            // Create a label
            let label = document.createElement("label");
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(key));

            // Create an li
            let li = document.createElement("li");
            li.appendChild(label);

            // Append the li to the ul
            ul.appendChild(li);
        }

        // Append the ul to the fieldset
        this.columnSelectorFieldset.appendChild(ul);

    }
}
