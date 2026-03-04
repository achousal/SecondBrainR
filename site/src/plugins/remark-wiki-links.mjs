import { visit } from "unist-util-visit";

/** Remark plugin: transform [[wiki links]] into styled inert spans. */
export default function remarkWikiLinks() {
  return (tree) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || index === undefined) return;

      const regex = /\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]/g;
      const value = node.value;
      if (!regex.test(value)) return;

      regex.lastIndex = 0;
      const children = [];
      let lastIndex = 0;
      let match;

      while ((match = regex.exec(value)) !== null) {
        if (match.index > lastIndex) {
          children.push({ type: "text", value: value.slice(lastIndex, match.index) });
        }

        const display = match[2] || match[1];
        children.push({
          type: "html",
          value: `<span class="wiki-ref">${display}</span>`,
        });

        lastIndex = match.index + match[0].length;
      }

      if (lastIndex < value.length) {
        children.push({ type: "text", value: value.slice(lastIndex) });
      }

      parent.children.splice(index, 1, ...children);
    });
  };
}
