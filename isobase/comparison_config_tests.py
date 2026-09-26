"""The pinning mechanism must detect drift; no installed Prolog is needed."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import comparison_config as config

class Pins(unittest.TestCase):
    def test_contract(self):
        contract=config.verify_contract()
        self.assertEqual(len(contract['required_predicates']),97)
        self.assertEqual(len(set(contract['required_predicates'])),97)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in config.LOCK['contract_sha256']:(root/name).write_bytes((config.CONTRACT_DIR/name).read_bytes())
            (root/'contract.json').write_text('{}')
            with patch.object(config,'CONTRACT_DIR',root),self.assertRaisesRegex(RuntimeError,'Contract input changed'):config.verify_contract()
    def test_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*args):return subprocess.check_output(['git','-C',d,*args],stderr=subprocess.DEVNULL,text=True).strip()
            git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            p=Path(d)/'source';p.write_text('original');git('add','.');git('commit','-m','fixture')
            revision=git('rev-parse','HEAD');config.verify_checkout(d,revision)
            with self.assertRaisesRegex(RuntimeError,'revision mismatch'):config.verify_checkout(d,'0'*40)
            p.write_text('modified')
            with self.assertRaisesRegex(RuntimeError,'modified'):config.verify_checkout(d,revision)
            git('checkout','--','source');(Path(d)/'unexpected.pl').write_text('true.')
            with self.assertRaisesRegex(RuntimeError,'modified'):config.verify_checkout(d,revision)
    def test_runtime_version(self):
        with patch.object(config,'verify_checkout'),patch.object(config,'executable',return_value='fixture'),patch.object(config,'output',return_value='SWI-Prolog version 0.0.0'):
            with self.assertRaisesRegex(RuntimeError,'version mismatch'):config.comparison_inputs()
    def test_configurable_paths(self):
        with tempfile.TemporaryDirectory(prefix='comparison paths ') as d:
            root=Path(d);trinity=root/'peer';gnu=root/'runtime'
            def executable(env,default):return env
            def output(args):return 'SWI-Prolog version 10.1.3' if args[0]=='SWIPL' else 'Prolog top-level (GNU Prolog) 1.6.0'
            with patch.dict('os.environ',{'TRINITY_ROOT':str(trinity),'GPROLOG_SOURCE':str(gnu)}),patch.object(config,'verify_checkout') as check,patch.object(config,'executable',side_effect=executable),patch.object(config,'output',side_effect=output):
                inputs=config.comparison_inputs()
                self.assertEqual(inputs[1],trinity.resolve());self.assertEqual(inputs[3],gnu.resolve())
                self.assertEqual([call.args[0] for call in check.call_args_list],[trinity.resolve(),gnu.resolve()])
    def test_environment_drift(self):
        fixture=str(Path(__file__).resolve())
        with patch.object(config,'comparison_inputs',return_value=(fixture,Path('.'),fixture,Path('.'))),patch.object(config,'executable',return_value=fixture),patch.object(config,'output',return_value='other build'),patch.object(config,'curl_runtime',return_value='other curl'):
            with self.assertRaisesRegex(RuntimeError,'Platform/toolchain differs'):config.record_run('must-not-run')
    def test_runtime_build_drift(self):
        fixture=str(Path(__file__).resolve());host=config.LOCK['baseline_platform'];chain=config.LOCK['baseline_toolchain']
        def output(args):return chain['cc'] if str(args[0])==fixture else chain['curl_config']
        with patch.object(config,'comparison_inputs',return_value=(fixture,Path('.'),fixture,Path('.'))),patch.object(config,'executable',return_value=fixture),patch.object(config,'output',side_effect=output),patch.object(config,'curl_runtime',return_value=chain['curl_runtime']),patch.object(config.platform,'system',return_value=host['system']),patch.object(config.platform,'machine',return_value=host['machine']),patch.object(config.platform,'release',return_value=host['release']):
            with self.assertRaisesRegex(RuntimeError,'Runtime binary differs'):config.record_run('must-not-run')
    def test_missing_executable(self):
        with patch.dict('os.environ',{'SWIPL':'/does/not/exist'}),self.assertRaisesRegex(RuntimeError,'Missing executable'):config.executable('SWIPL','swipl')

if __name__=='__main__':unittest.main()
