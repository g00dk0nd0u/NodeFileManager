import { createIcon } from "../icons.js";

function modifiedTime(timestamp) {
  if (timestamp == null) return "";
  const value = new Date(timestamp * 1000), two = (number) => String(number).padStart(2, "0");
  return `${two(value.getMonth() + 1)}${two(value.getDate())}_${two(value.getHours())}:${two(value.getMinutes())}`;
}

export function createNodeElement(node, handlers) {
  const element = document.createElement("article");
  element.className = "folder-node"; element.dataset.id = node.id;
  element.innerHTML = `<div class="node-title"><button class="node-close" type="button" aria-label="閉じる"></button><span></span><button class="node-favorite" type="button" aria-label="お気に入りを切り替える"></button><button class="node-new-folder" type="button" aria-label="新しいフォルダー"></button></div><div class="node-path"></div><div class="node-contents"></div><div class="node-preview"></div>`;
  element.querySelector(".node-close").append(createIcon("close"));
  element.querySelector(".node-favorite").append(createIcon("star"));
  element.querySelector(".node-new-folder").append(createIcon("plus"));
  element.querySelector("span").textContent = node.name;
  element.querySelector(".node-path").textContent = node.path; element.querySelector(".node-path").title = node.path;
  element.querySelector(".node-close").addEventListener("click", (event) => { event.stopPropagation(); handlers.close(node.id); });
  element.querySelector(".node-new-folder").addEventListener("click", (event) => { event.stopPropagation(); handlers.newFolder(node.id); });
  element.querySelector(".node-favorite").addEventListener("click", (event) => { event.stopPropagation(); handlers.favorite(node.id); });
  element.addEventListener("pointerdown", (event) => handlers.drag(event, node.id));
  element.addEventListener("contextmenu", (event) => { if (!event.target.closest(".folder-item, .file-item")) { event.preventDefault(); handlers.selectFolder(node.id); handlers.rename(); } });
  element.addEventListener("dragover", (event) => { if (event.dataTransfer.types.includes("application/x-nodefilemanager-item")) { event.preventDefault(); element.classList.add("drop-target"); } });
  element.addEventListener("dragleave", () => element.classList.remove("drop-target"));
  element.addEventListener("drop", (event) => { event.preventDefault(); element.classList.remove("drop-target"); handlers.drop(event, node.id); });
  return element;
}

export function updateNodeElement(element, node, selected, selectedItem, openFolders, handlers) {
  element.style.transform = `translate(${node.x}px, ${node.y}px)`; element.classList.toggle("selected", selected);
  element.querySelector(".node-favorite").classList.toggle("is-active", Boolean(node.favorite));
  element.querySelector(".node-favorite").setAttribute("aria-pressed", String(Boolean(node.favorite)));
  const contents = element.querySelector(".node-contents");
  const folderRows = (node.folders || []).map((folder) => {
    const row = document.createElement("div"); row.className = "folder-item"; row.dataset.id = folder.id;
    row.classList.toggle("open", openFolders.has(folder.id)); row.innerHTML = `<span class="item-icon"></span><span class="item-name"></span>`;
    row.querySelector(".item-icon").append(createIcon("folder")); row.querySelector(".item-name").textContent = folder.name;
    row.addEventListener("pointerdown", (event) => event.stopPropagation());
    row.addEventListener("click", (event) => { event.stopPropagation(); handlers.folder(node.id, folder); });
    row.addEventListener("dragover", (event) => { if (event.dataTransfer.types.includes("application/x-nodefilemanager-item")) event.preventDefault(); });
    row.addEventListener("drop", (event) => { event.preventDefault(); event.stopPropagation(); handlers.drop(event, folder.id); });
    return row;
  });
  const fileRows = (node.files || []).map((file) => {
    const row = document.createElement("div"); row.className = "file-item"; row.draggable = true; row.dataset.id = file.id;
    row.classList.toggle("selected", selectedItem === file.id); row.innerHTML = `<span class="item-icon"></span><span class="item-name"></span><time class="item-time"></time>`;
    row.querySelector(".item-icon").append(createIcon("file")); row.querySelector(".item-name").textContent = file.name; row.querySelector("time").textContent = modifiedTime(file.modifiedTime);
    row.addEventListener("pointerdown", (event) => { event.stopPropagation(); handlers.selectFile(file, row); });
    row.addEventListener("click", (event) => { event.stopPropagation(); handlers.preview(node.id, file); });
    row.addEventListener("dblclick", (event) => { event.stopPropagation(); handlers.open(file.id); });
    row.addEventListener("contextmenu", (event) => { event.preventDefault(); event.stopPropagation(); handlers.selectFile(file, row); handlers.rename(); });
    row.addEventListener("dragstart", (event) => { handlers.selectFile(file, row); event.dataTransfer.setData("application/x-nodefilemanager-item", file.id); event.dataTransfer.effectAllowed = "copyMove"; });
    return row;
  });
  contents.replaceChildren(...folderRows, ...fileRows);
  updatePreviewElement(element, node, handlers);
}

export function updatePreviewElement(element, node, handlers) {
  const preview = element.querySelector(".node-preview"); preview.replaceChildren(); preview.hidden = !node.preview;
  if (node.preview) {
    const header = document.createElement("div"); header.className = "preview-title"; header.textContent = node.preview.name;
    const close = document.createElement("button"); close.type = "button"; close.setAttribute("aria-label", "プレビューを閉じる"); close.append(createIcon("close")); close.addEventListener("click", () => handlers.closePreview(node.id)); header.prepend(close); preview.append(header);
    const url = `/api/files/preview?id=${encodeURIComponent(node.preview.id)}`;
    if ([".jpg", ".jpeg", ".png"].includes(node.preview.extension.toLowerCase())) {
      const image = document.createElement("img"); image.src = url; image.alt = node.preview.name; image.addEventListener("load", () => handlers.previewResized(node.id)); preview.append(image);
    } else {
      const frame = document.createElement("iframe"); frame.src = `${url}#page=${node.preview.page}`; frame.title = node.preview.name; preview.append(frame);
      const controls = document.createElement("div"); controls.className = "preview-controls";
      const previous = document.createElement("button"); previous.setAttribute("aria-label", "前のページ"); previous.append(createIcon("previous")); previous.disabled = node.preview.page <= 1; previous.addEventListener("click", () => handlers.previewPage(node.id, -1));
      const page = document.createElement("span"); page.textContent = String(node.preview.page);
      const next = document.createElement("button"); next.setAttribute("aria-label", "次のページ"); next.append(createIcon("next")); next.addEventListener("click", () => handlers.previewPage(node.id, 1)); controls.append(previous, page, next); preview.append(controls);
    }
  }
}
