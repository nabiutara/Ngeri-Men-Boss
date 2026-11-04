"""Build the portable app without Git history, model binaries, or runtime data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import shutil
import os

ROOT = Path(__file__).resolve().parent
ARCHIVE = Path(os.environ.get('TOUCHLINE_PACKAGE_OUTPUT', ROOT.parent / 'touchline-studio.zip'))
FILES = ['server.py', 'football_engine.py', 'requirements.txt', 'Start Touchline.cmd',
         'README.md', 'REPOSITORY-ANALYSIS.md', 'MODEL-PROVENANCE.json', 'AGENTS.md',
         'build_package.py', '.gitignore', 'dist/index.html', 'dist/app.js',
         'dist/styles.css', 'dist/football-features.js',
         'tests/test_football_engine.py', 'tests/test_football_ui.cjs']
FILES += ['SOURCE-GUIDE.md', 'CODE-MAP.md', 'DEPENDENCIES.json']
FILES += ['PYCHARM-SETUP.md']
FILES += ['REVIEW.md', 'tests/test_video_import.cjs']
FILES += ['dist/foot-markers.js', 'tests/test_foot_markers.cjs']
FILES += ['launch.py']
FILES += ['tests/test_launch.py']
FILES += ['benchmark.py', 'evaluation.py', 'prepare_training.py', 'EVALUATION.md',
          'tests/test_evaluation.py', 'tests/test_training_export.py']
FILES += ['dist/player-connections.js', 'tests/test_player_connections.cjs']
FILES += ['STABILITY.md', 'OVERLAY-FIX.md', 'CV-RESOURCES.md',
          'tests/test_player_labels.cjs', 'tests/match1-duplicate-fixtures.json']
FILES += ['training_workflow.py', 'FRAME-LABELING.md', 'dist/frame-review.js',
          'dist/frame-review-ui.js', 'tests/test_frame_review.cjs',
          'tests/test_training_workflow.py', 'tests/test_training_api.py',
          'tests/test_frame_review_ui.cjs']

def main():
    with ZipFile(ARCHIVE, 'w', ZIP_DEFLATED) as archive:
        for file in FILES:
            archive.write(ROOT / file, 'Touchline Studio/' + file)
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(FILES)
        assert all('.git' not in Path(name).parts for name in archive.namelist())
    shutil.copy2(ARCHIVE, ROOT / 'dist/touchline-studio.zip')
    print(f'Packaged {len(FILES)} standalone application files ({ARCHIVE.stat().st_size:,} bytes).')

if __name__ == '__main__':
    main()
