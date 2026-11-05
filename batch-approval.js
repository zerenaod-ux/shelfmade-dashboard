/**
 * Batch Approval Module
 * Adds bulk approval UI to the dashboard
 * Injects checkboxes and bulk approve button
 */

// Inject batch approval toolbar
function injectBatchApprovalUI() {
  const librarySection = document.getElementById('view-library');
  if (!librarySection) return;

  const toolbar = document.querySelector('#view-library .toolbar');
  if (!toolbar) return;

  // Check if already injected
  if (document.getElementById('batch-toolbar')) return;

  // Create batch toolbar
  const batchToolbar = document.createElement('div');
  batchToolbar.id = 'batch-toolbar';
  batchToolbar.style.cssText = 'display: flex; gap: 10px; margin-top: 10px; align-items: center;';
  batchToolbar.innerHTML = `
    <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
      <input type="checkbox" id="select-all" style="width: 18px; height: 18px;">
      <span>Select all visible</span>
    </label>
    <span id="selected-count" style="color: var(--muted); font-size: 13px;">0 selected</span>
    <button id="batch-approve" class="primary" disabled style="background: var(--forest); color: white;">
      Approve Selected
    </button>
    <button id="batch-reject" disabled style="background: #e74c3c; color: white; border-color: #e74c3c;">
      Reject Selected
    </button>
  `;

  toolbar.parentNode.insertBefore(batchToolbar, toolbar.nextSibling);

  // Add event listeners
  document.getElementById('select-all').addEventListener('change', toggleSelectAll);
  document.getElementById('batch-approve').addEventListener('click', batchApprove);
  document.getElementById('batch-reject').addEventListener('click', batchReject);
}

// Add checkboxes to video cards
function addCheckboxesToCards() {
  const cards = document.querySelectorAll('#library .card');
  cards.forEach(card => {
    if (card.querySelector('.batch-checkbox')) return; // Already has checkbox

    const itemId = card.dataset.itemId;
    if (!itemId) return;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'batch-checkbox';
    checkbox.dataset.id = itemId;
    checkbox.style.cssText = 'position: absolute; top: 10px; right: 10px; width: 20px; height: 20px; z-index: 10;';
    
    // Prevent checkbox from triggering card click
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', updateSelectedCount);

    card.style.position = 'relative';
    card.appendChild(checkbox);
  });
}

// Toggle select all
function toggleSelectAll(e) {
  const checked = e.target.checked;
  document.querySelectorAll('#library .batch-checkbox').forEach(cb => {
    cb.checked = checked;
  });
  updateSelectedCount();
}

// Update selected count
function updateSelectedCount() {
  const selected = document.querySelectorAll('#library .batch-checkbox:checked').length;
  const countEl = document.getElementById('selected-count');
  const approveBtn = document.getElementById('batch-approve');
  const rejectBtn = document.getElementById('batch-reject');

  countEl.textContent = `${selected} selected`;
  approveBtn.disabled = selected === 0;
  rejectBtn.disabled = selected === 0;
}

// Batch approve
async function batchApprove() {
  const selected = Array.from(document.querySelectorAll('#library .batch-checkbox:checked'))
    .map(cb => cb.dataset.id);

  if (selected.length === 0) return;
  if (!confirm(`Approve ${selected.length} videos? Confirm you reviewed the facts, narration, and visuals for every selected video.`)) return;

  const approveBtn = document.getElementById('batch-approve');
  approveBtn.disabled = true;
  approveBtn.textContent = 'Approving...';

  try {
    const response = await fetch('/api/batch-decision', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-ShelfMade': 'local'
      },
      body: JSON.stringify({
        ids: selected,
        status: 'approved',
        checks: { facts: true, narration: true, visuals: true }
      })
    });

    const result = await response.json();

    if (result.success && result.success.length > 0) {
      alert(`Approved ${result.success.length} videos successfully.`);
      location.reload(); // Refresh to show updated status
    } else {
      alert(`Approval completed with errors:\nSuccess: ${result.success.length}\nFailed: ${result.failed.length}`);
      if (result.failed && result.failed.length > 0) {
        console.error('Failed items:', result.failed);
      }
    }
  } catch (error) {
    alert('Batch approval failed: ' + error.message);
    console.error(error);
  } finally {
    approveBtn.disabled = false;
    approveBtn.textContent = 'Approve Selected';
  }
}

// Batch reject
async function batchReject() {
  const selected = Array.from(document.querySelectorAll('#library .batch-checkbox:checked'))
    .map(cb => cb.dataset.id);

  if (selected.length === 0) return;

  if (!confirm(`Reject ${selected.length} videos?`)) return;

  const rejectBtn = document.getElementById('batch-reject');
  rejectBtn.disabled = true;
  rejectBtn.textContent = 'Rejecting...';

  try {
    const response = await fetch('/api/batch-decision', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-ShelfMade': 'local'
      },
      body: JSON.stringify({
        ids: selected,
        status: 'rejected'
      })
    });

    const result = await response.json();

    if (result.success && result.success.length > 0) {
      alert(`Rejected ${result.success.length} videos successfully.`);
      location.reload(); // Refresh to show updated status
    } else {
      alert(`Rejection completed with errors:\nSuccess: ${result.success.length}\nFailed: ${result.failed.length}`);
      if (result.failed && result.failed.length > 0) {
        console.error('Failed items:', result.failed);
      }
    }
  } catch (error) {
    alert('Batch rejection failed: ' + error.message);
    console.error(error);
  } finally {
    rejectBtn.disabled = false;
    rejectBtn.textContent = 'Reject Selected';
  }
}

// Initialize when library view is active
function initBatchApproval() {
  const observer = new MutationObserver(() => {
    if (document.getElementById('view-library').classList.contains('hidden')) return;
    injectBatchApprovalUI();
    addCheckboxesToCards();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  // Initial injection
  if (!document.getElementById('view-library').classList.contains('hidden')) {
    injectBatchApprovalUI();
    addCheckboxesToCards();
  }
}

// Start
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initBatchApproval);
} else {
  initBatchApproval();
}
