function loadRegistryList() {
  fetch('/static/registry.json')
    .then(response => response.json())
    .then(data => {
      const list = document.getElementById('registryList');
      list.innerHTML = '';

      if (!data.catalogs || !data.catalogs.length) {
        list.innerHTML = '<li class="list-group-item text-muted">No catalogs available.</li>';
        return;
      }

      data.catalogs.forEach((catalog, index) => {
        const title = catalog.metadata?.title || 'Untitled';
        const description = catalog.metadata?.description || '';
        const href = catalog.links?.[0]?.href || '#';

        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
          <div>
            <strong>${title}</strong><br>
            <small>${description}</small><br>
            <code>${href}</code>
          </div>
          <div class="btn-group">
            <button class="btn btn-sm btn-outline-primary" onclick="editCatalog(${index})">Edit</button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteCatalog(${index})">Delete</button>
          </div>
        `;
        list.appendChild(li);
      });
    })
    .catch(error => {
      console.error('Failed to load registry:', error);
    });
}

function saveNewCatalog() {
  const name = document.getElementById('new-catalog-name').value.trim();
  const description = document.getElementById('new-catalog-description').value.trim();
  const url = document.getElementById('new-catalog-url').value.trim();

  if (!name || !url) {
    alert("Name and URL are required.");
    return;
  }

  fetch('/static/registry.json')
    .then(response => response.json())
    .then(data => {
      const newCatalog = {
        metadata: { title: name, description },
        links: [
          {
            rel: "http://opds-spec.org/catalog",
            href: url,
            type: "application/opds+json"
          }
        ]
      };

      data.catalogs.push(newCatalog);

      return fetch('/save-registry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
    })
    .then(response => {
      if (!response.ok) throw new Error('Failed to save registry.');
      return response.json();
    })
    .then(() => {
      document.getElementById('new-catalog-name').value = '';
      document.getElementById('new-catalog-description').value = '';
      document.getElementById('new-catalog-url').value = '';
      loadRegistryList();
    })
    .catch(error => {
      alert('Error saving catalog: ' + error.message);
    });
}

function editCatalog(index) {
  alert("Edit logic not yet implemented (but will go here for index: " + index + ")");
}

function deleteCatalog(index) {
  if (!confirm("Are you sure you want to delete this catalog?")) return;

  fetch('/static/registry.json')
    .then(response => response.json())
    .then(data => {
      data.catalogs.splice(index, 1);
      return fetch('/save-registry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
    })
    .then(() => loadRegistryList())
    .catch(error => {
      alert('Error deleting catalog: ' + error.message);
    });
}

// Tab auto-loading logic
document.addEventListener('DOMContentLoaded', function () {
  const tabContainer = document.getElementById('opdsTabs');

  if (tabContainer) {
    tabContainer.addEventListener('shown.bs.tab', function (event) {
      const target = event.target.getAttribute('data-bs-target');
      if (target === '#registry') {
        loadRegistryList();
      }
    });

    const activeTab = tabContainer.querySelector('.nav-link.active');
    if (activeTab && activeTab.getAttribute('data-bs-target') === '#registry') {
      loadRegistryList();
    }
  }
});
