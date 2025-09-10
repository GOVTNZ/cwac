/**
 * @typedef {Object} ProgressUpdate
 * @property {string} logs
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

  /** @type {HTMLTextAreaElement} */
  const logsTextArea = document.getElementById('logs');

  logsTextArea.value = data.logs;
  logsTextArea.scrollTop = logsTextArea.scrollHeight;

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

  if (data.state !== 'running') {
    clearInterval(updateProgressInterval);
    progressBar.classList.remove('bg-primary');
    progressBar.classList.add('bg-success');
    document.getElementById('scan-state').innerText = 'finished';
  }
}

const updateProgressInterval = setInterval(() => updateProgress(), 1000);
