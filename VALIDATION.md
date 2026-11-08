# Validation

Validated locally on Windows with Python 3.12.

- Downloaded all eleven configured public sources successfully in strict mode; no fabricated values or silent source substitutions.
- Rebuilt the processed tables offline from checksum-verified, content-addressed raw files.
- Nine pytest checks pass against the delivered project, including Streamlit AppTest rendering and widget changes.
- Checked fixed-rate mortgage math, zero interest, inflation/rebasing, missing data, duplicate dates, incomplete-year exclusion, revision-year parsing, cohort labels and population weighting.
- Verified that corrupt processed data is rejected and an unavailable-source build cannot publish a new snapshot.
- Started Streamlit on a temporary loopback port; both the dashboard HTTP page and health endpoint responded successfully. The temporary test server was stopped.
- The Windows launcher creates the isolated environment and verifies the bundled snapshot. Dependency versions are pinned and the tested development environment is recorded in requirements-lock.txt.

The bundled annual intersection is 1984–2024. Newer individual observations remain inspectable; 2025 CPI-related data has a missing month, so the pipeline does not fabricate a complete annual value. Census marriage ages extend through 2025, while the available age-specific AD-3 workbooks end in 2023. All these coverage dates are visible in the app.

No remote GitHub repository was created or pushed, no cloud resources were deployed, and no recurring background job was installed. Git was initialized locally. Public-source download availability and future source schema changes remain external dependencies for refreshes; existing snapshots can be viewed offline.
