export type DiffRow = {
  type: "same" | "added" | "removed" | "changed";
  left: string;
  right: string;
  leftLine: number | null;
  rightLine: number | null;
};

export type InlineSegment = {
  type: "equal" | "added" | "removed";
  value: string;
};

const BLOCK_TAGS = new Set([
  "ADDRESS", "ARTICLE", "ASIDE", "BLOCKQUOTE", "DIV", "DL", "DT", "DD", "FIELDSET",
  "FIGCAPTION", "FIGURE", "FOOTER", "FORM", "H1", "H2", "H3", "H4", "H5", "H6",
  "HEADER", "HR", "LI", "MAIN", "NAV", "OL", "P", "PRE", "SECTION", "TABLE", "TR", "UL",
]);

export function htmlToText(html: string): string {
  if (!html) return "";
  if (typeof DOMParser === "undefined") return html.replace(/<[^>]+>/g, "");
  const root = new DOMParser().parseFromString(html, "text/html").body;
  const output: string[] = [];
  const visit = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      output.push(node.textContent || "");
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node as Element;
    for (const child of Array.from(element.childNodes)) visit(child);
    if (BLOCK_TAGS.has(element.tagName)) output.push("\n");
  };
  for (const child of Array.from(root.childNodes)) visit(child);
  return output.join("").replace(/[ \t]+\n/g, "\n").replace(/\n[ \t]+/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

function coarseDiff(left: string[], right: string[]): DiffRow[] {
  let prefix = 0;
  while (prefix < left.length && prefix < right.length && left[prefix] === right[prefix]) prefix += 1;
  let suffix = 0;
  while (
    suffix < left.length - prefix &&
    suffix < right.length - prefix &&
    left[left.length - 1 - suffix] === right[right.length - 1 - suffix]
  ) suffix += 1;
  const rows: DiffRow[] = [];
  for (let i = 0; i < prefix; i += 1) rows.push({ type: "same", left: left[i], right: right[i], leftLine: i + 1, rightLine: i + 1 });
  const leftMiddle = left.slice(prefix, left.length - suffix);
  const rightMiddle = right.slice(prefix, right.length - suffix);
  if (leftMiddle.length && rightMiddle.length) {
    rows.push({ type: "changed", left: leftMiddle.join("\n"), right: rightMiddle.join("\n"), leftLine: prefix + 1, rightLine: prefix + 1 });
  } else if (leftMiddle.length) {
    rows.push({ type: "removed", left: leftMiddle.join("\n"), right: "", leftLine: prefix + 1, rightLine: null });
  } else if (rightMiddle.length) {
    rows.push({ type: "added", left: "", right: rightMiddle.join("\n"), leftLine: null, rightLine: prefix + 1 });
  }
  for (let i = 0; i < suffix; i += 1) {
    const leftIndex = left.length - suffix + i;
    const rightIndex = right.length - suffix + i;
    rows.push({ type: "same", left: left[leftIndex], right: right[rightIndex], leftLine: leftIndex + 1, rightLine: rightIndex + 1 });
  }
  return rows;
}

export function diffLines(leftText: string, rightText: string): DiffRow[] {
  const left = leftText.split("\n");
  const right = rightText.split("\n");
  if (left.length * right.length > 40000) return coarseDiff(left, right);

  const dp: number[][] = Array.from({ length: left.length + 1 }, () => Array(right.length + 1).fill(0));
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      dp[i][j] = left[i] === right[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const operations: Array<{ type: "same" | "added" | "removed"; left: string; right: string }> = [];
  let i = 0;
  let j = 0;
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && left[i] === right[j]) {
      operations.push({ type: "same", left: left[i], right: right[j] }); i += 1; j += 1;
    } else if (j < right.length && (i === left.length || dp[i][j + 1] >= dp[i + 1][j])) {
      operations.push({ type: "added", left: "", right: right[j] }); j += 1;
    } else {
      operations.push({ type: "removed", left: left[i], right: "" }); i += 1;
    }
  }

  const rows: DiffRow[] = [];
  let leftLine = 1;
  let rightLine = 1;
  for (let index = 0; index < operations.length; index += 1) {
    const operation = operations[index];
    const next = operations[index + 1];
    if (operation.type === "removed" && next?.type === "added") {
      rows.push({ type: "changed", left: operation.left, right: next.right, leftLine, rightLine });
      leftLine += 1; rightLine += 1; index += 1;
    } else if (operation.type === "added" && next?.type === "removed") {
      rows.push({ type: "changed", left: next.left, right: operation.right, leftLine, rightLine });
      leftLine += 1; rightLine += 1; index += 1;
    } else {
      rows.push({
        type: operation.type,
        left: operation.left,
        right: operation.right,
        leftLine: operation.type === "added" ? null : leftLine,
        rightLine: operation.type === "removed" ? null : rightLine,
      });
      if (operation.type !== "added") leftLine += 1;
      if (operation.type !== "removed") rightLine += 1;
    }
  }
  return rows;
}

function tokenDiff(leftTokens: string[], rightTokens: string[]): InlineSegment[] {
  const dp: number[][] = Array.from({ length: leftTokens.length + 1 }, () => Array(rightTokens.length + 1).fill(0));
  for (let i = leftTokens.length - 1; i >= 0; i -= 1) {
    for (let j = rightTokens.length - 1; j >= 0; j -= 1) {
      dp[i][j] = leftTokens[i] === rightTokens[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const result: InlineSegment[] = [];
  let i = 0; let j = 0;
  while (i < leftTokens.length || j < rightTokens.length) {
    if (i < leftTokens.length && j < rightTokens.length && leftTokens[i] === rightTokens[j]) {
      result.push({ type: "equal", value: leftTokens[i] }); i += 1; j += 1;
    } else if (j < rightTokens.length && (i === leftTokens.length || dp[i][j + 1] >= dp[i + 1][j])) {
      result.push({ type: "added", value: rightTokens[j] }); j += 1;
    } else {
      result.push({ type: "removed", value: leftTokens[i] }); i += 1;
    }
  }
  return result;
}

export function inlineDiff(leftText: string, rightText: string): InlineSegment[] {
  const leftTokens = leftText.split(/(\s+)/).filter(Boolean);
  const rightTokens = rightText.split(/(\s+)/).filter(Boolean);
  if (leftTokens.length * rightTokens.length > 10000) {
    return [
      ...(leftText ? [{ type: "removed" as const, value: leftText }] : []),
      ...(rightText ? [{ type: "added" as const, value: rightText }] : []),
    ];
  }
  return tokenDiff(leftTokens, rightTokens);
}

export type InlineDocumentSegment = InlineSegment | { type: "break"; value: "\n" };

function mergeInlineSegments(segments: InlineSegment[]): InlineSegment[] {
  const normalized = [...segments];
  for (let index = 0; index < normalized.length - 1; index += 1) {
    if (normalized[index].type === "added" && normalized[index + 1].type === "removed") {
      [normalized[index], normalized[index + 1]] = [normalized[index + 1], normalized[index]];
      break;
    }
  }
  return normalized.reduce<InlineSegment[]>((result, segment) => {
    const previous = result[result.length - 1];
    if (previous?.type === segment.type && segment.type === "equal") {
      previous.value += segment.value;
    } else {
      result.push({ ...segment });
    }
    return result;
  }, []);
}

export function inlineSuggestionSegments(leftText: string, rightText: string): InlineDocumentSegment[] {
  const rows = diffLines(leftText, rightText);
  const segments: InlineDocumentSegment[] = [];
  rows.forEach((row, rowIndex) => {
    if (row.type === "same") segments.push({ type: "equal", value: row.left });
    if (row.type === "added") segments.push({ type: "added", value: row.right });
    if (row.type === "removed") segments.push({ type: "removed", value: row.left });
    if (row.type === "changed") segments.push(...mergeInlineSegments(inlineDiff(row.left, row.right)));
    if (rowIndex < rows.length - 1) segments.push({ type: "break", value: "\n" });
  });
  return segments;
}
