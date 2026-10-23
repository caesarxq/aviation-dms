import { describe, expect, it } from 'vitest';
import { inlineSuggestionSegments } from './diff';

describe('inline suggestion rendering', () => {
  it('renders a single stream with insertions and deletions', () => {
    expect(inlineSuggestionSegments('alpha\nold line', 'alpha\nnew line')).toEqual([
      { type: 'equal', value: 'alpha' },
      { type: 'break', value: '\n' },
      { type: 'removed', value: 'old' },
      { type: 'added', value: 'new' },
      { type: 'equal', value: ' line' },
    ]);
  });

  it('does not create a change stream when the content is identical', () => {
    expect(inlineSuggestionSegments('<p>same</p>', '<p>same</p>')).toEqual([
      { type: 'equal', value: '<p>same</p>' },
    ]);
  });
});
