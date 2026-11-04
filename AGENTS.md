# Touchline Studio project instructions

This is an independent local application and Git repository. Do not add an upstream
remote or make it a fork unless the user explicitly requests it. Keep third-party
model and algorithm provenance accurate in the documentation and analysis output.

Preserve the existing interface, editable interpretations, and manual correction
controls when changing the tracking pipeline. Runtime code must not import or read
the reference checkout under the outer workspace's `work/football_analysis` folder.

Ask the user before introducing or changing physical measurements: pitch length or
width, known reference distances, camera calibration measurements, or metric speed
and distance calculations. Never assume standard pitch dimensions for their footage.
Normalized image/pitch coordinates are currently dimensionless and require no
physical measurements. Do not silently invent measurements or convert pixels to meters.

Keep model selection, result class handling, and UI choices consistent. Preserve
the football model checksum check and restricted checkpoint loading. Model provenance
is not Git ancestry and must not be removed to imply original ownership of weights.

Run the Python regression suite and JavaScript projection tests after pipeline
changes. Use `python build_package.py` to refresh the distributable ZIP after edits.
Exclude Git metadata, environments, runtime data, credentials, and reference clones
from the package. Keep the app local unless the user explicitly requests publishing.
