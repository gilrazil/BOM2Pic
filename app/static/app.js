document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('uploadForm');
  const fileInput = document.getElementById('xlsxFiles');
  const imageColumnSelect = document.getElementById('imageColumn');
  const nameColumnSelect = document.getElementById('nameColumn');
  const processBtn = document.getElementById('processBtn');
  const alertBox = document.getElementById('alertBox');

  // Cumulative counter elements
  const totalCounter = document.getElementById('totalCounter');
  const counterDisplay = document.getElementById('counterDisplay');

  function setAlert(message, type = 'danger') {
    alertBox.textContent = message;
    alertBox.className = `alert alert-${type}`;
    alertBox.classList.remove('d-none');
    alertBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function clearAlert() {
    alertBox.classList.add('d-none');
  }

  function toggleLoading(isLoading) {
    processBtn.disabled = isLoading;
    processBtn.textContent = isLoading ? 'Processing...' : 'Process';
  }

  // Populate column dropdowns A-Z
  function populateColumns() {
    const columns = [];
    for (let i = 0; i < 26; i++) {
      columns.push(String.fromCharCode(65 + i)); // A, B, C, ...
    }
    
    [imageColumnSelect, nameColumnSelect].forEach(select => {
      select.innerHTML = '<option value="">Choose column...</option>';
      columns.forEach(col => {
        const option = document.createElement('option');
        option.value = col;
        option.textContent = col;
        select.appendChild(option);
      });
    });
    
    // Set defaults
    imageColumnSelect.value = 'A';
    nameColumnSelect.value = 'C';
  }

  // Initialize columns
  populateColumns();

  // Cumulative counter functions
  function renderOdometer(num) {
    const numStr = num.toString().padStart(6, '0');
    return numStr.split('').map(digit => 
      `<span class="digit">${digit}</span>`
    ).join('');
  }

  function getCumulativeCount() {
    const stored = localStorage.getItem('bom2pic-cumulative-count');
    return stored ? parseInt(stored, 10) : 0;
  }

  function setCumulativeCount(count) {
    localStorage.setItem('bom2pic-cumulative-count', count.toString());
  }

  function updateCounterDisplay(newCount) {
    if (counterDisplay) {
      counterDisplay.innerHTML = renderOdometer(newCount);
    }
  }

  function animateCount(fromCount, toCount) {
    const duration = 1500; // 1.5 seconds
    const startTime = performance.now();
    
    function animate(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Ease-out animation
      const easedProgress = 1 - Math.pow(1 - progress, 3);
      const currentCount = Math.floor(fromCount + (toCount - fromCount) * easedProgress);
      
      updateCounterDisplay(currentCount);
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    }
    
    requestAnimationFrame(animate);
  }

  // Initialize counter display
  const currentCount = getCumulativeCount();
  updateCounterDisplay(currentCount);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearAlert();

    const allFiles = Array.from(fileInput.files || []);
    const imageColumn = document.getElementById('imageColumn').value;
    const nameColumn = document.getElementById('nameColumn').value;

    // Filter out system files like .DS_Store
    const files = allFiles.filter(f => {
      const name = f.name.toLowerCase();
      return !name.startsWith('.') && name.endsWith('.xlsx');
    });

    // Basic validation
    if (!files.length) {
      if (allFiles.length > 0) {
        setAlert('No valid .xlsx files found. Please select Excel files only.');
      } else {
        setAlert('Please select at least one .xlsx file (you can also choose a folder).');
      }
      return;
    }
    const tooBig = files.find(f => f.size > 20 * 1024 * 1024);
    if (tooBig) {
      setAlert(`File too large: ${tooBig.name}. Max 20MB each.`);
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
          if (data && data.detail) {
            detail = data.detail;
          }
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
      a.download = resp.headers.get('Content-Disposition')?.match(/filename=(.+)/)?.[1] || 'bom2pic.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      // Update cumulative counter
      const oldCount = getCumulativeCount();
      const newCount = oldCount + processed;
      setCumulativeCount(newCount);
      animateCount(oldCount, newCount);

      // Show success summary
      setAlert(`Success! Processed ${processed} images (${saved} saved, ${duplicate} duplicates). Download started.`, 'success');
    } catch (error) {
      console.error('Upload error:', error);
      setAlert('Network error. Please try again.');
    } finally {
      toggleLoading(false);
    }
  });

  // Handle file input changes for folder/file selection
  fileInput.addEventListener('change', function() {
    const files = Array.from(this.files || []);
    if (files.length > 0) {
      console.log(`Selected ${files.length} file(s)`);
    }
  });
});