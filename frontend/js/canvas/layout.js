export const PANEL_WIDTH = Object.freeze({ single: 330, mixed: 430 });
export const BRANCH_SPACING = Object.freeze({ trail: 70, shelfX: 70, shelfY: 70 });

export function panelWidth(node) {
  return (node.files?.length && node.folders?.length) ? PANEL_WIDTH.mixed : PANEL_WIDTH.single;
}

export function childPositions(parent, count) {
  const spacing = panelWidth(parent) + 40;
  const start = parent.x - ((count - 1) * spacing) / 2;
  return Array.from({ length: count }, (_, index) => ({ x: start + index * spacing, y: parent.y + 130 }));
}
