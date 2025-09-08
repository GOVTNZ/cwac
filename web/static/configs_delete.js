document.querySelectorAll('button.config-delete').forEach(btn => {
  const { filename } = btn.dataset;

  btn.addEventListener('click', async () => {
    if (confirm(`Are you sure you want to delete ${filename}?`)) {
      await fetch(`/configs/${filename}`, { method: 'DELETE' });

      // the result of this operation will be
      location.reload();
    }
  });
});
