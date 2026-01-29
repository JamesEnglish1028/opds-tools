<script>
document.addEventListener("DOMContentLoaded", () => {
  loadDbCatalogs();

  document.getElementById("addCatalogForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const title = document.getElementById("catalogName").value;
    const description = document.getElementById("catalogDescription").value;
    const url = document.getElementById("catalogURL").value;

    const response = await fetch("/api/catalogs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({title, description, url})
    });

    if (response.ok) {
      loadDbCatalogs();
      e.target.reset();
    } else {
      alert("Failed to add catalog");
    }
  });
});

async function loadDbCatalogs() {
  const res = await fetch("/api/catalogs");
  const catalogs = await res.json();
  const list = document.getElementById("registryList");
  list.innerHTML = "";

  catalogs.forEach(cat => {
    const li = document.createElement("li");
    li.className = "list-group-item d-flex justify-content-between align-items-start";
    li.innerHTML = `
      <div>
        <div><strong>${cat.title}</strong></div>
        <small>${cat.description}</small><br>
        <code>${cat.url}</code>
      </div>
      <button class="btn btn-sm btn-outline-danger" onclick="deleteCatalog(${cat.id})">Delete</button>
    `;
    list.appendChild(li);
  });
}

async function deleteCatalog(id) {
  if (!confirm("Are you sure you want to delete this catalog?")) return;
  const res = await fetch(`/api/catalogs/${id}`, { method: "DELETE" });
  if (res.ok) {
    loadDbCatalogs();
  } else {
    alert("Failed to delete catalog.");
  }
}
</script>
