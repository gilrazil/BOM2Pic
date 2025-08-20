// Supabase client configuration (will be set from server)
let supabaseClient = null;
let currentUser = null;

document.addEventListener('DOMContentLoaded', function() {
  // Initialize Supabase client
  initializeSupabase();
  
  const form = document.getElementById('uploadForm');
  const fileInput = document.getElementById('xlsxFiles');
  const folderBtn = document.getElementById('folderBtn');
  const imageColumnSelect = document.getElementById('imageColumn');
  const nameColumnSelect = document.getElementById('nameColumn');
  const processBtn = document.getElementById('processBtn');
  const alertBox = document.getElementById('alertBox');

  // Authentication elements
  const signInBtn = document.getElementById('signInBtn');
  const signOutBtn = document.getElementById('signOutBtn');
  const signInModal = new bootstrap.Modal(document.getElementById('signInModal'));
  const signInForm = document.getElementById('signInForm');

  // Cumulative counter elements
  const totalCounter = document.getElementById('totalCounter');
  const counterDisplay = document.getElementById('counterDisplay');

  function setAlert(message, type = 'danger') {
    alertBox.innerHTML = message; // Use innerHTML to allow HTML links
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

  // Authentication functions
  function initializeSupabase() {
    // We'll set this from environment variables via a separate config endpoint
    // For now, we'll check if user is authenticated via session storage
    checkAuthState();
  }

  function checkAuthState() {
    // Check if user is signed in (simplified for demo)
    const authToken = localStorage.getItem('supabase-auth-token');
    if (authToken) {
      // User appears to be signed in
      showAuthenticatedState({
        email: localStorage.getItem('user-email') || 'user@example.com',
        plan: localStorage.getItem('user-plan') || 'free'
      });
    } else {
      showUnauthenticatedState();
    }
  }

  function showAuthenticatedState(user) {
    currentUser = user;
    document.getElementById('notAuthenticatedUI').style.display = 'none';
    document.getElementById('authenticatedUI').style.display = 'flex';
    document.getElementById('userEmail').textContent = user.email;
    document.getElementById('userPlan').textContent = `${user.plan.charAt(0).toUpperCase() + user.plan.slice(1)} Plan`;
    
    // Update plan badge color
    const planBadge = document.getElementById('userPlan');
    planBadge.className = 'badge ' + (user.plan === 'free' ? 'bg-secondary' : 'bg-success');
  }

  function showUnauthenticatedState() {
    currentUser = null;
    document.getElementById('notAuthenticatedUI').style.display = 'flex';
    document.getElementById('authenticatedUI').style.display = 'none';
  }

  // Event listeners for authentication
  signInBtn.addEventListener('click', function() {
    signInModal.show();
  });

  signOutBtn.addEventListener('click', function() {
    // Simple sign out - clear local storage
    localStorage.removeItem('supabase-auth-token');
    localStorage.removeItem('user-email');
    localStorage.removeItem('user-plan');
    showUnauthenticatedState();
    setAlert('Signed out successfully', 'success');
  });

  signInForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const email = document.getElementById('emailInput').value;
    const sendBtn = document.getElementById('sendMagicLinkBtn');
    const spinner = document.getElementById('signInSpinner');
    const messageDiv = document.getElementById('signInMessage');
    
    // Show loading state
    sendBtn.disabled = true;
    spinner.classList.remove('d-none');
    
    try {
      // For demo purposes, simulate magic link sending
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Show success message
      messageDiv.innerHTML = `
        <div class="alert alert-success mb-0">
          <strong>Magic link sent!</strong><br>
          Check your email and click the link to sign in.
        </div>
      `;
      messageDiv.classList.remove('d-none');
      
      // For demo, auto-sign in after 3 seconds (remove this in production)
      setTimeout(() => {
        localStorage.setItem('supabase-auth-token', 'demo-token');
        localStorage.setItem('user-email', email);
        localStorage.setItem('user-plan', 'free');
        signInModal.hide();
        showAuthenticatedState({ email, plan: 'free' });
        setAlert('Successfully signed in! You now have 200 free images per month.', 'success');
      }, 3000);
      
    } catch (error) {
      messageDiv.innerHTML = `
        <div class="alert alert-danger mb-0">
          Failed to send magic link. Please try again.
        </div>
      `;
      messageDiv.classList.remove('d-none');
    } finally {
      sendBtn.disabled = false;
      spinner.classList.add('d-none');
    }
  });

  // Cumulative counter functions
  function updateCumulativeCount(newImages) {
    const current = getCumulativeCount();
    const updated = current + newImages;
    localStorage.setItem('bom2pic-total-images', updated.toString());
    updateCounterDisplay();
  }

  function getCumulativeCount() {
    return parseInt(localStorage.getItem('bom2pic-total-images') || '0', 10);
  }

  function updateCounterDisplay() {
    if (counterDisplay) {
      const count = getCumulativeCount();
      animateCount(counterDisplay, count);
    }
  }

  function animateCount(element, targetCount) {
    const currentCount = parseInt(element.textContent.replace(/,/g, '') || '0', 10);
    const increment = Math.ceil((targetCount - currentCount) / 20);
    
    if (currentCount < targetCount) {
      const newCount = Math.min(currentCount + increment, targetCount);
      element.textContent = newCount.toLocaleString();
      setTimeout(() => animateCount(element, targetCount), 50);
    }
  }

  // Initialize counter display
  updateCounterDisplay();

  // Handle folder button (Chrome/Safari only)
  if (folderBtn) {
    folderBtn.addEventListener('click', function() {
      const folderInput = document.createElement('input');
      folderInput.type = 'file';
      folderInput.accept = '.xlsx';
      folderInput.multiple = true;
      folderInput.webkitdirectory = true;

      folderInput.onchange = function() {
        const dt = new DataTransfer();
        for (const file of folderInput.files) {
          if (file.name.toLowerCase().endsWith('.xlsx')) {
            dt.items.add(file);
          }
        }
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
      };

      folderInput.click();
    });

    if (!('webkitdirectory' in document.createElement('input'))) {
      folderBtn.style.display = 'none';
    }
  }

  // Main form submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearAlert();

    const allFiles = Array.from(fileInput.files || []);
    const imageColumn = imageColumnSelect.value;
    const nameColumn = nameColumnSelect.value;

    // Filter out system files like .DS_Store and ensure only .xlsx
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
      // Add authentication header if user is signed in
      const headers = {};
      const authToken = localStorage.getItem('supabase-auth-token');
      if (authToken && authToken !== 'demo-token') {
        headers['Authorization'] = `Bearer ${authToken}`;
      }

      const resp = await fetch('/process', { 
        method: 'POST', 
        body: formData,
        headers: headers
      });
      
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

      // Read counts from headers
      const processed = parseInt(resp.headers.get('X-B2P-Processed') || '0', 10);
      const saved = parseInt(resp.headers.get('X-B2P-Saved') || '0', 10);
      const duplicate = parseInt(resp.headers.get('X-B2P-Duplicate') || '0', 10);
      const plan = resp.headers.get('X-B2P-Plan') || 'demo';
      const authenticated = resp.headers.get('X-B2P-User-Authenticated') === 'true';

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);

      // Update cumulative counter
      updateCumulativeCount(processed);

      // Display summary with plan info
      let planMessage = '';
      if (authenticated) {
        planMessage = ` (${plan} plan)`;
      } else {
        planMessage = ' (demo mode - <a href="#" onclick="document.getElementById(\'signInBtn\').click()">sign in</a> for 200 free images/month)';
      }

      setAlert(`Processed ${processed} images${planMessage} (${saved} saved, ${duplicate} duplicates). <a href="${url}" download="bom2pic_images.zip">Download ZIP</a>`, 'success');

      // Clear form
      fileInput.value = '';
      imageColumnSelect.value = '';
      nameColumnSelect.value = '';
      form.classList.remove('was-validated');

    } catch (error) {
      console.error('Fetch error:', error);
      setAlert('An unexpected error occurred. Please try again.');
    } finally {
      toggleLoading(false);
    }
  });

  // Form validation
  form.addEventListener('change', function() {
    if (form.checkValidity()) {
      processBtn.removeAttribute('disabled');
    } else {
      processBtn.setAttribute('disabled', 'true');
    }
  });

  form.addEventListener('submit', function() {
    form.classList.add('was-validated');
  });

  // Populate column dropdowns (A-Z)
  function populateColumns() {
    const columns = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    const defaultOption = '<option value="">Select column...</option>';
    imageColumnSelect.innerHTML = defaultOption + columns.map(col => `<option value="${col}">${col}</option>`).join('');
    nameColumnSelect.innerHTML = defaultOption + columns.map(col => `<option value="${col}">${col}</option>`).join('');
  }
  populateColumns();
});