document.addEventListener("DOMContentLoaded", function () {
  const navButtons = document.querySelectorAll(".nav-collection-btn");
  const pubContainer = document.getElementById("publication-section");

  navButtons.forEach(button => {
    button.addEventListener("click", function () {
      const url = this.dataset.url;
      if (!url) {
        alert("No URL associated with this navigation link.");
        return;
      }

      pubContainer.innerHTML = "<p class='text-muted'>Loading publications...</p>";
      fetch(`/fetch_partial?source_url=${encodeURIComponent(url)}`)
        .then(response => {
          if (!response.ok) {
            throw new Error("Failed to fetch publications.");
          }
          return response.text();
        })
        .then(html => {
          pubContainer.innerHTML = html;
        })
        .catch(error => {
          pubContainer.innerHTML = `<p class='text-danger'>Error: ${error.message}</p>`;
        });
    });
  });
});
