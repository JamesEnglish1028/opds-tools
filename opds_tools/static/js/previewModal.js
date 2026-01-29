// static/js/previewModal.js

function formatXml(xml) {
  const PADDING = "  ";
  const reg = /(>)(<)(\/*)/g;
  let formatted = "";
  let pad = 0;

  xml = xml.replace(reg, "$1\r\n$2$3");
  xml.split("\r\n").forEach((node) => {
    let indent = 0;
    if (node.match(/.+<\/\w[^>]*>$/)) {
      indent = 0;
    } else if (node.match(/^<\/\w/)) {
      if (pad !== 0) pad -= 1;
    } else if (node.match(/^<\w([^>]*[^/])?>.*$/)) {
      indent = 1;
    } else {
      indent = 0;
    }

    formatted += PADDING.repeat(pad) + node + "\r\n";
    pad += indent;
  });

  return formatted;
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.opds-preview-link').forEach(link => {
    link.addEventListener('click', async function (e) {
      e.preventDefault();
      const url = this.dataset.url;
      const rel = this.dataset.rel;

      const modal = new bootstrap.Modal(document.getElementById('previewModal'));
      const modalBody = document.getElementById('previewModalBody');
      const modalTitle = document.getElementById('previewModalLabel');

      modalTitle.textContent = `Preview for rel: ${rel}`;
      modalBody.innerHTML = '<p class="text-muted">Loading preview...</p>';

      try {
        const response = await fetch(`/preview-proxy?url=${encodeURIComponent(url)}`);
        const rawText = await response.text();

        try {
          const data = JSON.parse(rawText);
          modalBody.innerHTML = `
            <pre class="bg-light p-3 border rounded small text-start">${JSON.stringify(data, null, 2)}</pre>
          `;
        } catch {
          modalBody.innerHTML = `<pre class="bg-light p-3 border rounded small text-start text-muted">${rawText}</pre>`;
        }

      } catch (error) {
        modalBody.innerHTML = `<div class="text-danger">Failed to load preview: ${error.message}</div>`;
      }

      modal.show();
    });
  });
});
