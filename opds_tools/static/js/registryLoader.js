function loadRegistry() {
  const input = document.getElementById('registry-url');
  const accordion = document.getElementById('catalogAccordion');
  const titleEl = document.getElementById('registryTitle');
  const url = input.value.trim();

  if (!url) {
    alert("Please enter a registry URL.");
    return;
  }

  accordion.innerHTML = '<div class="p-2">Loading...</div>';
  if (titleEl) titleEl.textContent = '';

  fetch(`/registry/fetch-registry?url=${encodeURIComponent(url)}`)
    .then(res => {
      if (!res.ok) {
        return res.json().then(errData => {
          throw new Error(errData.error || `Failed to fetch: ${res.statusText}`);
        });
      }
      return res.json();
    })
    .then(data => {
      const catalogs = data.catalogs || data.navigation;
      if (!Array.isArray(catalogs) || catalogs.length === 0) {
        throw new Error("No valid 'catalogs' or 'navigation' entries found in response.");
      }

      accordion.innerHTML = '';
      const registryTitle = data.metadata?.title || data.title || 'Registry Catalogs';
      if (titleEl) titleEl.textContent = registryTitle;

      const stateGroups = {};

      catalogs.forEach(catalog => {
        const desc = catalog.metadata?.description || '';
        const stateMatch = desc.match(/,\s*([A-Z]{2})\s*$/);
        const state = stateMatch ? stateMatch[1] : 'Other';

        if (!stateGroups[state]) stateGroups[state] = [];
        stateGroups[state].push(catalog);
      });

      const sortedStates = Object.keys(stateGroups).sort();

      sortedStates.forEach((state, index) => {
        const collapseId = `collapse-${state}-${index}`;
        const headingId = `heading-${state}-${index}`;

        const card = document.createElement('div');
        card.className = 'accordion-item';

        card.innerHTML = `
          <h2 class="accordion-header" id="${headingId}">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
              data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
              ${state}
            </button>
          </h2>
          <div id="${collapseId}" class="accordion-collapse collapse" aria-labelledby="${headingId}"
            data-bs-parent="#catalogAccordion">
            <div class="accordion-body p-0">
              <ul class="list-group list-group-flush" id="list-${state}"></ul>
            </div>
          </div>
        `;
        accordion.appendChild(card);

        const ul = card.querySelector(`#list-${state}`);
        stateGroups[state].forEach(catalog => {
          const title = catalog.metadata?.title || catalog.title || 'Untitled';
          const catalogUrl = catalog.links?.[0]?.href || '#';

          const item = document.createElement('li');
          item.className = 'list-group-item d-flex justify-content-between align-items-center';
          item.innerHTML = `
            <div>
              <strong>${title}</strong><br>
              <small class="text-muted">${catalogUrl}</small>
            </div>
            <button class="btn btn-sm btn-outline-primary" onclick="selectCatalog('${catalogUrl}')">Use</button>
          `;
          ul.appendChild(item);
        });
      });
    })
    .catch(err => {
      console.error("🛑 Registry Load Error:", err);
      accordion.innerHTML = `<div class="p-2 text-danger">Error: ${err.message}</div>`;
    });
}

window.selectCatalog = function (url) {
  const input = document.getElementById('feed_url');
  const resolvedUrl = /^https?:\/\//i.test(url)
    ? url
    : new URL(url, window.location.origin).href;

  if (input) input.value = resolvedUrl;

  const modalEl = document.getElementById('registryModal');
  if (modalEl) {
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (modalInstance) modalInstance.hide();
  }

  const form = document.getElementById('feed-form');
  if (form) form.submit();
};
