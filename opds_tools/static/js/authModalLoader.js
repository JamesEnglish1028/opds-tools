function loadAuthModal(url) {
  const modalContent = document.getElementById("authDocModalContent");
  modalContent.innerHTML = '<div class="modal-body">Loading...</div>';

  fetch(`/auth_doc_modal?url=${encodeURIComponent(url)}`)
    .then(res => {
      if (!res.ok) throw new Error("Network error");
      return res.text();
    })
    .then(html => {
      modalContent.innerHTML = html;
    })
    .catch(err => {
      modalContent.innerHTML = '<div class="modal-body text-danger">Failed to load document.</div>';
    });
}
