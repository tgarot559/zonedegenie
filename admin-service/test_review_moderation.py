import unittest,sqlite3,os,json
from datetime import datetime
from unittest.mock import patch,MagicMock
import reviews
class DB:
 def __init__(self,c):self.c=c
 def __enter__(self):return self
 def __exit__(self,*args):self.c.commit()
 def execute(self,sql,args=()):return self.c.execute(sql.replace('%s','?').replace('now()','CURRENT_TIMESTAMP'),args)
class ModerationTest(unittest.TestCase):
 def setUp(self):
  self.p=patch.dict(os.environ,{'SESSION_SECRET':'moderation-test-secret','PUBLIC_ORIGIN':'https://admin.example'});self.p.start();self.addCleanup(self.p.stop)
  self.c=sqlite3.connect(':memory:',detect_types=sqlite3.PARSE_DECLTYPES);self.addCleanup(self.c.close)
  self.c.execute('CREATE TABLE client_reviews(id TEXT PRIMARY KEY,name TEXT,email TEXT,message TEXT,rating INTEGER,publication_consent BOOLEAN,created_at TIMESTAMP,moderation_status TEXT,published_at TIMESTAMP,moderated_at TIMESTAMP,moderation_reason TEXT)')
  self.c.execute("INSERT INTO client_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)",('a'*64,'Camille','private@example.com','Mon avis <script> est personnel.',2,True,datetime.now(),'pending',None,None,''))
  self.c.execute("INSERT INTO client_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)",('b'*64,'Alex','hidden@example.com','Ce retour doit rester privé.',5,False,datetime.now(),'pending',None,None,''))
  self.dbpatch=patch.object(reviews,'connection',return_value=DB(self.c));self.dbpatch.start();self.addCleanup(self.dbpatch.stop)
 def handler(self,action='publish',rid='a'*64):
  h=MagicMock();h.headers={'Origin':'https://admin.example'};h.auth.return_value='session';h.form.return_value={'id':rid,'action':action,'verified':'yes','csrf':reviews.signature('session')};return h
 def public(self):
  h=MagicMock();h.headers={'Origin':reviews.PUBLIC};reviews.get(h,'/reviews-public');return json.loads(h.output.call_args.args[0])
 def test_pending_invisible(self):self.assertEqual(self.public(),{'reviews':[]})
 def test_consent_and_owner_approval_required(self):
  h=self.handler(rid='b'*64);reviews.moderate(h);h.output.assert_called_with('Avis introuvable ou absence d’accord de publication.',409);self.assertEqual(self.public(),{'reviews':[]})
 def test_publish_then_remove(self):
  reviews.moderate(self.handler());data=self.public();self.assertEqual(len(data['reviews']),1);self.assertEqual(data['reviews'][0]['rating'],2);self.assertNotIn('email',data['reviews'][0]);self.assertNotIn('private@example.com',json.dumps(data))
  reviews.moderate(self.handler('hide'));self.assertEqual(self.public(),{'reviews':[]})
 def test_unverified_cannot_publish(self):
  h=self.handler();h.form.return_value.pop('verified');reviews.moderate(h);h.output.assert_called_with('Vérification nécessaire',400);self.assertEqual(self.public(),{'reviews':[]})
 def test_bad_csrf_cannot_publish(self):
  h=self.handler();h.form.return_value['csrf']='bad';reviews.moderate(h);h.output.assert_called_with('Session expirée',403)
 def test_unauthenticated_cannot_publish(self):
  h=self.handler();h.auth.return_value=None;reviews.moderate(h);h.output.assert_called_with('Connexion nécessaire',403)
 def test_foreign_origin_cannot_publish(self):
  h=self.handler();h.headers['Origin']='https://evil.example';reviews.moderate(h);h.output.assert_called_with('Origine refusée',403)
 def test_revoked_consent_not_exposed(self):
  reviews.moderate(self.handler());self.c.execute('UPDATE client_reviews SET publication_consent=false');self.assertEqual(self.public(),{'reviews':[]})
 def test_admin_escapes_message(self):
  h=self.handler();reviews.get(h,'/reviews-admin');body=h.page.call_args.args[0];self.assertNotIn('<script>',body);self.assertIn('&lt;script&gt;',body)
if __name__=='__main__':unittest.main()
