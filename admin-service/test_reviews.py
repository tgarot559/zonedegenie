import unittest,os,time
from unittest.mock import patch,MagicMock
import reviews
class ReviewTest(unittest.TestCase):
 def setUp(self):
  self.e=patch.dict(os.environ,{'SESSION_SECRET':'test-secret-for-tests'});self.e.start();self.addCleanup(self.e.stop)
 def form(self):return {'token':reviews.issue(),'message':'Un retour de test suffisamment long.','had_call':'yes'}
 def test_private_by_default(self):self.assertFalse(reviews.validate(self.form())[-1])
 def test_publication_opt_in(self):f=self.form();f['publish']='yes';self.assertTrue(reviews.validate(f)[-1])
 def test_invalid_token(self):f=self.form();f['token']='bad';self.assertRaises(ValueError,reviews.validate,f)
 def test_expired_token(self):
  with patch.object(reviews.time,'time',return_value=time.time()-8000):token=reviews.issue()
  self.assertFalse(reviews.validate_token(token))
 def test_required_actual_call(self):f=self.form();f.pop('had_call');self.assertRaises(ValueError,reviews.validate,f)
 def test_honeypot(self):f=self.form();f['website']='spam';self.assertRaises(ValueError,reviews.validate,f)
 def test_retries_same_id(self):f=self.form();self.assertEqual(reviews.validate(f)[0],reviews.validate(f)[0])
 def test_db_failure_not_success(self):
  h=MagicMock();h.headers={'Origin':reviews.PUBLIC};h.form.return_value=self.form()
  with patch.object(reviews,'connection',side_effect=RuntimeError):reviews.post(h)
  self.assertEqual(h.output.call_args.args[1],503)
 def test_private_admin(self):
  h=MagicMock();h.auth.return_value=None
  with patch.object(reviews,'connection') as db:reviews.get(h,'/reviews-admin');db.assert_not_called()
if __name__=='__main__':unittest.main()
