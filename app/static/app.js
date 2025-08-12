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

    const fileInput = document.getElementById('xlsxFile');
    const file = fileInput.files[0];
    const imageColumn = document.getElementById('imageColumn').value;
    const nameColumn = document.getElementById('nameColumn').value;

    // Basic validation
    if (!file || !file.name.toLowerCase().endsWith('.xlsx')) {
      setAlert('Please select a valid .xlsx file.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setAlert('File too large. Max 20MB.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
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

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Bom2Pic_Images.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setAlert('ZIP downloaded successfully.', 'success');
    } catch (err) {
      console.error(err);
      setAlert('Unexpected error. Please try again.');
    } finally {
      toggleLoading(false);
    }
  });
});


