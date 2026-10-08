# Mapping Rules

## Criteria for the Five States

### `standalone_mapped`
- A standalone page file or independently accessible page exists.
- Its title, regions, and actions match the required page's primary meaning.

### `embedded_covered`
- No standalone page exists.
- An existing tab, dialog, drawer, or detail region clearly implements the requirement.
- Both the entry point and destination content must be visible; neither may be missing.

### `missing_page`
- No suitable content was found after checking candidate pages and destinations.

### `mis_mapping`
- The mapped target clearly addresses a different subject.
- Example: mapping a purchasing-management list to a property-management page.

### `out_of_scope_prototype`
- The page exists but is not defined in the current requirement scope.

## Warning Signs of Incorrect Mapping

- Only filename keywords match.
- The main title, search filters, or table columns differ from the required page's subject.
- The mapping would conceal an actually missing page.
