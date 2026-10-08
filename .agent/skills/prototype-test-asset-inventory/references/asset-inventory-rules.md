# Asset Inventory Rules

## Required Inventory Targets

- Technical entry pages
- Platform shell pages
- Module list pages
- Detail/review pages
- Dashboard pages
- Settings/configuration pages
- Pages that may contain dialogs

## Key Annotations

- `entry_page`
- `standalone_page`
- `embedded_candidate`
- `out_of_scope_asset`
- `missing_asset_risk`

## Common Misjudgments

- Treating a sign-in page as a business-defect assessment page when the user considers it only a technical entry point.
- Treating a filename containing a business keyword as the target page without verification.
- Missing embedded destinations by overlooking tabs on detail pages.
