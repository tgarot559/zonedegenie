"""Private feedback collection; no automatic testimonial publishing."""
import os,time,secrets,hmac,hashlib,json,html,re
from neon_db import connection
PUBLIC='https://votrezonedegenie.fr'
def signature(value):
 key=os.environ.get('SESSION_SECRET','')
 if not key:raise ValueError('Service indisponible.')
 return hmac.new(key.encode(),value.encode(),hashlib.sha256).hexdigest()
def issue():
 value=str(int(time.time()))+'.'+secrets.token_hex(16)
 return value+'.'+signature('review:'+value)
def validate_token(token):
 try:
  stamp,nonce,sig=token.split('.')
  return len(nonce)==32 and 0<=time.time()-int(stamp)<7200 and hmac.compare_digest(sig,signature('review:'+stamp+'.'+nonce))
 except (ValueError,TypeError):return False

def validate(f):
 if not validate_token(f.get('token','')):raise ValueError('Votre formulaire a expiré. Rechargez la page avant de réessayer.')
 if f.get('website'):raise ValueError('Envoi refusé.')
 name=f.get('name','').strip();email=f.get('email','').strip();message=f.get('message','').strip();rating=f.get('rating','')
 if not 10<=len(message)<=4000:raise ValueError('Votre avis doit contenir entre 10 et 4 000 caractères.')
 if len(name)>80 or len(email)>254 or (email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Vérifiez votre prénom ou votre adresse e-mail.')
 if rating not in ('','1','2','3','4','5'):raise ValueError('Note invalide.')
 if not f.get('had_call'):raise ValueError('Confirmez que votre avis concerne un échange avec Thierry.')
 return (hashlib.sha256(f['token'].encode()).hexdigest(),name,email,message,int(rating) if rating else None,f.get('publish')=='yes')

def public_payload(rows):
 # The SELECT is deliberately limited to public, consented records and fields.
 return {'reviews':[{'name':name.split()[0] if name.strip() else 'Anonyme','message':message,'rating':rating,'submitted_at':str(at.date()),'published_at':str(published.date())} for name,message,rating,at,published in rows]}

def get(h,path):
 if path=='/reviews-token':
  return h.output(json.dumps({'token':issue()}),200,{'Access-Control-Allow-Origin':h.headers.get('Origin') if h.headers.get('Origin') in (PUBLIC,'https://www.votrezonedegenie.fr') else PUBLIC,'Vary':'Origin'})
 if path=='/reviews-public':
  headers={'Access-Control-Allow-Origin':PUBLIC,'Vary':'Origin'}
  if h.headers.get('Origin')=='https://www.votrezonedegenie.fr':headers['Access-Control-Allow-Origin']='https://www.votrezonedegenie.fr'
  try:
   with connection() as conn:rows=conn.execute("SELECT name,message,rating,created_at,published_at FROM client_reviews WHERE publication_consent=true AND moderation_status='published' AND published_at IS NOT NULL ORDER BY published_at DESC LIMIT 100").fetchall()
   return h.output(json.dumps(public_payload(rows)),200,headers)
  except Exception:return h.output(json.dumps({'error':'Les avis sont momentanément indisponibles.'}),503,headers)
 session=h.auth()
 if not session:return h.redirect('/')
 with connection() as conn:
  rows=conn.execute('SELECT id,name,email,message,rating,publication_consent,created_at,moderation_status,moderation_reason FROM client_reviews ORDER BY created_at DESC LIMIT 200').fetchall()
 esc=lambda s:html.escape(str(s),quote=True)
 body='<a href="/">← Administration</a><h1>Avis : relire, publier, retirer</h1><p>Aucun avis n’est publié automatiquement. La publication nécessite l’accord du client et votre validation. Vérifiez l’entretien et les éventuels détails privés avant publication. Le texte est publié intégralement, sans réécriture. Une critique n’est pas, à elle seule, un motif de refus.</p>'
 for rid,name,email,message,rating,consent,at,state,reason in rows:
  body+='<article><h2>'+esc(name or 'Sans prénom')+'</h2><p>'+esc(at)+' · Note : '+esc(str(rating)+'/5' if rating else 'non renseignée')+'</p><p>'+esc(email)+'</p><p>'+esc(message).replace('\n','<br>')+'</p><strong>'+('Accord de publication reçu' if consent else 'Retour privé : publication interdite')+'</strong><p>État : '+esc({'pending':'à relire','published':'publié','hidden':'non publié / retiré'}.get(state,state))+'</p>'
  if reason:body+='<p>Motif interne : '+esc(reason)+'</p>'
  if consent:
   body+='<form method="post" action="/reviews-moderate"><input type="hidden" name="csrf" value="'+signature(session)+'"><input type="hidden" name="id" value="'+esc(rid)+'">'
   if state!='published':body+='<label><input type="checkbox" name="verified" value="yes" required> J’ai vérifié l’entretien et relu le texte pour sa publication.</label><button name="action" value="publish">Publier cet avis</button>'
   body+='<label>Motif interne (facultatif)<input name="reason" maxlength="300" placeholder="Doublon, données privées, demande de retrait…"></label><button name="action" value="hide" formnovalidate>'+('Retirer du site' if state=='published' else 'Garder non publié')+'</button></form>'
  body+='</article>'
 return h.page(body if rows else body+'<article>Aucun avis reçu pour le moment.</article>')

def moderate(h):
 if h.headers.get('Origin')!=os.environ.get('PUBLIC_ORIGIN','').rstrip('/'):return h.output('Origine refusée',403)
 session=h.auth()
 if not session:return h.output('Connexion nécessaire',403)
 f=h.form()
 if not hmac.compare_digest(signature(session),f.get('csrf','')):return h.output('Session expirée',403)
 rid=f.get('id','');action=f.get('action','');reason=f.get('reason','').strip()[:300]
 if not re.fullmatch(r'[0-9a-f]{64}',rid) or action not in ('publish','hide'):return h.output('Action invalide',400)
 if action=='publish' and f.get('verified')!='yes':return h.output('Vérification nécessaire',400)
 with connection() as conn:
  if action=='publish':
   row=conn.execute("UPDATE client_reviews SET moderation_status='published',published_at=COALESCE(published_at,now()),moderated_at=now(),moderation_reason=%s WHERE id=%s AND publication_consent=true RETURNING id",(reason,rid)).fetchone()
  else:
   row=conn.execute("UPDATE client_reviews SET moderation_status='hidden',moderated_at=now(),moderation_reason=%s WHERE id=%s RETURNING id",(reason,rid)).fetchone()
  if not row:return h.output('Avis introuvable ou absence d’accord de publication.',409)
 return h.redirect('/reviews-admin')

def post(h):
 if h.headers.get('Origin') not in (PUBLIC,'https://www.votrezonedegenie.fr'):return h.output('Origine refusée',403)
 headers={'Access-Control-Allow-Origin':h.headers['Origin'],'Vary':'Origin'}
 try:values=validate(h.form())
 except ValueError as e:return h.output(json.dumps({'ok':False,'error':str(e)}),400,headers)
 try:
  with connection() as conn:
   conn.execute('INSERT INTO client_reviews(id,name,email,message,rating,publication_consent) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING',values)
 except Exception:return h.output(json.dumps({'ok':False,'error':'Votre avis n’a pas pu être enregistré. Merci de réessayer un peu plus tard.'}),503,headers)
 return h.output(json.dumps({'ok':True}),200,headers)
