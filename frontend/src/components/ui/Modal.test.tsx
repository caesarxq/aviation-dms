import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Modal } from './Modal';
import { vi } from 'vitest';

describe('Modal', () => {
  it('renders children when open', () => {
    render(
      <MemoryRouter>
        <Modal open={true} onClose={() => {}} title="Test Modal">
          <p>Modal content</p>
        </Modal>
      </MemoryRouter>
    );
    expect(screen.getByText('Test Modal')).toBeInTheDocument();
    expect(screen.getByText('Modal content')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <MemoryRouter>
        <Modal open={false} onClose={() => {}} title="Test Modal">
          <p>Modal content</p>
        </Modal>
      </MemoryRouter>
    );
    expect(screen.queryByText('Modal content')).not.toBeInTheDocument();
  });

  it('renders guide text and associates it with the dialog', () => {
    render(
      <MemoryRouter>
        <Modal open={true} onClose={() => {}} title="Test Modal" description="Use this form to record a controlled change.">
          <p>Modal content</p>
        </Modal>
      </MemoryRouter>
    );
    expect(screen.getByRole('note')).toHaveTextContent('Use this form to record a controlled change.');
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-describedby', 'modal-description');
  });

  it('calls onClose when close button clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Modal open={true} onClose={onClose} title="Test Modal">
          <p>Content</p>
        </Modal>
      </MemoryRouter>
    );
    const closeBtn = screen.getByRole('button', { name: /close/i });
    await user.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('moves focus into the dialog, traps tab navigation, and restores focus on close', async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <MemoryRouter>
        <button type="button">Open modal</button>
        <Modal open={false} onClose={() => {}} title="Focus dialog">
          <button type="button">Save</button>
        </Modal>
      </MemoryRouter>
    );
    const opener = screen.getByRole('button', { name: 'Open modal' });
    opener.focus();
    rerender(
      <MemoryRouter>
        <button type="button">Open modal</button>
        <Modal open={true} onClose={() => {}} title="Focus dialog">
          <button type="button">Save</button>
        </Modal>
      </MemoryRouter>
    );

    const dialog = screen.getByRole('dialog', { name: 'Focus dialog' });
    const close = within(dialog).getByRole('button', { name: 'Close dialog' });
    const save = within(dialog).getByRole('button', { name: 'Save' });
    expect(close).toHaveFocus();
    save.focus();
    await user.tab();
    expect(close).toHaveFocus();

    rerender(
      <MemoryRouter>
        <button type="button">Open modal</button>
        <Modal open={false} onClose={() => {}} title="Focus dialog">
          <button type="button">Save</button>
        </Modal>
      </MemoryRouter>
    );
    expect(opener).toHaveFocus();
  });

  it('uses readable dark text on the light modal surface', () => {
    render(
      <MemoryRouter>
        <Modal open={true} onClose={() => {}} title="Contrast dialog">
          <p>Readable content</p>
        </Modal>
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: 'Contrast dialog' })).toHaveClass('text-kfl-text');
    expect(screen.getByText('Readable content').parentElement).toHaveClass('text-kfl-text');
  });
});