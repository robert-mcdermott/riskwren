// Where each record sits in the picture of how one record is connected: the record in the
// middle, its neighbors in a column either side of it, group by group, and, for a neighbor
// that has been opened, its own neighbors in a column beyond it. Positions only; nothing
// here touches the page.

export const VIEW = { width: 1200, height: 640, node: { width: 200, height: 34 } };
const STEP = 44; // from one record to the next in a column
const HEADING = 26; // the room a group's name takes above its records
const NEAR = 250; // from the middle to the columns of neighbors
const FAR = 490; // and to the columns beyond them

function columns(groups, perGroup) {
  // Each group goes whole to whichever side is shorter, so the two stay balanced.
  const sides = [{ sign: 1, groups: [], height: 0 }, { sign: -1, groups: [], height: 0 }];
  for (const group of groups) {
    const shown = group.records.slice(0, perGroup);
    const more = group.records.length - shown.length;
    const side = sides[0].height <= sides[1].height ? sides[0] : sides[1];
    side.groups.push({ group, shown, more });
    side.height += HEADING + (shown.length + (more ? 1 : 0)) * STEP;
  }
  return sides;
}

/**
 * graph: { center, groups: [{ key, label, records }] }, as the server gives it.
 * opened: { ref: graph } for the neighbors whose own connections are shown.
 * Returns { nodes, edges, labels }. A node is { id, record, x, y, ring, side, group?, more? }:
 * ring 0 is the middle, 1 its neighbors, 2 a neighbor's neighbors. `more` is how many of a
 * group did not fit and are in the list alone; `beyond`, on a neighbor, how many of its own.
 */
export function layout(graph, opened = {}, { perGroup = 6, perChild = 4 } = {}) {
  const { width, height } = VIEW;
  const cx = width / 2;
  const cy = height / 2;
  const room = height - 16;
  let each = perGroup;
  let sides = columns(graph.groups, each);
  while (each > 1 && Math.max(sides[0].height, sides[1].height) > room) {
    each -= 1;
    sides = columns(graph.groups, each);
  }
  const nodes = [{ id: graph.center.ref, record: graph.center, x: cx, y: cy, ring: 0, side: 0 }];
  const edges = [];
  const labels = [];
  const placed = new Set([graph.center.ref]);
  for (const side of sides) {
    const x = cx + side.sign * NEAR;
    let y = Math.max(8, (height - side.height) / 2);
    for (const { group, shown, more } of side.groups) {
      labels.push({ group: group.key, text: group.label, x, y: y + HEADING - 8, side: side.sign });
      y += HEADING;
      const slots = [...shown.map((record) => ({ record })), ...(more ? [{ more }] : [])];
      for (const slot of slots) {
        const id = slot.record ? `${group.key}/${slot.record.ref}` : `${group.key}/more`;
        nodes.push({ id, x, y: y + STEP / 2, ring: 1, side: side.sign, group: group.key, ...slot });
        edges.push({ from: graph.center.ref, to: id, group: group.key });
        if (slot.record) placed.add(slot.record.ref);
        y += STEP;
      }
    }
  }
  // An opened neighbor's own neighbors, beyond it, as near its height as there is room.
  for (const side of [1, -1]) {
    const x = cx + side * FAR;
    let free = STEP / 2 + 4;
    const parents = nodes.filter((node) => node.ring === 1 && node.side === side && node.record && opened[node.record.ref]);
    for (const parent of parents) {
      const beyond = opened[parent.record.ref].groups.flatMap((group) => group.records.map((record) => ({ record, via: group.label })))
        .filter((item, index, all) => !placed.has(item.record.ref) && all.findIndex((other) => other.record.ref === item.record.ref) === index);
      let shown = 0;
      let y = Math.max(free, parent.y - ((Math.min(beyond.length, perChild) - 1) * STEP) / 2);
      for (const item of beyond.slice(0, perChild)) {
        if (y > height - STEP / 2) break;
        const id = `${parent.id}>${item.record.ref}`;
        nodes.push({ id, record: item.record, via: item.via, x, y, ring: 2, side, group: parent.group });
        edges.push({ from: parent.id, to: id, group: parent.group });
        y += STEP;
        shown += 1;
      }
      free = y;
      if (beyond.length > shown) parent.beyond = beyond.length - shown;
    }
  }
  return { nodes, edges, labels };
}
