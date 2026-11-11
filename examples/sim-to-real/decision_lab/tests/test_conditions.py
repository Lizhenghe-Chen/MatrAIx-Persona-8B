import unittest
from ..core.conditions import shuffled_background,permute_options,restore_probabilities

class ConditionsTests(unittest.TestCase):
    def test_blocks_stay_together_and_splits_do_not_mix(self):
        rows=[{'person':str(i),'stratum':'s','background':{'age':'young','income':i,'household':i+10}} for i in range(5)]
        assignments={str(i):'train' if i<3 else 'test' for i in range(5)}
        result,audit=shuffled_background(rows,['age'],['income','household'],assignments)
        for row in result:
            self.assertNotEqual(row['background']['income'],int(row['person']))
            self.assertEqual(row['background']['household'],row['background']['income']+10)
            self.assertEqual(assignments[row['person']],assignments[audit['donors'][row['person']]])
        self.assertEqual(audit['shuffled_people'],5)
        self.assertEqual(rows[0]['background']['income'],0)
    def test_singletons_reported(self):
        rows=[{'person':'p','stratum':'s','background':{'age':20,'income':1}}]
        result,audit=shuffled_background(rows,['age'],['income'],{'p':'test'})
        self.assertEqual(audit['unshuffled_singletons'],['p']);self.assertEqual(result,rows)
    def test_mapping_back_to_original(self):
        row={'options':['red','blue','neither'],'answer':1}
        reordered=permute_options(row,[2,0,1])
        self.assertEqual(reordered['answer'],2)
        self.assertEqual(restore_probabilities([.1,.2,.7],[2,0,1]),[.2,.7,.1])
    def test_same_block_values_not_counted_as_changed(self):
        rows=[{'person':p,'stratum':'s','background':{'age':20,'income':1}} for p in ['a','b']]
        _,audit=shuffled_background(rows,['age'],['income'],{'a':'test','b':'test'})
        self.assertEqual(audit['shuffled_people'],2)
        self.assertEqual(audit['content_changed_people'],[])
