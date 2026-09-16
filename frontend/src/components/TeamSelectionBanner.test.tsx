import { fireEvent, render, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TeamSelectionBanner from './TeamSelectionBanner';

describe('TeamSelectionBanner', () => {
  it('renders detected clusters and calls back with the selected cluster id', () => {
    const onSelectCluster = vi.fn();

    const { container } = render(
      <TeamSelectionBanner
        clusters={[
          { clusterId: 0, rgbCentroid: [24, 94, 224], trackIds: [4, 6, 8] },
          { clusterId: 1, rgbCentroid: [220, 50, 60], trackIds: [12, 14] },
        ]}
        isSubmitting={false}
        onSelectCluster={onSelectCluster}
      />,
    );
    const scoped = within(container);

    fireEvent.click(scoped.getByRole('button', { name: /use cluster 1/i }));

    expect(scoped.getByText(/detected team colors/i)).toBeTruthy();
    expect(onSelectCluster).toHaveBeenCalledWith(1);
  });

  it('tells the operator that tactical interpretation is paused until a team is selected', () => {
    const { container } = render(
      <TeamSelectionBanner
        clusters={[{ clusterId: 0, rgbCentroid: [24, 94, 224], trackIds: [4, 6, 8] }]}
        isSubmitting={false}
        onSelectCluster={() => {}}
      />,
    );
    const scoped = within(container);

    expect(scoped.getByText(/tactical interpretation is paused/i)).toBeTruthy();
  });
});
