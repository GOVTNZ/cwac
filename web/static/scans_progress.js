/**
 * @typedef {Object} ProgressLogs
 * @property {string} chromedriver
 * @property {string} audit
 */

/**
 * @typedef {Object} ProgressUpdate
 * @property {ProgressLogs} logs
 * @property {number} time
 * @property {number} iteration
 * @property {number} total
 * @property {string} speed
 * @property {string} percent
 * @property {string} elapsed
 * @property {string} remaining
 * @property {string} state
 */

/**
 * Updates the text area with the given content, and scrolls to the bottom
 *
 * @param {string} id
 * @param {string} content
 */
function updateTextArea(id, content) {
  /** @type {HTMLTextAreaElement} */
  const logsTextArea = document.getElementById(id);

  logsTextArea.value = content;
  logsTextArea.scrollTop = logsTextArea.scrollHeight;
}

/**
 * Updates the progress of the current scan
 *
 * @return {Promise<void>}
 */
async function updateProgress() {
  const resp = await fetch('/scans/progress/update');

  if (!resp.ok) {
    alert(`${resp.status} ${resp.statusText} fetching progress update`);

    return;
  }

  /** @type {ProgressUpdate} */
  const data = await resp.json();

  updateTextArea('logs-audit', data.logs.audit);
  updateTextArea('logs-chromedriver', data.logs.chromedriver);

  const progressBar = document.getElementById('scan-progress');

  progressBar.style.width = `${data.percent}%`;
  progressBar.ariaValueNow = data.percent;

  document.getElementById('scan-progress-stat').innerText =
    `p:${data.iteration}/${data.total}`;
  document.getElementById('scan-progress-speed').innerText =
    `v:${data.speed}p/s`;
  document.getElementById('scan-progress-elapsed').innerText =
    `t:${data.elapsed}`;
  document.getElementById('scan-progress-remaining').innerText =
    `t-:${data.remaining}`;

  if (data.state === 'running') {
    setTimeout(updateProgress, 1000);

    return;
  }

  progressBar.classList.remove('bg-primary');
  progressBar.classList.add('bg-success');
  document.getElementById('scan-state').innerText = 'Finished scanning';

  const scanControl = document.getElementById('scan-control');

  scanControl.innerText = 'View results';
  scanControl.classList.remove('disabled');
}

updateProgress().catch(console.error);
