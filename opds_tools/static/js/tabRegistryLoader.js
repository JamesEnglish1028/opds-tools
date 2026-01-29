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
