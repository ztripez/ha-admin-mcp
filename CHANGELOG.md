# Changelog

All notable changes to this project are documented in this file.

## [0.5.0] - 2026-02-24

### Added
- New voice setup tools for Assist pipeline management: `list_assist_pipelines`, `get_assist_pipeline`, `create_assist_pipeline`, `update_assist_pipeline`, `delete_assist_pipeline`, `get_preferred_assist_pipeline`, and `set_preferred_assist_pipeline`.
- New Assist satellite setup tools: `list_assist_satellites`, `get_assist_satellite_configuration`, `set_assist_satellite_wake_words`, and `set_assist_satellite_pipeline`.
- `get_voice_setup_status` one-shot diagnostics tool for voice integration readiness and entity/service coverage.

### Changed
- Admin server prompt and docs now explicitly include voice assistant setup coverage.
- Integration manifest version updated to `0.5.0`.

## [0.4.2] - 2026-02-24

### Added
- `create_automation` and `update_automation` now accept optional `category_id` for direct automation category assignment.
- Destructive regression automation lifecycle now exercises category assignment when category tools are available.

### Changed
- `update_entity` now accepts `categories` mapping updates so entity category assignment is exposed through MCP.
- Integration manifest version updated to `0.4.2`.

## [0.4.1] - 2026-02-24

### Added
- Destructive regression lifecycle coverage for automation, script, and scene YAML CRUD.

### Changed
- Regression suite now classifies missing component/service support as skip for the new YAML lifecycle checks.
- Integration manifest version updated to `0.4.1`.

## [0.4.0] - 2026-02-24

### Added
- Category registry CRUD tools: `list_categories`, `create_category`, `update_category`, `delete_category`.
- Category lifecycle coverage in destructive regression tests.

### Changed
- Admin server prompt and docs updated to include category registry support.
- Integration manifest version updated to `0.4.0`.
