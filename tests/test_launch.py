import importlib.util
import io
import os
import shutil
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import launch


class LauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows batch launcher')
    def test_copied_launcher_rejects_incomplete_folder_before_setup(self):
        with tempfile.TemporaryDirectory(prefix='touchline incomplete ') as directory:
            launcher=Path(directory)/'Start Touchline.cmd'
            shutil.copyfile(Path(launch.__file__).with_name('Start Touchline.cmd'),launcher)
            result=subprocess.run(['cmd.exe','/d','/c',str(launcher)],input='\n',text=True,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('Touchline application files are missing',result.stdout)
            self.assertNotIn('Installing the tracking engine',result.stdout)
            self.assertFalse((Path(directory)/'.venv').exists())
            self.assertFalse((Path(directory)/'work').exists())

    def test_spawn_failure_shows_os_error(self):
        probe=MagicMock();probe.__enter__.return_value.connect_ex.return_value=1
        output=io.StringIO()
        with tempfile.TemporaryDirectory() as directory, patch.object(launch,'ROOT',Path(directory)), patch.object(sys,'argv',['launch.py','--no-browser']), patch.object(launch,'health',return_value=None), patch.object(launch.socket,'socket',return_value=probe), patch.object(launch.subprocess,'Popen',side_effect=OSError('Not enough memory')), redirect_stdout(output):
            self.assertEqual(launch.main(),1)
        self.assertIn('Not enough memory',output.getvalue())

    def test_failed_start_shows_only_current_attempt_log(self):
        probe=MagicMock();probe.__enter__.return_value.connect_ex.return_value=1
        process=MagicMock();process.poll.return_value=1
        output=io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'work').mkdir()
            log=root/'work/server.log';log.write_text('unrelated old error\n',encoding='utf-8')
            def spawn(*args,**kwargs):
                kwargs['stderr'].write(b'Current startup failure\n');kwargs['stderr'].flush()
                return process
            with patch.object(launch,'ROOT',root), patch.object(sys,'argv',['launch.py','--no-browser']), patch.object(launch,'health',return_value=None), patch.object(launch.socket,'socket',return_value=probe), patch.object(launch.subprocess,'Popen',side_effect=spawn), redirect_stdout(output):
                self.assertEqual(launch.main(),1)
        self.assertIn('Current startup failure',output.getvalue())
        self.assertNotIn('unrelated old error',output.getvalue())

    def test_ready_server_is_supervised_until_it_exits(self):
        probe=MagicMock();probe.__enter__.return_value.connect_ex.return_value=1
        process=MagicMock();process.poll.return_value=None;process.wait.return_value=7
        with tempfile.TemporaryDirectory() as directory, patch.object(launch,'ROOT',Path(directory)), patch.object(sys,'argv',['launch.py','--no-browser']), patch.object(launch,'health',side_effect=[None,{'app':'touchline-studio'}]), patch.object(launch.socket,'socket',return_value=probe), patch.object(launch.subprocess,'Popen',return_value=process) as spawn:
            self.assertEqual(launch.main(),7)
            process.wait.assert_called_once()
            self.assertNotIn('creationflags',spawn.call_args.kwargs)

    def test_existing_server_is_reused(self):
        with patch.object(sys,'argv',['launch.py','--no-browser']), patch.object(launch,'health',return_value={'app':'touchline-studio'}), patch.object(launch.subprocess,'Popen') as spawn:
            self.assertEqual(launch.main(),0)
            spawn.assert_not_called()

    def test_foreign_port_is_not_killed_or_replaced(self):
        probe=MagicMock();probe.__enter__.return_value.connect_ex.return_value=0
        with patch.object(sys,'argv',['launch.py','--no-browser']), patch.object(launch,'health',return_value=None), patch.object(launch.socket,'socket',return_value=probe), patch.object(launch.subprocess,'Popen') as spawn:
            self.assertEqual(launch.main(),1)
            spawn.assert_not_called()

    def test_dead_child_reports_failure_without_opening_browser(self):
        probe=MagicMock();probe.__enter__.return_value.connect_ex.return_value=1
        process=MagicMock();process.poll.return_value=1
        with tempfile.TemporaryDirectory() as directory, patch.object(launch,'ROOT',Path(directory)), patch.object(sys,'argv',['launch.py']), patch.object(launch,'health',return_value=None), patch.object(launch.socket,'socket',return_value=probe), patch.object(launch.subprocess,'Popen',return_value=process), patch.object(launch.webbrowser,'open') as browser:
            self.assertEqual(launch.main(),1)
            browser.assert_not_called()

if __name__=='__main__':unittest.main()
