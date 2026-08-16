function modifiedTime(timestamp) {
  if (timestamp == null) return "";
  const value = new Date(timestamp * 1000), two = (number) => String(number).padStart(2, "0");
  return `${two(value.getMonth() + 1)}${two(value.getDate())}_${two(value.getHours())}:${two(value.getMinutes())}`;
}

export function createNodeElement(node, handlers) {
  const element = document.createElement("article");
  element.className = "folder-node"; element.dataset.id = node.id;
  element.innerHTML = `<div class="node-title"><button class="node-toggle" type="button" aria-label="展開">${node.expanded ? "▾" : "▸"}</button><span></span></div><div class="node-path"></div><div class="node-contents"></div>`;
  element.querySelector("span").textContent = node.name;
  element.querySelector(".node-path").textContent = node.path; element.querySelector(".node-path").title = node.path;
  element.querySelector("button").addEventListener("click", (event) => { event.stopPropagation(); handlers.toggle(node.id); });
  element.addEventListener("pointerdown", (event) => handlers.drag(event, node.id));
  element.addEventListener("contextmenu", (event) => { if (!event.target.closest(".folder-item, .file-item")) { event.preventDefault(); handlers.selectFolder(node.id); handlers.rename(); } });
  element.addEventListener("dragover", (event) => { if (event.dataTransfer.types.includes("application/x-nodefilemanager-item")) { event.preventDefault(); element.classList.add("drop-target"); } });
  element.addEventListener("dragleave", () => element.classList.remove("drop-target"));
  element.addEventListener("drop", (event) => { event.preventDefault(); element.classList.remove("drop-target"); handlers.drop(event, node.id); });
  return element;
}

export function updateNodeElement(element, node, selected, selectedItem, openFolders, handlers) {
  element.style.transform = `translate(${node.x}px, ${node.y}px)`; element.classList.toggle("selected", selected);
  element.querySelector(".node-toggle").textContent = node.expanded ? "▾" : "▸";
  const contents = element.querySelector(".node-contents"); contents.hidden = !node.expanded;
  const folderRows = (node.folders || []).map((folder) => {
    const row = document.createElement("div"); row.className = "folder-item"; row.dataset.id = folder.id;
    row.classList.toggle("open", openFolders.has(folder.id)); row.innerHTML = `<span class="item-name"></span>`;
    row.querySelector("span").textContent = `📁 ${folder.name}`;
    row.addEventListener("pointerdown", (event) => event.stopPropagation());
    row.addEventListener("click", (event) => { event.stopPropagation(); handlers.folder(node.id, folder); });
    return row;
  });
  const fileRows = (node.files || []).map((file) => {
    const row = document.createElement("div"); row.className = "file-item"; row.draggable = true; row.dataset.id = file.id;
    row.classList.toggle("selected", selectedItem === file.id); row.innerHTML = `<span class="item-name"></span><time class="item-time"></time>`;
    row.querySelector(".item-name").textContent = `📄 ${file.name}`; row.querySelector("time").textContent = modifiedTime(file.modifiedTime);
    row.addEventListener("pointerdown", (event) => { event.stopPropagation(); handlers.selectFile(file, row); });
    row.addEventListener("dblclick", (event) => { event.stopPropagation(); handlers.open(file.id); });
    row.addEventListener("contextmenu", (event) => { event.preventDefault(); event.stopPropagation(); handlers.selectFile(file, row); handlers.rename(); });
    row.addEventListener("dragstart", (event) => { handlers.selectFile(file, row); event.dataTransfer.setData("application/x-nodefilemanager-item", file.id); event.dataTransfer.effectAllowed = "copyMove"; });
    return row;
  });
  contents.replaceChildren(...folderRows, ...fileRows);
}
