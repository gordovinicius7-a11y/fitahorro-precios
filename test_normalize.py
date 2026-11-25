import unittest
from update import normalize, REGIONS

class TestNormalize(unittest.TestCase):
    def setUp(self):
        self.row={'chain':'mercadona','zone':'mad1','sku':'123','display_name':'Pechuga','category':'Carne','subcategory':'Pollo','unit_price':3.5,'reference_price':7.0,'reference_format':'kg','captured_at':'2026-11-25','brand':'','url':'https://example.com'}
    def test_valid(self):
        r=normalize(self.row,'mercadona','mad1','2026-11-25');self.assertEqual((r['price'],r['reference'],r['date']),(3.5,7.0,'2026-11-25'))
    def test_bad_price(self):
        for v in [0,-1,float('nan'),float('inf'),None]:
            self.assertIsNone(normalize(dict(self.row,unit_price=v),'mercadona','mad1','2026-11-25'))
    def test_wrong_zone_date(self):
        self.assertIsNone(normalize(self.row,'mercadona','bcn1','2026-11-25'));self.assertIsNone(normalize(self.row,'mercadona','mad1','2026-11-26'))
    def test_missing_unit(self):
        self.assertIsNone(normalize(dict(self.row,reference_format=None),'mercadona','mad1','2026-11-25')['reference'])
    def test_regions(self):
        self.assertNotIn(('mercadona','bcn1'),REGIONS['madrid']);self.assertIn(('dia','es-default'),REGIONS['general'])
if __name__=='__main__':unittest.main()
