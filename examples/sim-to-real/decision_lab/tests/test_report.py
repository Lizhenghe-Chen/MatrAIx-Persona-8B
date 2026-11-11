import unittest
from ..reporting.report import render

class ReportTests(unittest.TestCase):
    def document(self):
        s={'brier':.5,'mean_tv_pp':10,'accuracy':.5,'groups':{'Question':{'options':['<A>','B'],'human':[.4,.6],'model':[.5,.5]}}}
        return {'status':'development','title':'Synthetic test','conclusion':'No research conclusion','method':'Test only','limitations':['Synthetic'],'provenance':['Fixture'],'studies':[{'name':'Test','sample_note':'Two synthetic options','arms':[{'label':'Probability output','scores':s}]}]}
    def test_visible_numbers_and_escape(self):
        h=render(self.document());self.assertIn('40.0%',h);self.assertIn('&lt;A&gt;',h);self.assertIn('不能作为独立成功证据',h)
    def test_requires_provenance(self):
        d=self.document();d['provenance']=[]
        with self.assertRaises(ValueError):render(d)
