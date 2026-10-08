# Evidence Spec

## Minimum Contents of a Finding

- `evidence_id`
- `source_type`
- `source_path_or_url`
- `locator`
- `excerpt_or_snapshot`
- `why_it_matters`

## Suggested source_type Values

- `requirement_doc`
- `html_file`
- `screenshot`
- `router_code`
- `playbook_data`
- `manual_observation`

## locator Conventions

- Documents: section name, page name, field name, heading
- HTML: filename, element text, function name, tab name, button name
- Screenshots: page region or states before/after an action
- Code: interface name, route, configuration key, function name

## Evidence Collection Constraints

- Every mapping conclusion needs at least one requirement citation and one prototype citation.
- A missing-page conclusion must identify the candidate files and destinations that were checked.
- An incorrect-mapping conclusion must explain why the current page does not implement the required page.
- Conclusions that static evidence is insufficient must also cite evidence and explain the limitation.
