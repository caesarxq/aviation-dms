import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { InlineSuggestionView } from './InlineSuggestionView';

describe('InlineSuggestionView', () => {
  it('renders changes in one inline stream', () => {
    render(<InlineSuggestionView originalText="old procedure" proposedText="new procedure" />);
    expect(screen.getByTestId('inline-suggestion-stream')).toHaveTextContent('oldnew procedure');
    expect(screen.getByText('old')).toHaveAttribute('class', expect.stringContaining('line-through'));
    expect(screen.getByText('new')).toHaveAttribute('class', expect.stringContaining('bg-emerald-100'));
  });

  it('shows an empty state when there are no changes', () => {
    render(<InlineSuggestionView originalText="same" proposedText="same" />);
    expect(screen.getByText(/No proposed changes yet/)).toBeInTheDocument();
  });
});
