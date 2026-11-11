import unittest
from ..subgroups import summarize

class SubgroupTests(unittest.TestCase):
    def test_people_not_task_counts(self):
        rows=[dict(person='a',task=str(i),options=['x','y'],answer=0,stratum='s',background={'age':'young'}) for i in range(3)]
        rows.append(dict(person='b',task='0',options=['x','y'],answer=1,stratum='s',background={}))
        p={(r['person'],r['task']):[1,0] for r in rows}
        result=summarize(rows,p,['age'])
        self.assertEqual(result[0]['accuracy'],.5)
        self.assertEqual(result[0]['brier'],1)
        unknown=next(r for r in result if r['value']=='unknown')
        self.assertEqual(unknown['people'],1);self.assertTrue(unknown['small_group'])
