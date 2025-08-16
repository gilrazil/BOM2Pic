function populateColumns(select) {
  const letters = [];
  for (let i = 0; i < 26; i++) letters.push(String.fromCharCode(65 + i));
  select.innerHTML = letters.map(l => `<option value="${l}">${l}</option>`).join('');
}

function setAlert(message, type = 'danger') {
  const alertBox = document.getElementById('alertBox');
  alertBox.className = `alert alert-${type}`;
  alertBox.textContent = message;
  alertBox.classList.remove('d-none');
}

function clearAlert() {
  const alertBox = document.getElementById('alertBox');
  alertBox.className = 'alert d-none';
  alertBox.textContent = '';
}

function toggleLoading(isLoading) {
  const btn = document.getElementById('processBtn');
  const text = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner-border');
  btn.disabled = isLoading;
  spinner.classList.toggle('d-none', !isLoading);
  text.textContent = isLoading ? 'Processing…' : 'Process';
}

document.addEventListener('DOMContentLoaded', () => {
  populateColumns(document.getElementById('imageColumn'));
  populateColumns(document.getElementById('nameColumn'));

  const form = document.getElementById('uploadForm');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearAlert();

    const fileInput = document.getElementById('xlsxFiles');
    const files = Array.from(fileInput.files || []);
    const imageColumn = document.getElementById('imageColumn').value;
    const nameColumn = document.getElementById('nameColumn').value;

    // Basic validation
    if (!files.length) {
      setAlert('Please select at least one .xlsx file (you can also choose a folder).');
      return;
    }
    const tooBig = files.find(f => f.size > 20 * 1024 * 1024);
    if (tooBig) {
      setAlert(`File too large: ${tooBig.name}. Max 20MB each.`);
      return;
    }
    const invalid = files.find(f => !f.name.toLowerCase().endsWith('.xlsx'));
    if (invalid) {
      setAlert(`Unsupported file: ${invalid.name}. Only .xlsx files are allowed.`);
      return;
    }

    const formData = new FormData();
    for (const f of files) formData.append('files', f, f.name);
    formData.append('imageColumn', imageColumn);
    formData.append('nameColumn', nameColumn);

    toggleLoading(true);
    try {
      const resp = await fetch('/process', { method: 'POST', body: formData });
      if (!resp.ok) {
        let detail = 'Processing failed.';
        try {
          const data = await resp.json();
          if (data && data.detail) detail = data.detail;
        } catch (err) {
          detail = await resp.text();
        }
        setAlert(detail || 'Processing failed.');
        return;
      }

      // Read counts from headers for KISS summary (filename-only duplicates)
      const processed = parseInt(resp.headers.get('X-B2P-Processed') || '0', 10);
      const saved = parseInt(resp.headers.get('X-B2P-Saved') || '0', 10);
      const duplicate = parseInt(resp.headers.get('X-B2P-Duplicate') || '0', 10);

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // Extract filename from Content-Disposition if present
      const cd = resp.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename\s*=\s*"?([^";]+)"?/i);
      a.download = match ? match[1] : 'bom2pic.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setAlert(`ZIP ready. Processed: ${processed}. Saved: ${saved}. Duplicate: ${duplicate}.`, 'success');
    } catch (err) {
      console.error(err);
      setAlert('Unexpected error. Please try again.');
    } finally {
      toggleLoading(false);
    }
  });
});


