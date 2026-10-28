# Guide Les 5 R — préparation à la vente

Branche `feat/guide-5r-payant`, basée sur `gh-pages` (production). Aucune clé Stripe dans le dépôt. Le produit Stripe réel existe : `prod_VWV5EfGGv7uQdb`, prix unique `price_1UVS5VBLugj24SuB9VJsYQ47` (1500 centimes EUR). Aucun paiement d’essai réel effectué.

## Parcours

- `/guide/` : offre, extrait public limité, deux consentements, bouton de paiement.
- Checkout Stripe hébergé, compte non requis. Nom d’affichage prévu : Votre Zone de Génie.
- `/guide/acces/#order=…&token=…` : accès personnel. Le fragment n’est pas envoyé au serveur statique. Aucun outil tiers sur cette page.
- API `/guide-access` puis `/guide.pdf` : signature de lien, commande et paiement vérifiés côté serveur, montant/devise/SKU/mode réel contrôlés. Remboursement ou contestation révoquent l’accès.
- Webhook signé : livraison persistée même si le client ferme la page. `completed` seul ne suffit pas : le paiement doit être `paid`. Succès différés pris en charge.
- E-mail transactionnel avec lien d’accès et copie des conditions. Réservation atomique anti-doublon, envoi incertain signalé dans l’admin (pas de renvoi aveugle).
- Après séance : le modèle d’e-mail existant donne un lien cadeau signé, valable un an. Les confirmations manuelles d’entretien et d’envoi restent en place.
- L’ancien PDF public de six pages reste accessible pour préserver les anciens liens. La nouvelle version complète n’est jamais publiée en clair dans ce dépôt public : `assets/guide-5r.enc` est chiffré AES-GCM, clé uniquement dans Render.

## À terminer avant ouverture

1. Dans Render `votre-zone-de-genie-admin`, ajouter `GUIDE_STRIPE_KEY` : clé RESTREINTE du compte confirmé, permissions Checkout Sessions écriture/lecture, Prices lecture, PaymentIntents et Charges lecture. Vérifier les permissions contre les appels réels. Ne pas copier la clé en conversation, dans Git ou dans un fichier partagé.
2. Finaliser `guide-conditions.txt` et `/guide/conditions.html` : régime TVA/facturation, encadré légal contenu numérique, coordonnées du médiateur désigné par IROKO. `GUIDE_TERMS_READY` reste `false` jusqu’alors.
3. Déployer la branche validée vers `gh-pages`. Le build existant applique `neon_schema.sql`. Vérifier les routes, l’accès cadeau et la lecture du PDF chiffré. Le secret `GUIDE_FILE_KEY` et le prix ont été préparés dans Render ; `GUIDE_SALES_ENABLED=false`.
4. Créer un webhook Stripe sur `https://votre-zone-de-genie-admin.onrender.com/guide-webhook`, événements `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `charge.refunded`, `charge.dispute.created`; enregistrer son secret dans `GUIDE_STRIPE_WEBHOOK_SECRET`.
5. Vérifier SMTP, consentements, emails, webhooks et parcours avec un environnement Stripe sandbox isolé (ne pas remplacer les clés de production). Les tests unitaires couvrent les décisions sensibles mais ne remplacent pas ce test intégré. Le contrôle live est strictement fermé aux sessions test : adapter le mode uniquement dans l’environnement sandbox isolé.
6. Contrôler les informations publiques Stripe/nom apparaissant au paiement et les mentions de facturation. Activer `GUIDE_TERMS_READY=true` puis `GUIDE_SALES_ENABLED=true` seulement après validation complète.

L’activation nécessite clé, prix, webhook, clé de fichier, SMTP et conditions finalisées. Elle échoue en mode fermé. Aucun nouveau service ni abonnement d’hébergement créé. Le site conserve Cal.com et l’offre 30 minutes à 90 €.

## Validation locale

`cd admin-service && python -m unittest -v`

Tests ciblés : faux liens, mauvais montant/devise/SKU/commande, mode test refusé, paiement en attente, remboursement/contestation, cadeau expiré, signature webhook invalide, e-mail déjà réservé, non-décryptage avant droit d’accès.
