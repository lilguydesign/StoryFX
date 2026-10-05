// Request IDs identify a pending connector; they never approve it or carry access.
let consumed = false;

export function showAssociationLink(active) {
  if (!active || consumed || document.querySelector('dialog[open]')) return;
  const url = new URL(window.location.href);
  const request = url.searchParams.get('windows_request');
  if (!request || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(request)) return;
  consumed = true;
  document.querySelector('#windows-form').elements.request_id.value = request;
  url.searchParams.delete('windows_request');
  window.history.replaceState(null, '', url.pathname + url.search + url.hash);
  document.querySelector('#windows-dialog').showModal();
}
