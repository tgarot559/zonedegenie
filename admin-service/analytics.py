"""Statistiques agrégées, sans cookie ni identifiant de visiteur."""
import os, html
from datetime import datetime, timezone, timedelta
import psycopg

EVENTS = {"page_home", "page_cadeau", "click_reserver", "click_cadeau", "click_interet_cadeau"}
ALLOWED_PATHS = {"/", "/cadeau/", "/cadeau"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_daily (
 day DATE NOT NULL,
 event TEXT NOT NULL,
 count BIGINT NOT NULL DEFAULT 0,
 PRIMARY KEY (day,event),
 CHECK (count >= 0)
);
"""
def record(event, path):
    if event not in EVENTS or path not in ALLOWED_PATHS:
        raise ValueError("Événement non autorisé.")
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)
            cursor.execute("""
                INSERT INTO analytics_daily(day,event,count)
                VALUES ((now() AT TIME ZONE 'Europe/Paris')::date,%s,1)
                ON CONFLICT(day,event) DO UPDATE SET count=analytics_daily.count+1
            """, (event,))
def snapshot(days=30):
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)
            cursor.execute("""
              SELECT day,event,count FROM analytics_daily
              WHERE day >= ((now() AT TIME ZONE 'Europe/Paris')::date - %s)
              ORDER BY day DESC,event
            """, (days-1,))
            rows=cursor.fetchall()
            cursor.execute("SELECT status,count(*) FROM gift_orders GROUP BY status")
            orders=dict(cursor.fetchall())
            cursor.execute("SELECT status,count(*) FROM gift_cards GROUP BY status")
            cards=dict(cursor.fetchall())
    totals={event:0 for event in EVENTS}
    daily={}
    for day,event,count in rows:
        totals[event]+=count
        daily.setdefault(str(day),{})[event]=count
    return totals,daily,orders,cards
def render_dashboard():
    t,d,orders,cards=snapshot()
    number=lambda n:f"{n:,}".replace(","," ")
    kpis=[
      ("Pages d’accueil vues",t["page_home"],"Vues, pas visiteurs uniques"),
      ("Pages cadeau vues",t["page_cadeau"],"Vues de la boutique"),
      ("Clics « Réserver »",t["click_reserver"],"Vers le calendrier"),
      ("Clics « Offrir »",t["click_cadeau"],"Vers la carte cadeau"),
      ("Intérêts carte cadeau",t["click_interet_cadeau"],"Demandes d’information"),
      ("Commandes payées",orders.get("paid",0),"Statut en base Neon"),
      ("Cartes actives",cards.get("active",0),"Émises en base Neon"),
      ("Cartes utilisées",cards.get("redeemed",0),"Utilisées en base Neon"),
    ]
    tiles="".join('<article class="stat"><small>'+html.escape(name)+'</small><strong>'+number(value)+'</strong><span>'+html.escape(desc)+'</span></article>' for name,value,desc in kpis)
    head='<tr><th>Jour</th><th>Accueil</th><th>Cadeau</th><th>Réserver</th><th>Offrir</th><th>Intérêt</th></tr>'
    body="".join('<tr><td>'+html.escape(day)+'</td>'+''.join('<td>'+number(vals.get(e,0))+'</td>' for e in ("page_home","page_cadeau","click_reserver","click_cadeau","click_interet_cadeau"))+'</tr>' for day,vals in sorted(d.items(),reverse=True))
    if not body:body='<tr><td colspan="6">La collecte vient de commencer : aucune donnée pour cette période.</td></tr>'
    return """<style>
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
    .stat{background:#fff;border:1px solid #d8dfeb;border-radius:16px;padding:18px;display:flex;flex-direction:column;gap:8px}
    .stat small{font-size:14px;color:#41546d}.stat strong{font-size:34px;color:#102039}
    .stat span{font-size:12px;color:#667589}
    .table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;background:#fff}td,th{text-align:left;padding:12px;border-bottom:1px solid #e4e9ed;white-space:nowrap}
    </style>
    <a href="/">← Mes rendez-vous</a>
    <h1>Pilotage · Votre Zone de Génie</h1>
    <p>Indicateurs des 30 derniers jours pour le trafic et les clics ; état actuel pour les commandes et les cartes.</p>
    <section class="stats">"""+tiles+"""</section>
    <article><h2>Évolution quotidienne</h2><div class="table-scroll"><table>"""+head+body+"""</table></div></article>
    <article><h2>Ce que ces chiffres veulent dire</h2>
    <p>Comptage agrégé des pages et des clics, sans cookie publicitaire, adresse IP conservée ni identifiant personnel. Un rechargement est compté comme une nouvelle vue ; ces chiffres ne sont pas des visiteurs uniques.</p>
    <p><strong>Abandon de panier : non encore mesurable.</strong> La boutique cadeau ne dispose pas encore d’un panier ou d’un paiement Mollie ouvert au public. Les clics « Offrir » sont un signal d’intérêt, pas un achat abandonné.</p>
    <p>Les ventes, paiements échoués et codes consommés seront identifiés à partir des événements réels de la boutique quand elle sera activée. Les anciennes visites ne sont pas reconstituables.</p></article>"""
