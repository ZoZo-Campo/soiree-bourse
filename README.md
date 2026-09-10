# Soirée Bourse

Application de bureau Python indépendante de Marco pour animer une soirée où le prix des boissons évolue selon les ventes et de petites fluctuations aléatoires.

Deux fenêtres distinctes :

- **Écran public** : courbes, prix du verre et variations en pourcentage.
- **Espace serveurs** : sélection des boissons, ventes, marges, cagnotte, réglages, crash et restauration des tarifs.

## Lancement rapide sur macOS

Prérequis : **Python 3.11 ou plus récent avec Tkinter**.

```bash
git clone https://github.com/ZoZo-Campo/soiree-bourse.git
cd soiree-bourse
python3 app.py
```

Au premier lancement, l’application crée automatiquement `.venv` et installe le pilote MySQL s’il manque. Elle utilise ensuite cet environnement, même lorsque `app.py` est lancé avec le Python général de l’ordinateur.

Vous pouvez aussi double-cliquer sur **Lancer.command**. Au premier lancement, `config.ini` est créé automatiquement à partir de `config.example.ini`. Il reste local et n’est pas suivi par Git. L’espace serveurs et l’écran public s’ouvrent automatiquement dans deux fenêtres distinctes.

### Installation complète en ligne de commande

Après avoir téléchargé ou cloné le dépôt :

```bash
cd soiree-bourse
chmod +x installer.sh
./installer.sh
```

Le script vérifie Python 3.11 et Tkinter, crée `.venv`, installe le pilote MySQL, crée la configuration locale sans écraser une configuration existante, exécute les tests puis lance l’application. Utiliser `./installer.sh --install-only` pour installer sans ouvrir l’application.

Le mode démonstration utilise uniquement la bibliothèque standard de Python. Aucun serveur Marco ni pilote MySQL n’est nécessaire pour l’essayer.

## Tester sans toucher à Marco ou à Fouaille

1. Dans **Catalogue**, choisir **Démonstration / caisse locale**, puis **Charger le catalogue**.
2. Configurer les boissons fictives et cliquer **Démarrer la soirée**.
3. Dans **Ventes**, enregistrer des ventes fictives.
4. Pour essayer rapidement le crash, régler le seuil de cagnotte à **5 €** dans **Réglages**.
5. Lorsque le seuil est atteint, cliquer **Déclencher un crash** et confirmer.
6. Terminer avec **Fin de soirée : restaurer les prix**.

**Ce mode ne se connecte pas à Fouaille et ne modifie aucun prix de Marco.** Les données de démonstration sont sauvegardées uniquement dans le dossier local `data/`.

## Affichage pour les spectateurs

L’écran public s’ouvre automatiquement. Le bouton **Ouvrir l’écran public** permet de le rouvrir s’il a été fermé. Déplacer cette fenêtre sur le projecteur ou la télévision, puis cliquer **Plein écran public** depuis la régie. La touche **Échap** quitte le plein écran.

Utiliser le **bureau étendu**, pas la recopie vidéo, et garder l’espace serveurs sur l’écran du personnel. L’écran public ne contient aucun bouton de gestion, aucune marge et aucune cagnotte. Les cours sont synchronisés avec la régie. Au-delà de six boissons, les pages alternent automatiquement.

## Fonctionnement du marché

- Une courbe colorée et un cours par boisson, avec variation en pourcentage.
- Prix initial, coût par verre, minimum et maximum configurables.
- Variation aléatoire et influence relative des ventes, bornées par les limites de chaque boisson.
- **Marge brute = recettes − coût des verres vendus.**
- **Cagnotte nette = marge brute − frais fixes.** Seules les ventes la remplissent ; les mouvements de cours seuls ne créent aucun bénéfice.
- Seuil de sécurité de **200 € par défaut**, modifiable dans l’interface.
- **Chaque crash exige une confirmation manuelle.** Atteindre le seuil débloque le bouton sans déclencher de crash automatique.
- Après confirmation : chute, période à prix bas, fort rebond puis retour progressif. Les amplitudes et durées sont réglables.
- Les prix minimums doivent être au moins égaux au coût déclaré par verre.

## Connexion MySQL Fouaille — facultative

**Aucun test ni aucune connexion à la base Fouaille réelle n’a été effectué pendant le développement.** Le connecteur suit le schéma présent dans Marco ; son fonctionnement avec votre serveur reste à vérifier par l’organisateur.

Pour préparer ce mode :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Sur macOS, **Installer_MySQL.command** réalise cette installation. Renseigner ensuite la section `[mysql]` de **config.ini** ou la variable d’environnement **BOURSE_DATABASE_URL** :

```ini
[mysql]
url = mysql://utilisateur:mot_de_passe@hote:3306/base
ssl_ca =
```

Encoder les caractères spéciaux du mot de passe dans l’URL. Pour TLS, renseigner le chemin du certificat CA dans `ssl_ca`. **Ne jamais publier `config.ini`, une URL contenant des identifiants, ni les fichiers de données ou d’export.**

Dans **Catalogue**, choisir **Fouaille MySQL · prix partagés** pour lire les boissons. Le repère des ventes est mémorisé dès l’ouverture de l’application ou du catalogue. Les prix ne sont appliqués qu’au démarrage de la soirée, après confirmation explicite.

Le connecteur :

- lit `products` et les nouvelles ventes dans `orders` ;
- modifie uniquement `products.price` pour les boissons sélectionnées ;
- importe au démarrage les ventes arrivées depuis l’ouverture de l’application, puis toutes les nouvelles ventes jusqu’à la fin ;
- conserve localement le prix d’origine, permet une hausse/baisse manuelle et une restauration individuelle ou globale ;
- interprète `orders.price` comme le **total négatif de la ligne** et `amount` comme la quantité ;
- dédoublonne les ventes importées et conserve le montant réellement payé ;
- ne modifie ni commandes, ni soldes des membres, ni stocks.

En mode Fouaille, les ventes sont effectuées dans la caisse habituelle ; la saisie manuelle locale est désactivée. Les remboursements et modifications d’anciennes commandes ne sont pas automatiquement traités en V1. Les caisses doivent relire leurs tarifs pour refléter les changements.

## Fin de soirée et reprise après coupure

Avant la première écriture, les prix d’origine sont sauvegardés localement. **Fin de soirée : restaurer les prix** arrête les variations et rétablit ces tarifs.

Une écriture non confirmée arrête le marché. Le journal local permet de **réconcilier l’écriture en attente** après rétablissement de la connexion. Après une relance, la soirée reste en pause, sans connexion automatique. En cas de modification concurrente d’un tarif, l’application signale un conflit au lieu de forcer l’écrasement.

Après une fermeture inattendue, l’application propose soit de continuer avec les compteurs locaux, soit de restaurer tous les prix et de terminer. Le prochain démarrage repart alors avec des compteurs à zéro.

Le profil dynamique utilise par défaut 5 % d’aléatoire et 4 % d’influence des ventes. Le maximum proposé lors du chargement d’un produit est trois fois son prix catalogue et reste librement configurable.

La restauration requiert une base accessible. Conserver le dossier `data/` jusqu’à la clôture et ne faire fonctionner qu’une régie de prix à la fois. Arrêter les ventes en caisse pendant le démarrage et la clôture pour délimiter correctement la soirée.

## Tests locaux

```bash
python3 -m unittest discover -s tests -v
```

**21 tests** utilisent des données fictives, des fichiers temporaires et un faux connecteur, avec les connexions réseau bloquées. Ils couvrent notamment le calcul des marges, les bornes de prix, le crash manuel, les coupures simulées, la restauration et la séparation des données public/serveurs.

## Organisation du code

| Fichier | Rôle |
| --- | --- |
| `app.py` | Lancement, configuration initiale et verrou de processus |
| `bourse/engine.py` | Calculs, règles et cycle du marché |
| `bourse/ui.py` | Espace serveurs |
| `bourse/public.py` | Affichage public sans données de gestion |
| `bourse/charts.py` | Tracé des courbes |
| `bourse/database.py` | Connecteur MySQL |
| `bourse/storage.py` | Sauvegarde locale SQLite et exports |
| `config.example.ini` | Configuration vierge à personnaliser localement |
| `tests/` | Vérifications sans connexion Fouaille |

Les exports CSV et JSON sont disponibles depuis **Journal & exports** ; leurs montants sont en **centimes**.

Le [guide complet en français](LISEZ_MOI.md) détaille les réglages et les procédures de récupération.
