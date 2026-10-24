# Votre Zone de Génie — Administration

Service Python 3.12+ autonome, sans dépendance. GitHub Pages continue d’héberger le site public ; cet admin nécessite un serveur HTTPS et un disque persistant.

## État

Implémenté et testé localement. Non déployé ; connexions Cal.com et SMTP non vérifiées en production. Aucun e-mail n’a été envoyé. Aucun cron, webhook ou envoi automatique n’est installé.

## Parcours

- Connexion par mot de passe administrateur ; cookie sécurisé 8 heures et protection CSRF.
- Lecture Cal.com en direct, paginée, uniquement pour l’événement 7609933.
- E-mail préalable facultatif : aperçu, destinataire issu de Cal.com, vérification manuelle du paiement puis confirmation d’envoi.
- Formulaire mobile de trois questions facultatives, lien individuel signé valable 30 jours. Réponses consultables dans l’admin ; purge après 60 jours lors de l’ouverture du tableau de bord.
- Guide : envoi possible une heure après la fin prévue, confirmation manuelle que l’entretien a eu lieu, puis confirmation d’envoi.
- Historique SQLite bloquant un deuxième envoi pour le même rendez-vous et même message, y compris après une interruption SMTP. Les cas incertains nécessitent une vérification manuelle dans Gmail ; aucun bouton de renvoi automatique.
- Aucune copie des données privées dans GitHub ; clés dans l’environnement serveur uniquement.

## Configuration sécurisée

Renseigner les variables de `.env.example` dans le gestionnaire de secrets de l’hébergement. Ne pas les committer. `PUBLIC_ORIGIN` doit être l’origine HTTPS exacte sans chemin ni slash final. Générer deux secrets différents pour ADMIN_PASSWORD et SESSION_SECRET (au moins 32 caractères aléatoires).

CAL_API_KEY doit autoriser les lectures des réservations de Thierry, sans écriture nécessaire. Le jeton MCP ChatGPT ne peut pas être récupéré pour ce serveur.

SMTP_PASSWORD pour Gmail désigne un mot de passe d’application, jamais le mot de passe du compte Google. La validation en deux étapes doit être activée et cette option disponible pour le compte. MAIL_FROM et SMTP_USER doivent être la même adresse Gmail autorisée.

Le fichier DATA_PATH doit être sur disque persistant, sauvegardé et accessible seulement au processus serveur. Un disque éphémère ferait perdre le blocage des doublons après redéploiement ; ne pas utiliser en production. Une seule instance serveur doit être déployée pour ce registre SQLite.

Commande de démarrage : `python zdg-admin/server.py`. Health check `/health`. Ne pas servir le dossier de code comme fichiers statiques. Le serveur ne sert aucune donnée privée sans authentification, à l’exception du formulaire possédant un lien signé individuel.

## Contrôles avant lancement

1. HTTPS, mot de passe admin, secret de session et disque persistant configurés.
2. Tester une connexion Cal.com avec une réservation du bon événement.
3. Vérifier le PDF public `/documents/le-temps-de-laisser-murir.pdf`.
4. Tester un envoi vers une réservation interne expressément autorisée ; vérifier le reçu réel et l’adresse de réponse.
5. Tester l’aperçu mobile et le retour de formulaire.
6. Ajouter ensuite le lien d’accès à l’admin sur le site public si souhaité. Ne pas activer les workflows Cal.com standards en parallèle.

Tests : `cd zdg-admin && python -m unittest -v`. Ils couvrent les jetons, l’échappement HTML, l’offre autorisée, les annulations, le délai d’une heure, les doublons et les résultats SMTP incertains. Ils ne prouvent pas les connexions externes.

Limites : le paiement est vérifié manuellement par Thierry avant confirmation ; une réservation acceptée n’est pas présentée comme preuve de paiement. L’acceptation SMTP ne prouve pas la livraison en boîte de réception. Aucun envoi global, aucun renvoi après résultat incertain.
