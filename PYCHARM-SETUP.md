# Open this project in PyCharm

The project files and three Run configurations are prepared. Automatic IDE launch
did not expose a usable PyCharm window, and registering a new global SDK through
a direct configuration write was not granted. Consequently interpreter selection
has not been verified in the IDE. Follow this once to finish the local setup.

1. Open PyCharm, select **File > Open**, and choose this `touchline-studio` directory.
   To use the app without an editor, double-click **Start Touchline.cmd** instead.
2. If PyCharm asks where to open the project, choose a new window to keep your other
   project open. Review any project-trust prompt yourself.
3. Open **File → Settings → Project: Touchline Studio → Python Interpreter**.
4. Choose **Add Interpreter → Add Local Interpreter**, then select an existing
   environment (the exact labels can vary). Select this interpreter:

   ```text
   C:\Users\Hype\Documents\Codex\2026-10-30\ultralytics-yolo-plugin-yolo-openai-curated-2\work\yolo-env\Scripts\python.exe
   ```

5. If an interpreter name is offered, use **Python 3.13 (Touchline Studio)**. Apply
   the interpreter to the project. The environment already contains the installed
   YOLO dependencies; creating another environment is unnecessary for this computer.
6. Choose **Touchline Studio** from the Run selector and click Run. It runs
   `launch.py --lan` from this project folder. If the saved Run configuration still
   reports an invalid interpreter, open **Run → Edit Configurations**, select it,
   and set its Python interpreter to the same existing environment.
7. Choose **Touchline Python tests** to run the Python regression suite, or
   **Build Touchline package** to rebuild the ZIP.

All Python, JavaScript, HTML, CSS, tests, and documentation belong to this single
project. They do not need to be pasted into the Python editor. Browser code remains
under `dist/`; Python serves and analyzes video. Start reading with SOURCE-GUIDE.md,
then CODE-MAP.md. External Libraries exposes the installed third-party dependencies.

`.idea/` is local IDE state and is ignored by Git. `.run/` contains the shared Run
configurations for this workspace. A different computer needs its own interpreter
selection; these machine-specific IDE configurations are not bundled into the ZIP.
