import { render, screen } from '@testing-library/react';
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
});