export function createNodeElement(node, handlers) {
  const element = document.createElement("article");
  element.className = "folder-node";
  element.dataset.id = node.id;
  element.innerHTML = `<div class="node-title"><button class="node-toggle" type="button" aria-label="展開">${node.hasChildren ? (node.expanded ? "▾" : "▸") : "·"}</button><span></span></div><div class="node-path"></div>`;
  element.querySelector("span").textContent = node.name;
  element.querySelector(".node-path").textContent = node.path;
  element.querySelector(".node-path").title = node.path;
  element.querySelector("button").addEventListener("click", (event) => { event.stopPropagation(); if (node.hasChildren) handlers.toggle(node.id); });
  element.addEventListener("pointerdown", (event) => handlers.drag(event, node.id));
  return element;
}

export function updateNodeElement(element, node, selected) {
  element.style.transform = `translate(${node.x}px, ${node.y}px)`;
  element.classList.toggle("selected", selected);
  element.querySelector(".node-toggle").textContent = node.hasChildren ? (node.expanded ? "▾" : "▸") : "·";
}
