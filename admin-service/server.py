import os,json,sqlite3,secrets,hmac,hashlib,time,html,smtplib,ssl,urllib.request,urllib.parse
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from email.message import EmailMessage
from datetime import datetime,timezone
from pathlib import Path
E=os.environ
DB=E.get('DATA_PATH','./data/zdg-admin.sqlite3')
SECRET=E.get('SESSION_SECRET','')
PASSWORD=E.get('ADMIN_PASSWORD','')
ORIGIN=E.get('PUBLIC_ORIGIN','').rstrip('/')
GUIDE='https://votrezonedegenie.fr/documents/le-temps-de-laisser-murir.pdf'
EVENT_ID=7609933
FAILURES={}
STYLE='''body{margin:0;background:#faf7f2;color:#233345;font:16px/1.6 system-ui}main{max-width:1050px;margin:auto;padding:30px 20px}h1,h2,h3{font-family:Georgia,serif;line-height:1.2}h1{font-size:38px}a{color:#655181}button,.button{background:#655181;color:white;border:0;border-radius:10px;padding:13px 20px;font:inherit;cursor:pointer;display:inline-block;text-decoration:none}input,textarea{box-sizing:border-box;width:100%;padding:12px;border:1px solid #cfc6d5;border-radius:8px;font:inherit;background:white}input[type=checkbox]{width:auto}label{display:block;margin:15px 0}article,.panel{background:white;border:1px solid #e2dce7;border-radius:18px;padding:24px;margin:20px 0}.muted{color:#617080}.tag{background:#eee8f2;padding:5px 12px;border-radius:20px;display:inline-block}.row{display:flex;gap:15px;flex-wrap:wrap;align-items:center}pre{white-space:pre-wrap}.notice{border-left:4px solid #655181;padding:12px 20px;background:#eee8f2}small{font-size:13px}iframe{width:100%;min-height:530px;border:1px solid #eee}'''
from zoneinfo import ZoneInfo
def datefr(value):
 try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y à %H:%M')
 except:return value
def esc(v):return html.escape(str(v),quote=True)
def db():
 c=sqlite3.connect(DB,timeout=10);c.execute('CREATE TABLE IF NOT EXISTS deliveries(uid TEXT, kind TEXT, recipient TEXT, status TEXT, at TEXT, PRIMARY KEY(uid,kind))');c.execute('CREATE TABLE IF NOT EXISTS answers(uid TEXT PRIMARY KEY, payload TEXT, at TEXT)');return c
def sign(s):return hmac.new(SECRET.encode(),s.encode(),hashlib.sha256).hexdigest()
def token(uid):
 s=f'{uid}|{int(time.time())}';return s+'|'+sign(s)
def checktoken(t):
 try:
  uid,stamp,sig=t.rsplit('|',2);return uid if hmac.compare_digest(sign(uid+'|'+stamp),sig) and 0<=time.time()-int(stamp)<30*86400 else None
 except:return None
def cal(path):
 if not E.get('CAL_API_KEY'):raise ValueError('Connexion Cal.com à configurer côté serveur.')
 req=urllib.request.Request('https://api.cal.com/v2/'+path,headers={'Authorization':'Bearer '+E['CAL_API_KEY'],'cal-api-version':'2024-08-13'})
 with urllib.request.urlopen(req,timeout=20) as r:d=json.load(r)
 if d.get('status')!='success':raise ValueError('Cal.com ne confirme pas la lecture.')
 return d['data'],d.get('pagination',{})
def booking(uid):
 b,_=cal('bookings/'+urllib.parse.quote(uid,safe=''))
 if b.get('eventTypeId',b.get('eventType',{}).get('id'))!=EVENT_ID:raise ValueError('Ce rendez-vous ne correspond pas à cette offre.')
 if b.get('status','').lower() not in ('accepted','confirmed'):raise ValueError('Ce rendez-vous est annulé, en attente ou non confirmé.')
 attendees=b.get('attendees',[])
 if len(attendees)!=1:raise ValueError('Le destinataire doit être vérifié : un seul participant est attendu.')
 a=attendees[0]
 if not a.get('email') or '\n' in a['email'] or '\r' in a['email']:raise ValueError('Adresse du participant invalide.')
 return b,a
def template(b,a,kind):
 from guides import gift_url
 guide=gift_url(b['uid']) if kind=='after' else ''
 name=esc(a.get('name') or '');greeting='Bonjour '+name+',' if name else 'Bonjour,'
 if kind=='before':
  url=ORIGIN+'/questions?t='+urllib.parse.quote(token(b['uid']))
  subject='Notre échange approche, bienvenue'
  body=f'''<p>{greeting}</p><p>Merci pour votre confiance. Je serai heureux de vous écouter lors de notre prochain échange.</p><p>Si vous le souhaitez, vous pouvez partager quelques mots avant notre rendez-vous. Cela prend deux minutes et reste entièrement facultatif : vous pouvez aussi préférer tout me raconter de vive voix.</p><p><a style="display:inline-block;background:#655181;color:#fff;padding:14px 20px;border-radius:8px;text-decoration:none" href="{esc(url)}">Partager quelques mots avant notre échange</a></p><p>Vous n’avez rien à préparer ni à prouver. Venez comme vous êtes.</p><p>À bientôt,<br>Thierry</p>'''
 else:
  subject='Pour laisser notre échange faire son chemin'
  body=f'''<p>{greeting}</p><p>Merci pour notre conversation.</p><p>Comme promis, voici votre guide <em>Le temps de laisser mûrir</em>. Quelques repères et questions pour revenir, à votre rythme, sur ce qui vous a parlé.</p><p><a style="display:inline-block;background:#655181;color:#fff;padding:14px 20px;border-radius:8px;text-decoration:none" href="{esc(guide)}">Télécharger mon guide</a></p><p>Vous n’avez rien à compléter ni à me renvoyer. Gardez simplement ce qui vous est utile.</p><p>Si vous en avez envie, vous pouvez aussi me dire comment vous avez vécu notre échange : ce qui vous a été utile, ce qui vous a manqué ou ce que vous auriez aimé différent. Votre retour m’aide à faire évoluer mon accompagnement.</p><p><a href="https://votrezonedegenie.fr/avis/">Partager mon avis sur notre échange</a></p><p>Cette démarche est facultative. Vous pouvez laisser mûrir et revenir plus tard.</p><p>Prenez soin de vous,<br>Thierry</p>'''
 return subject,f'''<!doctype html><html lang="fr"><meta charset="utf-8"><body style="margin:0;background:#faf7f2;color:#233345;font:16px/1.7 Arial,sans-serif"><div style="max-width:600px;margin:auto;padding:32px 20px"><p style="color:#655181;letter-spacing:2px;font-size:12px">VOTRE ZONE DE GÉNIE</p><h1 style="font:30px/1.2 Georgia,serif">{esc(subject)}</h1>{body}<hr style="border:0;border-top:1px solid #ddd"><small>Thierry Garot · Votre Zone de Génie<br>Un échange humain, à votre rythme.</small></div></body></html>'''
def eligible(b,kind):
 end=datetime.fromisoformat(b['end'].replace('Z','+00:00'))
 if kind=='after' and datetime.now(timezone.utc).timestamp()<end.timestamp()+3600:raise ValueError('Le guide est disponible à l’envoi une heure après la fin prévue.')
 if kind=='before' and datetime.now(timezone.utc)>=end:raise ValueError('Le rendez-vous est déjà terminé.')
def send(uid,kind):
 b,a=booking(uid);eligible(b,kind)
 if not all(E.get(x) for x in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','MAIL_FROM')):raise ValueError('L’envoi e-mail n’est pas encore configuré.')
 subject,body=template(b,a,kind)
 with db() as c:
  try:c.execute('INSERT INTO deliveries VALUES(?,?,?,?,?)',(uid,kind,a['email'],'envoi en cours',datetime.now(timezone.utc).isoformat()))
  except sqlite3.IntegrityError:raise ValueError('Un envoi existe déjà pour ce message. Aucun nouvel envoi effectué ; vérifier l’historique.')
 msg=EmailMessage();msg['From']='Thierry · Votre Zone de Génie <'+E['MAIL_FROM']+'>';msg['To']=a['email'];msg['Reply-To']=E['MAIL_FROM'];msg['Subject']=subject;msg['Message-ID']='<'+hashlib.sha256((uid+kind).encode()).hexdigest()+'@votrezonedegenie.fr>';msg.set_content('Merci pour notre échange. Retrouvez votre guide : '+__import__('guides').gift_url(uid)+'\nSi vous le souhaitez, partagez votre avis : https://votrezonedegenie.fr/avis/\nVotre retour reste privé sauf accord explicite de publication. À bientôt, Thierry.' if kind=='after' else 'Merci pour votre confiance. Vous n’avez rien à préparer ni à prouver. À bientôt, Thierry.');msg.add_alternative(body,subtype='html')
 try:
  with smtplib.SMTP_SSL(E['SMTP_HOST'],int(E.get('SMTP_PORT','465')),timeout=30,context=ssl.create_default_context()) as smtp:
   smtp.login(E['SMTP_USER'],E['SMTP_PASSWORD']);smtp.send_message(msg)
 except Exception:
  with db() as c:c.execute('UPDATE deliveries SET status=? WHERE uid=? AND kind=?',('À vérifier : résultat d’envoi incertain',uid,kind))
  raise ValueError('L’envoi n’a pas été confirmé. Vérifier la boîte Gmail avant toute autre tentative. Aucun renvoi automatique.')
 with db() as c:c.execute('UPDATE deliveries SET status=? WHERE uid=? AND kind=?',('Accepté par le serveur e-mail',uid,kind))
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def output(self,content,status=200,headers=None):
  self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Robots-Tag','noindex, nofollow');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-src 'self'; form-action 'self' https://www.mollie.com; base-uri 'none'; frame-ancestors 'self'")
  for k,v in (headers or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(content.encode())
 def page(self,body,status=200,headers=None):self.output('<!doctype html><html lang="fr"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>Votre Zone de Génie · Administration</title><style>'+STYLE+'</style><main><p class="tag">Votre Zone de Génie · Espace privé</p>'+body+'</main></html>',status,headers)
 def auth(self):
  cookie=self.headers.get('Cookie','');s=next((x.strip()[4:] for x in cookie.split(';') if x.strip().startswith('zdg=')),'')
  try:stamp,nonce,sig=s.split('.');return s if 0<=time.time()-int(stamp)<28800 and hmac.compare_digest(sign(stamp+'.'+nonce),sig) else None
  except:return None
 def form(self):
  n=int(self.headers.get('Content-Length','0'))
  if n>20000:raise ValueError('Formulaire trop volumineux.')
  return {k:v[0] for k,v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()}
 def redirect(self,path,headers=None):self.output('',303,{'Location':path,**(headers or {})})
 def do_GET(self):
  try:self.get()
  except Exception as e:self.page('<h1>Action indisponible</h1><p>'+esc(str(e) if isinstance(e,ValueError) else 'Le service externe est indisponible. Réessayez après vérification.')+'</p><a href="/">Retour</a>',400)
 def get(self):
  u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
  if u.path in ('/guide-config','/guide-access','/guide.pdf','/guides-admin'):
   from guides import get
   return get(self,u,q)
  if u.path in ('/gift-status','/cadeau','/gift-return','/gift.pdf','/gifts-admin'):
   from gifts import get
   return get(self,u,q)
  if u.path in ('/reviews-token','/reviews-admin','/reviews-public'):
   from reviews import get
   return get(self,u.path)
  if u.path=='/health':return self.output('ok')
  if u.path=='/stats':
   if not self.auth():return self.redirect('/')
   from analytics import render_dashboard
   return self.page(render_dashboard())
  if u.path=='/questions':
   t=q.get('t',[''])[0];uid=checktoken(t)
   if not uid:return self.page('<h1>Ce lien a expiré.</h1><p>Vous pouvez tout simplement en parler avec Thierry pendant l’appel.</p>',410)
   with db() as c:row=c.execute('SELECT payload FROM answers WHERE uid=?',(uid,)).fetchone()
   fields=''
   for i,label in enumerate(['Qu’est-ce qui vous a donné envie de réserver aujourd’hui ?','Pour quoi les autres viennent-ils spontanément vous chercher ?','Y a-t-il quelque chose que vous souhaitez me partager avant l’appel ?']):fields+=f'<label>{label}<textarea name="q{i}" rows="3" maxlength="2000"></textarea></label>'
   return self.page('<h1>Quelques mots avant notre échange.</h1><p>Deux minutes, si vous le souhaitez. Toutes les questions sont facultatives. Vous pouvez aussi préférer tout raconter de vive voix.</p>'+('<p class="notice">Vos réponses ont déjà été reçues.</p>' if row else '<form method="post" action="/questions"><input type="hidden" name="token" value="'+esc(t)+'">'+fields+'<p class="muted">Ces réponses seront accessibles à Thierry pour préparer votre échange. Évitez les informations sensibles. Elles seront supprimées après 60 jours.</p><button>Transmettre mes réponses à Thierry</button></form>'))
  session=self.auth()
  if not session:
   if not SECRET or not PASSWORD:return self.page('<h1>Installation en cours.</h1><p>L’accès privé doit être configuré avant toute connexion.</p>',503)
   return self.page('<h1>Bonjour Thierry.</h1><p>Votre espace de suivi des entretiens.</p><form method="post" action="/login"><label>Mot de passe administrateur<input name="password" type="password" autocomplete="current-password" required></label><button>Ouvrir mon espace</button></form>')
  csrf=sign(session)
  if u.path=='/preview':
   uid=q.get('uid',[''])[0];kind=q.get('kind',[''])[0]
   if kind not in ('before','after'):raise ValueError('Type de message invalide.')
   b,a=booking(uid);subject,body=template(b,a,kind)
   if q.get('body')==['1']:return self.output(body)
   eligible(b,kind)
   return self.page(f'<a href="/">← Rendez-vous</a><h1>Vérifier avant d’envoyer.</h1><p>Destinataire : <strong>{esc(a["name"])} · {esc(a["email"])}</strong><br>Objet : {esc(subject)}</p><iframe title="Aperçu du message" sandbox src="/preview?uid={esc(uid)}&kind={kind}&body=1"></iframe><form method="post" action="/send"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="uid" value="{esc(uid)}"><input type="hidden" name="kind" value="{kind}"><label><input type="checkbox" name="confirm" required> Je vérifie le destinataire et je confirme cet envoi.</label>'+('<label><input type="checkbox" name="paid" required> J’ai vérifié dans Cal.com que le paiement est bien reçu.</label>' if kind=='before' else '<label><input type="checkbox" name="held" required> Cet entretien a bien eu lieu.</label>')+'<button>Confirmer et envoyer cet e-mail</button></form>')
  if u.path!='/':return self.page('<h1>Page introuvable</h1>',404)
  cursor=q.get('cursor',[''])[0]
  data,pagination=cal('bookings?take=50&eventTypeId=7609933&sortStart=desc'+('&cursor='+urllib.parse.quote(cursor,safe='') if cursor else ''))
  with db() as c:
   c.execute("DELETE FROM answers WHERE at < datetime('now','-60 days')");history={(r[0],r[1]):r[2] for r in c.execute('SELECT uid,kind,status FROM deliveries')};answers={r[0]:json.loads(r[1]) for r in c.execute('SELECT uid,payload FROM answers')}
  cards=''
  for b in data:
   if b.get('eventTypeId',b.get('eventType',{}).get('id'))!=EVENT_ID:continue
   a=(b.get('attendees') or [{}])[0];uid=b['uid'];cards+=f'<article><h2>{esc(a.get("name","Participant"))}</h2><p>{esc(datefr(b.get("start")))} → {esc(datefr(b.get("end")))}<br>{esc(a.get("email",""))} · {esc(b.get("status",""))}</p><div class="row">'
   for kind,title in [('before','Préparer l’e-mail avant l’appel'),('after','Préparer l’envoi du guide')]:cards+=f'<span class="tag">{esc(history[(uid,kind)])}</span>' if (uid,kind) in history else f'<a class="button" href="/preview?uid={esc(uid)}&kind={kind}">{title}</a>'
   cards+='</div>'
   if uid in answers:cards+='<h3>Réponses facultatives</h3>'+''.join('<p>'+esc(v).replace('\n','<br>')+'</p>' for v in answers[uid])
   cards+='</article>'
  self.page('<div class="row"><h1>Vos entretiens, votre rythme.</h1><form method="post" action="/logout"><input type="hidden" name="csrf" value="'+csrf+'"><button>Déconnexion</button></form></div><p class="notice">Mode manuel : aucun envoi automatique. Vous choisissez le rendez-vous, relisez le message et confirmez l’envoi. Le guide est proposé à partir d’une heure après la fin prévue.</p><a class="button" href="/gifts-admin">Cartes cadeaux et Mollie</a> <a class="button" href="/guides-admin">Ventes du guide</a> <a class="button" href="/reviews-admin">Avis reçus</a> <a class="button" href="/stats">📊 Pilotage et statistiques</a> <a class="button" href="/">Actualiser Cal.com</a>'+ (cards or '<article>Aucun rendez-vous de cette offre dans cette page.</article>')+ ('<a href="/?cursor='+esc(pagination['nextCursor'])+'">Page suivante</a>' if pagination.get('nextCursor') else ''))
 def do_POST(self):
  try:self.post()
  except Exception as e:self.page('<h1>Action non effectuée</h1><p>'+esc(str(e) if isinstance(e,ValueError) else 'Une erreur est survenue. Vérifiez l’état avant de recommencer.')+'</p><a href="/">Retour</a>',400)
 def analytics_event(self):
  origin=self.headers.get('Origin','')
  if origin not in ('https://votrezonedegenie.fr','https://www.votrezonedegenie.fr'):
   return self.output('Origine refusée',403)
  if int(self.headers.get('Content-Length','0'))>500:return self.output('Données trop volumineuses',413)
  from analytics import record
  f=self.form()
  try:record(f.get('event',''),f.get('path',''))
  except ValueError:return self.output('Événement invalide',400,{'Access-Control-Allow-Origin':origin})
  except Exception:return self.output('Collecte indisponible',503,{'Access-Control-Allow-Origin':origin})
  return self.output('ok',200,{'Access-Control-Allow-Origin':origin})
 def post(self):
  path=urllib.parse.urlsplit(self.path).path
  if path in ('/guide-checkout','/guide-webhook'):
   from guides import post
   try:return post(self,path)
   except Exception as e:
    if path=='/guide-webhook':return self.output('Réessayer',503)
    message=str(e) if isinstance(e,ValueError) else 'Le paiement n’a pas pu être préparé. Réessayez sans repayer, ou contactez Thierry.'
    return self.output('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Votre guide · Paiement</title><style>'+STYLE+'</style><main><h1>Revenons à votre guide.</h1><p>'+esc(message)+'</p><a class="button" href="https://votrezonedegenie.fr/guide/">Retour au guide</a><p><a href="mailto:thierry.garot@iroko-conseil.pro">Contacter Thierry</a></p></main></html>',400)
  if path in ('/gift-checkout','/gift-redeem','/mollie-webhook'):
   from gifts import post
   return post(self,path)
  if path=='/reviews-moderate':
   from reviews import moderate
   return moderate(self)
  if path=='/reviews-submit':
   from reviews import post
   return post(self)
  if path=='/analytics/event':return self.analytics_event()
  if self.headers.get('Origin')!=ORIGIN:raise ValueError('Origine de la requête refusée.')
  f=self.form()
  if path=='/login':
   if not SECRET or not PASSWORD:raise ValueError('Installation non terminée.')
   ip=self.client_address[0];n,until=FAILURES.get(ip,(0,0))
   if until>time.time():raise ValueError('Trop de tentatives. Patientez 15 minutes.')
   if not hmac.compare_digest(f.get('password',''),PASSWORD):FAILURES[ip]=(n+1,time.time()+900 if n>=4 else 0);raise ValueError('Connexion refusée.')
   FAILURES.pop(ip,None);s=str(int(time.time()))+'.'+secrets.token_hex(24);s+='.'+sign(s)
   return self.redirect('/',{'Set-Cookie':'zdg='+s+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=28800'})
  if path=='/questions':
   uid=checktoken(f.get('token',''))
   if not uid:raise ValueError('Lien invalide ou expiré.')
   answers=[f.get('q'+str(i),'')[:2000] for i in range(3)]
   with db() as c:c.execute('INSERT INTO answers VALUES(?,?,?) ON CONFLICT(uid) DO NOTHING',(uid,json.dumps(answers),datetime.now(timezone.utc).isoformat()))
   return self.page('<h1>Merci pour vos mots.</h1><p>Thierry pourra les lire avant votre échange. À bientôt, et venez comme vous êtes.</p>')
  s=self.auth()
  if not s or not hmac.compare_digest(sign(s),f.get('csrf','')):raise ValueError('Session expirée. Reconnectez-vous.')
  if path=='/logout':return self.redirect('/',{'Set-Cookie':'zdg=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0'})
  if path=='/send':
   kind=f.get('kind')
   if kind not in ('before','after') or not f.get('confirm') or (kind=='before' and not f.get('paid')) or (kind=='after' and not f.get('held')):raise ValueError('Confirmation nécessaire.')
   send(f.get('uid',''),kind);return self.redirect('/')
  raise ValueError('Action inconnue.')
if __name__=='__main__':
 Path(DB).parent.mkdir(parents=True,exist_ok=True)
 ThreadingHTTPServer(('0.0.0.0',int(E.get('PORT','8000'))),Handler).serve_forever()
