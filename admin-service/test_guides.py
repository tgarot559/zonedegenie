import unittest,os,time,uuid,io,json
from unittest.mock import patch,MagicMock
from urllib.parse import urlsplit,parse_qs
import guides
class GuideTest(unittest.TestCase):
 def setUp(self):
  self.p=patch.dict(os.environ,{'SESSION_SECRET':'tests-only-secret-for-guide-links'},clear=True);self.p.start();self.oid=uuid.uuid4()
  self.s={'id':'cs_live_example','metadata':{'guide_order':str(self.oid),'sku':guides.SKU},'mode':'payment','currency':'eur','amount_total':1500,'livemode':True,'payment_status':'paid','status':'complete'}
 def tearDown(self):self.p.stop()
 def test_closed_by_default(self):self.assertFalse(guides.ready())
 def test_payment_binding(self):
  self.assertEqual(guides.status_of(self.s,self.oid,self.s['id']),'paid')
  for key,value in [('amount_total',1),('currency','usd'),('livemode',False),('mode','subscription'),('id','cs_other'),('metadata',{'sku':'other'})]:
   with self.subTest(key=key),self.assertRaises(ValueError):guides.status_of({**self.s,key:value},self.oid,self.s['id'])
 def test_pending_not_entitled(self):self.assertEqual(guides.status_of({**self.s,'payment_status':'unpaid'},self.oid,self.s['id']),'pending')
 def test_refund_dispute_revoked(self):
  for charge in ({'amount_refunded':1},{'disputed':True}):self.assertEqual(guides.status_of({**self.s,'payment_intent':{'latest_charge':charge}},self.oid,self.s['id']),'revoked')
 def test_bad_link_never_contacts_stripe(self):
  with patch.object(guides,'refresh') as refresh,self.assertRaises(ValueError):guides.authorize({'order':[str(self.oid)],'token':['fake']})
  refresh.assert_not_called()
 def test_gift_is_separate_and_expires(self):
  q=parse_qs(urlsplit(guides.gift_url('booking')).fragment);self.assertTrue(guides.check_gift(q['gift'][0]));self.assertFalse(guides.check_gift(q['gift'][0]+'x'))
  with patch.object(guides.time,'time',return_value=time.time()+366*86400):self.assertFalse(guides.check_gift(q['gift'][0]))
  self.assertFalse(guides.check_gift(guides.sign('guide:'+str(self.oid))))
 def test_nonce_signature_and_expiry(self):
  nonce='a'*32+'.'+str(int(time.time()));value=nonce+'.'+guides.sign('checkout:'+nonce)
  self.assertTrue(guides.validate_nonce(value));self.assertFalse(guides.validate_nonce(value+'x'))
  with patch.object(guides.time,'time',return_value=time.time()+3601):self.assertFalse(guides.validate_nonce(value))
 def test_unpaid_download_never_decrypts(self):
  h=MagicMock();h.headers={}
  with patch.object(guides,'authorize',return_value=('pending',self.oid)),patch.object(guides,'pdf_bytes') as pdf:guides.get(h,urlsplit('/guide.pdf'),{})
  pdf.assert_not_called();h.send_response.assert_called_with(403)
 def test_invalid_webhook_has_no_effect(self):
  h=MagicMock();h.headers={'Content-Length':'2','Stripe-Signature':'invalid'};h.rfile=io.BytesIO(b'{}')
  with patch.object(guides,'refresh') as refresh:guides.post(h,'/guide-webhook')
  refresh.assert_not_called();h.send_response.assert_called_with(400)
 def test_duplicate_mail_not_sent(self):
  c=MagicMock();c.__enter__.return_value=c;c.execute.return_value.fetchone.return_value=None
  with patch.object(guides,'connection',return_value=c),patch('smtplib.SMTP_SSL') as smtp:guides.email_receipt(self.oid)
  smtp.assert_not_called()
if __name__=='__main__':unittest.main()
