/* base642csv.js

Given a base64 CSV string, decode it and download it as a CSV file.
*/

function download_base64_csv(base64string, filename) {
    // Decode the base64 string
    const decodedCSV = atob(base64string);

    // Convert the decoded CSV data to a Blob object
    const blob = new Blob([decodedCSV], { type: "text/csv" });

    // Create a URL object from the Blob object
    const url = URL.createObjectURL(blob);

    // Create a link element to trigger the download
    const link = document.createElement("a");
    link.href = url;

    link.download = filename;
    document.body.appendChild(link);
    link.click();

    // Cleanup the URL object and link element
    URL.revokeObjectURL(url);
    document.body.removeChild(link);
}