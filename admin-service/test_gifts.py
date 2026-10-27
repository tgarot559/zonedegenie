import unittest,os,uuid,copy,io
from unittest.mock import patch,MagicMock
import gifts
class GiftsTest(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'GIFT_SECRET':'s'*40,'MOLLIE_API_KEY':'live_example','GIFT_SALES_ENABLED':'false'},clear=False);self.env.start();self.addCleanup(self.env.stop)
  self.oid=uuid.uuid4();self.p={'id':'tr_example','metadata':{'gift_order':str(self.oid)},'mode':'live','amount':{'currency':'EUR','value':'90.00'},'status':'paid'}
 def test_closed_by_default(self): self.assertFalse(gifts.enabled())
 def test_test_key_cannot_open_sales(self):
  with patch.dict(os.environ,{'GIFT_SALES_ENABLED':'true','MOLLIE_API_KEY':'test_example'}):self.assertFalse(gifts.enabled())
 def test_paid(self):self.assertEqual(gifts.verified_status(self.p,self.oid,'tr_example'),'paid')
 def test_wrong_amount_mode_id_or_order(self):
  for key,value in [('amount',{'currency':'EUR','value':'1.00'}),('mode','test'),('id','tr_other'),('metadata',{'gift_order':str(uuid.uuid4())})]:
   p=copy.deepcopy(self.p);p[key]=value
   with self.assertRaises(ValueError):gifts.verified_status(p,self.oid,'tr_example')
 def test_pending_is_not_paid(self):
  for status in ['open','pending','authorized']:
   p=copy.deepcopy(self.p);p['status']=status;self.assertEqual(gifts.verified_status(p,self.oid,'tr_example'),'pending')
 def test_refund_and_chargeback_disable_card(self):
  for key in ['amountRefunded','amountChargedBack']:
   p=copy.deepcopy(self.p);p[key]={'value':'0.01'};self.assertEqual(gifts.verified_status(p,self.oid,'tr_example'),'refunded')
 def test_tokens_distinct_stable_per_order(self):
  self.assertEqual(gifts.code(self.oid),gifts.code(self.oid));self.assertNotEqual(gifts.token(self.oid),gifts.token(uuid.uuid4()));self.assertNotEqual(gifts.token(self.oid),gifts.code(self.oid))
 def test_bad_token_cannot_read_payment_or_pdf(self):
  h=MagicMock();u=MagicMock(path='/gift.pdf')
  with patch.object(gifts,'refresh') as refresh:
   with self.assertRaises(ValueError):gifts.get(h,u,{'order':[str(self.oid)],'token':['wrong']})
   refresh.assert_not_called()
 def test_pdf(self):self.assertTrue(gifts.pdf(self.oid).startswith(b'%PDF-'))
 def test_unpaid_pdf_denied(self):
  h=MagicMock();u=MagicMock(path='/gift.pdf')
  with patch.object(gifts,'refresh',return_value='pending'),patch.object(gifts,'pdf') as pdf:
   gifts.get(h,u,{'order':[str(self.oid)],'token':[gifts.token(self.oid)]});pdf.assert_not_called()
 def test_webhook_looks_up_known_order_and_rechecks(self):
  h=MagicMock();h.form.return_value={'id':'tr_example'}
  with patch.object(gifts,'connection') as conn,patch.object(gifts,'refresh') as refresh:
   conn.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=(self.oid,)
   gifts.post(h,'/mollie-webhook');refresh.assert_called_once_with(self.oid)
if __name__=='__main__':unittest.main()
