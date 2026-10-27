# Cartes cadeaux Mollie

Sur le service Render dédié, configurer dans Environment (jamais dans Git) :
- MOLLIE_API_KEY : clé du profil Mollie Votre Zone de Génie, en mode réel.
- GIFT_SECRET : secret aléatoire stable d'au moins 32 caractères. Ne pas changer après émission de cartes.
- DATABASE_URL : connexion Neon déjà utilisée par check_neon.py.
- PUBLIC_ORIGIN : https://votre-zone-de-genie-admin.onrender.com
- GIFT_SALES_ENABLED : false jusqu'à vérification du compte, du contact client et du parcours.

Admin : /gifts-admin (mot de passe habituel). Diagnostic de connexion sans révélation de secrets.
Parcours : /cadeau → POST /gift-checkout → Mollie → /gift-return → /gift.pdf.
Notification Mollie : POST /mollie-webhook. Le statut reçu n'est jamais accepté sans relecture API.
Montant fixé côté serveur : 90 EUR. Seuls les paiements live de 90 EUR, liés à la commande, donnent accès au PDF.
Référence unique, stockage PostgreSQL, émission idempotente et utilisation atomique dans l'admin.
Remboursement ou contestation invalident la carte à la vérification. Aucun envoi d'email automatique.
Le client doit conserver sa page de retour. L'admin conserve le suivi des acheteurs.

Avant ouverture : contrôler Mollie, moyens de paiement et conditions de vente ; faire un test contrôlé du parcours complet, confirmer le contact email, puis activer GIFT_SALES_ENABLED=true et relier le bouton public à /cadeau. Le site public reste fermé tant que ces contrôles ne sont pas faits.

Tests : python -m unittest -v (dans admin-service). Tests simulés ne prouvent pas une transaction réelle ni la livraison des notifications.
