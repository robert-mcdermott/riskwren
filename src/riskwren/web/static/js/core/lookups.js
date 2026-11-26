// Things many pages need and that rarely change: the vocabularies and the units.

import { get } from "./api.js";

export async function vocabularies() {
  return (await get("/api/v1/vocabularies")).data;
}

export async function units() {
  const { units: list, tree } = (await get("/api/v1/units")).data;
  return { list, tree, byId: new Map(list.map((unit) => [unit.id, unit])) };
}

/** The label of a vocabulary value, or the key tidied up if it is not (or no longer) in it. */
export function label(vocab, name, key) {
  if (key == null || key === "") return "";
  const found = (vocab[name] ?? []).find((item) => item.key === key);
  return found ? found.label : String(key).replace(/_/g, " ");
}

export function options(vocab, name, { blank = null } = {}) {
  const items = (vocab[name] ?? []).filter((item) => !item.retired).map((item) => [item.key, item.label]);
  return blank == null ? items : [["", blank], ...items];
}

/** Units as select options, indented to show the hierarchy. only: a set of unit ids to offer. */
export function unitOptions(tree, { only = null, blank = null } = {}) {
  const out = blank == null ? [] : [["", blank]];
  const walk = (node, depth) => {
    const offered = node.status === "active" && (!only || only.has(node.id));
    if (offered) out.push([node.id, `${" ".repeat(depth)}${node.name}`]);
    for (const child of node.children) walk(child, depth + (offered ? 1 : 0));
  };
  tree.forEach((root) => walk(root, 0));
  return out;
}
