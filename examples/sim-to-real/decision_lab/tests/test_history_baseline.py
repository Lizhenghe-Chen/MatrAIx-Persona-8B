import unittest
from ..history_baseline import HistoricalProportions

class HistoryTests(unittest.TestCase):
    def row(self,p,options,answer=0,task='q',context='original'):
        return dict(person=p,task=task,options=options,answer=answer,context=context,question='Choose')
    def test_semantics_not_positions(self):
        model=HistoricalProportions().fit([self.row('a',['cheap','costly']),self.row('b',['costly','cheap'],1)])
        result,support=model.predict([self.row('test',['costly','cheap'])])
        self.assertEqual(result[('test','q')],[0,1]);self.assertEqual(support[('test','q')],2)
    def test_unseen_and_context_fallback(self):
        model=HistoricalProportions().fit([self.row('a',['x','y'])])
        result,support=model.predict([self.row('b',['x','y'],context='different')])
        self.assertEqual(result[('b','q')],[.5,.5]);self.assertEqual(support[('b','q')],0)
    def test_people_are_equal_before_weights(self):
        train=[self.row('a',['x','y'],task=str(i)) for i in range(3)]+[self.row('b',['x','y'],1)]
        result,_=HistoricalProportions().fit(train).predict([self.row('c',['x','y'])])
        self.assertEqual(result[('c','q')],[.5,.5])
    def test_leakage_rejected(self):
        row=self.row('a',['x','y']);model=HistoricalProportions().fit([row])
        with self.assertRaises(ValueError):model.predict([row])
