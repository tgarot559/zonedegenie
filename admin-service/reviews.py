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

def get(h,path):
 if path=='/reviews-token':
  return h.output(json.dumps({'token':issue()}),200,{'Access-Control-Allow-Origin':h.headers.get('Origin') if h.headers.get('Origin') in (PUBLIC,'https://www.votrezonedegenie.fr') else PUBLIC,'Vary':'Origin'})
 if not h.auth():return h.redirect('/')
 with connection() as conn:
  rows=conn.execute('SELECT name,email,message,rating,publication_consent,created_at FROM client_reviews ORDER BY created_at DESC LIMIT 200').fetchall()
 esc=lambda s:html.escape(str(s),quote=True)
 body='<a href="/">← Administration</a><h1>Les retours après entretien</h1><p>Aucun avis n’est publié automatiquement. Un accord de publication ne constitue pas une vérification de l’entretien ; contrôlez la réservation avant toute utilisation publique.</p>'
 for name,email,message,rating,consent,at in rows:
  body+='<article><h2>'+esc(name or 'Sans prénom')+'</h2><p>'+esc(at)+' · Note : '+esc(str(rating)+'/5' if rating else 'non renseignée')+'</p><p>'+esc(email)+'</p><p>'+esc(message).replace('\n','<br>')+'</p><strong>'+('Publication autorisée avec prénom ou anonymement' if consent else 'Retour privé uniquement')+'</strong></article>'
 return h.page(body if rows else body+'<article>Aucun avis reçu pour le moment.</article>')

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
