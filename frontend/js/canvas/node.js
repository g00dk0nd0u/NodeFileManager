export function createNodeElement(node, handlers) {
  const element = document.createElement("article");
  element.className = "folder-node";
  element.dataset.id = node.id;
  element.innerHTML = `<div class="node-title"><button class="node-toggle" type="button" aria-label="展開">${node.hasChildren ? (node.expanded ? "▾" : "▸") : "·"}</button><span></span></div><div class="node-path"></div><div class="node-files"></div>`;
  element.querySelector("span").textContent = node.name;
  element.querySelector(".node-path").textContent = node.path;
  element.querySelector(".node-path").title = node.path;
  element.querySelector("button").addEventListener("click", (event) => { event.stopPropagation(); if (node.hasChildren) handlers.toggle(node.id); });
  element.addEventListener("pointerdown", (event) => handlers.drag(event, node.id));
  element.addEventListener("contextmenu", (event) => { if (!event.target.closest(".file-item")) { event.preventDefault(); handlers.selectFolder(node.id); handlers.rename(); } });
  element.addEventListener("dragover", (event) => { if (event.dataTransfer.types.includes("application/x-nodefilemanager-item")) { event.preventDefault(); element.classList.add("drop-target"); } });
  element.addEventListener("dragleave", () => element.classList.remove("drop-target"));
  element.addEventListener("drop", (event) => { event.preventDefault(); element.classList.remove("drop-target"); handlers.drop(event, node.id); });
  return element;
}

export function updateNodeElement(element, node, selected, selectedItem, handlers) {
  element.style.transform = `translate(${node.x}px, ${node.y}px)`;
  element.classList.toggle("selected", selected);
  element.querySelector(".node-toggle").textContent = node.hasChildren ? (node.expanded ? "▾" : "▸") : "·";
  const list = element.querySelector(".node-files");
  list.hidden = !node.expanded;
  list.replaceChildren(...(node.expanded ? (node.files || []).map((file) => {
    const row = document.createElement("div");
    row.className = "file-item"; row.draggable = true; row.dataset.id = file.id;
    row.title = `${file.path}\nダブルクリック: 開く / 右クリック: 名前変更`;
    row.classList.toggle("selected", selectedItem === file.id); row.textContent = `📄 ${file.name}`;
    row.addEventListener("pointerdown", (event) => { event.stopPropagation(); handlers.selectFile(file); });
    row.addEventListener("dblclick", (event) => { event.stopPropagation(); handlers.open(file.id); });
    row.addEventListener("contextmenu", (event) => { event.preventDefault(); event.stopPropagation(); handlers.selectFile(file); handlers.rename(); });
    row.addEventListener("dragstart", (event) => { handlers.selectFile(file); event.dataTransfer.setData("application/x-nodefilemanager-item", file.id); event.dataTransfer.effectAllowed = "copyMove"; });
    return row;
  }) : []));
}
