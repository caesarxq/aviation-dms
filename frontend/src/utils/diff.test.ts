import { describe, expect, it } from 'vitest';
import { diffLines, htmlToText, inlineDiff } from './diff';

describe('document diff utilities', () => {
  it('aligns inserted lines without marking following lines as changed', () => {
    const rows = diffLines('alpha\ncharlie', 'alpha\nbravo\ncharlie');
    expect(rows).toEqual([
      { type: 'same', left: 'alpha', right: 'alpha', leftLine: 1, rightLine: 1 },
      { type: 'added', left: '', right: 'bravo', leftLine: null, rightLine: 2 },
      { type: 'same', left: 'charlie', right: 'charlie', leftLine: 2, rightLine: 3 },
    ]);
  });

  it('strips markup while retaining readable document text', () => {
    expect(htmlToText('<h1>Title</h1><p>Hello <strong>world</strong>.</p>')).toBe('Title\nHello world.');
  });

  it('returns word-level additions and removals for a changed line', () => {
    expect(inlineDiff('old procedure', 'new procedure')).toEqual([
      { type: 'added', value: 'new' },
      { type: 'removed', value: 'old' },
      { type: 'equal', value: ' ' },
      { type: 'equal', value: 'procedure' },
    ]);
  });

  it('uses a bounded coarse replacement for very large inputs', () => {
    const left = Array.from({ length: 400 }, (_, i) => `line-${i}`).join('\n');
    const right = Array.from({ length: 400 }, (_, i) => `changed-${i}`).join('\n');
    const rows = diffLines(left, right);
    expect(rows.length).toBeLessThanOrEqual(3);
    expect(rows.some((row) => row.type === 'changed')).toBe(true);
  });
});
