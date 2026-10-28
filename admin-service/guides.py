"""One-off guide sales. All entitlements verified server-side; no public PDF."""
import os, json, uuid, secrets, hashlib, hmac, time, re, base64
from pathlib import Path
from urllib.parse import urlencode
from neon_db import connection

SITE='https://votrezonedegenie.fr'
SKU='guide-5r-v1'
CONSENT='2026-10-28-guide-v1'
ORIGINS=(SITE,'https://www.votrezonedegenie.fr')

def sign(value):
    key=os.environ.get('SESSION_SECRET','')
    if len(key)<16: raise ValueError('Accès au guide non configuré.')
    return hmac.new(key.encode(),value.encode(),hashlib.sha256).hexdigest()

def access_url(oid):
    return SITE+'/guide/acces/#'+urlencode({'order':str(oid),'token':sign('guide:'+str(oid))})

def gift_url(uid):
    payload=base64.urlsafe_b64encode((str(uid)+'|'+str(int(time.time())+365*86400)).encode()).decode().rstrip('=')
    return SITE+'/guide/acces/#'+urlencode({'gift':payload+'.'+sign('guide-gift:'+payload)})

def check_gift(value):
    try:
        payload,sig=value.split('.')
        if not hmac.compare_digest(sig,sign('guide-gift:'+payload)): return False
        uid,until=base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)).decode().rsplit('|',1)
        return bool(uid) and time.time()<int(until)
    except (ValueError,UnicodeError):return False

def pdf_bytes():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw=Path(__file__).with_name('assets').joinpath('guide-5r.enc').read_bytes()
    key=base64.b64decode(os.environ['GUIDE_FILE_KEY'],validate=True)
    return AESGCM(key).decrypt(raw[:12],raw[12:],SKU.encode())

def ready():
    return (os.environ.get('GUIDE_SALES_ENABLED')=='true' and
      os.environ.get('GUIDE_STRIPE_KEY','').startswith(('rk_live_','sk_live_')) and
      bool(os.environ.get('GUIDE_STRIPE_PRICE_ID')) and bool(os.environ.get('GUIDE_STRIPE_WEBHOOK_SECRET')) and bool(os.environ.get('GUIDE_FILE_KEY')) and
      all(os.environ.get(x) for x in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','MAIL_FROM')) and
      os.environ.get('GUIDE_TERMS_READY')=='true')

def client():
    from stripe import StripeClient
    return StripeClient(os.environ['GUIDE_STRIPE_KEY'],stripe_version='2026-08-26.dahlia',max_network_retries=2)

def status_of(s,oid,sid):
    if (s.get('id')!=sid or s.get('metadata',{}).get('guide_order')!=str(oid) or
        s.get('metadata',{}).get('sku')!=SKU or s.get('mode')!='payment' or
        s.get('currency')!='eur' or s.get('amount_total')!=1500 or s.get('livemode') is not True):
        raise ValueError('Ce paiement ne correspond pas à cette commande.')
    pi=s.get('payment_intent') or {}
    charge=pi.get('latest_charge') or {} if hasattr(pi,'get') else {}
    if hasattr(charge,'get') and (charge.get('amount_refunded',0)>0 or charge.get('disputed')):return 'revoked'
    return 'paid' if s.get('payment_status')=='paid' else ('expired' if s.get('status')=='expired' else 'pending')

def refresh(oid):
    with connection() as c:row=c.execute('SELECT stripe_session_id,status FROM guide_orders WHERE id=%s',(oid,)).fetchone()
    if not row or not row[0]:return 'pending'
    if row[1]=='revoked':return 'revoked'
    s=client().v1.checkout.sessions.retrieve(row[0],{'expand':['payment_intent.latest_charge']})
    status=status_of(s,oid,row[0])
    pi=s.get('payment_intent');pid=pi.get('id') if hasattr(pi,'get') else pi
    email=(s.get('customer_details') or {}).get('email') or ''
    with connection() as c:
        c.execute("UPDATE guide_orders SET status=%s,payment_intent_id=%s,buyer_email=CASE WHEN %s<>'' THEN %s ELSE buyer_email END,paid_at=CASE WHEN %s='paid' THEN COALESCE(paid_at,now()) ELSE paid_at END WHERE id=%s AND status<>'revoked'",(status,pid,email,email,status,oid))
    if status=='paid':email_receipt(oid)
    return status

def email_receipt(oid):
    """Reserve exactly once before SMTP; uncertain deliveries require manual review."""
    import smtplib,ssl
    from email.message import EmailMessage
    with connection() as c:
        row=c.execute("UPDATE guide_orders SET email_status='sending' WHERE id=%s AND status='paid' AND email_status='pending' AND buyer_email<>'' RETURNING buyer_email",(oid,)).fetchone()
    if not row:return
    try:
        msg=EmailMessage();msg['From']='Thierry · Votre Zone de Génie <'+os.environ['MAIL_FROM']+'>';msg['To']=row[0]
        msg['Subject']='Votre guide Les 5 R est prêt';msg['Reply-To']=os.environ['MAIL_FROM']
        msg['Message-ID']='<guide-'+str(oid)+'@votrezonedegenie.fr>'
        msg.set_content('Bonjour,\n\nVotre achat du guide Le temps de laisser mûrir — Les 5 R est confirmé. Montant total payé : 15 €.\nRéférence : '+str(oid)+'\n\nVotre accès personnel : '+access_url(oid)+'\n\nVous avez demandé la fourniture immédiate du contenu numérique et reconnu la perte de votre droit de rétractation dès le début de cette fourniture. Les conditions acceptées sont jointes à ce message.\n\nBonne découverte,\nThierry Garot\nIROKO SAS, 60 rue François 1er, 75008 Paris, SIREN 945 241 156.\nContact : thierry.garot@iroko-conseil.pro')
        terms=Path(__file__).with_name('guide-conditions.txt').read_bytes()
        msg.add_attachment(terms,maintype='text',subtype='plain',filename='Conditions-achat-guide.txt')
        with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.environ.get('SMTP_PORT','465')),timeout=30,context=ssl.create_default_context()) as smtp:
            smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);smtp.send_message(msg)
        result='sent'
    except Exception:result='uncertain'
    with connection() as c:c.execute('UPDATE guide_orders SET email_status=%s WHERE id=%s',(result,oid))

def respond(h,data,status=200):
    origin=h.headers.get('Origin','')
    h.send_response(status)
    for k,v in {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',**({'Access-Control-Allow-Origin':origin,'Vary':'Origin'} if origin in ORIGINS else {})}.items():h.send_header(k,v)
    h.end_headers();h.wfile.write(json.dumps(data).encode())

def authorize(q):
    gift=q.get('gift',[''])[0]
    if gift:
        if not check_gift(gift):raise ValueError('Ce lien cadeau est invalide ou expiré.')
        return 'gift',None
    try:oid=uuid.UUID(q.get('order',[''])[0])
    except ValueError:raise ValueError('Lien d’accès invalide.') from None
    if not hmac.compare_digest(sign('guide:'+str(oid)),q.get('token',[''])[0]):raise ValueError('Lien d’accès invalide.')
    return refresh(oid),oid

def get(h,u,q):
    if u.path=='/guide-config':
        nonce=secrets.token_urlsafe(24)+'.'+str(int(time.time()))
        return respond(h,{'available':ready(),'nonce':nonce+'.'+sign('checkout:'+nonce)})
    if u.path in ('/guide-access','/guide.pdf'):
        try:status,oid=authorize(q)
        except ValueError as e:return respond(h,{'error':str(e)},403)
        except Exception:return respond(h,{'error':'Vérification momentanément indisponible. Réessayez sans repayer.'},503)
        if u.path=='/guide-access':return respond(h,{'status':status,'reference':str(oid) if oid else None})
        if status not in ('paid','gift'):return respond(h,{'error':'Le paiement n’est pas confirmé.'},403)
        try:data=pdf_bytes()
        except Exception:return respond(h,{'error':'Téléchargement momentanément indisponible. Contactez Thierry avec votre référence.'},503)
        h.send_response(200)
        for k,v in {'Content-Type':'application/pdf','Content-Disposition':'attachment; filename="Le-temps-de-laisser-murir-Les-5R.pdf"','Content-Length':str(len(data)),'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex','X-Content-Type-Options':'nosniff'}.items():h.send_header(k,v)
        h.end_headers();h.wfile.write(data);return
    if u.path=='/guides-admin':
        if not h.auth():return h.redirect('/')
        from html import escape
        with connection() as c:rows=c.execute('SELECT id,buyer_email,status,email_status,created_at FROM guide_orders ORDER BY created_at DESC LIMIT 100').fetchall()
        body='<a href="/">← Administration</a><h1>Ventes du guide</h1><p>Ventes '+('ouvertes' if ready() else 'fermées — configuration à terminer')+'</p>'
        for oid,email,status,mail,created in rows:
            body+='<article><p>'+escape(str(created))+' · '+escape(email or '')+'</p><p>'+escape(status)+' · e-mail : '+escape(mail)+'</p>'
            if status=='paid':body+='<a href="'+escape(access_url(oid))+'">Ouvrir le lien personnel</a>'
            body+='</article>'
        return h.page(body)

def validate_nonce(value):
    try:
        nonce,stamp,sig=value.split('.')
        return len(nonce)>=24 and 0<=time.time()-int(stamp)<3600 and hmac.compare_digest(sig,sign('checkout:'+nonce+'.'+stamp))
    except (ValueError,TypeError):return False

def post(h,path):
    if path=='/guide-webhook':
        import stripe
        n=int(h.headers.get('Content-Length','0'))
        if not 0<n<=1000000:return respond(h,{},413)
        payload=h.rfile.read(n)
        try:event=stripe.Webhook.construct_event(payload,h.headers.get('Stripe-Signature',''),os.environ['GUIDE_STRIPE_WEBHOOK_SECRET'])
        except Exception:return respond(h,{},400)
        if event.get('livemode') is not True:return respond(h,{},400)
        obj=event['data']['object'];kind=event['type']
        try:
            if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed'):
                if obj.get('metadata',{}).get('sku')==SKU:
                    oid=uuid.UUID(obj['metadata']['guide_order'])
                    with connection() as c:row=c.execute('SELECT stripe_session_id FROM guide_orders WHERE id=%s',(oid,)).fetchone()
                    if not row or row[0]!=obj['id']:return respond(h,{},400)
                    refresh(oid)
            elif kind in ('charge.refunded','charge.dispute.created'):
                pi=obj.get('payment_intent')
                if pi:
                    with connection() as c:c.execute("UPDATE guide_orders SET status='revoked' WHERE payment_intent_id=%s",(pi,))
        except Exception:return respond(h,{},503)
        return respond(h,{'received':True})
    if path!='/guide-checkout':return False
    if h.headers.get('Origin') not in ORIGINS:raise ValueError('Origine refusée.')
    if not ready():raise ValueError('Les ventes ne sont pas encore ouvertes. Aucun paiement effectué.')
    f=h.form()
    if not validate_nonce(f.get('nonce','')):raise ValueError('Rechargez la page avant de continuer.')
    if f.get('terms')!='yes' or f.get('immediate')!='yes':raise ValueError('Votre accord est nécessaire pour le téléchargement immédiat.')
    oid=uuid.uuid5(uuid.NAMESPACE_URL,'guide:'+f['nonce'])
    with connection() as c:c.execute('INSERT INTO guide_orders(id,consent_version) VALUES(%s,%s) ON CONFLICT(id) DO NOTHING',(oid,CONSENT))
    with connection() as c:
        row=c.execute('SELECT stripe_session_id FROM guide_orders WHERE id=%s FOR UPDATE',(oid,)).fetchone()
        if row and row[0]:
            s=client().v1.checkout.sessions.retrieve(row[0])
            return h.redirect(s['url'] if s.get('status')=='open' and s.get('url','').startswith('https://checkout.stripe.com/') else access_url(oid))
        s=client().v1.checkout.sessions.create({'mode':'payment','locale':'fr','line_items':[{'price':os.environ['GUIDE_STRIPE_PRICE_ID'],'quantity':1}],
          'success_url':access_url(oid),'cancel_url':SITE+'/guide/?paiement=annule',
          'metadata':{'guide_order':str(oid),'sku':SKU,'consent_version':CONSENT,'immediate_delivery':'accepted'},
          'payment_intent_data':{'metadata':{'guide_order':str(oid),'sku':SKU}},
          'branding_settings':{'display_name':'Votre Zone de Génie'},
          'integration_identifier':'guide_5r_jqmzvnta'},options={'idempotency_key':'guide-'+str(oid)})
        if not s.get('url','').startswith('https://checkout.stripe.com/'):raise ValueError('Le paiement n’a pas pu être préparé.')
        c.execute('UPDATE guide_orders SET stripe_session_id=%s WHERE id=%s',(s['id'],oid))
    return h.redirect(s['url'])
