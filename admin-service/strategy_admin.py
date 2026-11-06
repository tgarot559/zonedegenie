"""Protected strategy sales cockpit backed by the existing Neon database.

All entry points must be called only after Handler.auth() and CSRF verification.
No browser-accessible client API or unauthenticated data endpoint is exported.
"""
import html
from decimal import Decimal, InvalidOperation
from datetime import datetime
from neon_db import connection

PRIVATE_PATH = "/pilotage-2fb1c941fae6e5e95b0203d4"
OFFERS = {
    "mentorat-declic-3h": ("Mentorat Déclic · 3 h", 180),
    "mentorat-elan-5h": ("Mentorat Élan · 5 h", 300),
    "mentorat-trajectoire-10h": ("Mentorat Trajectoire · 10 h", 600),
    "partenaire-strategique": ("Partenariat stratégique mensuel", 240),
    "codir": ("Intervention CODIR", 0),
}
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS strategy_clients (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL DEFAULT '',
        offer TEXT NOT NULL,
        minutes_total INTEGER NOT NULL CHECK(minutes_total >= 0),
        payment_reference TEXT NOT NULL DEFAULT '',
        payment_status TEXT NOT NULL DEFAULT 'à vérifier',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS strategy_sessions (
        id BIGSERIAL PRIMARY KEY,
        client_id BIGINT NOT NULL REFERENCES strategy_clients(id),
        held_at DATE NOT NULL,
        minutes_used INTEGER NOT NULL CHECK(minutes_used > 0),
        note TEXT NOT NULL DEFAULT '',
        actions TEXT NOT NULL DEFAULT '',
        consent_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
)

def esc(v):
    return html.escape(str(v or ""), quote=True)

def prepare(cursor):
    for statement in SCHEMA:
        cursor.execute(statement)

def _integer(value, minimum=0, maximum=100000):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError("Nombre invalide.")
    if not minimum <= n <= maximum:
        raise ValueError("Nombre hors limites.")
    return n

def _card(title, value, caption):
    return ('<div class="stat"><small>'+esc(title)+'</small><strong>'+esc(value)+
            '</strong><span>'+esc(caption)+'</span></div>')

def render(csrf):
    with connection() as conn:
        with conn.cursor() as cur:
            prepare(cur)
            cur.execute("""SELECT c.id,c.name,c.email,c.offer,c.minutes_total,c.payment_status,
                            c.payment_reference,COALESCE(SUM(s.minutes_used),0)
                        FROM strategy_clients c LEFT JOIN strategy_sessions s ON s.client_id=c.id
                        GROUP BY c.id ORDER BY c.created_at DESC LIMIT 200""")
            clients = cur.fetchall()
            cur.execute("""SELECT s.client_id,c.name,s.held_at,s.minutes_used,s.note,s.actions
                        FROM strategy_sessions s JOIN strategy_clients c ON c.id=s.client_id
                        ORDER BY s.held_at DESC,s.id DESC LIMIT 30""")
            sessions = cur.fetchall()
            cur.execute("""CREATE TABLE IF NOT EXISTS analytics_daily
                         (day DATE NOT NULL,event TEXT NOT NULL,count BIGINT NOT NULL DEFAULT 0,
                         PRIMARY KEY(day,event),CHECK(count>=0))""")
            cur.execute("""SELECT event,SUM(count) FROM analytics_daily
                         WHERE day >= (now() AT TIME ZONE 'Europe/Paris')::date - 29
                         AND event LIKE 'strategy_%' GROUP BY event""")
            signals = dict(cur.fetchall())
    cards = ''.join([
        _card("Pages Stratégie vues", signals.get("strategy_page",0), "Vues et non visiteurs uniques · 30 jours"),
        _card("Clics vers échanges gratuits", signals.get("strategy_click_free",0), "Départs vers Cal.com"),
        _card("Clics vers mentorat", signals.get("strategy_click_mentorat",0), "Intention de réservation"),
        _card("Clics CODIR / partenariat", signals.get("strategy_click_b2b",0), "Demandes de cadrage"),
        _card("Clients suivis", len(clients), "Saisie manuelle, pas une synchronisation de paiement"),
        _card("Minutes de séances saisies", sum(row[7] for row in clients), "Consommation confirmée manuellement")
    ])
    lines = ""
    for cid,name,email,offer,total,status,reference,used in clients:
        remaining=max(total-used,0)
        lines += ('<tr><td>'+esc(name)+'<br><small>'+esc(email)+'</small></td><td>'+esc(OFFERS.get(offer,(offer,))[0])+
                  '</td><td>'+esc(status)+'<br><small>'+esc(reference)+'</small></td><td>'+esc(used)+' / '+esc(total)+
                  ' min<br><strong>'+esc(remaining)+' min restantes</strong></td><td>'+
                  '<form method="post" action="/strategy/session"><input type="hidden" name="csrf" value="'+esc(csrf)+'">'+
                  '<input type="hidden" name="client_id" value="'+esc(cid)+'">'+
                  '<input type="date" name="held_at" required aria-label="Date de séance">'+
                  '<input type="number" name="minutes" min="1" max="600" placeholder="Minutes" required>'+
                  '<textarea name="note" maxlength="3000" rows="2" placeholder="Compte rendu validé"></textarea>'+
                  '<textarea name="actions" maxlength="1500" rows="2" placeholder="Prochaines actions"></textarea>'+
                  '<label><input type="checkbox" name="consent" required> Participants informés du traitement des notes</label>'+
                  '<button>Enregistrer la séance</button></form></td></tr>')
    if not lines:
        lines='<tr><td colspan="5">Aucun client enregistré. Commencer par un forfait dont le paiement a été vérifié.</td></tr>'
    history=''.join('<tr><td>'+esc(name)+'</td><td>'+esc(day)+'</td><td>'+esc(minutes)+' min</td><td>'+esc(note)+'</td><td>'+esc(actions)+'</td></tr>' for cid,name,day,minutes,note,actions in sessions)
    options=''.join('<option value="'+esc(slug)+'">'+esc(label)+'</option>' for slug,(label,_) in OFFERS.items())
    return """<style>
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
    .stat{background:white;border:1px solid #d9e4f4;border-radius:14px;padding:18px;display:flex;flex-direction:column}
    .stat strong{font-size:30px;color:#092756}.stat span,.stat small{font-size:12px;color:#536881}
    .table-scroll{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:14px;border-bottom:1px solid #dce6f2;text-align:left;vertical-align:top;min-width:120px}
    td form{min-width:230px}td form input,td form textarea{margin:6px 0}input[type=checkbox]{width:auto}
    .warning{background:#fff4e9;border-left:4px solid #fa5a0a;padding:18px}.wide{max-width:720px}
    </style>
    <a href="/">← Administration générale</a> · <a href="/stats">Statistiques historiques</a>
    <h1>Pilotage · Stratégie & mentorat</h1>
    <p class="warning">Espace privé. Les clics sont des intentions, pas des réservations ni des paiements. Les clients et les heures sont enregistrés manuellement après vérification. Ne jamais enregistrer de données sensibles non nécessaires.</p>
    <div class="stats">"""+cards+"""</div>
    <article class="wide"><h2>Ajouter un client / forfait</h2>
      <form method="post" action="/strategy/client">
      <input type="hidden" name="csrf" value=""""+esc(csrf)+"""">
      <label>Nom du client<input name="name" maxlength="140" required></label>
      <label>Email professionnel (facultatif)<input name="email" type="email" maxlength="200"></label>
      <label>Offre<select name="offer">"""+options+"""</select></label>
      <label>Minutes contractualisées (0 = CODIR sur devis)<input type="number" name="minutes_total" min="0" max="100000" placeholder="180, 300, 600..." required></label>
      <label>Statut de paiement<select name="payment_status"><option value="à vérifier">À vérifier</option><option value="vérifié manuellement">Vérifié manuellement</option><option value="devis accepté">Devis accepté</option></select></label>
      <label>Référence facture / réservation<input name="payment_reference" maxlength="150"></label>
      <button>Enregistrer le client</button></form></article>
    <article><h2>Forfaits et heures restantes</h2><div class="table-scroll"><table><thead><tr><th>Client</th><th>Offre</th><th>Paiement</th><th>Consommation</th><th>Ajouter une séance</th></tr></thead><tbody>"""+lines+"""</tbody></table></div></article>
    <article><h2>Derniers comptes rendus</h2><div class="table-scroll"><table><thead><tr><th>Client</th><th>Date</th><th>Durée</th><th>Résumé</th><th>Actions</th></tr></thead><tbody>"""+(history or '<tr><td colspan="5">Aucune séance consignée.</td></tr>')+"""</tbody></table></div></article>
    <article><h2>Assistant IA · Préparation</h2><p>Le module de transcription automatique n'est pas encore activé : la création de la clé OpenAI a été refusée par le fournisseur. En attendant, les comptes rendus peuvent être saisis et validés dans les fiches clients, après information des participants. Aucun audio n'est enregistré ici.</p></article>"""

def act(path, fields):
    if path == "/strategy/client":
        name=fields.get("name","").strip()[:140]
        if len(name)<2:raise ValueError("Nom requis.")
        offer=fields.get("offer","")
        if offer not in OFFERS:raise ValueError("Offre invalide.")
        minutes=_integer(fields.get("minutes_total"),0)
        status=fields.get("payment_status","")
        if status not in ("à vérifier","vérifié manuellement","devis accepté"):raise ValueError("Statut invalide.")
        with connection() as conn:
            with conn.cursor() as cur:
                prepare(cur)
                cur.execute("""INSERT INTO strategy_clients
                (name,email,offer,minutes_total,payment_status,payment_reference)
                VALUES (%s,%s,%s,%s,%s,%s)""",(name,fields.get("email","").strip()[:200],offer,minutes,status,fields.get("payment_reference","")[:150]))
        return
    if path == "/strategy/session":
        cid=_integer(fields.get("client_id"),1)
        minutes=_integer(fields.get("minutes"),1,600)
        try:
            day=datetime.strptime(fields.get("held_at",""),"%Y-%m-%d").date()
        except ValueError:raise ValueError("Date invalide.")
        if fields.get("consent")!="on":raise ValueError("Information des participants à confirmer.")
        with connection() as conn:
            with conn.cursor() as cur:
                prepare(cur)
                cur.execute("SELECT minutes_total FROM strategy_clients WHERE id=%s FOR UPDATE",(cid,))
                result=cur.fetchone()
                if not result:raise ValueError("Client introuvable.")
                cur.execute("SELECT COALESCE(SUM(minutes_used),0) FROM strategy_sessions WHERE client_id=%s",(cid,))
                used=cur.fetchone()[0]
                if result[0] and used+minutes>result[0]:
                    raise ValueError("Durée supérieure aux heures restantes. Ajuster le contrat avant saisie.")
                cur.execute("""INSERT INTO strategy_sessions
                (client_id,held_at,minutes_used,note,actions,consent_confirmed)
                VALUES (%s,%s,%s,%s,%s,TRUE)""",(cid,day,minutes,fields.get("note","")[:3000],fields.get("actions","")[:1500]))
        return
    raise ValueError("Action inconnue.")
