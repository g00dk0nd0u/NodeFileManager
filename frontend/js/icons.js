const paths = {
  folder: '<path d="M3 5.5h4l1.5 2H17v7.5H3z"/>',
  file: '<path d="M5 2.5h6l4 4v9H5z"/><path d="M11 2.5v4h4"/>',
  star: '<path d="m10 2.5 2.2 4.4 4.8.7-3.5 3.4.8 4.8-4.3-2.3-4.3 2.3.8-4.8L3 7.6l4.8-.7z"/>',
  close: '<path d="m5 5 10 10M15 5 5 15"/>',
  plus: '<path d="M10 4v12M4 10h12"/>',
  refresh: '<path d="M16 7V3l-1.8 1.8A7 7 0 1 0 17 10"/>',
  previous: '<path d="m12.5 5-5 5 5 5"/>',
  next: '<path d="m7.5 5 5 5-5 5"/>',
  up: '<path d="m5 12.5 5-5 5 5"/>',
  search: '<circle cx="8.5" cy="8.5" r="4.5"/><path d="m12 12 4 4"/>',
};

export function createIcon(name) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.classList.add("icon");
  icon.setAttribute("viewBox", "0 0 20 20");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("fill", "none");
  icon.setAttribute("stroke", "currentColor");
  icon.setAttribute("stroke-width", "1.6");
  icon.setAttribute("stroke-linecap", "round");
  icon.setAttribute("stroke-linejoin", "round");
  icon.innerHTML = paths[name];
  return icon;
}
