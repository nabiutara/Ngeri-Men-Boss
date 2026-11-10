# Local library

Restart **Start Touchline.cmd**, then click **Library** in the top bar.
All retained user work lives in one folder beside the launcher:

```text
Library/
  library.sqlite3       Video, analysis-run and project index
  videos/               Copied original videos, identified by SHA-256
  analyses/             Separate tracking JSON for each analysis run
  projects/             Autosaved notes, corrections, colors and drawings
  reviewed-frames/
    frames/             Each confirmed JPEG together with review.json
    datasets/           Existing training snapshots
    runs/               Existing inactive training candidates
  imports/              Temporary files while copying videos
```

New imports copy the full video to the PC. Identical content is stored once even
when renamed; different videos with the same filename remain separate. Reanalysis
uses the retained copy and produces a new run and project. Old runs are retained.
Failed, cancelled and interrupted runs appear in history. Model weights and setup
logs remain operational files under `work/`; they are not part of the media library.

The Library screen opens videos, saved projects and completed runs. It shows reviewed
frame thumbnails, timestamps and split assignments, with label downloads and a link
back into the label editor when the video is available. File Explorer buttons open
the library, videos, analyses, or reviewed frame folders on the PC running the app.
Explorer actions must originate from that PC, not another device on Wi-Fi.

Edits autosave to the project file after a short pause. Wait for **Saved in Library**
before closing. The browser still keeps a recovery copy; an error saving to disk is
shown rather than reported as success. The Library's **Save current project** also
copies an already-open legacy clip and saves its current edits. **Save project** in
the top bar still downloads a portable JSON backup. Browser-only drafts remain in
the frame editor until confirmed or exported; confirmed reviews are saved on disk.

On first use, existing `work/training` data and valid `work/jobs/*.json` results are
copied into Library. Originals are left untouched as a recovery copy. This is a
one-time migration; subsequent saves use the library. In this workspace, two reviewed
frames and 15 result files were recovered. Videos previously deleted as temporary
uploads cannot be recovered by the migration: import their originals again.
Results with a source fingerprint reconnect by content. Older results without one
are downloadable but require you to import the tracking JSON with the matching video.
No association is guessed from a filename. Opening the frame editor loads missing
confirmed server reviews; existing browser drafts are preserved.

For a backup, close the app and copy the entire **Library** folder. Restore that
folder beside the launcher. Paths in the database are relative. Library is excluded
from Git and the distributable ZIP, so building or pushing the app does not ship
videos, labels, or notes. Do not rename files inside Library manually: use its
catalog to find them. No automatic library deletion is performed.

Ring colors can now differ from labels and boxes. Under **Rings & connections**,
choose Follow overlay colors, Own team ring colors, or Detected kit colors. A
selected player also has **Custom ring color only**. Unchecking it restores the
selected team/kit mode. These choices persist in both library and portable projects.

Current limits: the library is for the local PC service, not the optional cloud
worker. The catalog is unpaginated, and opening a retained video currently downloads
it into a browser File for compatibility with the label editor; very large videos
can use substantial browser memory. Concurrent edits to the same project from
multiple tabs/devices use last-save-wins. Close the old server before migrating so
it cannot continue writing to the legacy training folder.

Verification: all 66 Python tests and nine JavaScript suites passed. Storage/API tests cover content deduplication, same-name separation,
restart history, non-destructive migration, project persistence, path/host/origin
checks, byte ranges, and allowlisted Explorer destinations (Explorer is mocked in
tests). JavaScript tests cover save ordering, changed tracking, failure recovery,
pending-save warnings, and independent ring colors. Browser visual verification has
not been completed; no new tracking-accuracy claim is made.
