# Soirée Bourse — V1 Python

Application de bureau indépendante de Marco. Au premier lancement, `config.ini` est créé à partir de `config.example.ini` si nécessaire. Ce fichier personnel est exclu de Git. Elle démarre avec six boissons fictives, sans aucune connexion réseau. Python 3.11 ou plus récent avec Tkinter suffit pour ce mode.

## Démarrer sur ce Mac

Double-cliquer **Lancer.command**. Python 3.11+ et Tkinter doivent être installés sur le Mac. Si macOS ouvre le fichier comme du texte, clic droit → Ouvrir avec → Terminal. L’espace serveurs et l’écran public s’ouvrent automatiquement dans deux fenêtres distinctes.

Pour tout installer et lancer depuis le Terminal :

```bash
chmod +x installer.sh
./installer.sh
```

Le script conserve toujours un éventuel `config.ini` existant. L’option `--install-only` prépare l’application sans l’ouvrir.

1. Ouvrir **Catalogue**. Double-cliquer une boisson pour choisir si elle est vendue ce soir et régler coût, prix initial, minimum et maximum.
2. Ouvrir **Réglages** pour adapter la cagnotte de sécurité (200 € par défaut), les frais fixes et les variations.
3. Cliquer **Démarrer la soirée**. Les courbes évoluent toutes les 10 secondes par défaut.
4. En mode local, saisir les ventes dans **Ventes**. La démonstration ne génère aucune vente toute seule.
5. Quand la cagnotte atteint le seuil, **Déclencher un crash** devient disponible. Chaque clic nécessite une confirmation.
6. En fin de soirée, cliquer **Fin de soirée : restaurer les prix**. Exporter le bilan dans **Journal & exports**.

Le mode local utilise des boissons fictives : il permet de prendre l’application en main et de vérifier les calculs, sans toucher à Fouaille.

## Écran public et espace serveurs

La régie est maintenant l’**Espace serveurs**. Elle contient les ventes, coûts, marges, cagnotte, réglages, bouton de crash, restauration et messages techniques.

Cliquer **Ouvrir l’écran public** pour ouvrir une seconde fenêtre indépendante. Les spectateurs voient uniquement les boissons sélectionnées, le prix de chaque verre, sa variation en pourcentage et les courbes correspondantes. Aucune commande de régie, quantité vendue, marge ou cagnotte n’est présente sur cet écran. Il se met à jour en même temps que les cours.

Pour une soirée avec projecteur ou télévision :

1. Utiliser les écrans en **bureau étendu**, pas en recopie vidéo.
2. Garder **Espace serveurs** sur l’écran du personnel.
3. Déplacer **Cours & prix** sur l’écran destiné au public.
4. Depuis la régie, cliquer **Plein écran public**. La touche **Échap**, lorsque l’écran public est actif, permet de sortir du plein écran.

Les confirmations de crash et les erreurs restent attachées à la fenêtre des serveurs. L’écran public ne possède aucun bouton donnant accès à la régie. Cette séparation sert à l’affichage sur deux écrans ; elle ne remplace pas un contrôle d’accès au clavier ou à la session de l’ordinateur. La recopie vidéo montrerait aussi la régie : utiliser le bureau étendu pour conserver les commandes hors de la vue des spectateurs.

Fermer l’écran public laisse la soirée fonctionner. Le rouvrir affiche les derniers cours. Au-delà de six boissons, les pages de six boissons et leurs courbes alternent automatiquement toutes les douze secondes. Avant le démarrage, les prix ne sont pas annoncés. En cas d’écriture de prix non confirmée, l’écran public affiche simplement « Cours momentanément indisponibles » jusqu’à la réconciliation ; aucun détail interne n’y est transmis.

## Courbes, cours et marge

Une couleur par boisson. Le graphique présente les 120 derniers points disponibles par boisson (au maximum 2 400 points affichés au total) ; l’historique complet est conservé pour l’export. Les colonnes indiquent le dernier mouvement en pourcentage et l’évolution depuis le prix initial de la soirée.

- **Recettes** : montant réellement vendu, conservé au prix payé au moment de chaque vente.
- **Marge brute** : recettes moins coût des verres vendus.
- **Cagnotte nette** : marge brute moins frais fixes. Elle peut être négative au début si des frais fixes sont renseignés.
- **Marge par verre** : prix actuel moins coût d’un verre.

Le coût par verre se renseigne manuellement. Par exemple, 30 € pour un fût de 10 litres, avec des verres de 25 cl : 40 verres théoriques, soit 0,75 € par verre, avant pertes, gobelets et autres coûts. Ajuster le coût pour intégrer ces éléments. Le catalogue ne fournit pas ces coûts.

La V1 impose **coût ≤ minimum ≤ prix initial ≤ maximum**, avec un minimum strictement positif. Les fluctuations ne vendent donc pas un verre sous son coût déclaré. La cagnotte reste une estimation fondée sur ces coûts, pas une mesure du solde bancaire, des stocks ou du résultat comptable après taxes.

Le marché combine une petite variation aléatoire, l’influence relative des ventes depuis le dernier mouvement et un retour modéré vers le prix initial. Avant le seuil, un léger biais positif est appliqué. Les cours peuvent monter et descendre à tout moment ; seules les ventes alimentent la cagnotte. Atteindre le seuil ne déclenche jamais un crash automatique.

Un crash confirmé produit une chute (30 % par défaut), deux paliers à prix bas, une remontée sur cinq paliers jusqu’à 20 % au-dessus du prix avant crash, puis un retour sur huit paliers vers ce prix. Minimum et maximum limitent tous ces mouvements. Un palier dure un intervalle d’actualisation. Chaque nouveau crash demande votre confirmation ; il n’y a pas de cycle de crash automatique. Le crash ne dépense pas fictivement la cagnotte : celle-ci n’évolue qu’avec les ventes et les frais déclarés.

## Connexion Fouaille — à activer par l’organisateur

**Aucun test ni aucune connexion à la base Fouaille n’a été effectué lors de la réalisation de cette V1.** Le connecteur est écrit d’après le schéma présent dans Marco ; la compatibilité réelle reste à vérifier par vous avant utilisation en soirée.

1. Double-cliquer **Installer_MySQL.command** pour installer le pilote PyMySQL dans un environnement propre à ce dossier. Cette installation télécharge le pilote Python ; elle ne se connecte pas à Fouaille.
2. Renseigner `url` dans **config.ini**, section `[mysql]`, ou définir `BOURSE_DATABASE_URL`. Exemple de format : `mysql://utilisateur:mot_de_passe@hote:3306/base`. Encoder les caractères spéciaux du mot de passe dans l’URL. Pour TLS, renseigner `ssl_ca` avec le certificat CA. Ne pas publier ce fichier une fois les identifiants ajoutés.
3. Dans **Catalogue**, choisir **Fouaille MySQL · prix partagés**, puis **Charger le catalogue**. Cette action lit la base mais ne modifie pas les prix.
4. Configurer et sélectionner les boissons, puis démarrer. Une confirmation annonce explicitement l’écriture des prix partagés. Les ventes intervenues depuis l’ouverture de l’application ou le chargement du catalogue sont alors incluses.

L’application a sa propre configuration et n’utilise pas le serveur de Marco. L’accès requis est `SELECT` sur `products` et `orders`, et `UPDATE` sur la colonne `products.price`. La table `products` doit être transactionnelle (InnoDB). Les noms de champs proviennent du code Marco : `products(id, name, price, available)` et `orders(id, product_id, amount, price, date)`.

En mode Fouaille :

- Les tarifs des seules boissons sélectionnées sont modifiés dans `products.price`, y compris au crash et à la restauration. Les caisses connectées doivent relire leurs tarifs ; cette application ne force pas leur écran à se rafraîchir.
- Les ventes continuent à être effectuées dans votre caisse habituelle. La régie importe les nouvelles lignes de `orders` pour les boissons sélectionnées. La saisie manuelle locale est désactivée afin d’éviter un double comptage.
- Le format attendu est celui de Marco : `orders.price` contient **le total de ligne négatif**, et `amount` la quantité. Pour une ligne à −9 € avec trois verres, la recette est 9 €, pas 27 €.
- Les ventes antérieures au démarrage sont exclues. Les identifiants déjà importés sont dédoublonnés ; les lignes validées tardivement avec un identifiant supérieur au repère de début sont reprises. Arrêter les ventes pendant le démarrage et la clôture pour délimiter la soirée sans transaction en cours.
- Les remboursements, annulations et modifications d’anciennes commandes ne sont pas gérés automatiquement en V1. Une nouvelle ligne au format incompatible arrête le marché. Réconcilier ces situations dans la caisse et le bilan ; la restauration des prix reste disponible.
- Les soldes des membres, stocks et commandes ne sont jamais modifiés par la régie.
- Une seule régie doit gérer les prix d’une soirée. Le lancement en double depuis le même dossier est bloqué ; les autres ordinateurs ou copies ne sont pas verrouillés globalement.

## Pause, coupure et restauration

**Pause** fige les cours et conserve les prix actuellement publiés. Pendant une pause, le bouton **Actualiser les ventes Fouaille** importe les nouvelles ventes. **Reprendre** importe aussi les ventes avant de remettre le marché en mouvement.

Avant la première écriture, tous les tarifs d’origine sont sauvegardés localement, à partir d’une lecture fraîche de la base. Chaque mise à jour des prix utilise une transaction et un journal local préalable. Une modification concurrente inattendue arrête l’opération plutôt que d’écraser ce tarif.

Après fermeture ou coupure, la soirée reprend toujours **en pause**, sans connexion automatique. En cas d’écriture non confirmée :

1. Rétablir la connexion à la même base.
2. Dans **Journal & exports**, cliquer **Réconcilier l’écriture en attente**. L’opération vérifie si chaque prix est encore l’ancien ou déjà le nouveau, puis termine l’opération interrompue. Le marché reste en pause.
3. Reprendre ou cliquer **Fin de soirée : restaurer les prix**. Ce dernier bouton peut aussi réconcilier directement l’opération interrompue avant de restaurer.

En cas de conflit avec un prix modifié par un autre outil, aucune écriture forcée n’est effectuée. Le message précise le produit concerné. Exporter le bilan pour consulter les valeurs `original`, puis réconcilier avec l’administrateur de Fouaille.

La restauration exige que la base soit accessible. Une fermeture brutale ou une perte réseau ne peut pas restaurer des prix à distance immédiatement. **Ne pas supprimer ni déplacer `data/` pendant une soirée.** Fermer la fenêtre propose de restaurer les prix ou de conserver la soirée en pause.

Si le dernier import des ventes échoue à la clôture mais que les prix peuvent être restaurés, la restauration est effectuée et le bilan est marqué « à vérifier ».

## Fichiers et réglages dans le code

- `app.py` : lancement et verrou de processus.
- `bourse/ui.py` : espace serveurs Tkinter.
- `bourse/public.py` : écran public, prix et pourcentages uniquement.
- `bourse/charts.py` : tracé des courbes partagé entre les deux écrans.
- `bourse/engine.py` : calculs, réglages `DEFAULTS`, mouvements et cycle de crash.
- `bourse/database.py` : connexion et requêtes Fouaille.
- `bourse/storage.py` : sauvegarde et exports locaux.
- `config.ini` : connexion MySQL et valeurs du premier lancement.
- `data/soiree.sqlite3` : état, ventes, historique, journal et sauvegarde de restauration.
- `exports/<identifiant-soirée>/` : ventes CSV, historique CSV et bilan JSON. **Montants CSV/JSON en centimes**, séparateur CSV point-virgule.

Les réglages modifiés dans l’interface sont persistants et priment sur les valeurs initiales de `config.ini`. Les coûts et limites sont fixes pendant une soirée. Le seuil et les autres paramètres sont modifiables hors du cycle de crash/rebond.

## Vérifications locales

Depuis ce dossier : `python3 -m unittest discover -s tests -v`.

Les tests utilisent exclusivement des boissons fictives, des fichiers temporaires locaux et un faux connecteur. Les appels réseau y sont bloqués. Ils vérifient les montants, les bornes des cours, le crash manuel, le rebond, le dédoublonnage, les coupures, les conflits et la restauration. Ils ne valident pas une connexion Fouaille réelle.
