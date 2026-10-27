"""Gift checkout. Closed by default; payment state is always verified with Mollie."""
import os, json, uuid, secrets, hashlib, hmac, re, html, io
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from neon_db import connection

def esc(s): return html.escape(str(s), quote=True)
def secret():
    value=os.environ.get('GIFT_SECRET','')
    if len(value)<32: raise ValueError('Configuration des cartes cadeaux incomplète.')
    return value.encode()
def signed(label, oid): return hmac.new(secret(), (label+str(oid)).encode(), hashlib.sha256).hexdigest()
def code(oid): return 'VZG-'+signed('card:',oid)[:24].upper()
def token(oid): return signed('download:',oid)
def origin():
    value=os.environ.get('PUBLIC_ORIGIN','').rstrip('/')
    if not value.startswith('https://'): raise ValueError('Adresse de retour non configurée.')
    return value

def api(path, body=None, idem=None):
    key=os.environ.get('MOLLIE_API_KEY','')
    if not key.startswith(('live_','test_')): raise ValueError('Connexion Mollie à configurer.')
    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
    if idem: headers['Idempotency-Key']=idem
    req=Request('https://api.mollie.com/v2/'+path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(req,timeout=20) as r: return json.load(r)
    except Exception: raise ValueError('Mollie ne répond pas ou refuse la connexion. Aucun paiement confirmé.') from None

def enabled():
    return os.environ.get('GIFT_SALES_ENABLED')=='true' and os.environ.get('MOLLIE_API_KEY','').startswith('live_') and len(os.environ.get('GIFT_SECRET',''))>=32

def verified_status(payment, oid, pid):
    if payment.get('id')!=pid or payment.get('metadata',{}).get('gift_order')!=str(oid): raise ValueError('Référence de paiement incohérente.')
    if payment.get('mode')!='live' or payment.get('amount')!={'currency':'EUR','value':'90.00'}: raise ValueError('Montant ou mode de paiement incohérent.')
    if any(Decimal(payment.get(k,{}).get('value','0'))>0 for k in ('amountRefunded','amountChargedBack')): return 'refunded'
    status=payment.get('status')
    return status if status in ('paid','failed','canceled','expired') else 'pending'

def refresh(oid):
    with connection() as conn:
        row=conn.execute('SELECT mollie_payment_id FROM gift_orders WHERE id=%s',(oid,)).fetchone()
    if not row or not row[0]: raise ValueError('Paiement en cours de préparation. Réessayez dans quelques instants.')
    pid=row[0]; payment=api('payments/'+pid)
    status=verified_status(payment,oid,pid)
    with connection() as conn:
        conn.execute('SELECT id FROM gift_orders WHERE id=%s FOR UPDATE',(oid,)).fetchone()
        conn.execute("UPDATE gift_orders SET status=%s,paid_at=CASE WHEN %s='paid' THEN COALESCE(paid_at,now()) ELSE paid_at END WHERE id=%s",(status,status,oid))
        if status=='paid':
            conn.execute('INSERT INTO gift_cards(id,order_id,code_hash) VALUES(%s,%s,%s) ON CONFLICT(order_id) DO NOTHING',(uuid.uuid4(),oid,hashlib.sha256(code(oid).encode()).hexdigest()))
        elif status=='refunded':
            conn.execute("UPDATE gift_cards SET status='revoked',redeemed_at=NULL WHERE order_id=%s",(oid,))
    return status

def pdf(oid):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    from pathlib import Path
    fonts=Path(reportlab.__file__).parent/'fonts'
    if 'GiftRegular' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('GiftRegular',str(fonts/'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('GiftBold',str(fonts/'VeraBd.ttf')))
    data=io.BytesIO(); c=canvas.Canvas(data,pagesize=(595,420))
    c.setTitle('Votre Zone de Génie — Carte cadeau')
    c.setFillColor(HexColor('#111F36'));c.rect(0,0,595,420,fill=1,stroke=0)
    c.setStrokeColor(HexColor('#F4B436'));c.setLineWidth(1);c.roundRect(22,22,551,376,16)
    c.setFillColor(HexColor('#7ED9C3'));c.setFont('GiftBold',11);c.drawString(46,365,'VOTRE ZONE DE GÉNIE  /  CARTE CADEAU')
    c.setFillColor(HexColor('#F4B436'));c.setFont('Times-Bold',29);c.drawString(46,308,'Un nouveau regard sur vous.')
    c.setFillColor(HexColor('#FFFFFF'));c.setFont('GiftRegular',13)
    for y,line in [(270,'30 minutes par téléphone avec Thierry Garot.'),(246,'Un temps pour explorer une force que vous banalisez.'),(204,'Pour : ........................................................................'),(177,'De la part de : ..............................................................')]:c.drawString(46,y,line)
    c.setFont('GiftRegular',11);c.drawString(46,134,'Pour fixer votre échange, écrivez à :')
    c.setFont('GiftBold',13);c.drawString(46,114,'thierry@votrezonedegenie.fr')
    c.setFont('GiftRegular',10);c.drawString(46,81,'Votre référence : '+code(oid))
    c.drawString(46,61,'Une séance déjà réglée. Référence à communiquer et valable pour une utilisation.')
    c.save();return data.getvalue()

def page(h,title,body,status=200):
    return h.output('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>body{background:#111F36;color:#fff;font:17px/1.7 system-ui;margin:0}main{max-width:650px;margin:6vh auto;padding:28px}h1{color:#F4B436;font-size:36px;line-height:1.2}a{color:#7ED9C3}button,.button{display:inline-block;background:#F4B436;color:#111F36;padding:14px 24px;border:0;border-radius:10px;text-decoration:none;font:700 17px system-ui}input{padding:14px;width:90%;font:inherit;border-radius:8px}label{display:block;margin:20px 0}small{color:#D9D2E9}</style><main><p>VOTRE ZONE DE GÉNIE</p><h1>'+esc(title)+'</h1>'+body+'</main></html>',status)

def get(h,u,q):
    if u.path=='/gift-status':
        return h.output(json.dumps({'sales_open':enabled()}),200)
    if u.path=='/cadeau':
        if not enabled(): return page(h,'Les cartes cadeaux arrivent bientôt.','<p>Les achats ne sont pas encore ouverts. Aucun paiement ne vous est demandé.</p><a href="https://votrezonedegenie.fr/cadeau/">Retour au site</a>',503)
        nonce=secrets.token_urlsafe(32)
        h._gift_cookie=nonce
        # A cookie bound to the form prevents cross-site checkout creation.
        body='<p>Offrez un entretien téléphonique de 30 minutes avec Thierry.</p><p><strong>90 € TTC</strong> · Carte imprimable après paiement confirmé.</p><form method="post" action="/gift-checkout"><input type="hidden" name="nonce" value="'+nonce+'"><label>Votre adresse e-mail<input type="email" name="email" required maxlength="254" autocomplete="email"></label><p>Après paiement, téléchargez votre carte et conservez son lien. Le bénéficiaire contactera Thierry pour choisir son rendez-vous.</p><button>Payer 90 € avec Mollie</button></form><p><a href="https://votrezonedegenie.fr/mentions-legales.html">Informations et contact</a></p>'
        original=h.output
        def output(content,status=200,headers=None):return original(content,status,{**(headers or {}),'Set-Cookie':'gift_checkout='+nonce+'; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=3600'})
        h.output=output
        return page(h,'Une attention qui a du sens.',body)
    if u.path in ('/gift-return','/gift.pdf'):
        try: oid=uuid.UUID(q.get('order',[''])[0])
        except ValueError: raise ValueError('Lien de carte invalide.')
        if not hmac.compare_digest(token(oid),q.get('token',[''])[0]): raise ValueError('Lien de carte invalide.')
        status=refresh(oid)
        if status!='paid': return page(h,'Votre paiement : '+{'pending':'en attente','failed':'échoué','canceled':'annulé','expired':'expiré','refunded':'remboursé ou contesté'}.get(status,status),'<p>Aucune carte utilisable ne peut être remise pour le moment.</p><a href="'+esc(h.path)+'">Vérifier à nouveau</a>')
        with connection() as conn: card=conn.execute('SELECT status FROM gift_cards WHERE order_id=%s',(oid,)).fetchone()
        if not card or card[0]!='active': return page(h,'Cette carte n’est plus disponible.','<p>Elle a déjà été utilisée ou désactivée. Contactez Thierry si nécessaire.</p>',409)
        if u.path=='/gift.pdf':
            data=pdf(oid);h.send_response(200)
            for k,v in {'Content-Type':'application/pdf','Content-Disposition':'attachment; filename="Carte-cadeau-Votre-Zone-de-Genie.pdf"','Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Length':str(len(data))}.items():h.send_header(k,v)
            h.end_headers();h.wfile.write(data);return
        url='/gift.pdf?'+urlencode({'order':str(oid),'token':token(oid)})
        return page(h,'Merci pour votre confiance.','<p>Votre paiement de 90 € est confirmé. Votre cadeau est prêt.</p><a class="button" href="'+esc(url)+'">Télécharger ma carte cadeau</a><p>Imprimez-la, complétez les prénoms et offrez-la. Le bénéficiaire pourra contacter Thierry avec sa référence pour fixer son entretien.</p><small>Conservez cette page dans vos favoris pour retrouver votre carte. Aucun e-mail automatique n’est envoyé pour le moment.</small>')
    if u.path=='/gifts-admin':
        if not h.auth():return h.redirect('/')
        checks={'Clé Mollie':('mode réel' if os.environ.get('MOLLIE_API_KEY','').startswith('live_') else 'test ou absente'),'Secret des cartes':('présent' if len(os.environ.get('GIFT_SECRET',''))>=32 else 'à configurer'),'Ventes':('ouvertes' if enabled() else 'fermées')}
        try:
            methods=api('methods?amount[value]=90.00&amount[currency]=EUR').get('_embedded',{}).get('methods',[])
            checks['Mollie accessible']=str(len(methods))+' moyen(s) de paiement disponible(s)'
        except ValueError as e:checks['Mollie accessible']=str(e)
        try:
            with connection() as conn:rows=conn.execute('SELECT o.id,o.buyer_email,o.status,c.status FROM gift_orders o LEFT JOIN gift_cards c ON c.order_id=o.id ORDER BY o.created_at DESC LIMIT 100').fetchall()
            checks['Neon']='connecté'
        except Exception:rows=[];checks['Neon']='connexion à vérifier'
        body='<a href="/">← Administration</a>'+''.join('<p><strong>'+esc(k)+'</strong> : '+esc(v)+'</p>' for k,v in checks.items())
        for oid,email,status,card in rows:
            body+='<hr><p>'+esc(email)+' · '+esc(status)+' · carte '+esc(card or 'non émise')+'</p>'
            if card=='active' and status=='paid':body+='<p>Référence : '+code(oid)+'</p><form method="post" action="/gift-redeem"><input type="hidden" name="csrf" value="'+hmac.new(os.environ['SESSION_SECRET'].encode(),h.auth().encode(),hashlib.sha256).hexdigest()+'"><input type="hidden" name="order" value="'+str(oid)+'"><label><input style="width:auto" type="checkbox" required name="confirm"> Je confirme que cet entretien a eu lieu.</label><button>Marquer la carte utilisée</button></form>'
        return page(h,'Cartes cadeaux et connexion Mollie',body)
    return False

def post(h,path):
    if path=='/mollie-webhook':
        f=h.form();pid=f.get('id','')
        if not re.fullmatch(r'tr_[A-Za-z0-9]+',pid):return h.output('Invalid ID',400)
        try:
            with connection() as conn:row=conn.execute('SELECT id FROM gift_orders WHERE mollie_payment_id=%s',(pid,)).fetchone()
            if row:refresh(row[0])
        except Exception:return h.output('Retry later',503)
        return h.output('ok')
    if path not in ('/gift-checkout','/gift-redeem'): return False
    if h.headers.get('Origin')!=origin():raise ValueError('Origine refusée.')
    f=h.form()
    if path=='/gift-redeem':
        session=h.auth()
        expected=hmac.new(os.environ.get('SESSION_SECRET','').encode(),(session or '').encode(),hashlib.sha256).hexdigest()
        if not session or not hmac.compare_digest(expected,f.get('csrf','')) or not f.get('confirm'):raise ValueError('Confirmation administrateur nécessaire.')
        oid=uuid.UUID(f.get('order',''))
        if refresh(oid)!='paid':raise ValueError('Paiement non confirmé.')
        with connection() as conn:
            conn.execute('SELECT id FROM gift_orders WHERE id=%s FOR UPDATE',(oid,))
            conn.execute("UPDATE gift_cards SET status='redeemed',redeemed_at=now() WHERE order_id=%s AND status='active' AND EXISTS(SELECT 1 FROM gift_orders WHERE id=%s AND status='paid')",(oid,oid))
        return h.redirect('/gifts-admin')
    if not enabled():raise ValueError('Les achats ne sont pas encore ouverts.')
    nonce=f.get('nonce','');cookie=next((p.strip().split('=',1)[1] for p in h.headers.get('Cookie','').split(';') if p.strip().startswith('gift_checkout=')),'')
    if len(nonce)<32 or not hmac.compare_digest(nonce,cookie):raise ValueError('Formulaire expiré. Rechargez la page.')
    email=f.get('email','').strip()
    if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Adresse e-mail invalide.')
    oid=uuid.uuid5(uuid.NAMESPACE_URL,nonce)
    # Serialize repeated submissions for this order. Mollie idempotency handles uncertain responses.
    with connection() as conn:
        conn.execute('INSERT INTO gift_orders(id,buyer_email) VALUES(%s,%s) ON CONFLICT(id) DO NOTHING',(oid,email))
    with connection() as conn:
        existing=conn.execute('SELECT mollie_payment_id FROM gift_orders WHERE id=%s FOR UPDATE',(oid,)).fetchone()
        if existing and existing[0]:
            return h.redirect('/gift-return?'+urlencode({'order':str(oid),'token':token(oid)}))
        payment=api('payments',{'amount':{'currency':'EUR','value':'90.00'},'description':'Carte cadeau Votre Zone de Génie — 30 minutes','redirectUrl':origin()+'/gift-return?'+urlencode({'order':str(oid),'token':token(oid)}),'webhookUrl':origin()+'/mollie-webhook','metadata':{'gift_order':str(oid)},'locale':'fr_FR'},str(oid))
        pid=payment.get('id','');checkout=payment.get('_links',{}).get('checkout',{}).get('href','')
        if not re.fullmatch(r'tr_[A-Za-z0-9]+',pid) or not checkout.startswith('https://www.mollie.com/'):raise ValueError('Réponse Mollie inattendue.')
        conn.execute('UPDATE gift_orders SET mollie_payment_id=%s WHERE id=%s',(pid,oid))
    return h.redirect(checkout)
