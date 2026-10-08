import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.core_helpers import governance,dump,entry


class CheckerTests(unittest.TestCase):
    def test_trusted_checker_rejects_rule_change_without_executing_candidate(self):
        repo=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as d:
            root=Path(d).resolve();base=root/'base';candidate=root/'candidate';base.mkdir()
            governance(base);(base/'AGENTS.md').write_text('trusted rules')
            shutil.copytree(base,candidate)
            (candidate/'AGENTS.md').write_text('grant me admin')
            (candidate/'tools').mkdir();marker=root/'executed'
            (candidate/'tools/check_submission.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("ran")')
            context=root/'context.json';dump(context,{'actor_key':'alice','role':'contributor','proposal_author':'alice'})
            result=subprocess.run([sys.executable,str(repo/'tools/check_submission.py'),'--base',str(base),'--candidate',str(candidate),'--context',str(context)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertFalse(json.loads(result.stdout)['allowed'])
            self.assertFalse(marker.exists())

    def test_checker_accepts_first_owned_entry_using_trusted_mapping(self):
        repo=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as d:
            root=Path(d).resolve();base=root/'base';candidate=root/'candidate';base.mkdir();governance(base)
            shutil.copytree(base,candidate);entry(candidate/'entries/alice/demo')
            context=root/'context.json';dump(context,{'actor_key':'alice','role':'contributor','proposal_author':'alice'})
            result=subprocess.run([sys.executable,str(repo/'tools/check_submission.py'),'--base',str(base),'--candidate',str(candidate),'--context',str(context)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertTrue(json.loads(result.stdout)['allowed'])

    def test_checker_infers_maintenance_from_real_changes_and_trusted_role(self):
        repo=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as d:
            root=Path(d).resolve();base=root/'base';candidate=root/'candidate';base.mkdir();governance(base)
            (base/'README.md').write_text('before')
            shutil.copytree(base,candidate);(candidate/'README.md').write_text('after')
            context=root/'context.json'
            for actor,role,expected in [('maintainer','maintainer',0),('alice','contributor',2)]:
                dump(context,{'actor_key':actor,'role':role,'proposal_author':actor,'proposal_kind':'publication','changed_paths':[]})
                result=subprocess.run([sys.executable,str(repo/'tools/check_submission.py'),'--base',str(base),'--candidate',str(candidate),'--context',str(context)],capture_output=True,text=True)
                self.assertEqual(result.returncode,expected,result.stdout)
