// Things many pages need and that rarely change: the vocabularies and the units.

import { get } from "./api.js";

export async function vocabularies() {
  return (await get("/api/v1/vocabularies")).data;
}

/** How risks are rated: the scoring method, the categories with their appetite, and the rules. */
export async function program({ fresh = false } = {}) {
  return (await get("/api/v1/program", null, { fresh })).data;
}

/** Risk categories as select options, the narrower ones indented under the broader. */
export function categoryOptions(programData, { blank = null, topOnly = false } = {}) {
  const out = blank == null ? [] : [["", blank]];
  for (const top of programData.categories) {
    if (top.status !== "active") continue;
    out.push([top.key, top.name]);
    if (topOnly) continue;
    for (const child of top.children) if (child.status === "active") out.push([child.key, `\u00a0\u00a0\u00a0${child.name}`]);
  }
  return out;
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
/** ``keep``: the unit a record already belongs to, always offered, so that editing a record
 *  never moves it, even when the editor may not add records there or the unit is closed. */
export function unitOptions(tree, { only = null, blank = null, keep = null } = {}) {
  const out = blank == null ? [] : [["", blank]];
  const walk = (node, depth) => {
    const offered = node.id === keep || (node.status === "active" && (!only || only.has(node.id)));
    if (offered) out.push([node.id, `${" ".repeat(depth)}${node.name}`]);
    for (const child of node.children) walk(child, depth + (offered ? 1 : 0));
  };
  tree.forEach((root) => walk(root, 0));
  return out;
}
