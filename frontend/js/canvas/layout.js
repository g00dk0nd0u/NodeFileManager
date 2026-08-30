export const PANEL_WIDTH = Object.freeze({ single: 330, mixed: 430 });
export const BRANCH_SPACING = Object.freeze({ trail: 70, shelfX: 70, shelfY: 70 });

export function panelWidth(node) {
  return (node.files?.length && node.folders?.length) ? PANEL_WIDTH.mixed : PANEL_WIDTH.single;
}

export function previewGeometry(node, workingSetBounds, preferredHeight = 280) {
  const availableHeight = Math.max(0, workingSetBounds.bottom - workingSetBounds.top);
  const height = Math.min(preferredHeight, availableHeight);
  const attachedTop = node.y + 32;
  const top = Math.max(workingSetBounds.top, Math.min(attachedTop, workingSetBounds.bottom - height));
  return { top: top - node.y, height, placement: top < attachedTop ? "up" : "down" };
}

export function childPositions(parent, count) {
  const spacing = panelWidth(parent) + 40;
  const start = parent.x - ((count - 1) * spacing) / 2;
  return Array.from({ length: count }, (_, index) => ({ x: start + index * spacing, y: parent.y + 130 }));
}
