# Claude Evidence Sources

The sanctioned evidence sources for the Claude phase are:

- `GET /pipeline/status`: pipeline health, run metadata, publication counts, current `AS_OF`, and analytics freshness.
- `GET /network/grid/{grid_id}/location`: grid ID, centroid coordinates, and the polygon reference. The full Polygon geometry is intentionally excluded.

Claude tools should cite these API responses for pipeline and grid-location claims. The optional `GET /network/grid/{grid_id}/neighbours` endpoint supplies centroid-based surrounding-grid context.